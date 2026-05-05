#!/usr/bin/env python3
import argparse
import glob
import hashlib
import json
import logging
import os
import runpy
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import tvm
from tvm import relax


def import_torch_with_fallback():
    try:
        import torch as torch_mod
        return torch_mod
    except ImportError:
        extra_pythonpath = (
            os.environ.get("REMOTE_TORCH_PYTHONPATH")
            or os.environ.get("REMOTE_REAL_EXTRA_PYTHONPATH")
            or os.environ.get("DEMO_EXTRA_PYTHONPATH")
            or ""
        )
        candidates = [entry for entry in extra_pythonpath.split(":") if entry]
        added = False
        for entry in reversed(candidates):
            if entry not in sys.path:
                sys.path.insert(0, entry)
                added = True
        if added:
            try:
                import torch as torch_mod
                return torch_mod
            except ImportError:
                pass
        return None


torch = import_torch_with_fallback()

try:
    from PIL import Image
except ImportError:
    Image = None


LOGGER = logging.getLogger("current_real_reconstruction")
SUPPORTED_INPUT_PATTERNS = ("*.pt", "*.npz", "*.npy")


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run current-style real reconstruction over latent inputs and emit benchmark-compatible timing logs."
    )
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--snr", type=float, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--variant", default="current")
    parser.add_argument(
        "--input-source-mode",
        default="prerecorded",
        choices=("prerecorded", "usrp"),
        help="输入来源模式：预录目录或 USRP RX 目录。",
    )
    parser.add_argument(
        "--input-source-label",
        default="",
        help="输入来源标签，供日志和 summary 标注。",
    )
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument(
        "--max-inputs",
        type=int,
        default=0,
        help="Optional cap on the number of latent files to process. 0 means all.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional numpy random seed.")
    parser.add_argument(
        "--profile-ops",
        action="store_true",
        help="Attempt vm.profile on the first profiled samples.",
    )
    parser.add_argument(
        "--profile-samples",
        type=int,
        default=1,
        help="How many samples should attempt vm.profile when --profile-ops is enabled.",
    )
    args = parser.parse_args()
    if args.max_inputs < 0:
        raise SystemExit(f"ERROR: --max-inputs must be >= 0 (got: {args.max_inputs})")
    if args.profile_samples < 0:
        raise SystemExit(f"ERROR: --profile-samples must be >= 0 (got: {args.profile_samples})")
    return args


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_tensor(array: np.ndarray, dev):
    runtime = getattr(tvm, "runtime", None)
    runtime_tensor_fn = getattr(runtime, "tensor", None) if runtime is not None else None
    if runtime_tensor_fn is None and runtime is not None:
        runtime_ndarray = getattr(runtime, "ndarray", None)
        if runtime_ndarray is not None:
            runtime_tensor_fn = lambda arr, device: runtime_ndarray.array(arr, device)
    if runtime_tensor_fn is None:
        raise AttributeError("module tvm.runtime has neither tensor nor ndarray.array")
    return runtime_tensor_fn(array, dev)


def ensure_batched_latent(latent: np.ndarray) -> np.ndarray:
    latent = np.asarray(latent, dtype=np.float32)
    if latent.ndim == 3:
        latent = np.expand_dims(latent, axis=0)
    if latent.ndim != 4:
        raise ValueError(f"expected latent with 3 or 4 dims, got shape={latent.shape}")
    return latent


