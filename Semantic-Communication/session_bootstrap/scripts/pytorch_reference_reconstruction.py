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


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    jscc_root = Path(args.jscc_root)
    generator_ckpt = Path(args.generator_ckpt)
    origin_ckpt = Path(args.origin_ckpt) if args.origin_ckpt else None
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reconstructions_dir = output_dir / "reconstructions"
    manifest_path = output_dir / args.manifest_name

    if not jscc_root.is_dir():
        raise SystemExit(f"ERROR: jscc root not found: {jscc_root}")
    if not generator_ckpt.is_file():
        raise SystemExit(f"ERROR: generator checkpoint not found: {generator_ckpt}")
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: input dir not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    reconstructions_dir.mkdir(parents=True, exist_ok=True)

    all_input_files = collect_input_files(input_dir, 0)
    if not all_input_files:
        raise SystemExit(f"ERROR: no latent files found in {input_dir}")
    input_files = all_input_files[: args.max_images] if args.max_images > 0 else all_input_files

    generator_ckpt_sha256 = file_sha256(generator_ckpt)
    expected_sha256 = str(args.expected_sha256 or "").strip().lower()
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
    total_elapsed_ms = 0.0
    run_samples_ms: list[float] = []

    with torch.inference_mode():
        for index, input_path in enumerate(input_files, start=1):
            base_name = input_path.stem.split("_latent")[0]
            sample_seed = per_file_seed(args.seed, str(input_path.name))
            started = time.perf_counter()
            latent, latent_meta = load_latent(input_path)
            if args.noise_mode == "awgn":
                model_input = awgn_channel(latent, args.snr, sample_seed)
            else:
                model_input = latent
            output = model(model_input.to(device))
            output_cpu = output.detach().cpu()
            save_path = reconstructions_dir / f"{base_name}_recon.png"
            save_png(output_cpu, save_path)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            total_elapsed_ms += elapsed_ms
            run_samples_ms.append(elapsed_ms)
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
            records.append(
                {
                    "input_path": str(input_path),
                    "input_sha256": file_sha256(input_path),
                    "base_name": base_name,
                    "sample_seed": sample_seed,
                    "noise_mode": args.noise_mode,
                    "snr": args.snr,
                    "latent_shape": list(latent.shape),
                    "output_shape": list(output_cpu.shape),
                    "output_range": [output_min, output_max],
                    "elapsed_ms": round(elapsed_ms, 3),
                    "output_path": str(save_path),
                    "output_sha256": file_sha256(save_path),
                    "latent_metadata": json_ready(latent_meta),
                }
            )
            print(
                json.dumps(
                    {
                        "openamp_demo_progress": {
                            "completed_count": index,
                            "expected_count": len(input_files),
                            "remaining_count": max(len(input_files) - index, 0),
                            "completion_ratio": round(index / len(input_files), 4) if input_files else 0.0,
                            "current_stage": "PyTorch reconstruction",
                            "sample": input_path.name,
                            "output_path": str(save_path),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    completed_at = iso_timestamp()
    manifest = {
        "run_type": "pytorch_reference_reconstruction",
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
        "inferred_model": spec,
        "timing": {
            "total_ms": round(total_elapsed_ms, 3),
            "mean_ms": round(total_elapsed_ms / len(records), 3) if records else None,
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
        "run_median_ms": round(statistics.median(run_samples_ms), 3) if run_samples_ms else None,
        "run_mean_ms": round(sum(run_samples_ms) / len(run_samples_ms), 3) if run_samples_ms else None,
        "run_min_ms": round(min(run_samples_ms), 3) if run_samples_ms else None,
        "run_max_ms": round(max(run_samples_ms), 3) if run_samples_ms else None,
        "run_variance_ms2": round(statistics.pvariance(run_samples_ms), 6) if len(run_samples_ms) > 1 else 0.0,
        "output_shape": records[-1]["output_shape"] if records else None,
        "output_dtype": "uint8" if records else None,
        "snr": args.snr,
        "batch_size": 1,
        "save_format": "png",
        "seed": args.seed,
        "max_inputs": args.max_images,
        "noise_mode": args.noise_mode,
        "device": str(device),
        "generator_ckpt": str(generator_ckpt),
        "origin_ckpt": None if origin_ckpt is None else str(origin_ckpt),
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
