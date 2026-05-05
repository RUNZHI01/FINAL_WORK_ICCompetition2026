#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import multiprocessing as mp
import os
import queue
import runpy
import statistics
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np


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
        for entry in reversed(candidates):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        try:
            import torch as torch_mod

            return torch_mod
        except ImportError:
            return None


torch = import_torch_with_fallback()

try:
    from PIL import Image
except ImportError:
    Image = None


LOGGER = logging.getLogger("big_little_pipeline")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def emit_demo_progress(*, completed_count: int, expected_count: int, input_path: str = "", output_path: str = "") -> None:
    print(
        json.dumps(
            {
                "openamp_demo_progress": {
                    "delta": 1,
                    "completed_count": completed_count,
                    "expected_count": expected_count,
                    "input_path": input_path,
                    "output_path": output_path,
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a big.LITTLE-style heterogeneous pipeline where small-core roles "
            "preload latents and save outputs while big-core roles run TVM inference."
        )
    )
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--snr", type=float, required=True)
    parser.add_argument("--batch-size", type=int, required=True)
    parser.add_argument("--variant", default="current")
    parser.add_argument("--execution-mode", choices=("pipeline", "serial"), default="pipeline")
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument("--max-inputs", type=int, default=0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--big-cores", default="")
    parser.add_argument("--little-cores", default="")
    parser.add_argument("--allow-missing-affinity", action="store_true")
    parser.add_argument("--input-queue-size", type=int, default=4)
    parser.add_argument("--output-queue-size", type=int, default=4)
    parser.add_argument("--backend", choices=("processes", "threads"), default="processes")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-infer-ms", type=float, default=15.0)
    parser.add_argument("--summary-json", default="")
    parser.add_argument("--summary-md", default="")
    args = parser.parse_args()
    if args.max_inputs < 0:
        raise SystemExit(f"ERROR: --max-inputs must be >= 0 (got: {args.max_inputs})")
    if args.input_queue_size <= 0:
        raise SystemExit(f"ERROR: --input-queue-size must be > 0 (got: {args.input_queue_size})")
    if args.output_queue_size <= 0:
        raise SystemExit(f"ERROR: --output-queue-size must be > 0 (got: {args.output_queue_size})")
    if args.mock_infer_ms < 0:
        raise SystemExit(f"ERROR: --mock-infer-ms must be >= 0 (got: {args.mock_infer_ms})")
    return args


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_batched_latent(latent: np.ndarray) -> np.ndarray:
    latent = np.asarray(latent, dtype=np.float32)
    if latent.ndim == 3:
        latent = np.expand_dims(latent, axis=0)
    if latent.ndim != 4:
        raise ValueError(f"expected latent with 3 or 4 dims, got shape={latent.shape}")
    return latent


def load_torch_payload(path: Path) -> Any:
    if torch is None:
        raise RuntimeError(f"torch is required to load .pt latent inputs: {path}")
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        return torch.load(path, map_location="cpu")


def load_pt_quantized(path: Path) -> np.ndarray:
    payload = load_torch_payload(path)
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


def awgn_channel(latent: np.ndarray, snr: float, rng: np.random.Generator) -> np.ndarray:
    latent = np.asarray(latent, dtype=np.float32)
    power = np.mean(np.square(latent), axis=(-3, -2, -1), keepdims=True) * 2.0
    noise_power = power * (10.0 ** (-snr / 10.0))
    noise = np.sqrt(noise_power / 2.0) * rng.standard_normal(latent.shape).astype(np.float32)
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


def runtime_tensor(array: np.ndarray, dev):
    import tvm  # pylint: disable=import-error

    runtime = getattr(tvm, "runtime", None)
    runtime_tensor_fn = getattr(runtime, "tensor", None) if runtime is not None else None
    if runtime_tensor_fn is None and runtime is not None:
        runtime_ndarray = getattr(runtime, "ndarray", None)
        if runtime_ndarray is not None:
            runtime_tensor_fn = lambda arr, device: runtime_ndarray.array(arr, device)
    if runtime_tensor_fn is None:
        raise AttributeError("module tvm.runtime has neither tensor nor ndarray.array")
    return runtime_tensor_fn(array, dev)


def maybe_run_runtime_preload() -> str | None:
    preload_py = os.environ.get("TVM_RUNTIME_PRELOAD_PY", "").strip()
    if not preload_py:
        return None
    LOGGER.info("running runtime preload: %s", preload_py)
    runpy.run_path(preload_py, run_name="__main__")
    return preload_py


def parse_cpu_list(raw: str) -> list[int]:
    text = raw.strip()
    if not text:
        return []
    cpus: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = int(start_raw.strip())
            end = int(end_raw.strip())
            if end < start:
                raise ValueError(f"invalid CPU range: {token}")
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(token))
    return sorted(cpus)


def safe_sched_getaffinity() -> list[int] | None:
    if not hasattr(os, "sched_getaffinity"):
        return None
    try:
        return sorted(int(cpu) for cpu in os.sched_getaffinity(0))
    except OSError:
        return None


def apply_affinity(role: str, cpus: list[int], allow_missing: bool, backend: str) -> dict[str, Any]:
    before = safe_sched_getaffinity()
    result: dict[str, Any] = {
        "role": role,
        "requested": list(cpus),
        "before": before,
        "after": before,
        "status": "skipped" if not cpus else "pending",
        "error": None,
    }
    if not cpus:
        return result
    if backend == "threads":
        message = "per-role affinity is unavailable with thread backend"
        if allow_missing:
            result["status"] = "unsupported_thread_backend"
            result["error"] = message
            return result
        raise OSError(message)
    if not hasattr(os, "sched_setaffinity"):
        message = "os.sched_setaffinity is unavailable on this platform"
        if allow_missing:
            result["status"] = "unsupported_ignored"
            result["error"] = message
            return result
        raise OSError(message)
    try:
        os.sched_setaffinity(0, set(cpus))
        after = safe_sched_getaffinity()
        result["after"] = after
        if after is not None and set(after) != set(cpus):
            result["status"] = "partial"
            result["error"] = f"requested={cpus} applied={after}"
        else:
            result["status"] = "applied"
        return result
    except OSError as err:
        if allow_missing:
            result["status"] = "failed_ignored"
            result["error"] = f"{type(err).__name__}: {err}"
            return result
        raise


def summarize_samples(samples: list[float]) -> dict[str, Any]:
    if not samples:
        return {"count": 0, "median_ms": None, "mean_ms": None, "min_ms": None, "max_ms": None, "variance_ms2": 0.0}
    return {
        "count": len(samples),
        "median_ms": round(statistics.median(samples), 3),
        "mean_ms": round(sum(samples) / len(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "variance_ms2": round(statistics.pvariance(samples), 6) if len(samples) > 1 else 0.0,
    }


def collect_input_files(input_dir: Path, max_inputs: int) -> tuple[list[Path], int]:
    input_patterns = ("*.pt", "*.npz", "*.npy")
    input_files: list[Path] = []
    for pattern in input_patterns:
        input_files.extend(Path(path) for path in glob.glob(str(input_dir / pattern)))
    unique_files = sorted({path.resolve(): path for path in input_files}.values())
    available_count = len(unique_files)
    if max_inputs:
        unique_files = unique_files[:max_inputs]
    return unique_files, available_count


def mock_infer(noisy: np.ndarray, sleep_ms: float) -> np.ndarray:
    if sleep_ms > 0:
        time.sleep(sleep_ms / 1000.0)
    output = np.asarray(noisy, dtype=np.float32)
    if output.ndim != 4:
        raise ValueError(f"expected noisy latent with 4 dims, got shape={output.shape}")
    if output.shape[1] < 3:
        repeats = (3 + output.shape[1] - 1) // output.shape[1]
        output = np.tile(output, (1, repeats, 1, 1))
    output = output[:, :3, :, :]
    output = output - np.min(output)
    max_value = np.max(output)
    if max_value > 0:
        output = output / max_value
    return output.astype(np.float32)


def preloader_worker(
    input_files: list[str],
    snr: float,
    seed: int | None,
    little_cores: list[int],
    allow_missing_affinity: bool,
    backend: str,
    input_queue,
    stats_queue,
) -> None:
    result: dict[str, Any] = {"role": "preloader", "status": "ok"}
    try:
        result["affinity"] = apply_affinity("preloader", little_cores, allow_missing_affinity, backend)
        rng = np.random.default_rng(seed)
        load_samples_ms: list[float] = []
        awgn_samples_ms: list[float] = []
        queued = 0
        for index, raw_path in enumerate(input_files):
            input_path = Path(raw_path)
            base_name = input_path.stem.split("_latent")[0]
            load_t0 = time.perf_counter()
            latent = load_latent(input_path)
            load_t1 = time.perf_counter()
            noisy = awgn_channel(latent, snr=snr, rng=rng).astype(np.float32)
            load_t2 = time.perf_counter()
            input_queue.put(
                {
                    "index": index,
                    "input_file": input_path.name,
                    "base_name": base_name,
                    "noisy": noisy,
                }
            )
            load_samples_ms.append((load_t1 - load_t0) * 1000.0)
            awgn_samples_ms.append((load_t2 - load_t1) * 1000.0)
            queued += 1
        input_queue.put(None)
        result.update(
            {
                "queued_count": queued,
                "load_samples_ms": [round(value, 3) for value in load_samples_ms],
                "awgn_samples_ms": [round(value, 3) for value in awgn_samples_ms],
                "load_summary": summarize_samples(load_samples_ms),
                "awgn_summary": summarize_samples(awgn_samples_ms),
            }
        )
    except Exception as err:  # pragma: no cover - error path exercised through wrapper failures.
        result.update(
            {
                "status": "error",
                "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(),
            }
        )
        try:
            input_queue.put(None)
        except Exception:
            pass
    finally:
        stats_queue.put(result)


def inferencer_worker(
    artifact_path_raw: str,
    expected_sha256: str,
    dry_run: bool,
    mock_infer_ms: float,
    big_cores: list[int],
    allow_missing_affinity: bool,
    backend: str,
    input_queue,
    output_queue,
    stats_queue,
) -> None:
    result: dict[str, Any] = {"role": "inferencer", "status": "ok"}
    try:
        result["affinity"] = apply_affinity("inferencer", big_cores, allow_missing_affinity, backend)
        artifact_path = Path(artifact_path_raw)
        artifact_sha256 = file_sha256(artifact_path) if artifact_path.is_file() else None
        if expected_sha256 and artifact_sha256 and artifact_sha256 != expected_sha256:
            raise ValueError(
                f"artifact sha256 mismatch path={artifact_path} expected={expected_sha256} actual={artifact_sha256}"
            )
        tvm_version = None
        dev = None
        fn = None
        load_ms = 0.0
        vm_init_ms = 0.0
        if not dry_run:
            import tvm  # pylint: disable=import-error
            from tvm import relax  # pylint: disable=import-error

            dev = tvm.cpu(0)
            preload_py = maybe_run_runtime_preload()
            load_t0 = time.perf_counter()
            lib = tvm.runtime.load_module(str(artifact_path))
            load_t1 = time.perf_counter()
            vm = relax.VirtualMachine(lib, dev)
            load_t2 = time.perf_counter()
            fn = vm["main"]
            tvm_version = tvm.__version__
            load_ms = (load_t1 - load_t0) * 1000.0
            vm_init_ms = (load_t2 - load_t1) * 1000.0
        else:
            preload_py = None
        run_samples_ms: list[float] = []
        processed = 0
        output_shape = None
        output_dtype = None
        while True:
            item = input_queue.get()
            if item is None:
                output_queue.put(None)
                break
            infer_t0 = time.perf_counter()
            noisy = np.asarray(item["noisy"], dtype=np.float32)
            if dry_run:
                output_np = mock_infer(noisy=noisy, sleep_ms=mock_infer_ms)
            else:
                runtime_input = runtime_tensor(noisy, dev)
                output = fn(runtime_input)
                output_np = output.numpy() if hasattr(output, "numpy") else np.asarray(output)
            infer_t1 = time.perf_counter()
            output_queue.put(
                {
                    "index": item["index"],
                    "input_file": item["input_file"],
                    "base_name": item["base_name"],
                    "output": output_np,
                }
            )
            run_samples_ms.append((infer_t1 - infer_t0) * 1000.0)
            processed += 1
            output_shape = list(np.asarray(output_np).shape)
            output_dtype = str(np.asarray(output_np).dtype)
        result.update(
            {
                "artifact_path": str(artifact_path),
                "artifact_sha256": artifact_sha256,
                "artifact_sha256_expected": expected_sha256 or None,
                "artifact_sha256_match": None if not expected_sha256 else artifact_sha256 == expected_sha256,
                "dry_run": dry_run,
                "mock_infer_ms": mock_infer_ms if dry_run else None,
                "tvm_version": tvm_version,
                "runtime_preload_py": preload_py,
                "load_ms": round(load_ms, 3),
                "vm_init_ms": round(vm_init_ms, 3),
                "processed_count": processed,
                "run_samples_ms": [round(value, 3) for value in run_samples_ms],
                "run_summary": summarize_samples(run_samples_ms),
                "output_shape": output_shape,
                "output_dtype": output_dtype,
            }
        )
    except Exception as err:  # pragma: no cover - error path exercised through wrapper failures.
        result.update(
            {
                "status": "error",
                "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(),
            }
        )
        try:
            output_queue.put(None)
        except Exception:
            pass
    finally:
        stats_queue.put(result)


def postprocessor_worker(
    output_dir_raw: str,
    little_cores: list[int],
    allow_missing_affinity: bool,
    backend: str,
    expected_count: int,
    output_queue,
    stats_queue,
) -> None:
    result: dict[str, Any] = {"role": "postprocessor", "status": "ok"}
    try:
        result["affinity"] = apply_affinity("postprocessor", little_cores, allow_missing_affinity, backend)
        reconstructions_dir = Path(output_dir_raw) / "reconstructions"
        reconstructions_dir.mkdir(parents=True, exist_ok=True)
        save_samples_ms: list[float] = []
        saved_count = 0
        last_output_path = None
        while True:
            item = output_queue.get()
            if item is None:
                break
            save_t0 = time.perf_counter()
            save_path = save_reconstruction(np.asarray(item["output"]), reconstructions_dir / f"{item['base_name']}_recon")
            save_t1 = time.perf_counter()
            save_samples_ms.append((save_t1 - save_t0) * 1000.0)
            saved_count += 1
            last_output_path = str(save_path)
            emit_demo_progress(
                completed_count=saved_count,
                expected_count=expected_count,
                input_path=str(item.get("input_file") or ""),
                output_path=last_output_path,
            )
        result.update(
            {
                "output_count": saved_count,
                "save_samples_ms": [round(value, 3) for value in save_samples_ms],
                "save_summary": summarize_samples(save_samples_ms),
                "last_output_path": last_output_path,
            }
        )
    except Exception as err:  # pragma: no cover - error path exercised through wrapper failures.
        result.update(
            {
                "status": "error",
                "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        stats_queue.put(result)


def safe_join_process(process: mp.Process, timeout_sec: float = 300.0) -> None:
    process.join(timeout=timeout_sec)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5.0)


def safe_join_thread(thread: threading.Thread, timeout_sec: float = 5.0) -> None:
    thread.join(timeout=timeout_sec)


def collect_worker_stats(stats_queue, expected: int) -> dict[str, dict[str, Any]]:
    stats_by_role: dict[str, dict[str, Any]] = {}
    deadline = time.time() + 5.0
    while len(stats_by_role) < expected and time.time() < deadline:
        try:
            payload = stats_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        role = str(payload.get("role", f"unknown_{len(stats_by_role)}"))
        stats_by_role[role] = payload
    return stats_by_role


def worker_error_messages(
    stats_by_role: dict[str, dict[str, Any]],
    workers: dict[str, Any],
    backend: str,
) -> list[str]:
    errors: list[str] = []
    for role, worker in workers.items():
        payload = stats_by_role.get(role)
        if payload is None:
            errors.append(f"{role}: missing worker stats")
            continue
        if payload.get("status") != "ok":
            errors.append(f"{role}: {payload.get('error', 'unknown error')}")
        elif backend == "processes" and getattr(worker, "exitcode", 0) not in (0, None):
            errors.append(f"{role}: exit_code={worker.exitcode}")
    return errors


def build_markdown(summary: dict[str, Any]) -> str:
    infer = summary.get("stages", {}).get("inferencer", {})
    preload = summary.get("stages", {}).get("preloader", {})
    save = summary.get("stages", {}).get("postprocessor", {})
    affinity = summary.get("affinity", {})
    lines = [
        "# big.LITTLE Pipeline Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- variant: {summary.get('variant')}",
        f"- execution_mode: {summary.get('execution_mode')}",
        f"- dry_run: {summary.get('dry_run')}",
        f"- processed_count: {summary.get('processed_count')}",
        f"- output_count: {summary.get('output_count')}",
        f"- total_wall_ms: {summary.get('total_wall_ms')}",
        f"- images_per_sec: {summary.get('images_per_sec')}",
        f"- big_cores: {summary.get('big_cores')}",
        f"- little_cores: {summary.get('little_cores')}",
        "",
        "## Stage Metrics",
        "",
        f"- preload_mean_ms: {preload.get('load_summary', {}).get('mean_ms')}",
        f"- awgn_mean_ms: {preload.get('awgn_summary', {}).get('mean_ms')}",
        f"- infer_median_ms: {infer.get('run_summary', {}).get('median_ms')}",
        f"- save_mean_ms: {save.get('save_summary', {}).get('mean_ms')}",
        "",
        "## Affinity",
        "",
        f"- preloader: {affinity.get('preloader')}",
        f"- inferencer: {affinity.get('inferencer')}",
        f"- postprocessor: {affinity.get('postprocessor')}",
    ]
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        for error in summary["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def run_serial(args: argparse.Namespace) -> dict[str, Any]:
    if not args.dry_run:
        raise SystemExit("ERROR: --execution-mode serial currently requires --dry-run.")

    artifact_path = Path(args.artifact_path)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not artifact_path.is_file():
        raise SystemExit(f"ERROR: artifact not found: {artifact_path}")
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: input dir not found: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    big_cores = parse_cpu_list(args.big_cores)
    little_cores = parse_cpu_list(args.little_cores)
    input_files, available_input_count = collect_input_files(input_dir=input_dir, max_inputs=args.max_inputs)
    if not input_files:
        raise SystemExit(f"ERROR: no supported latent files found in {input_dir}")

    expected_sha256 = args.expected_sha256.strip().lower()
    artifact_sha256 = file_sha256(artifact_path)
    if expected_sha256 and artifact_sha256 != expected_sha256:
        raise SystemExit(
            "ERROR: artifact sha256 mismatch "
            f"path={artifact_path} expected={expected_sha256} actual={artifact_sha256}"
        )

    reconstructions_dir = output_dir / "reconstructions"
    reconstructions_dir.mkdir(parents=True, exist_ok=True)
    serial_started_at = time.perf_counter()
    affinity_target = big_cores or little_cores
    serial_affinity = apply_affinity(
        "serial",
        affinity_target,
        args.allow_missing_affinity,
        backend="processes",
    )
    rng = np.random.default_rng(args.seed)
    load_samples_ms: list[float] = []
    awgn_samples_ms: list[float] = []
    run_samples_ms: list[float] = []
    save_samples_ms: list[float] = []
    processed_count = 0
    last_output = None

    for input_path in input_files:
        base_name = input_path.stem.split("_latent")[0]
        load_t0 = time.perf_counter()
        latent = load_latent(input_path)
        load_t1 = time.perf_counter()
        noisy = awgn_channel(latent, snr=args.snr, rng=rng).astype(np.float32)
        load_t2 = time.perf_counter()
        run_t0 = time.perf_counter()
        output = mock_infer(noisy, args.mock_infer_ms)
        run_t1 = time.perf_counter()
        save_reconstruction(output, reconstructions_dir / f"{base_name}_recon")
        emit_demo_progress(
            completed_count=processed_count + 1,
            expected_count=len(input_files),
            input_path=str(input_path),
            output_path=str((reconstructions_dir / f"{base_name}_recon").with_suffix(".png" if Image is not None else ".npy")),
        )
        save_t1 = time.perf_counter()
        load_samples_ms.append((load_t1 - load_t0) * 1000.0)
        awgn_samples_ms.append((load_t2 - load_t1) * 1000.0)
        run_samples_ms.append((run_t1 - run_t0) * 1000.0)
        save_samples_ms.append((save_t1 - run_t1) * 1000.0)
        processed_count += 1
        last_output = output

    serial_ended_at = time.perf_counter()
    output_count = len(list(reconstructions_dir.glob("*")))
    total_wall_ms = (serial_ended_at - serial_started_at) * 1000.0
    images_per_sec = None if processed_count == 0 else round(processed_count / (total_wall_ms / 1000.0), 3)
    ms_per_image = None if processed_count == 0 else round(total_wall_ms / processed_count, 3)
    output_shape = None if last_output is None else list(np.asarray(last_output).shape)
    output_dtype = None if last_output is None else str(np.asarray(last_output).dtype)
    preload_load_summary = summarize_samples(load_samples_ms)
    preload_awgn_summary = summarize_samples(awgn_samples_ms)
    run_summary = summarize_samples(run_samples_ms)
    save_summary = summarize_samples(save_samples_ms)
    inferencer_stage = {
        "role": "inferencer",
        "status": "ok",
        "affinity": serial_affinity,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_sha256_expected": expected_sha256 or None,
        "artifact_sha256_match": None if not expected_sha256 else artifact_sha256 == expected_sha256,
        "load_ms": 0.0,
        "vm_init_ms": 0.0,
        "run_samples_ms": [round(value, 3) for value in run_samples_ms],
        "run_summary": run_summary,
        "processed_count": processed_count,
        "output_shape": output_shape,
        "output_dtype": output_dtype,
        "dry_run": True,
    }
    preloader_stage = {
        "role": "preloader",
        "status": "ok",
        "affinity": None,
        "load_samples_ms": [round(value, 3) for value in load_samples_ms],
        "awgn_samples_ms": [round(value, 3) for value in awgn_samples_ms],
        "load_summary": preload_load_summary,
        "awgn_summary": preload_awgn_summary,
        "queued_count": processed_count,
    }
    postprocessor_stage = {
        "role": "postprocessor",
        "status": "ok",
        "affinity": None,
        "output_count": output_count,
        "save_samples_ms": [round(value, 3) for value in save_samples_ms],
        "save_summary": save_summary,
    }
    return {
        "status": "ok",
        "mode": "big_little_serial",
        "execution_mode": "serial",
        "backend": "serial",
        "variant": args.variant,
        "dry_run": True,
        "mock_infer_ms": args.mock_infer_ms,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_sha256_expected": expected_sha256 or None,
        "artifact_sha256_match": None if not expected_sha256 else artifact_sha256 == expected_sha256,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "output_count": output_count,
        "processed_count": processed_count,
        "input_count": len(input_files),
        "available_input_count": available_input_count,
        "load_ms": 0.0,
        "vm_init_ms": 0.0,
        "run_samples_ms": [round(value, 3) for value in run_samples_ms],
        "run_count": run_summary["count"],
        "run_median_ms": run_summary["median_ms"],
        "run_mean_ms": run_summary["mean_ms"],
        "run_min_ms": run_summary["min_ms"],
        "run_max_ms": run_summary["max_ms"],
        "run_variance_ms2": run_summary["variance_ms2"],
        "output_shape": output_shape,
        "output_dtype": output_dtype,
        "preload_load_samples_ms": [round(value, 3) for value in load_samples_ms],
        "preload_awgn_samples_ms": [round(value, 3) for value in awgn_samples_ms],
        "save_samples_ms": [round(value, 3) for value in save_samples_ms],
        "preload_load_summary": preload_load_summary,
        "preload_awgn_summary": preload_awgn_summary,
        "save_summary": save_summary,
        "total_wall_ms": round(total_wall_ms, 3),
        "images_per_sec": images_per_sec,
        "ms_per_image": ms_per_image,
        "snr": args.snr,
        "batch_size": args.batch_size,
        "max_inputs": args.max_inputs,
        "seed": args.seed,
        "big_cores": big_cores,
        "little_cores": little_cores,
        "input_queue_size": 0,
        "output_queue_size": 0,
        "save_format": "png" if Image is not None else "npy",
        "tvm_version": None,
        "affinity": {
            "serial": serial_affinity,
            "preloader": None,
            "inferencer": serial_affinity,
            "postprocessor": None,
        },
        "stages": {
            "preloader": preloader_stage,
            "inferencer": inferencer_stage,
            "postprocessor": postprocessor_stage,
        },
        "errors": [],
    }


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    artifact_path = Path(args.artifact_path)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not artifact_path.is_file():
        raise SystemExit(f"ERROR: artifact not found: {artifact_path}")
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: input dir not found: {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    big_cores = parse_cpu_list(args.big_cores)
    little_cores = parse_cpu_list(args.little_cores)
    input_files, available_input_count = collect_input_files(input_dir=input_dir, max_inputs=args.max_inputs)
    if not input_files:
        raise SystemExit(f"ERROR: no supported latent files found in {input_dir}")

    expected_sha256 = args.expected_sha256.strip().lower()
    pipeline_started_at = time.perf_counter()

    if args.backend == "threads":
        input_queue = queue.Queue(maxsize=args.input_queue_size)
        output_queue = queue.Queue(maxsize=args.output_queue_size)
        stats_queue = queue.Queue()
        workers = {
            "preloader": threading.Thread(
                target=preloader_worker,
                kwargs={
                    "input_files": [str(path) for path in input_files],
                    "snr": args.snr,
                    "seed": args.seed,
                    "little_cores": little_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "input_queue": input_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-preloader",
            ),
            "inferencer": threading.Thread(
                target=inferencer_worker,
                kwargs={
                    "artifact_path_raw": str(artifact_path),
                    "expected_sha256": expected_sha256,
                    "dry_run": args.dry_run,
                    "mock_infer_ms": args.mock_infer_ms,
                    "big_cores": big_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "input_queue": input_queue,
                    "output_queue": output_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-inferencer",
            ),
            "postprocessor": threading.Thread(
                target=postprocessor_worker,
                kwargs={
                    "output_dir_raw": str(output_dir),
                    "little_cores": little_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "expected_count": len(input_files),
                    "output_queue": output_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-postprocessor",
            ),
        }
        for worker in workers.values():
            worker.start()
        for worker in workers.values():
            safe_join_thread(worker)
    else:
        input_queue = mp.Queue(maxsize=args.input_queue_size)
        output_queue = mp.Queue(maxsize=args.output_queue_size)
        stats_queue = mp.Queue()
        workers = {
            "preloader": mp.Process(
                target=preloader_worker,
                kwargs={
                    "input_files": [str(path) for path in input_files],
                    "snr": args.snr,
                    "seed": args.seed,
                    "little_cores": little_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "input_queue": input_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-preloader",
            ),
            "inferencer": mp.Process(
                target=inferencer_worker,
                kwargs={
                    "artifact_path_raw": str(artifact_path),
                    "expected_sha256": expected_sha256,
                    "dry_run": args.dry_run,
                    "mock_infer_ms": args.mock_infer_ms,
                    "big_cores": big_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "input_queue": input_queue,
                    "output_queue": output_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-inferencer",
            ),
            "postprocessor": mp.Process(
                target=postprocessor_worker,
                kwargs={
                    "output_dir_raw": str(output_dir),
                    "little_cores": little_cores,
                    "allow_missing_affinity": args.allow_missing_affinity,
                    "backend": args.backend,
                    "expected_count": len(input_files),
                    "output_queue": output_queue,
                    "stats_queue": stats_queue,
                },
                name="biglittle-postprocessor",
            ),
        }
        for worker in workers.values():
            worker.start()
        for worker in workers.values():
            safe_join_process(worker)

    pipeline_ended_at = time.perf_counter()
    stats_by_role = collect_worker_stats(stats_queue=stats_queue, expected=3)
    errors = worker_error_messages(stats_by_role=stats_by_role, workers=workers, backend=args.backend)

    preloader = stats_by_role.get("preloader", {})
    inferencer = stats_by_role.get("inferencer", {})
    postprocessor = stats_by_role.get("postprocessor", {})
    reconstructions_dir = output_dir / "reconstructions"
    output_count = len(list(reconstructions_dir.glob("*")))
    processed_count = int(postprocessor.get("output_count", inferencer.get("processed_count", 0)) or 0)
    total_wall_ms = (pipeline_ended_at - pipeline_started_at) * 1000.0
    images_per_sec = None if processed_count == 0 else round(processed_count / (total_wall_ms / 1000.0), 3)
    ms_per_image = None if processed_count == 0 else round(total_wall_ms / processed_count, 3)

    summary = {
        "status": "error" if errors else "ok",
        "mode": "big_little_pipeline",
        "execution_mode": "pipeline",
        "backend": args.backend,
        "variant": args.variant,
        "dry_run": args.dry_run,
        "mock_infer_ms": args.mock_infer_ms if args.dry_run else None,
        "artifact_path": inferencer.get("artifact_path", str(artifact_path)),
        "artifact_sha256": inferencer.get("artifact_sha256"),
        "artifact_sha256_expected": inferencer.get("artifact_sha256_expected"),
        "artifact_sha256_match": inferencer.get("artifact_sha256_match"),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "output_count": output_count,
        "processed_count": processed_count,
        "input_count": len(input_files),
        "available_input_count": available_input_count,
        "load_ms": inferencer.get("load_ms"),
        "vm_init_ms": inferencer.get("vm_init_ms"),
        "run_samples_ms": inferencer.get("run_samples_ms", []),
        "run_count": inferencer.get("run_summary", {}).get("count"),
        "run_median_ms": inferencer.get("run_summary", {}).get("median_ms"),
        "run_mean_ms": inferencer.get("run_summary", {}).get("mean_ms"),
        "run_min_ms": inferencer.get("run_summary", {}).get("min_ms"),
        "run_max_ms": inferencer.get("run_summary", {}).get("max_ms"),
        "run_variance_ms2": inferencer.get("run_summary", {}).get("variance_ms2"),
        "output_shape": inferencer.get("output_shape"),
        "output_dtype": inferencer.get("output_dtype"),
        "preload_load_samples_ms": preloader.get("load_samples_ms", []),
        "preload_awgn_samples_ms": preloader.get("awgn_samples_ms", []),
        "save_samples_ms": postprocessor.get("save_samples_ms", []),
        "preload_load_summary": preloader.get("load_summary", summarize_samples([])),
        "preload_awgn_summary": preloader.get("awgn_summary", summarize_samples([])),
        "save_summary": postprocessor.get("save_summary", summarize_samples([])),
        "total_wall_ms": round(total_wall_ms, 3),
        "images_per_sec": images_per_sec,
        "ms_per_image": ms_per_image,
        "snr": args.snr,
        "batch_size": args.batch_size,
        "max_inputs": args.max_inputs,
        "seed": args.seed,
        "big_cores": big_cores,
        "little_cores": little_cores,
        "input_queue_size": args.input_queue_size,
        "output_queue_size": args.output_queue_size,
        "save_format": "png" if Image is not None else "npy",
        "tvm_version": inferencer.get("tvm_version"),
        "affinity": {
            "preloader": preloader.get("affinity"),
            "inferencer": inferencer.get("affinity"),
            "postprocessor": postprocessor.get("affinity"),
        },
        "stages": {
            "preloader": preloader,
            "inferencer": inferencer,
            "postprocessor": postprocessor,
        },
        "errors": errors,
    }
    return summary


def write_outputs(summary: dict[str, Any], args: argparse.Namespace) -> None:
    if args.summary_json:
        Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_md:
        Path(args.summary_md).write_text(build_markdown(summary), encoding="utf-8")


def main() -> None:
    configure_logging()
    args = parse_args()
    summary = run_serial(args) if args.execution_mode == "serial" else run_pipeline(args)
    write_outputs(summary, args)
    LOGGER.info(
        "big.LITTLE pipeline finished status=%s processed=%s total_wall_ms=%s images_per_sec=%s",
        summary["status"],
        summary["processed_count"],
        summary["total_wall_ms"],
        summary["images_per_sec"],
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
