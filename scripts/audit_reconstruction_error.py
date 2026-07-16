#!/usr/bin/env python3
"""Audit sampled reconstruction error against source images."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
METRIC_FIELDS = (
    "mse",
    "rmse",
    "mae",
    "max_abs_diff",
    "p95_abs_diff",
    "psnr_db",
    "ssim",
    "pixel_equal_ratio",
)
CSV_FIELDS = (
    "stem",
    "status",
    "shape_match",
    "original_path",
    "reconstruction_path",
    "original_shape",
    "reconstruction_shape",
    *METRIC_FIELDS,
)


def image_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for extension in IMAGE_EXTENSIONS:
        paths.extend(root.glob(f"*{extension}"))
        paths.extend(root.glob(f"*{extension.upper()}"))
    return sorted(set(paths), key=lambda path: path.name.lower())


def original_stem_for_reconstruction(recon_path: Path, recon_suffix: str) -> str:
    stem = recon_path.stem
    if recon_suffix and stem.endswith(recon_suffix):
        return stem[: -len(recon_suffix)]
    return stem


def build_original_index(original_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in image_paths(original_dir):
        index.setdefault(path.stem, path)
    return index


def find_candidates(original_dir: Path, recon_dir: Path, recon_suffix: str = "_recon") -> list[dict[str, Any]]:
    originals = build_original_index(original_dir)
    candidates: list[dict[str, Any]] = []
    for recon_path in image_paths(recon_dir):
        stem = original_stem_for_reconstruction(recon_path, recon_suffix)
        original_path = originals.get(stem)
        if original_path is None:
            continue
        candidates.append(
            {
                "stem": stem,
                "original_path": original_path,
                "reconstruction_path": recon_path,
            }
        )
    return sorted(candidates, key=lambda item: str(item["stem"]))


def original_stem_from_manifest(manifest_path: Path) -> str:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    source_info = payload.get("source_info") if isinstance(payload, dict) else {}
    source_meta = source_info.get("source_meta") if isinstance(source_info, dict) else {}
    value = source_meta.get("original_filename") if isinstance(source_meta, dict) else ""
    return str(value or "").strip()


def find_usrp_manifest_candidates(
    original_dir: Path,
    recon_dir: Path,
    manifest_run_dir: Path,
    recon_suffix: str = "_recon",
) -> list[dict[str, Any]]:
    originals = build_original_index(original_dir)
    candidates: list[dict[str, Any]] = []
    for image_dir in sorted(manifest_run_dir.glob("image_*")):
        if not image_dir.is_dir():
            continue
        try:
            image_index = int(image_dir.name.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        stem = original_stem_from_manifest(image_dir / "manifest.json")
        if not stem:
            continue
        original_path = originals.get(stem)
        recon_path = recon_dir / f"{image_index:08d}{recon_suffix}.png"
        if original_path is None or not recon_path.is_file():
            continue
        candidates.append(
            {
                "stem": stem,
                "original_path": original_path,
                "reconstruction_path": recon_path,
                "manifest_path": image_dir / "manifest.json",
                "image_index": image_index,
            }
        )
    return sorted(candidates, key=lambda item: int(item["image_index"]))


def choose_sample(candidates: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    if sample_size <= 0 or sample_size >= len(candidates):
        return list(candidates)
    sampled = random.Random(seed).sample(candidates, sample_size)
    return sorted(sampled, key=lambda item: str(item["stem"]))


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def psnr_from_mse(mse: float, max_value: float = 255.0) -> float:
    if mse == 0.0:
        return float("inf")
    return 20.0 * math.log10(max_value) - 10.0 * math.log10(mse)


def global_ssim(original: np.ndarray, reconstruction: np.ndarray, max_value: float = 255.0) -> float:
    c1 = (0.01 * max_value) ** 2
    c2 = (0.03 * max_value) ** 2
    mu_orig = float(original.mean())
    mu_recon = float(reconstruction.mean())
    var_orig = float(original.var())
    var_recon = float(reconstruction.var())
    covariance = float(((original - mu_orig) * (reconstruction - mu_recon)).mean())
    numerator = (2.0 * mu_orig * mu_recon + c1) * (2.0 * covariance + c2)
    denominator = (mu_orig**2 + mu_recon**2 + c1) * (var_orig + var_recon + c2)
    if denominator == 0.0:
        return 1.0 if np.array_equal(original, reconstruction) else 0.0
    return numerator / denominator


def compare_pair(stem: str, original_path: Path, reconstruction_path: Path) -> dict[str, Any]:
    original = load_rgb(original_path)
    reconstruction = load_rgb(reconstruction_path)
    record: dict[str, Any] = {
        "stem": stem,
        "status": "ok",
        "original_path": str(original_path),
        "reconstruction_path": str(reconstruction_path),
        "original_shape": list(original.shape),
        "reconstruction_shape": list(reconstruction.shape),
        "shape_match": original.shape == reconstruction.shape,
    }
    if original.shape != reconstruction.shape:
        record["status"] = "shape_mismatch"
        for field in METRIC_FIELDS:
            record[field] = None
        return record

    diff = reconstruction - original
    abs_diff = np.abs(diff)
    mse = float(np.mean(np.square(diff)))
    pixel_equal = np.all(diff == 0.0, axis=2)
    record.update(
        {
            "mse": mse,
            "rmse": float(math.sqrt(mse)),
            "mae": float(abs_diff.mean()),
            "max_abs_diff": float(abs_diff.max()),
            "p95_abs_diff": float(np.percentile(abs_diff, 95)),
            "psnr_db": psnr_from_mse(mse),
            "ssim": float(global_ssim(original, reconstruction)),
            "pixel_equal_ratio": float(pixel_equal.mean()),
        }
    )
    return record


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    ok_records = [record for record in records if record.get("status") == "ok"]
    aggregate: dict[str, Any] = {
        "ok_count": len(ok_records),
        "shape_mismatch_count": sum(1 for record in records if record.get("status") == "shape_mismatch"),
    }
    for field in METRIC_FIELDS:
        values = [record[field] for record in ok_records if record.get(field) is not None]
        aggregate[f"mean_{field}"] = float(np.mean(values)) if values else None
        aggregate[f"min_{field}"] = float(np.min(values)) if values else None
        aggregate[f"max_{field}"] = float(np.max(values)) if values else None
    return aggregate


def audit_reconstructions(
    original_dir: str | Path,
    recon_dir: str | Path,
    sample_size: int = 20,
    seed: int = 0,
    recon_suffix: str = "_recon",
    manifest_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    original_root = Path(original_dir)
    recon_root = Path(recon_dir)
    if not original_root.is_dir():
        raise FileNotFoundError(f"original directory not found: {original_root}")
    if not recon_root.is_dir():
        raise FileNotFoundError(f"reconstruction directory not found: {recon_root}")

    manifest_root = Path(manifest_run_dir) if manifest_run_dir else None
    if manifest_root is not None and not manifest_root.is_dir():
        raise FileNotFoundError(f"manifest run directory not found: {manifest_root}")

    matching_mode = "usrp_manifest" if manifest_root is not None else "filename"
    candidates = (
        find_usrp_manifest_candidates(original_root, recon_root, manifest_root, recon_suffix=recon_suffix)
        if manifest_root is not None
        else find_candidates(original_root, recon_root, recon_suffix=recon_suffix)
    )
    sampled = choose_sample(candidates, sample_size=sample_size, seed=seed)
    records = [
        compare_pair(
            stem=str(item["stem"]),
            original_path=Path(item["original_path"]),
            reconstruction_path=Path(item["reconstruction_path"]),
        )
        for item in sampled
    ]
    return {
        "original_dir": str(original_root),
        "recon_dir": str(recon_root),
        "manifest_run_dir": str(manifest_root) if manifest_root is not None else None,
        "matching_mode": matching_mode,
        "sample_size_requested": sample_size,
        "seed": seed,
        "recon_suffix": recon_suffix,
        "candidate_count": len(candidates),
        "audited_count": len(records),
        "aggregate": summarize(records),
        "records": records,
    }


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def write_csv(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["original_shape"] = "x".join(str(value) for value in record.get("original_shape") or [])
            row["reconstruction_shape"] = "x".join(
                str(value) for value in record.get("reconstruction_shape") or []
            )
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Randomly audit reconstruction error against source images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--original-dir", required=True, help="Directory containing source images.")
    parser.add_argument("--recon-dir", required=True, help="Directory containing reconstructed images.")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of matched pairs to audit; <=0 audits all.")
    parser.add_argument("--seed", type=int, default=0, help="Seed for deterministic random sampling.")
    parser.add_argument("--recon-suffix", default="_recon", help="Suffix removed from reconstruction stems.")
    parser.add_argument(
        "--manifest-run-dir",
        default="",
        help="Optional USRP run directory containing image_XXXX/manifest.json files.",
    )
    parser.add_argument("--output-json", default="", help="Optional JSON report path.")
    parser.add_argument("--output-csv", default="", help="Optional CSV report path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = audit_reconstructions(
        original_dir=args.original_dir,
        recon_dir=args.recon_dir,
        sample_size=args.sample_size,
        seed=args.seed,
        recon_suffix=args.recon_suffix,
        manifest_run_dir=args.manifest_run_dir or None,
    )
    if args.output_json:
        write_json(payload, Path(args.output_json))
    if args.output_csv:
        write_csv(payload["records"], Path(args.output_csv))

    aggregate = payload["aggregate"]
    print(
        "audit-ok "
        f"candidates={payload['candidate_count']} "
        f"audited={payload['audited_count']} "
        f"mean_psnr={aggregate.get('mean_psnr_db')} "
        f"mean_ssim={aggregate.get('mean_ssim')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