def load_pt_quantized(path: Path) -> np.ndarray:
    if torch is None:
        raise RuntimeError(f"torch is required to load .pt latent inputs: {path}")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    required_keys = {"quant", "scale", "zero_point"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        raise KeyError(f"{path} is missing required keys: {sorted(required_keys)}")
    quant = np.asarray(payload["quant"], dtype=np.float32)
    scale = np.asarray(payload["scale"], dtype=np.float32)
    zero_point = np.asarray(payload["zero_point"], dtype=np.float32)
    latent = (quant - zero_point) * scale
    return ensure_batched_latent(latent)


def load_npz_latent(path: Path) -> np.ndarray:
    with np.load(path) as payload:
        if "latent" in payload:
            return ensure_batched_latent(payload["latent"])
        required_keys = {"quant", "scale", "zero_point"}
        if not required_keys.issubset(payload.files):
            raise KeyError(f"{path} is missing required keys: {sorted(required_keys)}")
        quant = np.asarray(payload["quant"], dtype=np.float32)
        scale = np.asarray(payload["scale"], dtype=np.float32)
        zero_point = np.asarray(payload["zero_point"], dtype=np.float32)
        latent = (quant - zero_point) * scale
        return ensure_batched_latent(latent)


def load_latent(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix == ".pt":
        return load_pt_quantized(path)
    if suffix == ".npz":
        return load_npz_latent(path)
    if suffix == ".npy":
        return ensure_batched_latent(np.load(path))
    raise ValueError(f"unsupported input file type: {path}")


def awgn_channel(latent: np.ndarray, snr: float) -> np.ndarray:
    latent = np.asarray(latent, dtype=np.float32)
    power = np.mean(np.square(latent), axis=(-3, -2, -1), keepdims=True) * 2.0
    noise_power = power * (10.0 ** (-snr / 10.0))
    noise = np.sqrt(noise_power / 2.0) * np.random.standard_normal(latent.shape).astype(np.float32)
    return latent + noise


def normalize_image(output: np.ndarray) -> np.ndarray:
    array = np.asarray(output)
    if array.ndim == 4 and array.shape[0] == 1:
        array = array[0]
    if array.ndim == 3 and array.shape[0] in (1, 3, 4):
        array = np.transpose(array, (1, 2, 0))
    if array.ndim == 3 and array.shape[-1] == 1:
        array = array[:, :, 0]
    if array.ndim not in (2, 3):
        raise ValueError(f"cannot convert output with shape={array.shape} to image")
    array = np.clip(array, 0.0, 1.0)
    return (array * 255.0 + 0.5).astype(np.uint8)


def save_reconstruction(output: np.ndarray, output_stem: Path) -> Path:
    if Image is not None:
        image_array = normalize_image(output)
        save_path = output_stem.with_suffix(".png")
        Image.fromarray(image_array).save(save_path, format="PNG")
        return save_path
    save_path = output_stem.with_suffix(".npy")
    np.save(save_path, np.asarray(output))
    return save_path


def collect_input_files(input_dir: Path) -> list[Path]:
    input_files: list[Path] = []
    for pattern in SUPPORTED_INPUT_PATTERNS:
        input_files.extend(Path(path) for path in glob.glob(str(input_dir / pattern)))
    return sorted({path.resolve(): path for path in input_files}.values())


def resolve_effective_input_dir(input_dir: Path, input_source_mode: str) -> Path:
    if input_source_mode != "usrp":
        return input_dir
    if not input_dir.is_dir():
        return input_dir
    if collect_input_files(input_dir):
        return input_dir

    candidate_dirs = [path for path in input_dir.iterdir() if path.is_dir()]
    candidate_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidate_dirs:
        if collect_input_files(candidate):
            return candidate
    return input_dir


def _normalized_key(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _parse_numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def _find_row_value(row, *candidate_keys):
    normalized = {_normalized_key(key): value for key, value in row.items()}
    for key in candidate_keys:
        if key in normalized:
            return normalized[key]
    return None


def _iter_dict_lists(payload):
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            yield payload
        for item in payload:
            yield from _iter_dict_lists(item)
        return
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_dict_lists(value)


def _score_profile_rows(rows) -> int:
    score = 0
    for row in rows[: min(len(rows), 10)]:
        keyset = {_normalized_key(key) for key in row}
        if keyset & {"name", "op", "operator", "opname", "funcname"}:
            score += 2
        if any("duration" in key or key.endswith("us") or key.endswith("ms") for key in keyset):
            score += 2
        if "percent" in keyset or "percentage" in keyset:
            score += 1
    return score


def _normalize_profile_rows(payload):
    best_rows = None
    best_score = -1
    for rows in _iter_dict_lists(payload):
        score = _score_profile_rows(rows)
        if score > best_score:
            best_score = score
            best_rows = rows

    if not best_rows:
        return []

    normalized_rows = []
    for row in best_rows:
        name = _find_row_value(row, "name", "opname", "operator", "op", "funcname", "hash")
        if name in (None, ""):
            continue

        duration_us = None
        raw_duration = None
        for key, scale in (
            ("durationus", 1.0),
            ("timingus", 1.0),
            ("durationms", 1000.0),
            ("timingms", 1000.0),
            ("durationns", 0.001),
            ("timingns", 0.001),
            ("duration", 1.0),
            ("time", 1.0),
        ):
            value = _find_row_value(row, key)
            numeric = _parse_numeric(value)
            if numeric is not None:
                raw_duration = numeric
                duration_us = numeric * scale
                break

        percent = _parse_numeric(_find_row_value(row, "percent", "percentage"))
        count = _parse_numeric(_find_row_value(row, "count", "calls", "numcalls"))
        device = _find_row_value(row, "device", "devicetype")
        normalized_rows.append(
            {
                "name": str(name),
                "duration_us": None if duration_us is None else round(duration_us, 3),
                "percent": None if percent is None else round(percent, 3),
                "count": None if count is None else int(count),
                "device": None if device in (None, "") else str(device),
                "raw_duration": raw_duration,
            }
        )

    normalized_rows = [row for row in normalized_rows if row["duration_us"] is not None or row["percent"] is not None]
    normalized_rows.sort(
        key=lambda row: (
            -1.0 if row["duration_us"] is None else -row["duration_us"],
            row["name"],
        )
    )

    total_duration_us = sum(row["duration_us"] or 0.0 for row in normalized_rows)
    if total_duration_us > 0.0:
        for row in normalized_rows:
            if row["percent"] is None and row["duration_us"] is not None:
                row["percent"] = round((row["duration_us"] / total_duration_us) * 100.0, 3)
    for row in normalized_rows:
        row.pop("raw_duration", None)
    return normalized_rows


def serialize_profile_report(report):
    report_text = ""
    report_json = None
    report_json_text = None
    json_error = None
    table_error = None

    if hasattr(report, "json"):
        try:
            raw_json = report.json()
            if isinstance(raw_json, str):
                report_json_text = raw_json
                report_json = json.loads(raw_json)
            else:
                report_json = raw_json
                report_json_text = json.dumps(raw_json, ensure_ascii=False)
        except Exception as err:  # pragma: no cover - depends on TVM runtime support.
            json_error = f"{type(err).__name__}: {err}"

    if hasattr(report, "table"):
        try:
            report_text = report.table()
        except Exception as err:  # pragma: no cover - depends on TVM runtime support.
            table_error = f"{type(err).__name__}: {err}"

    if not report_text:
        report_text = str(report)

    return {
        "report_text": report_text,
        "report_json": report_json,
        "report_json_text": report_json_text,
        "report_json_error": json_error,
        "report_table_error": table_error,
        "rows": _normalize_profile_rows(report_json) if report_json is not None else [],
    }


def attempt_vm_profile(vm, noisy: np.ndarray, dev, input_file: str):
    result = {
        "input_file": input_file,
        "requested": True,
        "supported": None,
        "status": "not_attempted",
        "api_call": None,
        "attempts": [],
    }

    if not hasattr(vm, "profile"):
        result.update(
            {
                "supported": False,
                "status": "unsupported",
                "error": "relax.VirtualMachine has no profile attribute",
            }
        )
        return result

    runtime_input = runtime_tensor(noisy.astype(np.float32), dev)
    attempts = [
        ("vm.profile('main', input)", lambda: vm.profile("main", runtime_input)),
        ("vm.profile(input)", lambda: vm.profile(runtime_input)),
    ]
    for call_name, callback in attempts:
        started = time.perf_counter()
        try:
            report = callback()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            serialized = serialize_profile_report(report)
            result.update(
                {
                    "supported": True,
                    "status": "profiled" if serialized["rows"] else "profiled_raw",
                    "api_call": call_name,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "rows": serialized["rows"],
                    "report_text": serialized["report_text"],
                    "report_json": serialized["report_json"],
                    "report_json_text": serialized["report_json_text"],
                    "report_json_error": serialized["report_json_error"],
                    "report_table_error": serialized["report_table_error"],
                }
            )
            result["attempts"].append(
                {
                    "call": call_name,
                    "status": "ok",
                    "elapsed_ms": round(elapsed_ms, 3),
                }
            )
            return result
        except TypeError as err:
            result["attempts"].append(
                {
                    "call": call_name,
                    "status": "type_error",
                    "error": str(err),
                }
            )
            continue
        except Exception as err:  # pragma: no cover - runtime dependent.
            result["attempts"].append(
                {
                    "call": call_name,
                    "status": "error",
                    "error": f"{type(err).__name__}: {err}",
                }
            )
            result.update(
                {
                    "supported": False,
                    "status": "error",
                    "api_call": call_name,
                    "error": f"{type(err).__name__}: {err}",
                }
            )
            return result

    result.update(
        {
            "supported": False,
            "status": "unsupported",
            "error": "all vm.profile signature attempts failed",
        }
    )
    return result


def aggregate_runtime_profiles(profile_results):
    successful = [
        sample
        for sample in profile_results
        if sample.get("status") in {"profiled", "profiled_raw"} and sample.get("rows")
    ]
    if not successful:
        return []

    aggregate = {}
    for sample in successful:
        for row in sample["rows"]:
            bucket = aggregate.setdefault(
                row["name"],
                {
                    "name": row["name"],
                    "durations_us": [],
                    "percents": [],
                    "counts": [],
                    "devices": set(),
                },
            )
            if row.get("duration_us") is not None:
                bucket["durations_us"].append(row["duration_us"])
            if row.get("percent") is not None:
                bucket["percents"].append(row["percent"])
            if row.get("count") is not None:
                bucket["counts"].append(row["count"])
            if row.get("device"):
                bucket["devices"].add(row["device"])

    rows = []
    for bucket in aggregate.values():
        mean_duration_us = (
            round(sum(bucket["durations_us"]) / len(bucket["durations_us"]), 3)
            if bucket["durations_us"]
            else None
        )
        mean_percent = (
            round(sum(bucket["percents"]) / len(bucket["percents"]), 3)
            if bucket["percents"]
            else None
        )
        mean_count = (
            round(sum(bucket["counts"]) / len(bucket["counts"]), 3)
            if bucket["counts"]
            else None
        )
        rows.append(
            {
                "name": bucket["name"],
                "mean_duration_us": mean_duration_us,
                "mean_percent": mean_percent,
                "mean_count": mean_count,
                "devices": sorted(bucket["devices"]),
                "samples": max(
                    len(bucket["durations_us"]),
                    len(bucket["percents"]),
                    len(bucket["counts"]),
                    0,
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            -1.0 if row["mean_duration_us"] is None else -row["mean_duration_us"],
            row["name"],
        )
    )

    total_duration_us = sum(row["mean_duration_us"] or 0.0 for row in rows)
    if total_duration_us > 0.0:
        for row in rows:
            if row["mean_percent"] is None and row["mean_duration_us"] is not None:
                row["mean_percent"] = round((row["mean_duration_us"] / total_duration_us) * 100.0, 3)
    return rows


def build_summary(
    args,
    artifact_path: Path,
    artifact_sha256: str,
    load_ms: float,
    vm_init_ms: float,
    run_samples_ms,
    processed_count: int,
    selected_input_count: int,
    available_input_count: int,
    reconstructions_dir: Path,
    output_dtype: str,
    output_shape,
    runtime_profiles,
    requested_input_dir: Path,
    resolved_input_dir: Path,
):
    aggregated_profiles = aggregate_runtime_profiles(runtime_profiles)
    runtime_profile_status = "not_requested"
    runtime_profile_supported = None
    if args.profile_ops:
        if any(sample.get("status") == "profiled" for sample in runtime_profiles):
            runtime_profile_status = "profiled"
            runtime_profile_supported = True
        elif any(sample.get("status") == "profiled_raw" for sample in runtime_profiles):
            runtime_profile_status = "profiled_raw"
            runtime_profile_supported = True
        elif runtime_profiles:
            runtime_profile_status = "unsupported"
            runtime_profile_supported = False
        else:
            runtime_profile_status = "requested_but_skipped"
            runtime_profile_supported = None

    summary = {
        "variant": args.variant,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_sha256_expected": args.expected_sha256 or None,
        "artifact_sha256_match": None
        if not args.expected_sha256
        else artifact_sha256 == args.expected_sha256.lower(),
        "input_source_mode": args.input_source_mode,
        "input_source_label": args.input_source_label or args.input_source_mode,
        "requested_input_dir": str(requested_input_dir),
        "resolved_input_dir": str(resolved_input_dir),
        "input_dir": str(resolved_input_dir),
        "output_dir": str(reconstructions_dir),
        "output_count": len(list(reconstructions_dir.glob("*"))),
        "processed_count": processed_count,
        "input_count": selected_input_count,
        "available_input_count": available_input_count,
        "load_ms": round(load_ms, 3),
        "vm_init_ms": round(vm_init_ms, 3),
        "run_count": len(run_samples_ms),
        "run_samples_ms": [round(value, 3) for value in run_samples_ms],
        "run_median_ms": round(statistics.median(run_samples_ms), 3) if run_samples_ms else None,
        "run_mean_ms": round(sum(run_samples_ms) / len(run_samples_ms), 3) if run_samples_ms else None,
        "run_min_ms": round(min(run_samples_ms), 3) if run_samples_ms else None,
        "run_max_ms": round(max(run_samples_ms), 3) if run_samples_ms else None,
        "run_variance_ms2": round(statistics.pvariance(run_samples_ms), 6) if len(run_samples_ms) > 1 else 0.0,
        "output_shape": output_shape,
        "output_dtype": output_dtype,
        "snr": args.snr,
        "batch_size": args.batch_size,
        "save_format": "png" if Image is not None else "npy",
        "seed": args.seed,
        "max_inputs": args.max_inputs,
        "runtime_profiling": {
            "requested": args.profile_ops,
            "profile_samples_requested": args.profile_samples if args.profile_ops else 0,
            "attempted_samples": len(runtime_profiles),
            "successful_samples": sum(
                1 for sample in runtime_profiles if sample.get("status") in {"profiled", "profiled_raw"}
            ),
            "supported": runtime_profile_supported,
            "status": runtime_profile_status,
            "top_ops": aggregated_profiles[:10],
            "sample_results": runtime_profiles,
        },
    }
    return summary


def main():
    configure_logging()
    args = parse_args()

    if args.seed is not None:
        np.random.seed(args.seed)

    artifact_path = Path(args.artifact_path)
    requested_input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    reconstructions_dir = output_dir / "reconstructions"

    if not artifact_path.is_file():
        raise SystemExit(f"ERROR: artifact not found: {artifact_path}")
    if not requested_input_dir.is_dir():
        raise SystemExit(f"ERROR: input dir not found: {requested_input_dir}")

    input_dir = resolve_effective_input_dir(requested_input_dir, args.input_source_mode)
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: resolved input dir not found: {input_dir}")
    LOGGER.info(
        "输入模式: %s (%s), 请求目录=%s, 实际目录=%s",
        args.input_source_mode,
        args.input_source_label or args.input_source_mode,
        requested_input_dir,
        input_dir,
    )

    expected_sha256 = args.expected_sha256.strip().lower()
    artifact_sha256 = file_sha256(artifact_path)
    if expected_sha256 and artifact_sha256 != expected_sha256:
        raise SystemExit(
            "ERROR: artifact sha256 mismatch "
            f"path={artifact_path} expected={expected_sha256} actual={artifact_sha256}"
        )

    reconstructions_dir.mkdir(parents=True, exist_ok=True)

    input_files = collect_input_files(input_dir)
    if not input_files:
        raise SystemExit(
            f"ERROR: no supported latent files found in {input_dir} (mode={args.input_source_mode})"
        )
    available_input_count = len(input_files)
    if args.max_inputs:
        input_files = input_files[: args.max_inputs]

    dev = tvm.cpu(0)
    preload_py = os.environ.get("TVM_RUNTIME_PRELOAD_PY", "").strip()
    if preload_py:
        LOGGER.info("运行时预加载脚本: %s", preload_py)
        runpy.run_path(preload_py, run_name="__main__")
    load_t0 = time.perf_counter()
    lib = tvm.runtime.load_module(str(artifact_path))
    load_t1 = time.perf_counter()
    vm = relax.VirtualMachine(lib, dev, profile=bool(args.profile_ops))
    load_t2 = time.perf_counter()
    fn = vm["main"]
    LOGGER.info("TVM 模型加载成功")

    run_samples_ms = []
    processed_count = 0
    last_output = None
    runtime_profiles = []

    for input_path in input_files:
        base_name = input_path.stem.split("_latent")[0]
        try:
            sample_t0 = time.perf_counter()
            latent = load_latent(input_path)
            noisy = awgn_channel(latent, args.snr).astype(np.float32)
            output = fn(runtime_tensor(noisy, dev))
            output_np = output.numpy() if hasattr(output, "numpy") else np.asarray(output)
            save_path = save_reconstruction(output_np, reconstructions_dir / f"{base_name}_recon")
            sample_t1 = time.perf_counter()
            elapsed_ms = (sample_t1 - sample_t0) * 1000.0
            LOGGER.info("批量推理时间（1 个样本）: %.6f 秒", elapsed_ms / 1000.0)
            LOGGER.info("重构图像保存至: %s", save_path)
            run_samples_ms.append(elapsed_ms)
            processed_count += 1
            print(
                json.dumps(
                    {
                        "openamp_demo_progress": {
                            "delta": 1,
                            "completed_count": processed_count,
                            "input_path": str(input_path),
                            "output_path": str(save_path),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            last_output = output_np
            if args.profile_ops and len(runtime_profiles) < args.profile_samples:
                runtime_profiles.append(
                    attempt_vm_profile(
                        vm=vm,
                        noisy=noisy,
                        dev=dev,
                        input_file=input_path.name,
                    )
                )
        except Exception as err:  # pragma: no cover - exercised through runtime smoke.
            LOGGER.error("处理文件失败 %s: %s", input_path, err)

    LOGGER.info("处理完成: %s/%s 文件成功", processed_count, len(input_files))

    output_shape = None
    output_dtype = None
    if last_output is not None:
        output_shape = list(np.asarray(last_output).shape)
        output_dtype = str(np.asarray(last_output).dtype)

    summary = build_summary(
        args=args,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        load_ms=(load_t1 - load_t0) * 1000.0,
        vm_init_ms=(load_t2 - load_t1) * 1000.0,
        run_samples_ms=run_samples_ms,
        processed_count=processed_count,
        selected_input_count=len(input_files),
        available_input_count=available_input_count,
        reconstructions_dir=reconstructions_dir,
        output_dtype=output_dtype,
        output_shape=output_shape,
        runtime_profiles=runtime_profiles,
        requested_input_dir=requested_input_dir,
        resolved_input_dir=input_dir,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
