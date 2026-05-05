#!/usr/bin/env python3
"""Compare two reconstruction directories and emit PSNR/SSIM/(optional) LPIPS reports."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import re
import statistics
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from output_shape_utils import analyze_shape_pair, crop_array_to_target


DEFAULT_REPORT_DIR = Path("session_bootstrap/reports")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two directories of reconstructed PNGs and compute per-image "
            "plus aggregate PSNR/SSIM, with optional LPIPS when torch+lpips are available."
        )
    )
    parser.add_argument("--ref-dir", required=True, help="Reference PNG directory.")
    parser.add_argument("--test-dir", required=True, help="Test PNG directory.")
    parser.add_argument(
        "--comparison-label",
        default="",
        help="Optional label used in the report body and default report filename.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=300,
        help="Maximum number of matched PNGs to compare. Use 0 for all matched images.",
    )
    parser.add_argument(
        "--size-mismatch",
        choices=("crop", "crop-top-left", "crop-center", "error"),
        default="crop-top-left",
        help=(
            "How to handle mismatched image sizes. "
            "'crop' preserves the historical top-left crop behavior."
        ),
    )
    parser.add_argument(
        "--allow-mismatch",
        action="store_true",
        help="Allow missing/extra filenames and compare only the common subset.",
    )
    parser.add_argument(
        "--lpips",
        choices=("auto", "force", "off"),
        default="auto",
        help="LPIPS mode. 'auto' skips it when dependencies are unavailable.",
    )
    parser.add_argument(
        "--lpips-net",
        default="alex",
        help="Backbone passed to lpips.LPIPS(net=...).",
    )
    parser.add_argument(
        "--lpips-device",
        default="cpu",
        help="Torch device for LPIPS, for example 'cpu' or 'cuda'.",
    )
    parser.add_argument(
        "--report-prefix",
        default="",
        help=(
            "Output path prefix without extension. Example: "
            "session_bootstrap/reports/quality_metrics_run1"
        ),
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory used when --report-prefix is omitted.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run id used in the default report prefix.",
    )
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Skip writing markdown/json reports and print only the terminal summary.",
    )
    return parser.parse_args()


def require_numpy():
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "ERROR: numpy is required to compute image quality metrics. "
            "Install it in the Python environment used for this script."
        ) from exc
    return np


def maybe_import_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return None
    return Image


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "comparison"


def now_timestamp() -> str:
    return dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def iso_timestamp() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def build_report_paths(args: argparse.Namespace, comparison_label: str) -> tuple[Path | None, Path | None, str]:
    if args.no_reports:
        run_id = args.run_id or f"quality_metrics_{slugify(comparison_label)}_{now_timestamp()}"
        return None, None, run_id
    if args.report_prefix:
        prefix = Path(args.report_prefix)
        run_id = prefix.name
    else:
        run_id = args.run_id or f"quality_metrics_{slugify(comparison_label)}_{now_timestamp()}"
        prefix = Path(args.report_dir) / run_id
    prefix.parent.mkdir(parents=True, exist_ok=True)
    return prefix.with_suffix(".md"), prefix.with_suffix(".json"), run_id


def collect_pngs(root: Path) -> dict[str, Path]:
    files = {
        str(path.relative_to(root)): path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".png"
    }
    return files


def validate_dirs(ref_dir: Path, test_dir: Path) -> None:
    if not ref_dir.is_dir():
        raise SystemExit(f"ERROR: reference directory not found: {ref_dir}")
    if not test_dir.is_dir():
        raise SystemExit(f"ERROR: test directory not found: {test_dir}")


def apply_png_filter(filter_type: int, raw_scanline: bytes, prev_scanline: bytes, bpp: int) -> bytes:
    row = bytearray(raw_scanline)
    prev = prev_scanline
    if filter_type == 0:
        return bytes(row)
    if filter_type == 1:
        for idx in range(len(row)):
            left = row[idx - bpp] if idx >= bpp else 0
            row[idx] = (row[idx] + left) & 0xFF
        return bytes(row)
    if filter_type == 2:
        for idx in range(len(row)):
            up = prev[idx] if prev else 0
            row[idx] = (row[idx] + up) & 0xFF
        return bytes(row)
    if filter_type == 3:
        for idx in range(len(row)):
            left = row[idx - bpp] if idx >= bpp else 0
            up = prev[idx] if prev else 0
            row[idx] = (row[idx] + ((left + up) // 2)) & 0xFF
        return bytes(row)
    if filter_type == 4:
        for idx in range(len(row)):
            left = row[idx - bpp] if idx >= bpp else 0
            up = prev[idx] if prev else 0
            up_left = prev[idx - bpp] if prev and idx >= bpp else 0
            row[idx] = (row[idx] + paeth_predictor(left, up, up_left)) & 0xFF
        return bytes(row)
    raise ValueError(f"unsupported PNG filter type: {filter_type}")


def paeth_predictor(left: int, up: int, up_left: int) -> int:
    predictor = left + up - up_left
    left_dist = abs(predictor - left)
    up_dist = abs(predictor - up)
    up_left_dist = abs(predictor - up_left)
    if left_dist <= up_dist and left_dist <= up_left_dist:
        return left
    if up_dist <= up_left_dist:
        return up
    return up_left


def load_png_with_pure_python(path: Path, np):
    payload = path.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG file: {path}")

    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace_method = None
    palette = None
    idat_chunks: list[bytes] = []

    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError(f"corrupt PNG chunk header: {path}")
        chunk_len = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data = payload[offset + 8 : offset + 8 + chunk_len]
        chunk_crc = payload[offset + 8 + chunk_len : offset + 12 + chunk_len]
        if len(chunk_crc) != 4:
            raise ValueError(f"corrupt PNG chunk CRC: {path}")
        offset += 12 + chunk_len

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace_method = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if compression != 0 or filter_method != 0:
                raise ValueError(f"unsupported PNG compression/filter method in {path}")
            if bit_depth != 8:
                raise ValueError(f"unsupported PNG bit depth {bit_depth} in {path}")
            if interlace_method != 0:
                raise ValueError(f"interlaced PNG is not supported without Pillow: {path}")
        elif chunk_type == b"PLTE":
            palette = chunk_data
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None:
        raise ValueError(f"missing PNG IHDR: {path}")

    channel_count_map = {
        0: 1,
        2: 3,
        3: 1,
        4: 2,
        6: 4,
    }
    if color_type not in channel_count_map:
        raise ValueError(f"unsupported PNG color type {color_type} in {path}")
    channels = channel_count_map[color_type]
    bytes_per_pixel = channels
    row_bytes = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(idat_chunks))
    expected_bytes = height * (1 + row_bytes)
    if len(raw) != expected_bytes:
        raise ValueError(f"unexpected PNG payload size in {path}: got {len(raw)}, expected {expected_bytes}")

    rows = []
    prev = b""
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = raw[cursor : cursor + row_bytes]
        cursor += row_bytes
        recon = apply_png_filter(filter_type, scanline, prev, bytes_per_pixel)
        rows.append(np.frombuffer(recon, dtype=np.uint8))
        prev = recon

    image = np.stack(rows, axis=0)
    image = image.reshape(height, width, channels)

    if color_type == 0:
        image = np.repeat(image, 3, axis=2)
    elif color_type == 2:
        pass
    elif color_type == 3:
        if palette is None:
            raise ValueError(f"indexed-color PNG is missing PLTE chunk: {path}")
        palette_array = np.frombuffer(palette, dtype=np.uint8)
        if palette_array.size % 3 != 0:
            raise ValueError(f"invalid PLTE chunk size in {path}")
        palette_array = palette_array.reshape(-1, 3)
        image = palette_array[image[:, :, 0]]
    elif color_type == 4:
        gray = image[:, :, 0:1]
        image = np.repeat(gray, 3, axis=2)
    elif color_type == 6:
        image = image[:, :, :3]

    return image.astype(np.float64) / 255.0


def load_image_as_float_rgb(path: Path, np):
    image_module = maybe_import_pillow()
    if image_module is not None:
        with image_module.open(path) as image:
            array = np.asarray(image.convert("RGB"), dtype=np.float64)
        return array / 255.0
    return load_png_with_pure_python(path, np)


def resolve_size_mismatch_mode(mode: str) -> str:
    if mode == "crop":
        return "crop-top-left"
    return mode


def maybe_crop_to_common_shape(ref_image, test_image, np, *, mode: str):
    if ref_image.shape == test_image.shape:
        return ref_image, test_image, False, ref_image.shape, test_image.shape, None

    analysis = analyze_shape_pair(
        list(ref_image.shape),
        list(test_image.shape),
        left_label="ref",
        right_label="test",
    )
    if analysis["relation"] != "spatial_mismatch" or not analysis["common_shape"]:
        raise ValueError(
            "cannot crop images with incompatible shapes: "
            f"ref={list(ref_image.shape)} test={list(test_image.shape)} relation={analysis['relation']}"
        )

    target_height, target_width = analysis["common_shape"][-2:]
    anchor = "center" if mode == "crop-center" else "top-left"
    ref_cropped, ref_crop = crop_array_to_target(
        ref_image,
        (target_height, target_width),
        anchor=anchor,
        np=np,
    )
    test_cropped, test_crop = crop_array_to_target(
        test_image,
        (target_height, target_width),
        anchor=anchor,
        np=np,
    )
    crop_metadata = {
        "analysis": analysis,
        "anchor": anchor,
        "ref_crop": ref_crop,
        "test_crop": test_crop,
    }
    return ref_cropped, test_cropped, True, ref_image.shape, test_image.shape, crop_metadata


def psnr_db(ref_image, test_image, np) -> float:
    mse = float(np.mean(np.square(ref_image - test_image)))
    if mse == 0.0:
        return math.inf
    return 10.0 * math.log10(1.0 / mse)


def gaussian_kernel_1d(np, size: int = 11, sigma: float = 1.5):
    radius = size // 2
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= np.sum(kernel)
    return kernel


def convolve_axis(image, kernel, axis: int, np):
    radius = len(kernel) // 2
    pad_width = [(0, 0)] * image.ndim
    pad_width[axis] = (radius, radius)
    padded = np.pad(image, pad_width, mode="reflect")
    output = np.zeros_like(image, dtype=np.float64)
    slices = [slice(None)] * image.ndim
    for index, weight in enumerate(kernel):
        slices[axis] = slice(index, index + image.shape[axis])
        output += weight * padded[tuple(slices)]
    return output


def gaussian_blur(image, kernel, np):
    blurred = convolve_axis(image, kernel, axis=0, np=np)
    blurred = convolve_axis(blurred, kernel, axis=1, np=np)
    return blurred


def ssim_score(ref_image, test_image, np) -> float:
    kernel = gaussian_kernel_1d(np)
    c1 = 0.01 * 0.01
    c2 = 0.03 * 0.03

    mu_ref = gaussian_blur(ref_image, kernel, np)
    mu_test = gaussian_blur(test_image, kernel, np)
    mu_ref_sq = mu_ref * mu_ref
    mu_test_sq = mu_test * mu_test
    mu_ref_test = mu_ref * mu_test

    sigma_ref_sq = gaussian_blur(ref_image * ref_image, kernel, np) - mu_ref_sq
    sigma_test_sq = gaussian_blur(test_image * test_image, kernel, np) - mu_test_sq
    sigma_ref_test = gaussian_blur(ref_image * test_image, kernel, np) - mu_ref_test

    sigma_ref_sq = np.maximum(sigma_ref_sq, 0.0)
    sigma_test_sq = np.maximum(sigma_test_sq, 0.0)

    numerator = (2.0 * mu_ref_test + c1) * (2.0 * sigma_ref_test + c2)
    denominator = (mu_ref_sq + mu_test_sq + c1) * (sigma_ref_sq + sigma_test_sq + c2)
    return float(np.mean(numerator / denominator))


class LpipsScorer:
    def __init__(self, mode: str, net: str, device: str):
        self.mode = mode
        self.net = net
        self.device = device
        self.enabled = False
        self.reason = "LPIPS disabled"
        self._torch = None
        self._model = None

        if mode == "off":
            return
        try:
            import lpips
            import torch
        except ModuleNotFoundError as exc:
            if mode == "force":
                raise SystemExit(
                    "ERROR: LPIPS requested with --lpips force but torch/lpips is unavailable."
                ) from exc
            self.reason = "torch/lpips unavailable; LPIPS skipped"
            return

        try:
            model = lpips.LPIPS(net=net)
            model = model.to(device)
            model.eval()
        except Exception as exc:
            if mode == "force":
                raise SystemExit(f"ERROR: failed to initialize LPIPS ({net} on {device}): {exc}") from exc
            self.reason = f"LPIPS init failed; skipped: {exc}"
            return

        self._torch = torch
        self._model = model
        self.enabled = True
        self.reason = f"LPIPS enabled ({net} on {device})"

    def score(self, ref_image, test_image, np) -> float | None:
        if not self.enabled:
            return None
        torch = self._torch
        ref_tensor = np.ascontiguousarray(ref_image.transpose(2, 0, 1))
        test_tensor = np.ascontiguousarray(test_image.transpose(2, 0, 1))
        ref_tensor = torch.from_numpy(ref_tensor).float().unsqueeze(0).to(self.device)
        test_tensor = torch.from_numpy(test_tensor).float().unsqueeze(0).to(self.device)
        ref_tensor = ref_tensor * 2.0 - 1.0
        test_tensor = test_tensor * 2.0 - 1.0
        with torch.no_grad():
            return float(self._model(ref_tensor, test_tensor).item())


def summarize_metric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "finite_count": 0,
            "perfect_match_count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
        }
    finite_values = [value for value in values if math.isfinite(value)]
    perfect_match_count = len(values) - len(finite_values)

    if finite_values:
        std_value = statistics.pstdev(finite_values) if len(finite_values) > 1 else 0.0
        mean_value = sum(finite_values) / len(finite_values)
        median_value = statistics.median(finite_values)
        min_value = min(finite_values)
        max_value = max(finite_values)
    else:
        std_value = 0.0
        mean_value = math.inf
        median_value = math.inf
        min_value = math.inf
        max_value = math.inf

    return {
        "count": len(values),
        "finite_count": len(finite_values),
        "perfect_match_count": perfect_match_count,
        "mean": mean_value,
        "median": median_value,
        "std": std_value,
        "min": min_value,
        "max": max_value,
    }


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return "nan"
        return "inf" if value > 0 else "-inf"
    return value


def fmt_metric(value: Any, digits: int) -> str:
    if value is None:
        return "NA"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f"{float(value):.{digits}f}"
    if value == math.inf:
        return "inf"
    if value == -math.inf:
        return "-inf"
    return str(value)


def build_shape_mismatch_summary(
    *,
    mismatch_rows: list[dict[str, Any]],
    normalized_pair_count: int,
    size_mismatch_mode_resolved: str,
) -> dict[str, Any]:
    if normalized_pair_count <= 0:
        return {
            "status": "none",
            "normalized_pair_count": 0,
            "normalization_mode": size_mismatch_mode_resolved,
            "message": "No shape mismatch detected.",
            "first_pattern": None,
        }

    first_pattern = mismatch_rows[0] if mismatch_rows else None
    if first_pattern is None:
        message = (
            f"Normalized {normalized_pair_count} shape-mismatched pair(s) via "
            f"{size_mismatch_mode_resolved}."
        )
    else:
        message = (
            f"Normalized {normalized_pair_count} shape-mismatched pair(s) via "
            f"{size_mismatch_mode_resolved}; top pattern ref={first_pattern['ref_shape']} "
            f"test={first_pattern['test_shape']} compared={first_pattern['compared_shape']} "
            f"anchor={first_pattern['anchor']}."
        )
    return {
        "status": "normalized_warning",
        "normalized_pair_count": normalized_pair_count,
        "normalization_mode": size_mismatch_mode_resolved,
        "message": message,
        "first_pattern": first_pattern,
    }


def build_markdown_report(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    psnr = aggregate["psnr_db"]
    ssim = aggregate["ssim"]
    lpips = aggregate.get("lpips")
    worst_rows = report["worst_cases"]

    lines = [
        "# Image Quality Metrics Report",
        "",
        f"- run_id: {report['run_id']}",
        f"- status: {report['status']}",
        f"- timestamp: {report['timestamp']}",
        f"- comparison_label: {report['comparison_label']}",
        f"- ref_dir: {report['ref_dir']}",
        f"- test_dir: {report['test_dir']}",
        f"- matched_png_count: {report['matched_png_count']}",
        f"- compared_image_count: {report['compared_image_count']}",
        f"- max_images: {report['max_images']}",
        f"- size_mismatch_mode: {report['size_mismatch_mode']}",
        f"- size_mismatch_mode_resolved: {report['size_mismatch_mode_resolved']}",
        f"- cropped_pair_count: {report['cropped_pair_count']}",
        f"- shape_mismatch_count: {report['shape_mismatch_count']}",
        f"- shape_mismatch_status: {report['shape_mismatch_status']}",
        f"- shape_mismatch_message: {report['shape_mismatch_message']}",
        f"- lpips_mode: {report['lpips_mode']}",
        f"- lpips_status: {report['lpips_status']}",
        f"- psnr_perfect_match_count: {aggregate['psnr_db']['perfect_match_count']}",
        f"- missing_in_test_count: {report['missing_in_test_count']}",
        f"- extra_in_test_count: {report['extra_in_test_count']}",
        "",
        "## Aggregate",
        "",
        "| Metric | Mean | Median | Std | Min | Max |",
        "|---|---:|---:|---:|---:|---:|",
        f"| PSNR (dB) | {fmt_metric(psnr['mean'], 4)} | {fmt_metric(psnr['median'], 4)} | {fmt_metric(psnr['std'], 4)} | {fmt_metric(psnr['min'], 4)} | {fmt_metric(psnr['max'], 4)} |",
        f"| SSIM | {fmt_metric(ssim['mean'], 6)} | {fmt_metric(ssim['median'], 6)} | {fmt_metric(ssim['std'], 6)} | {fmt_metric(ssim['min'], 6)} | {fmt_metric(ssim['max'], 6)} |",
    ]

    if lpips is not None:
        lines.append(
            f"| LPIPS | {fmt_metric(lpips['mean'], 6)} | {fmt_metric(lpips['median'], 6)} | {fmt_metric(lpips['std'], 6)} | {fmt_metric(lpips['min'], 6)} | {fmt_metric(lpips['max'], 6)} |"
        )
    else:
        lines.append("| LPIPS | skipped | skipped | skipped | skipped | skipped |")

    if report["shape_mismatch_status"] != "none":
        lines.extend(
            [
                "",
                "## Shape Mismatch Gate",
                "",
                f"- status: {report['shape_mismatch_status']}",
                f"- message: {report['shape_mismatch_message']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Paper Row",
            "",
            "| Comparison | Images | PSNR (dB) | SSIM | LPIPS |",
            "|---|---:|---:|---:|---:|",
            f"| {report['comparison_label']} | {report['compared_image_count']} | {fmt_metric(psnr['mean'], 4)} | {fmt_metric(ssim['mean'], 6)} | {fmt_metric(lpips['mean'], 6) if lpips is not None else 'skipped'} |",
            "",
        ]
    )

    if report["shape_mismatch_patterns"]:
        lines.extend(
            [
                "## Shape Mismatch Patterns",
                "",
                "| Count | Relation | Ref Shape | Test Shape | Compared Shape | Anchor | Center Hint |",
                "|---:|---|---|---|---|---|---|",
            ]
        )
        for row in report["shape_mismatch_patterns"]:
            lines.append(
                f"| {row['count']} | {row['relation']} | {row['ref_shape']} | {row['test_shape']} | "
                f"{row['compared_shape']} | {row['anchor']} | {row['normalization_hint_center']} |"
            )
        lines.append("")

    if report["missing_in_test"]:
        lines.extend(
            [
                "## Missing In Test",
                "",
                *[f"- {item}" for item in report["missing_in_test"][:10]],
                "",
            ]
        )
    if report["extra_in_test"]:
        lines.extend(
            [
                "## Extra In Test",
                "",
                *[f"- {item}" for item in report["extra_in_test"][:10]],
                "",
            ]
        )

    if worst_rows:
        lines.extend(
            [
                "## Worst Cases By PSNR",
                "",
                "| Image | PSNR (dB) | SSIM | LPIPS | Cropped |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for row in worst_rows:
            lines.append(
                f"| {row['relative_path']} | {fmt_metric(row['psnr_db'], 4)} | {fmt_metric(row['ssim'], 6)} | {fmt_metric(row['lpips'], 6)} | {row['cropped']} |"
            )
        lines.append("")

    return "\n".join(lines)


def terminal_summary(report: dict[str, Any]) -> str:
    lpips_summary = report["aggregate"].get("lpips")
    lines = [
        f"Compared {report['compared_image_count']} image pairs for {report['comparison_label']}",
        (
            "PSNR mean/median/min: "
            f"{fmt_metric(report['aggregate']['psnr_db']['mean'], 4)} / "
            f"{fmt_metric(report['aggregate']['psnr_db']['median'], 4)} / "
            f"{fmt_metric(report['aggregate']['psnr_db']['min'], 4)} dB"
        ),
        (
            "SSIM mean/median/min: "
            f"{fmt_metric(report['aggregate']['ssim']['mean'], 6)} / "
            f"{fmt_metric(report['aggregate']['ssim']['median'], 6)} / "
            f"{fmt_metric(report['aggregate']['ssim']['min'], 6)}"
        ),
    ]
    if lpips_summary is None:
        lines.append(f"LPIPS: skipped ({report['lpips_status']})")
    else:
        lines.append(
            "LPIPS mean/median/max: "
            f"{fmt_metric(lpips_summary['mean'], 6)} / "
            f"{fmt_metric(lpips_summary['median'], 6)} / "
            f"{fmt_metric(lpips_summary['max'], 6)}"
        )
    lines.append(
        f"Shape mismatch: {report['shape_mismatch_status']} "
        f"({report['shape_mismatch_message']})"
    )
    if report.get("markdown_report"):
        lines.append(f"Markdown report: {report['markdown_report']}")
    if report.get("json_report"):
        lines.append(f"JSON report: {report['json_report']}")
    return "\n".join(lines)


def compare_directories(args: argparse.Namespace) -> dict[str, Any]:
    np = require_numpy()

    ref_dir = Path(args.ref_dir).resolve()
    test_dir = Path(args.test_dir).resolve()
    validate_dirs(ref_dir, test_dir)

    comparison_label = args.comparison_label or f"{ref_dir.name}_vs_{test_dir.name}"
    markdown_report, json_report, run_id = build_report_paths(args, comparison_label)

    ref_pngs = collect_pngs(ref_dir)
    test_pngs = collect_pngs(test_dir)
    matched_paths = sorted(set(ref_pngs) & set(test_pngs))
    missing_in_test = sorted(set(ref_pngs) - set(test_pngs))
    extra_in_test = sorted(set(test_pngs) - set(ref_pngs))

    if not matched_paths:
        raise SystemExit(
            f"ERROR: no matched PNG filenames found between {ref_dir} and {test_dir}."
        )
    if (missing_in_test or extra_in_test) and not args.allow_mismatch:
        message = [
            "ERROR: directory contents do not match.",
            f"missing_in_test={len(missing_in_test)}",
            f"extra_in_test={len(extra_in_test)}",
        ]
        if missing_in_test:
            message.append(f"first_missing={missing_in_test[0]}")
        if extra_in_test:
            message.append(f"first_extra={extra_in_test[0]}")
        message.append("Re-run with --allow-mismatch only if a subset comparison is intentional.")
        raise SystemExit(" ".join(message))

    if args.max_images < 0:
        raise SystemExit("ERROR: --max-images must be >= 0.")
    if args.max_images:
        matched_paths = matched_paths[: args.max_images]

    size_mismatch_mode_resolved = resolve_size_mismatch_mode(args.size_mismatch)
    lpips_scorer = LpipsScorer(mode=args.lpips, net=args.lpips_net, device=args.lpips_device)

    per_image = []
    psnr_values = []
    ssim_values = []
    lpips_values = []
    cropped_pair_count = 0
    shape_mismatch_patterns = collections.Counter()

    for relative_path in matched_paths:
        ref_path = ref_pngs[relative_path]
        test_path = test_pngs[relative_path]
        ref_image = load_image_as_float_rgb(ref_path, np)
        test_image = load_image_as_float_rgb(test_path, np)
        crop_metadata = None

        if ref_image.shape != test_image.shape:
            if size_mismatch_mode_resolved == "error":
                raise SystemExit(
                    "ERROR: image size mismatch for "
                    f"{relative_path}: ref={ref_image.shape} test={test_image.shape}"
                )
            ref_image, test_image, cropped, ref_shape, test_shape, crop_metadata = maybe_crop_to_common_shape(
                ref_image,
                test_image,
                np,
                mode=size_mismatch_mode_resolved,
            )
        else:
            cropped = False
            ref_shape = ref_image.shape
            test_shape = test_image.shape

        if cropped:
            cropped_pair_count += 1
            pattern_key = (
                tuple(int(dim) for dim in ref_shape),
                tuple(int(dim) for dim in test_shape),
                tuple(int(dim) for dim in ref_image.shape),
                crop_metadata["anchor"],
            )
            shape_mismatch_patterns[pattern_key] += 1

        psnr_value = psnr_db(ref_image, test_image, np)
        ssim_value = ssim_score(ref_image, test_image, np)
        lpips_value = lpips_scorer.score(ref_image, test_image, np)

        psnr_values.append(psnr_value)
        ssim_values.append(ssim_value)
        if lpips_value is not None:
            lpips_values.append(lpips_value)

        per_image.append(
            {
                "relative_path": relative_path,
                "ref_path": str(ref_path),
                "test_path": str(test_path),
                "ref_shape": list(ref_shape),
                "test_shape": list(test_shape),
                "compared_shape": list(ref_image.shape),
                "cropped": cropped,
                "crop_metadata": crop_metadata,
                "psnr_db": psnr_value,
                "ssim": ssim_value,
                "lpips": lpips_value,
            }
        )

    worst_cases = sorted(per_image, key=lambda row: row["psnr_db"])[: min(10, len(per_image))]

    mismatch_rows = []
    for (ref_shape, test_shape, compared_shape, anchor), count in shape_mismatch_patterns.most_common():
        analysis = analyze_shape_pair(list(ref_shape), list(test_shape), left_label="ref", right_label="test")
        mismatch_rows.append(
            {
                "count": count,
                "relation": analysis["relation"],
                "ref_shape": list(ref_shape),
                "test_shape": list(test_shape),
                "compared_shape": list(compared_shape),
                "anchor": anchor,
                "normalization_hint_center": analysis["normalization_hint_center"],
                "normalization_hint_top_left": analysis["normalization_hint_top_left"],
            }
        )

    shape_mismatch_summary = build_shape_mismatch_summary(
        mismatch_rows=mismatch_rows,
        normalized_pair_count=cropped_pair_count,
        size_mismatch_mode_resolved=size_mismatch_mode_resolved,
    )

    report = {
        "run_id": run_id,
        "status": "success_shape_mismatch_warned" if cropped_pair_count else "success",
        "timestamp": iso_timestamp(),
        "comparison_label": comparison_label,
        "ref_dir": str(ref_dir),
        "test_dir": str(test_dir),
        "matched_png_count": len(set(ref_pngs) & set(test_pngs)),
        "compared_image_count": len(per_image),
        "max_images": args.max_images,
        "size_mismatch_mode": args.size_mismatch,
        "size_mismatch_mode_resolved": size_mismatch_mode_resolved,
        "cropped_pair_count": cropped_pair_count,
        "shape_mismatch_count": cropped_pair_count,
        "shape_mismatch_status": shape_mismatch_summary["status"],
        "shape_mismatch_message": shape_mismatch_summary["message"],
        "shape_mismatch_summary": shape_mismatch_summary,
        "shape_mismatch_patterns": mismatch_rows,
        "lpips_mode": args.lpips,
        "lpips_status": lpips_scorer.reason,
        "missing_in_test_count": len(missing_in_test),
        "extra_in_test_count": len(extra_in_test),
        "missing_in_test": missing_in_test,
        "extra_in_test": extra_in_test,
        "aggregate": {
            "psnr_db": summarize_metric(psnr_values),
            "ssim": summarize_metric(ssim_values),
            "lpips": summarize_metric(lpips_values) if lpips_values else None,
        },
        "worst_cases": worst_cases,
        "per_image": per_image,
        "markdown_report": str(markdown_report) if markdown_report is not None else None,
        "json_report": str(json_report) if json_report is not None else None,
    }

    if markdown_report is not None and json_report is not None:
        markdown_report.write_text(build_markdown_report(report), encoding="utf-8")
        json_report.write_text(
            json.dumps(sanitize_json(report), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return report


def main() -> int:
    args = parse_args()
    report = compare_directories(args)
    print(terminal_summary(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
