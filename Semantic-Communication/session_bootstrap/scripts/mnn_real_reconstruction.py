#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
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
            or os.environ.get("MNN_EXTRA_PYTHONPATH")
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


LOGGER = logging.getLogger("mnn_real_reconstruction")
PROGRESS_EMIT_LOCK = Lock()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run JSCC MNN reconstruction over latent inputs and emit a structured "
            "JSON summary suitable for benchmark matrix aggregation."
        )
    )
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--snr", type=float, required=True)
    parser.add_argument("--variant", default="current")
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument("--max-inputs", type=int, default=0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--interpreter-count", type=int, default=1)
    parser.add_argument("--session-threads", type=int, default=1)
    parser.add_argument("--precision", choices=("normal", "low", "high"), default="normal")
    parser.add_argument("--shape-mode", choices=("dynamic", "bucketed"), default="dynamic")
    parser.add_argument("--input-source-mode", choices=("prerecorded", "usrp"), default="prerecorded")
    parser.add_argument("--input-source-label", default="")
    parser.add_argument(
        "--bucket-shapes",
        default="",
        help="Comma-separated exact latent shapes. Accepts HxW or NxCxHxW tokens.",
    )
    parser.add_argument("--warmup-inputs", type=int, default=0)
    parser.add_argument("--auto-backend", action="store_true")
    parser.add_argument("--tune-num", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-infer-ms", type=float, default=15.0)
    args = parser.parse_args()
    if args.max_inputs < 0:
        raise SystemExit(f"ERROR: --max-inputs must be >= 0 (got: {args.max_inputs})")
    if args.interpreter_count <= 0:
        raise SystemExit(f"ERROR: --interpreter-count must be > 0 (got: {args.interpreter_count})")
    if args.session_threads <= 0:
        raise SystemExit(f"ERROR: --session-threads must be > 0 (got: {args.session_threads})")
    if args.warmup_inputs < 0:
        raise SystemExit(f"ERROR: --warmup-inputs must be >= 0 (got: {args.warmup_inputs})")
    if args.tune_num < 0:
        raise SystemExit(f"ERROR: --tune-num must be >= 0 (got: {args.tune_num})")
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


def parse_bucket_token(token: str) -> tuple[int, int, int, int]:
    cleaned = token.strip().lower().replace("x", ",")
    if not cleaned:
        raise ValueError("empty bucket shape token")
    dims = [int(part.strip()) for part in cleaned.split(",") if part.strip()]
    if len(dims) == 2:
        return (1, 32, dims[0], dims[1])
    if len(dims) == 4:
        return tuple(dims)  # type: ignore[return-value]
    raise ValueError(f"bucket shape must be HxW or NxCxHxW, got: {token}")


def parse_bucket_shapes(raw: str) -> list[tuple[int, int, int, int]]:
    if not raw.strip():
        return []
    return [parse_bucket_token(token) for token in raw.split(",") if token.strip()]


def collect_input_files(input_dir: Path, max_inputs: int) -> tuple[list[Path], int]:
    input_files: list[Path] = []
    for pattern in ("*.pt", "*.npz", "*.npy"):
        input_files.extend(Path(path) for path in glob.glob(str(input_dir / pattern)))
    unique_files = sorted({path.resolve(): path for path in input_files}.values())
    available_count = len(unique_files)
    if max_inputs:
        unique_files = unique_files[:max_inputs]
    return unique_files, available_count


def resolve_effective_input_dir(input_dir: Path, input_source_mode: str) -> Path:
    if input_source_mode != "usrp":
        return input_dir
    if not input_dir.is_dir():
        return input_dir
    files, _available_count = collect_input_files(input_dir, 0)
    if files:
        return input_dir

    candidate_dirs = [path for path in input_dir.iterdir() if path.is_dir()]
    candidate_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidate_dirs:
        candidate_files, _candidate_count = collect_input_files(candidate, 0)
        if candidate_files:
            return candidate
    return input_dir


def base_name_for_input(path: Path) -> str:
    name = path.stem
    if name.endswith("_latent"):
        return name[: -len("_latent")]
    return name


@dataclass
class SessionHandle:
    session: Any
    input_tensor: Any
    shape: tuple[int, int, int, int]


@dataclass
class WorkerContext:
    model_path: Path
    session_threads: int
    precision: str
    dry_run: bool
    mock_infer_ms: float
    auto_backend: bool
    tune_num: int
    bucket_shapes: list[tuple[int, int, int, int]]
    interpreter: Any = None
    dynamic_handle: SessionHandle | None = None
    bucket_handles: dict[tuple[int, int, int, int], SessionHandle] = field(default_factory=dict)
    bucket_hit_count: int = 0
    bucket_miss_count: int = 0

    def __post_init__(self) -> None:
        if self.dry_run:
            return
        try:
            import MNN as mnn_mod
        except ImportError as exc:
            raise RuntimeError("MNN is required when --dry-run is not enabled") from exc
        self.interpreter = mnn_mod.Interpreter(str(self.model_path))
        if self.auto_backend:
            self.interpreter.setSessionMode(9)
            if self.tune_num > 0:
                self.interpreter.setSessionHint(0, self.tune_num)
        for shape in self.bucket_shapes:
            self.bucket_handles[shape] = self._create_handle(shape)

    def _create_handle(self, shape: tuple[int, int, int, int]) -> SessionHandle:
        import MNN as mnn_mod

        config: dict[str, Any] = {"numThread": self.session_threads}
        if self.precision != "normal":
            config["precision"] = self.precision
        session = self.interpreter.createSession(config)
        input_tensor = self.interpreter.getSessionInput(session)
        self.interpreter.resizeTensor(input_tensor, shape)
        self.interpreter.resizeSession(session)
        return SessionHandle(session=session, input_tensor=input_tensor, shape=shape)

    def _resolve_handle(self, sample_shape: tuple[int, int, int, int]) -> tuple[SessionHandle | None, float]:
        if self.dry_run:
            return None, 0.0
        if sample_shape in self.bucket_handles:
            self.bucket_hit_count += 1
            return self.bucket_handles[sample_shape], 0.0
        self.bucket_miss_count += 1 if self.bucket_shapes else 0
        resize_start = time.perf_counter()
        if self.dynamic_handle is None:
            self.dynamic_handle = self._create_handle(sample_shape)
            resize_ms = (time.perf_counter() - resize_start) * 1000.0
            return self.dynamic_handle, resize_ms
        if self.dynamic_handle.shape != sample_shape:
            self.interpreter.resizeTensor(self.dynamic_handle.input_tensor, sample_shape)
            self.interpreter.resizeSession(self.dynamic_handle.session)
            self.dynamic_handle.shape = sample_shape
        resize_ms = (time.perf_counter() - resize_start) * 1000.0
        return self.dynamic_handle, resize_ms

    def process_item(
        self,
        path: Path,
        *,
        snr: float,
        seed: int | None,
        item_index: int,
        recon_dir: Path,
        warmup: bool,
    ) -> dict[str, Any]:
        sample_start = time.perf_counter()
        latent = load_latent(path)
        preprocess_done = time.perf_counter()
        rng = np.random.default_rng(None if seed is None else seed + item_index)
        noisy = awgn_channel(latent, snr, rng)
        channel_done = time.perf_counter()
        sample_shape = tuple(int(dim) for dim in noisy.shape)

        if self.dry_run:
            time.sleep(self.mock_infer_ms / 1000.0)
            output = np.asarray(noisy[:, :3, :, :], dtype=np.float32)
            resize_ms = 0.0
            run_ms = float(self.mock_infer_ms)
        else:
            import MNN as mnn_mod

            handle, resize_ms = self._resolve_handle(sample_shape)
            tmp_tensor = mnn_mod.Tensor(
                sample_shape,
                mnn_mod.Halide_Type_Float,
                np.asarray(noisy, dtype=np.float32),
                mnn_mod.Tensor_DimensionType_Caffe,
            )
            handle.input_tensor.copyFrom(tmp_tensor)
            run_start = time.perf_counter()
            self.interpreter.runSession(handle.session)
            run_ms = (time.perf_counter() - run_start) * 1000.0
            output_tensor = self.interpreter.getSessionOutput(handle.session)
            output_shape = output_tensor.getShape()
            output = np.asarray(output_tensor.getData(), dtype=np.float32).reshape(output_shape)

        save_ms = 0.0
        output_path = ""
        if not warmup:
            output_stem = recon_dir / f"{base_name_for_input(path)}_recon"
            save_start = time.perf_counter()
            output_path = str(save_reconstruction(output, output_stem))
            save_ms = (time.perf_counter() - save_start) * 1000.0
            with PROGRESS_EMIT_LOCK:
                print(
                    json.dumps(
                        {
                            "openamp_demo_progress": {
                                "delta": 1,
                                "input_path": str(path),
                                "output_path": output_path,
                            }
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

        total_ms = (time.perf_counter() - sample_start) * 1000.0
        return {
            "input_path": str(path),
            "input_shape": list(sample_shape),
            "output_path": output_path,
            "warmup": warmup,
            "preload_ms": round((preprocess_done - sample_start) * 1000.0, 3),
            "channel_ms": round((channel_done - preprocess_done) * 1000.0, 3),
            "resize_ms": round(resize_ms, 3),
            "run_ms": round(run_ms, 3),
            "save_ms": round(save_ms, 3),
            "total_ms": round(total_ms, 3),
        }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MNN Reconstruction Summary",
        "",
        f"- status: {payload['status']}",
        f"- variant: {payload['variant']}",
        f"- model_path: {payload['model_path']}",
        f"- model_sha256: {payload['model_sha256']}",
        f"- processed_count: {payload['processed_count']}",
        f"- warmup_count: {payload['warmup_count']}",
        f"- total_wall_ms: {payload['total_wall_ms']}",
        f"- images_per_sec: {payload['images_per_sec']}",
        f"- interpreter_count: {payload['interpreter_count']}",
        f"- session_threads: {payload['session_threads']}",
        f"- precision: {payload['precision']}",
        f"- shape_mode: {payload['shape_mode']}",
        f"- bucket_shapes: {payload['bucket_shapes']}",
        "",
        "## Sample Stats",
        "",
        f"- total_ms_mean: {payload['sample_stats']['total_ms']['mean_ms']}",
        f"- run_ms_mean: {payload['sample_stats']['run_ms']['mean_ms']}",
        f"- resize_ms_mean: {payload['sample_stats']['resize_ms']['mean_ms']}",
    ]
    if payload.get("errors"):
        lines.extend(["", "## Errors", ""])
        for error in payload["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def main() -> int:
    configure_logging()
    args = parse_args()

    model_path = Path(args.model_path)
    requested_input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    recon_dir = output_dir / "reconstructions"
    summary_json_path = output_dir / "summary.json"
    summary_md_path = output_dir / "summary.md"

    output_dir.mkdir(parents=True, exist_ok=True)
    recon_dir.mkdir(parents=True, exist_ok=True)

    if not args.dry_run and not model_path.is_file():
        raise SystemExit(f"ERROR: model path not found: {model_path}")
    input_dir = resolve_effective_input_dir(requested_input_dir, args.input_source_mode)
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: input directory not found: {requested_input_dir}")
    LOGGER.info(
        "输入模式: %s (%s), 请求目录=%s, 实际目录=%s",
        args.input_source_mode,
        args.input_source_label or args.input_source_mode,
        requested_input_dir,
        input_dir,
    )
    if args.expected_sha256 and args.expected_sha256.lower() != file_sha256(model_path).lower():
        raise SystemExit(
            "ERROR: model sha256 mismatch "
            f"path={model_path} expected={args.expected_sha256.lower()} actual={file_sha256(model_path).lower()}"
        )

    input_files, available_count = collect_input_files(input_dir, args.max_inputs)
    if not input_files:
        raise SystemExit(f"ERROR: no latent files found in {input_dir}")

    bucket_shapes = parse_bucket_shapes(args.bucket_shapes)
    warmup_files = input_files[: min(len(input_files), args.warmup_inputs)]
    measured_files = input_files[len(warmup_files) :]

    workers = [
        WorkerContext(
            model_path=model_path,
            session_threads=args.session_threads,
            precision=args.precision,
            dry_run=args.dry_run,
            mock_infer_ms=args.mock_infer_ms,
            auto_backend=args.auto_backend,
            tune_num=args.tune_num,
            bucket_shapes=bucket_shapes if args.shape_mode == "bucketed" else [],
        )
        for _ in range(args.interpreter_count)
    ]

    try:
        for warmup_index, warmup_path in enumerate(warmup_files):
            worker = workers[warmup_index % len(workers)]
            worker.process_item(
                warmup_path,
                snr=args.snr,
                seed=args.seed,
                item_index=warmup_index,
                recon_dir=recon_dir,
                warmup=True,
            )

        partitions: list[list[tuple[int, Path]]] = [[] for _ in range(len(workers))]
        for relative_index, measured_path in enumerate(measured_files):
            global_index = relative_index + len(warmup_files)
            partitions[relative_index % len(workers)].append((global_index, measured_path))

        run_started_at = time.time()
        wall_start = time.perf_counter()
        sample_results: list[dict[str, Any]] = []
        errors: list[str] = []

        def run_partition(worker_index: int) -> list[dict[str, Any]]:
            local_results: list[dict[str, Any]] = []
            worker = workers[worker_index]
            for item_index, path in partitions[worker_index]:
                local_results.append(
                    worker.process_item(
                        path,
                        snr=args.snr,
                        seed=args.seed,
                        item_index=item_index,
                        recon_dir=recon_dir,
                        warmup=False,
                    )
                )
            return local_results

        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            futures = [executor.submit(run_partition, index) for index in range(len(workers))]
            for future in futures:
                try:
                    sample_results.extend(future.result())
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{type(exc).__name__}: {exc}")

        total_wall_ms = round((time.perf_counter() - wall_start) * 1000.0, 3)
        run_finished_at = time.time()

        sample_results.sort(key=lambda item: item["input_path"])
        total_samples = [float(item["total_ms"]) for item in sample_results]
        run_samples = [float(item["run_ms"]) for item in sample_results]
        resize_samples = [float(item["resize_ms"]) for item in sample_results]

        processed_count = len(sample_results)
        payload: dict[str, Any] = {
            "status": "ok" if not errors else "error",
            "variant": args.variant,
            "model_path": str(model_path),
            "model_sha256": file_sha256(model_path) if model_path.is_file() else None,
            "input_source_mode": args.input_source_mode,
            "input_source_label": args.input_source_label or args.input_source_mode,
            "requested_input_dir": str(requested_input_dir),
            "input_dir": str(input_dir),
            "available_input_count": available_count,
            "selected_input_count": len(input_files),
            "warmup_count": len(warmup_files),
            "processed_count": processed_count,
            "output_count": len(list(recon_dir.glob("*"))),
            "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(run_started_at)),
            "run_finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(run_finished_at)),
            "total_wall_ms": total_wall_ms,
            "images_per_sec": round((processed_count * 1000.0 / total_wall_ms), 6) if total_wall_ms > 0 else None,
            "interpreter_count": args.interpreter_count,
            "session_threads": args.session_threads,
            "precision": args.precision,
            "shape_mode": args.shape_mode,
            "bucket_shapes": [list(shape) for shape in bucket_shapes],
            "bucket_hit_count": sum(worker.bucket_hit_count for worker in workers),
            "bucket_miss_count": sum(worker.bucket_miss_count for worker in workers),
            "auto_backend": args.auto_backend,
            "tune_num": args.tune_num if args.auto_backend else 0,
            "dry_run": args.dry_run,
            "mock_infer_ms": args.mock_infer_ms if args.dry_run else None,
            "snr": args.snr,
            "seed": args.seed,
            "output_dir": str(output_dir),
            "reconstruction_dir": str(recon_dir),
            "sample_stats": {
                "total_ms": summarize_samples(total_samples),
                "run_ms": summarize_samples(run_samples),
                "resize_ms": summarize_samples(resize_samples),
            },
            "errors": errors,
            "sample_results_preview": sample_results[: min(len(sample_results), 10)],
            "summary_json": str(summary_json_path),
            "summary_markdown": str(summary_md_path),
        }
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": "error",
            "variant": args.variant,
            "model_path": str(model_path),
            "input_source_mode": args.input_source_mode,
            "input_source_label": args.input_source_label or args.input_source_mode,
            "requested_input_dir": str(requested_input_dir),
            "input_dir": str(input_dir) if "input_dir" in locals() else str(requested_input_dir),
            "output_dir": str(output_dir),
            "reconstruction_dir": str(recon_dir),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    summary_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_md_path.write_text(build_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
