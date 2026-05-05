#!/usr/bin/env python3
"""Generate reproducible PyTorch JSCC reference reconstructions from latent inputs."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import logging
import os
import random
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

try:
    import torch
except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime env.
    raise SystemExit("ERROR: torch is required for PyTorch reference reconstruction.") from exc

try:
    from PIL import Image
except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime env.
    raise SystemExit("ERROR: Pillow is required for PNG output.") from exc


LOGGER = logging.getLogger("pytorch_reference_reconstruction")
LOCAL_EXPERIMENTAL_SUBPROCESS_MODE = "local_experimental_subprocess_per_image"
LOCAL_EXPERIMENTAL_SUBPROCESS_STAGE = (
    "PyTorch reconstruction (local experimental subprocess-per-image)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reference reconstructions from quantized JSCC latent inputs "
            "using the original PyTorch sub-generator weights."
        )
    )
    parser.add_argument("--jscc-root", required=True, help="Path to the upstream jscc repo root.")
    parser.add_argument(
        "--generator-ckpt",
        required=True,
        help="Path to export/compressed_gan.pt or another sub-generator state dict.",
    )
    parser.add_argument(
        "--origin-ckpt",
        default="",
        help="Optional full origin checkpoint for manifest provenance only.",
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing latent .pt/.npz/.npy files.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Run output root. PNGs are written under <output-dir>/reconstructions/.",
    )
    parser.add_argument("--snr", type=float, default=10.0, help="AWGN SNR in dB.")
    parser.add_argument(
        "--noise-mode",
        choices=("awgn", "none"),
        default="awgn",
        help="Whether to inject AWGN before decoding.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260312,
        help="Base seed used to derive a stable per-file noise seed.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Torch device for inference. CPU is recommended on Phytium Pi.",
    )
    parser.add_argument(
        "--torch-num-threads",
        type=int,
        default=0,
        help="If >0, call torch.set_num_threads() before model load.",
    )
    parser.add_argument(
        "--torch-num-interop-threads",
        type=int,
        default=0,
        help="If >0, call torch.set_num_interop_threads() before model load.",
    )
    parser.add_argument(
        "--local-disable-mkldnn",
        action="store_true",
        help=(
            "Isolated local-workspace experimental switch: disable oneDNN/MKLDNN "
            "for this PyTorch reference run before model load."
        ),
    )
    parser.add_argument(
        "--local-experimental-subprocess-per-image",
        action="store_true",
        help=(
            "Local-only experimental mode: run each image reconstruction in its own "
            "Python subprocess while the parent process only schedules work and "
            "aggregates results."
        ),
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=300,
        help="Maximum number of latent files to process. Use 0 for all files.",
    )
    parser.add_argument(
        "--manifest-name",
        default="pytorch_reference_manifest.json",
        help="Manifest filename written under --output-dir.",
    )
    parser.add_argument(
        "--expected-sha256",
        default="",
        help="Optional trusted generator checkpoint SHA-256. Mismatches fail fast.",
    )
    parser.add_argument(
        "--variant",
        default="baseline",
        help="Human-readable variant tag surfaced in the final JSON summary.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--local-experimental-subprocess-worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--local-experimental-subprocess-worker-input",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--local-experimental-subprocess-worker-record",
        default="",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def iso_timestamp() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def maybe_torch_load(path: Path) -> Any:
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        return torch.load(path, map_location="cpu")
    except Exception:
        return torch.load(path, map_location="cpu", weights_only=False)


def json_ready(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if torch.is_tensor(value):
        if value.ndim == 0:
            return value.item()
        return value.detach().cpu().tolist()
    return repr(value)


def add_jscc_to_pythonpath(jscc_root: Path) -> None:
    if not (jscc_root / "src" / "network" / "sub_generator.py").is_file():
        raise SystemExit(f"ERROR: jscc root does not contain src/network/sub_generator.py: {jscc_root}")
    sys.path.insert(0, str(jscc_root))


def normalize_state_dict(raw_state: Any) -> dict[str, Any]:
    if isinstance(raw_state, dict):
        if "state_dict" in raw_state and isinstance(raw_state["state_dict"], dict):
            raw_state = raw_state["state_dict"]
        elif "model_state_dict" in raw_state and isinstance(raw_state["model_state_dict"], dict):
            raw_state = raw_state["model_state_dict"]
    if not isinstance(raw_state, dict):
        raise SystemExit("ERROR: generator checkpoint did not load as a state dict.")

    stripped: dict[str, Any] = {}
    for key, value in raw_state.items():
        if "total_ops" in key or "total_params" in key:
            continue
        clean_key = key[7:] if key.startswith("module.") else key
        stripped[clean_key] = value
    return stripped


def infer_subgenerator_spec(state_dict: dict[str, Any]) -> dict[str, Any]:
    required_keys = (
        "conv01.weight",
        "convt1.weight",
        "convt2.weight",
        "convt3.weight",
        "conv11.weight",
    )
    missing = [key for key in required_keys if key not in state_dict]
    if missing:
        raise SystemExit(f"ERROR: generator checkpoint is missing required keys: {missing}")

    resblock_ids = sorted(
        {
            int(match.group(1))
            for key in state_dict
            if (match := re.match(r"resblock_(\d+)\.", key))
        }
    )
    if not resblock_ids:
        raise SystemExit("ERROR: generator checkpoint does not contain any resblock_* weights.")

    channels = [0] * 6
    channels[0] = int(state_dict["conv01.weight"].shape[0]) // 16

    for block_id in resblock_ids:
        pointwise_key = f"resblock_{block_id}.conv1.conv.2.weight"
        if pointwise_key not in state_dict:
            raise SystemExit(f"ERROR: checkpoint is missing {pointwise_key}")
        channels[1 + block_id // 3] = int(state_dict[pointwise_key].shape[0]) // 16

    channels[3] = int(state_dict["convt1.weight"].shape[1]) // 8
    channels[4] = int(state_dict["convt2.weight"].shape[1]) // 4
    channels[5] = int(state_dict["convt3.weight"].shape[1]) // 2

    if any(channel <= 0 for channel in channels):
        raise SystemExit(f"ERROR: failed to infer a valid sub-generator channel config: {channels}")

    return {
        "latent_channels": int(state_dict["conv01.weight"].shape[1]),
        "channels": channels,
        "n_residual_blocks": resblock_ids[-1] + 1,
        "output_channels": int(state_dict["conv11.weight"].shape[0]),
    }


def load_generator(jscc_root: Path, generator_ckpt: Path, device: torch.device):
    add_jscc_to_pythonpath(jscc_root)
    from src.network.sub_generator import SubMobileGenerator

    raw_state = maybe_torch_load(generator_ckpt)
    state_dict = normalize_state_dict(raw_state)
    spec = infer_subgenerator_spec(state_dict)

    model = SubMobileGenerator(
        image_dims=(spec["output_channels"], 256, 256),
        config={"channels": spec["channels"]},
        C=spec["latent_channels"],
        n_residual_blocks=spec["n_residual_blocks"],
    )
    model.load_state_dict(state_dict, strict=True)
    model = model.to(device)
    model.eval()
    return model, spec


def ensure_batched_latent(latent: Any) -> torch.Tensor:
    tensor = torch.as_tensor(latent, dtype=torch.float32, device="cpu")
    if tensor.ndim == 3:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 4:
        raise ValueError(f"expected latent shape with 3 or 4 dims, got {tuple(tensor.shape)}")
    return tensor


def load_pt_latent(path: Path) -> tuple[torch.Tensor, dict[str, Any]]:
    payload = maybe_torch_load(path)
    metadata: dict[str, Any] = {}

    if torch.is_tensor(payload):
        return ensure_batched_latent(payload), metadata

    if not isinstance(payload, dict):
        raise ValueError(f"unsupported .pt payload type in {path}: {type(payload)!r}")

    if {"quant", "scale", "zero_point"}.issubset(payload):
        quant = torch.as_tensor(payload["quant"], dtype=torch.float32, device="cpu")
        scale = torch.as_tensor(payload["scale"], dtype=torch.float32, device="cpu")
        zero_point = torch.as_tensor(payload["zero_point"], dtype=torch.float32, device="cpu")
        checksum = payload.get("checksum")
        if checksum:
            current_checksum = hashlib.md5(quant.numpy().tobytes()).hexdigest()
            if current_checksum != checksum:
                raise ValueError(
                    f"checksum mismatch in {path}: expected {checksum}, got {current_checksum}"
                )
            metadata["quant_checksum"] = checksum
        metadata["original_filename"] = payload.get("original_filename")
        metadata["latent_snr"] = json_ready(payload.get("snr"))
        metadata["config_str"] = payload.get("config_str")
        latent = (quant - zero_point) * scale
        return ensure_batched_latent(latent), metadata

    if "latent" in payload:
        return ensure_batched_latent(payload["latent"]), metadata

    raise ValueError(f"unsupported .pt payload keys in {path}: {sorted(payload.keys())}")


def load_npz_latent(path: Path) -> tuple[torch.Tensor, dict[str, Any]]:
    with np.load(path) as payload:
        if "latent" in payload:
            return ensure_batched_latent(payload["latent"]), {}
        required_keys = {"quant", "scale", "zero_point"}
        if not required_keys.issubset(payload.files):
            raise ValueError(f"{path} is missing required keys: {sorted(required_keys)}")
        quant = payload["quant"].astype("float32")
        scale = payload["scale"].astype("float32")
        zero_point = payload["zero_point"].astype("float32")
        latent = (quant - zero_point) * scale
        return ensure_batched_latent(latent), {}


def load_latent(path: Path) -> tuple[torch.Tensor, dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".pt":
        return load_pt_latent(path)
    if suffix == ".npz":
        return load_npz_latent(path)
    if suffix == ".npy":
        return ensure_batched_latent(np.load(path)), {}
    raise ValueError(f"unsupported latent file type: {path}")


def collect_input_files(input_dir: Path, max_images: int) -> list[Path]:
    patterns = ("*.pt", "*.npz", "*.npy")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(Path(path) for path in glob.glob(str(input_dir / pattern)))
    unique_files = sorted({path.resolve(): path for path in files}.values())
    if max_images > 0:
        unique_files = unique_files[:max_images]
    return unique_files


def per_file_seed(base_seed: int, sample_key: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{sample_key}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**63 - 1)


def awgn_channel(latent: torch.Tensor, snr: float, seed: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    power = torch.mean(latent.square(), dim=(-3, -2, -1), keepdim=True) * 2.0
    noise_power = power * (10.0 ** (-snr / 10.0))
    noise = torch.randn(latent.shape, generator=generator, dtype=latent.dtype)
    noise = torch.sqrt(noise_power / 2.0) * noise
    return latent + noise


def tensor_to_image(output: torch.Tensor) -> np.ndarray:
    tensor = output.detach().cpu().float()
    if tensor.ndim == 4 and tensor.shape[0] == 1:
        tensor = tensor[0]
    if tensor.ndim != 3:
        raise ValueError(f"cannot convert output with shape={tuple(tensor.shape)} to image")
    if tensor.shape[0] not in (1, 3, 4):
        raise ValueError(f"expected channel-first output with 1/3/4 channels, got {tuple(tensor.shape)}")
    array = tensor.clamp(0.0, 1.0).permute(1, 2, 0).numpy()
    if array.shape[-1] == 1:
        array = array[:, :, 0]
    return (array * 255.0 + 0.5).astype(np.uint8)


def save_png(output: torch.Tensor, path: Path) -> None:
    image_array = tensor_to_image(output)
    Image.fromarray(image_array).save(path, format="PNG")


def load_origin_checkpoint_metadata(origin_ckpt: Path) -> dict[str, Any] | None:
    if not origin_ckpt.is_file():
        return None
    try:
        payload = maybe_torch_load(origin_ckpt)
    except Exception as err:
        return {"load_error": str(err)}
    if not isinstance(payload, dict):
        return {"payload_type": type(payload).__name__}
    return {
        "keys": sorted(payload.keys()),
        "args": json_ready(payload.get("args")),
    }


def configure_torch_threads(
    torch_num_threads: int,
    torch_num_interop_threads: int,
) -> dict[str, int | None]:
    if torch_num_interop_threads > 0:
        set_num_interop_threads = getattr(torch, "set_num_interop_threads", None)
        if set_num_interop_threads is None:
            raise SystemExit("ERROR: this torch build does not support torch.set_num_interop_threads().")
        try:
            set_num_interop_threads(torch_num_interop_threads)
        except RuntimeError as err:
            raise SystemExit(
                "ERROR: failed to set torch inter-op threads to "
                f"{torch_num_interop_threads}: {err}"
            ) from err

    if torch_num_threads > 0:
        try:
            torch.set_num_threads(torch_num_threads)
        except RuntimeError as err:
            raise SystemExit(
                f"ERROR: failed to set torch intra-op threads to {torch_num_threads}: {err}"
            ) from err

    get_num_interop_threads = getattr(torch, "get_num_interop_threads", None)
    return {
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": (
            None if get_num_interop_threads is None else int(get_num_interop_threads())
        ),
    }


def configure_mkldnn(local_disable_mkldnn: bool) -> dict[str, Any]:
    mkldnn_backend = getattr(getattr(torch, "backends", None), "mkldnn", None)
    backend_present = mkldnn_backend is not None and hasattr(mkldnn_backend, "enabled")
    enabled_before = None
    enabled_after = None
    available = None

    if backend_present:
        enabled_before = bool(mkldnn_backend.enabled)
        if local_disable_mkldnn:
            mkldnn_backend.enabled = False
        enabled_after = bool(mkldnn_backend.enabled)
        is_available = getattr(mkldnn_backend, "is_available", None)
        if callable(is_available):
            try:
                available = bool(is_available())
            except Exception as err:  # pragma: no cover - backend-specific.
                available = f"error:{err}"
    elif local_disable_mkldnn:
        LOGGER.warning(
            "local_disable_mkldnn was requested, but torch.backends.mkldnn is unavailable in this build."
        )

    return {
        "local_disable_mkldnn": bool(local_disable_mkldnn),
        "mkldnn_backend_present": bool(backend_present),
        "mkldnn_available": available,
        "mkldnn_enabled_before": enabled_before,
        "mkldnn_enabled": enabled_after if backend_present else None,
    }


def validate_common_paths(jscc_root: Path, generator_ckpt: Path, input_dir: Path) -> None:
    if not jscc_root.is_dir():
        raise SystemExit(f"ERROR: jscc root not found: {jscc_root}")
    if not generator_ckpt.is_file():
        raise SystemExit(f"ERROR: generator checkpoint not found: {generator_ckpt}")
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: input dir not found: {input_dir}")


def resolve_expected_sha256(expected_sha256: str) -> str:
    return str(expected_sha256 or "").strip().lower()


def summarize_samples(samples: list[float]) -> dict[str, Any]:
    if not samples:
        return {
            "count": 0,
            "median_ms": None,
            "mean_ms": None,
            "min_ms": None,
            "max_ms": None,
            "variance_ms2": 0.0,
        }
    return {
        "count": len(samples),
        "median_ms": round(statistics.median(samples), 3),
        "mean_ms": round(sum(samples) / len(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "variance_ms2": round(statistics.pvariance(samples), 6) if len(samples) > 1 else 0.0,
    }


def emit_progress(index: int, total: int, input_path: Path, save_path: Path, stage: str) -> None:
    print(
        json.dumps(
            {
                "openamp_demo_progress": {
                    "completed_count": index,
                    "expected_count": total,
                    "remaining_count": max(total - index, 0),
                    "completion_ratio": round(index / total, 4) if total else 0.0,
                    "current_stage": stage,
                    "sample": input_path.name,
                    "output_path": str(save_path),
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def reconstruct_single_input(
    model: Any,
    device: torch.device,
    input_path: Path,
    reconstructions_dir: Path,
    snr: float,
    noise_mode: str,
    seed: int,
) -> dict[str, Any]:
    base_name = input_path.stem.split("_latent")[0]
    sample_seed = per_file_seed(seed, str(input_path.name))
    started = time.perf_counter()
    latent, latent_meta = load_latent(input_path)
    if noise_mode == "awgn":
        model_input = awgn_channel(latent, snr, sample_seed)
    else:
        model_input = latent
    output = model(model_input.to(device))
    output_cpu = output.detach().cpu()
    save_path = reconstructions_dir / f"{base_name}_recon.png"
    save_png(output_cpu, save_path)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    output_min = float(output_cpu.min().item())
    output_max = float(output_cpu.max().item())
    LOGGER.info(
        "saved %s from %s in %.3f ms (seed=%s, output_range=[%.6f, %.6f])",
        save_path,
        input_path.name,
        elapsed_ms,
        sample_seed,
        output_min,
        output_max,
    )
    return {
        "input_path": str(input_path),
        "input_sha256": file_sha256(input_path),
        "base_name": base_name,
        "sample_seed": sample_seed,
        "noise_mode": noise_mode,
        "snr": snr,
        "latent_shape": list(latent.shape),
        "output_shape": list(output_cpu.shape),
        "output_range": [output_min, output_max],
        "elapsed_ms": round(elapsed_ms, 3),
        "output_path": str(save_path),
        "output_sha256": file_sha256(save_path),
        "latent_metadata": json_ready(latent_meta),
    }


def run_single_process_reference(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    mkldnn_settings = configure_mkldnn(args.local_disable_mkldnn)
    torch_thread_settings = configure_torch_threads(
        torch_num_threads=args.torch_num_threads,
        torch_num_interop_threads=args.torch_num_interop_threads,
    )

    jscc_root = Path(args.jscc_root)
    generator_ckpt = Path(args.generator_ckpt)
    origin_ckpt = Path(args.origin_ckpt) if args.origin_ckpt else None
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reconstructions_dir = output_dir / "reconstructions"
    manifest_path = output_dir / args.manifest_name

    validate_common_paths(jscc_root, generator_ckpt, input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    reconstructions_dir.mkdir(parents=True, exist_ok=True)

    all_input_files = collect_input_files(input_dir, 0)
    if not all_input_files:
        raise SystemExit(f"ERROR: no latent files found in {input_dir}")
    input_files = all_input_files[: args.max_images] if args.max_images > 0 else all_input_files

    generator_ckpt_sha256 = file_sha256(generator_ckpt)
    expected_sha256 = resolve_expected_sha256(args.expected_sha256)
    if expected_sha256 and generator_ckpt_sha256 != expected_sha256:
        raise SystemExit(
            "ERROR: generator checkpoint sha256 mismatch "
            f"path={generator_ckpt} expected={expected_sha256} actual={generator_ckpt_sha256}"
        )

    device = torch.device(args.device)
    model_load_started = time.perf_counter()
    model, spec = load_generator(jscc_root, generator_ckpt, device)
    model_load_ms = (time.perf_counter() - model_load_started) * 1000.0

    started_at = iso_timestamp()
    LOGGER.info(
        "PyTorch reference generation started: inputs=%s snr=%s noise_mode=%s output_dir=%s",
        len(input_files),
        args.snr,
        args.noise_mode,
        output_dir,
    )
    LOGGER.info("Inferred sub-generator spec: %s", spec)

    records: list[dict[str, Any]] = []
    run_samples_ms: list[float] = []

    with torch.inference_mode():
        for index, input_path in enumerate(input_files, start=1):
            record = reconstruct_single_input(
                model=model,
                device=device,
                input_path=input_path,
                reconstructions_dir=reconstructions_dir,
                snr=args.snr,
                noise_mode=args.noise_mode,
                seed=args.seed,
            )
            records.append(record)
            run_samples_ms.append(float(record["elapsed_ms"]))
            emit_progress(
                index=index,
                total=len(input_files),
                input_path=input_path,
                save_path=Path(record["output_path"]),
                stage="PyTorch reconstruction",
            )

    run_summary = summarize_samples(run_samples_ms)

    completed_at = iso_timestamp()
    manifest = {
        "run_type": "pytorch_reference_reconstruction",
        "execution_mode": "single_process",
        "started_at": started_at,
        "completed_at": completed_at,
        "jscc_root": str(jscc_root),
        "generator_ckpt": str(generator_ckpt),
        "generator_ckpt_sha256": generator_ckpt_sha256,
        "origin_ckpt": None if origin_ckpt is None else str(origin_ckpt),
        "origin_ckpt_sha256": None if origin_ckpt is None or not origin_ckpt.is_file() else file_sha256(origin_ckpt),
        "origin_ckpt_metadata": None if origin_ckpt is None else load_origin_checkpoint_metadata(origin_ckpt),
        "input_dir": str(input_dir),
        "input_count": len(input_files),
        "output_dir": str(output_dir),
        "reconstructions_dir": str(reconstructions_dir),
        "output_count": len(records),
        "snr": args.snr,
        "noise_mode": args.noise_mode,
        "seed": args.seed,
        "device": str(device),
        **torch_thread_settings,
        **mkldnn_settings,
        "inferred_model": spec,
        "timing": {
            "total_ms": round(sum(run_samples_ms), 3) if run_samples_ms else None,
            "mean_ms": run_summary["mean_ms"],
        },
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Manifest written to %s", manifest_path)
    LOGGER.info("Completed %s/%s reference reconstructions", len(records), len(input_files))
    summary = {
        "variant": str(args.variant),
        "runtime": "pytorch_reference",
        "artifact_path": str(generator_ckpt),
        "artifact_sha256": generator_ckpt_sha256,
        "artifact_sha256_expected": expected_sha256 or None,
        "artifact_sha256_match": None if not expected_sha256 else generator_ckpt_sha256 == expected_sha256,
        "input_dir": str(input_dir),
        "output_dir": str(reconstructions_dir),
        "manifest_path": str(manifest_path),
        "output_count": len(records),
        "processed_count": len(records),
        "input_count": len(input_files),
        "available_input_count": len(all_input_files),
        "load_ms": round(model_load_ms, 3),
        "vm_init_ms": 0.0,
        "run_count": len(run_samples_ms),
        "run_samples_ms": [round(value, 3) for value in run_samples_ms],
        "run_median_ms": run_summary["median_ms"],
        "run_mean_ms": run_summary["mean_ms"],
        "run_min_ms": run_summary["min_ms"],
        "run_max_ms": run_summary["max_ms"],
        "run_variance_ms2": run_summary["variance_ms2"],
        "output_shape": records[-1]["output_shape"] if records else None,
        "output_dtype": "uint8" if records else None,
        "snr": args.snr,
        "batch_size": 1,
        "save_format": "png",
        "seed": args.seed,
        "max_inputs": args.max_images,
        "noise_mode": args.noise_mode,
        "device": str(device),
        **torch_thread_settings,
        **mkldnn_settings,
        "generator_ckpt": str(generator_ckpt),
        "origin_ckpt": None if origin_ckpt is None else str(origin_ckpt),
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def run_local_experimental_subprocess_worker(args: argparse.Namespace) -> None:
    if not args.local_experimental_subprocess_worker_input:
        raise SystemExit("ERROR: worker mode requires --local-experimental-subprocess-worker-input.")
    if not args.local_experimental_subprocess_worker_record:
        raise SystemExit("ERROR: worker mode requires --local-experimental-subprocess-worker-record.")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    mkldnn_settings = configure_mkldnn(args.local_disable_mkldnn)
    torch_thread_settings = configure_torch_threads(
        torch_num_threads=args.torch_num_threads,
        torch_num_interop_threads=args.torch_num_interop_threads,
    )

    jscc_root = Path(args.jscc_root)
    generator_ckpt = Path(args.generator_ckpt)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reconstructions_dir = output_dir / "reconstructions"
    input_path = Path(args.local_experimental_subprocess_worker_input)
    worker_record_path = Path(args.local_experimental_subprocess_worker_record)

    validate_common_paths(jscc_root, generator_ckpt, input_dir)
    if not input_path.is_file():
        raise SystemExit(f"ERROR: worker input not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reconstructions_dir.mkdir(parents=True, exist_ok=True)
    worker_record_path.parent.mkdir(parents=True, exist_ok=True)

    generator_ckpt_sha256 = file_sha256(generator_ckpt)
    expected_sha256 = resolve_expected_sha256(args.expected_sha256)
    if expected_sha256 and generator_ckpt_sha256 != expected_sha256:
        raise SystemExit(
            "ERROR: generator checkpoint sha256 mismatch "
            f"path={generator_ckpt} expected={expected_sha256} actual={generator_ckpt_sha256}"
        )

    device = torch.device(args.device)
    model_load_started = time.perf_counter()
    model, spec = load_generator(jscc_root, generator_ckpt, device)
    model_load_ms = (time.perf_counter() - model_load_started) * 1000.0

    with torch.inference_mode():
        record = reconstruct_single_input(
            model=model,
            device=device,
            input_path=input_path,
            reconstructions_dir=reconstructions_dir,
            snr=args.snr,
            noise_mode=args.noise_mode,
            seed=args.seed,
        )

    payload = {
        "status": "ok",
        "generator_ckpt_sha256": generator_ckpt_sha256,
        "worker_load_ms": round(model_load_ms, 3),
        "worker_torch_thread_settings": torch_thread_settings,
        "worker_mkldnn_settings": mkldnn_settings,
        "worker_device": str(device),
        "worker_inferred_model": spec,
        "record": record,
    }
    worker_record_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_local_experimental_worker_command(
    args: argparse.Namespace,
    input_path: Path,
    worker_record_path: Path,
) -> list[str]:
    helper_path = Path(__file__)
    if not helper_path.is_file():
        raise SystemExit(
            "ERROR: local experimental subprocess mode requires running this helper from a real file path."
        )

    command = [
        sys.executable,
        str(helper_path),
        "--jscc-root",
        args.jscc_root,
        "--generator-ckpt",
        args.generator_ckpt,
        "--input-dir",
        args.input_dir,
        "--output-dir",
        args.output_dir,
        "--snr",
        str(args.snr),
        "--noise-mode",
        args.noise_mode,
        "--seed",
        str(args.seed),
        "--device",
        args.device,
        "--torch-num-threads",
        str(args.torch_num_threads),
        "--torch-num-interop-threads",
        str(args.torch_num_interop_threads),
        "--manifest-name",
        args.manifest_name,
        "--variant",
        args.variant,
        "--log-level",
        args.log_level,
        "--local-experimental-subprocess-worker",
        "--local-experimental-subprocess-worker-input",
        str(input_path),
        "--local-experimental-subprocess-worker-record",
        str(worker_record_path),
    ]
    if args.local_disable_mkldnn:
        command.append("--local-disable-mkldnn")
    if args.origin_ckpt:
        command.extend(["--origin-ckpt", args.origin_ckpt])
    if args.expected_sha256:
        command.extend(["--expected-sha256", args.expected_sha256])
    return command


def run_local_experimental_subprocess_per_image(args: argparse.Namespace) -> None:
    jscc_root = Path(args.jscc_root)
    generator_ckpt = Path(args.generator_ckpt)
    origin_ckpt = Path(args.origin_ckpt) if args.origin_ckpt else None
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reconstructions_dir = output_dir / "reconstructions"
    manifest_path = output_dir / args.manifest_name
    worker_records_dir = output_dir / "local_experimental_subprocess_worker_records"

    validate_common_paths(jscc_root, generator_ckpt, input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    reconstructions_dir.mkdir(parents=True, exist_ok=True)
    worker_records_dir.mkdir(parents=True, exist_ok=True)

    all_input_files = collect_input_files(input_dir, 0)
    if not all_input_files:
        raise SystemExit(f"ERROR: no latent files found in {input_dir}")
    input_files = all_input_files[: args.max_images] if args.max_images > 0 else all_input_files

    generator_ckpt_sha256 = file_sha256(generator_ckpt)
    expected_sha256 = resolve_expected_sha256(args.expected_sha256)
    if expected_sha256 and generator_ckpt_sha256 != expected_sha256:
        raise SystemExit(
            "ERROR: generator checkpoint sha256 mismatch "
            f"path={generator_ckpt} expected={expected_sha256} actual={generator_ckpt_sha256}"
        )

    started_at = iso_timestamp()
    LOGGER.info(
        "Local-only experimental subprocess-per-image PyTorch reference run started: "
        "inputs=%s snr=%s noise_mode=%s output_dir=%s",
        len(input_files),
        args.snr,
        args.noise_mode,
        output_dir,
    )

    records: list[dict[str, Any]] = []
    run_samples_ms: list[float] = []
    worker_load_samples_ms: list[float] = []
    worker_compute_samples_ms: list[float] = []
    worker_metadata: dict[str, Any] | None = None

    wall_started = time.perf_counter()
    for index, input_path in enumerate(input_files, start=1):
        worker_record_path = worker_records_dir / f"{input_path.name}.json"
        if worker_record_path.exists():
            worker_record_path.unlink()

        command = build_local_experimental_worker_command(args, input_path, worker_record_path)
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if completed.returncode != 0:
            stdout_tail = "\n".join(completed.stdout.strip().splitlines()[-20:]) if completed.stdout else ""
            stderr_tail = "\n".join(completed.stderr.strip().splitlines()[-20:]) if completed.stderr else ""
            raise SystemExit(
                "ERROR: local experimental subprocess worker failed "
                f"input={input_path.name} exit_code={completed.returncode}\n"
                f"STDOUT (tail):\n{stdout_tail}\nSTDERR (tail):\n{stderr_tail}"
            )
        if not worker_record_path.is_file():
            raise SystemExit(
                "ERROR: local experimental subprocess worker did not write its record file "
                f"for {input_path.name}: {worker_record_path}"
            )

        payload = json.loads(worker_record_path.read_text(encoding="utf-8"))
        if payload.get("status") != "ok":
            raise SystemExit(
                "ERROR: local experimental subprocess worker returned a non-ok payload "
                f"for {input_path.name}: {payload!r}"
            )

        worker_record = dict(payload["record"])
        worker_record["subprocess_elapsed_ms"] = round(elapsed_ms, 3)
        worker_record["worker_load_ms"] = float(payload["worker_load_ms"])
        worker_record["worker_record_path"] = str(worker_record_path)
        records.append(worker_record)

        run_samples_ms.append(elapsed_ms)
        worker_load_samples_ms.append(float(payload["worker_load_ms"]))
        worker_compute_samples_ms.append(float(worker_record["elapsed_ms"]))

        if worker_metadata is None:
            worker_metadata = {
                "worker_torch_thread_settings": payload["worker_torch_thread_settings"],
                "worker_mkldnn_settings": payload["worker_mkldnn_settings"],
                "worker_device": payload["worker_device"],
                "worker_inferred_model": payload["worker_inferred_model"],
            }

        emit_progress(
            index=index,
            total=len(input_files),
            input_path=input_path,
            save_path=Path(worker_record["output_path"]),
            stage=LOCAL_EXPERIMENTAL_SUBPROCESS_STAGE,
        )

    total_wall_ms = (time.perf_counter() - wall_started) * 1000.0
    run_summary = summarize_samples(run_samples_ms)
    worker_load_summary = summarize_samples(worker_load_samples_ms)
    worker_compute_summary = summarize_samples(worker_compute_samples_ms)

    completed_at = iso_timestamp()
    manifest = {
        "run_type": "pytorch_reference_reconstruction",
        "execution_mode": LOCAL_EXPERIMENTAL_SUBPROCESS_MODE,
        "experimental_local_only": True,
        "started_at": started_at,
        "completed_at": completed_at,
        "jscc_root": str(jscc_root),
        "generator_ckpt": str(generator_ckpt),
        "generator_ckpt_sha256": generator_ckpt_sha256,
        "origin_ckpt": None if origin_ckpt is None else str(origin_ckpt),
        "origin_ckpt_sha256": None if origin_ckpt is None or not origin_ckpt.is_file() else file_sha256(origin_ckpt),
        "origin_ckpt_metadata": None if origin_ckpt is None else load_origin_checkpoint_metadata(origin_ckpt),
        "input_dir": str(input_dir),
        "input_count": len(input_files),
        "output_dir": str(output_dir),
        "reconstructions_dir": str(reconstructions_dir),
        "worker_records_dir": str(worker_records_dir),
        "output_count": len(records),
        "snr": args.snr,
        "noise_mode": args.noise_mode,
        "seed": args.seed,
        "device": worker_metadata["worker_device"] if worker_metadata else args.device,
        "torch_num_threads": (
            None
            if worker_metadata is None
            else worker_metadata["worker_torch_thread_settings"]["torch_num_threads"]
        ),
        "torch_num_interop_threads": (
            None
            if worker_metadata is None
            else worker_metadata["worker_torch_thread_settings"]["torch_num_interop_threads"]
        ),
        "local_disable_mkldnn": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["local_disable_mkldnn"]
        ),
        "mkldnn_backend_present": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_backend_present"]
        ),
        "mkldnn_available": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_available"]
        ),
        "mkldnn_enabled_before": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_enabled_before"]
        ),
        "mkldnn_enabled": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_enabled"]
        ),
        "inferred_model": None if worker_metadata is None else worker_metadata["worker_inferred_model"],
        "timing": {
            "total_ms": round(total_wall_ms, 3),
            "mean_ms": run_summary["mean_ms"],
            "worker_load_summary": worker_load_summary,
            "worker_compute_summary": worker_compute_summary,
        },
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Manifest written to %s", manifest_path)
    LOGGER.info("Completed %s/%s reference reconstructions", len(records), len(input_files))

    summary = {
        "variant": str(args.variant),
        "runtime": f"pytorch_reference_{LOCAL_EXPERIMENTAL_SUBPROCESS_MODE}",
        "execution_mode": LOCAL_EXPERIMENTAL_SUBPROCESS_MODE,
        "experimental_local_only": True,
        "artifact_path": str(generator_ckpt),
        "artifact_sha256": generator_ckpt_sha256,
        "artifact_sha256_expected": expected_sha256 or None,
        "artifact_sha256_match": None if not expected_sha256 else generator_ckpt_sha256 == expected_sha256,
        "input_dir": str(input_dir),
        "output_dir": str(reconstructions_dir),
        "manifest_path": str(manifest_path),
        "worker_records_dir": str(worker_records_dir),
        "output_count": len(records),
        "processed_count": len(records),
        "input_count": len(input_files),
        "available_input_count": len(all_input_files),
        "load_ms": 0.0,
        "vm_init_ms": 0.0,
        "run_count": len(run_samples_ms),
        "run_samples_ms": [round(value, 3) for value in run_samples_ms],
        "run_median_ms": run_summary["median_ms"],
        "run_mean_ms": run_summary["mean_ms"],
        "run_min_ms": run_summary["min_ms"],
        "run_max_ms": run_summary["max_ms"],
        "run_variance_ms2": run_summary["variance_ms2"],
        "worker_load_median_ms": worker_load_summary["median_ms"],
        "worker_load_mean_ms": worker_load_summary["mean_ms"],
        "worker_load_min_ms": worker_load_summary["min_ms"],
        "worker_load_max_ms": worker_load_summary["max_ms"],
        "worker_compute_median_ms": worker_compute_summary["median_ms"],
        "worker_compute_mean_ms": worker_compute_summary["mean_ms"],
        "worker_compute_min_ms": worker_compute_summary["min_ms"],
        "worker_compute_max_ms": worker_compute_summary["max_ms"],
        "output_shape": records[-1]["output_shape"] if records else None,
        "output_dtype": "uint8" if records else None,
        "snr": args.snr,
        "batch_size": 1,
        "save_format": "png",
        "seed": args.seed,
        "max_inputs": args.max_images,
        "noise_mode": args.noise_mode,
        "device": worker_metadata["worker_device"] if worker_metadata else args.device,
        "torch_num_threads": (
            None
            if worker_metadata is None
            else worker_metadata["worker_torch_thread_settings"]["torch_num_threads"]
        ),
        "torch_num_interop_threads": (
            None
            if worker_metadata is None
            else worker_metadata["worker_torch_thread_settings"]["torch_num_interop_threads"]
        ),
        "local_disable_mkldnn": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["local_disable_mkldnn"]
        ),
        "mkldnn_backend_present": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_backend_present"]
        ),
        "mkldnn_available": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_available"]
        ),
        "mkldnn_enabled_before": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_enabled_before"]
        ),
        "mkldnn_enabled": (
            None
            if worker_metadata is None
            else worker_metadata["worker_mkldnn_settings"]["mkldnn_enabled"]
        ),
        "generator_ckpt": str(generator_ckpt),
        "origin_ckpt": None if origin_ckpt is None else str(origin_ckpt),
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    if args.local_experimental_subprocess_worker:
        run_local_experimental_subprocess_worker(args)
        return
    if args.local_experimental_subprocess_per_image:
        run_local_experimental_subprocess_per_image(args)
        return
    run_single_process_reference(args)


if __name__ == "__main__":
    main()
