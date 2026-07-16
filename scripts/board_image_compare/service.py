from __future__ import annotations

import json
import math
import mimetypes
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .core import ImagePair, QualityMetrics, ResourceGate, is_color_noise, measure_quality, pair_images
from .remote import (
    BoardConnectionConfig,
    BoardSftpClient,
    ImageCache,
    RemoteJob,
    ResourceAborted,
    ResourcePaused,
    SUPPORTED_IMAGE_EXTENSIONS,
)


WEB_ROOT = Path(__file__).resolve().parent / "web"


@dataclass(frozen=True)
class ComparisonConfig:
    board_host: str
    board_user: str
    board_password: str
    board_port: int
    original_dir: Path
    remote_root: str
    manifest_root: Path | None = None


def _local_image_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def _manifest_original_name(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    source_info = payload.get("source_info")
    source_meta = source_info.get("source_meta") if isinstance(source_info, dict) else None
    value = source_meta.get("original_filename") if isinstance(source_meta, dict) else ""
    return str(value or "").strip()


def _quality_metrics_payload(metrics: QualityMetrics) -> dict[str, Any]:
    payload = asdict(metrics)
    psnr = metrics.psnr_db
    if psnr is not None and not math.isfinite(psnr):
        payload["psnr_db"] = "Infinity" if psnr > 0 else "-Infinity"
    return payload


class ComparisonServiceState:
    def __init__(
        self,
        *,
        cache_root: Path,
        remote_factory: Callable[[BoardConnectionConfig], BoardSftpClient] = BoardSftpClient,
    ) -> None:
        self.cache = ImageCache(cache_root)
        self._remote_factory = remote_factory
        self._config: ComparisonConfig | None = None
        self._remote: BoardSftpClient | None = None
        self._jobs: dict[str, RemoteJob] = {}
        self._pairs: dict[str, list[ImagePair]] = {}
        self._quality: dict[tuple[str, int], tuple[QualityMetrics, dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._transfer_lock = threading.Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="board-image-prefetch")
        self._scan_generation = 0
        self._quality_assistance = False
        self._last_resource: dict[str, Any] | None = None
        self._resource_gate = ResourceGate()
        self._closed = False

    def configure(self, config: ComparisonConfig) -> dict[str, Any]:
        if not config.board_host.strip() or not config.board_user.strip():
            raise ValueError("board host and user are required")
        if not config.original_dir.is_dir():
            raise ValueError(f"original directory not found: {config.original_dir}")
        if not config.remote_root.strip().startswith("/"):
            raise ValueError("remote root must be an absolute POSIX path")
        with self._lock:
            if self._remote is not None:
                self._remote.close()
            self._config = config
            self._remote = self._remote_factory(
                BoardConnectionConfig(
                    host=config.board_host,
                    user=config.board_user,
                    password=config.board_password,
                    port=config.board_port,
                )
            )
            self._jobs.clear()
            self._pairs.clear()
            self._quality.clear()
            self._scan_generation += 1
            self._quality_assistance = False
            self._last_resource = None
            self._resource_gate = ResourceGate()
        return self.public_config()

    def _require_config(self) -> ComparisonConfig:
        if self._config is None:
            raise RuntimeError("comparison service is not configured")
        return self._config

    def _require_remote(self) -> BoardSftpClient:
        if self._remote is None:
            raise RuntimeError("comparison service is not configured")
        return self._remote

    def public_config(self) -> dict[str, Any]:
        config = self._require_config()
        return {
            "board_host": config.board_host,
            "board_user": config.board_user,
            "board_port": config.board_port,
            "original_dir": str(config.original_dir),
            "remote_root": config.remote_root,
            "manifest_root": str(config.manifest_root) if config.manifest_root else "",
        }

    def public_state(self) -> dict[str, Any]:
        with self._lock:
            quality = {
                f"{job_id}:{index}": {**_quality_metrics_payload(metrics), **verdict}
                for (job_id, index), (metrics, verdict) in self._quality.items()
            }
            return {
                "configured": self._config is not None,
                "quality_assistance": self._quality_assistance,
                "quality": quality,
                "resources": self._last_resource,
            }

    def list_jobs(self) -> list[dict[str, Any]]:
        config = self._require_config()
        jobs = self._require_remote().list_jobs(config.remote_root)
        with self._lock:
            self._jobs = {job.id: job for job in jobs}
            self._pairs = {job_id: pairs for job_id, pairs in self._pairs.items() if job_id in self._jobs}
        return [self._serialize_job(job) for job in jobs]

    @staticmethod
    def _serialize_job(job: RemoteJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "name": job.name,
            "path": job.path,
            "modified_at": job.modified_at,
        }

    def _job(self, job_id: str) -> RemoteJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"unknown job: {job_id}")
        return job

    def _load_manifest_names(self, job: RemoteJob) -> dict[int, str]:
        config = self._require_config()
        root = config.manifest_root
        if root is None or not root.is_dir():
            return {}
        numeric_tokens = [token for token in job.name.replace("-", "_").split("_") if token.isdigit()]
        candidates = [path for path in root.iterdir() if path.is_dir()]
        if numeric_tokens:
            matching = [path for path in candidates if any(token in path.name for token in numeric_tokens)]
            if matching:
                candidates = matching
        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for run_dir in candidates:
            names: dict[int, str] = {}
            for image_dir in sorted(run_dir.glob("image_*")):
                try:
                    index = int(image_dir.name.split("_", 1)[1])
                    payload = json.loads((image_dir / "manifest.json").read_text(encoding="utf-8"))
                except (IndexError, ValueError, OSError, json.JSONDecodeError):
                    continue
                original_name = _manifest_original_name(payload)
                if original_name:
                    names[index] = original_name
            if names:
                return names
        return {}

    def job_detail(self, job_id: str) -> dict[str, Any]:
        job = self._job(job_id)
        with self._lock:
            pairs = self._pairs.get(job_id)
        if pairs is None:
            config = self._require_config()
            originals = _local_image_paths(config.original_dir)
            reconstructions = self._require_remote().list_job_images(job.path)
            pairs = pair_images(originals, reconstructions, self._load_manifest_names(job))
            with self._lock:
                self._pairs[job_id] = pairs
        return {
            "job": self._serialize_job(job),
            "pair_count": len(pairs),
            "pairs": [self._serialize_pair(job, pair) for pair in pairs],
        }

    def _serialize_pair(self, job: RemoteJob, pair: ImagePair) -> dict[str, Any]:
        cached = False
        if pair.reconstruction is not None:
            cached = self.cache.path_for(
                self._require_config().board_host,
                job.path,
                str(pair.reconstruction),
            ).is_file()
        return {
            "index": pair.index,
            "original_name": pair.original.name if pair.original else pair.original_name,
            "reconstruction_name": pair.reconstruction.name if pair.reconstruction else "",
            "original_available": pair.original is not None and pair.original.is_file(),
            "reconstruction_available": pair.reconstruction is not None,
            "cached": cached,
        }

    def _pair(self, job_id: str, index: int) -> tuple[RemoteJob, ImagePair]:
        if job_id not in self._pairs:
            self.job_detail(job_id)
        job = self._job(job_id)
        pairs = self._pairs[job_id]
        if index < 0 or index >= len(pairs):
            raise KeyError(f"image index out of range: {index}")
        return job, pairs[index]

    def _record_resources(self, snapshot) -> None:
        with self._lock:
            self._last_resource = {
                "cpu_percent": round(snapshot.cpu_percent, 2),
                "memory_percent": round(snapshot.memory_percent, 2),
                "sampled_at": time.time(),
            }

    def _download_pair(self, job_id: str, index: int) -> tuple[Path, bool]:
        job, pair = self._pair(job_id, index)
        if pair.reconstruction is None:
            raise FileNotFoundError(f"reconstruction missing at index {index}")
        config = self._require_config()
        target = self.cache.path_for(config.board_host, job.path, str(pair.reconstruction))
        if target.is_file():
            self._measure_pair(job_id, pair, target)
            return target, True

        with self._transfer_lock:
            if target.is_file():
                self._measure_pair(job_id, pair, target)
                return target, True
            remote = self._require_remote()
            snapshot, _ = remote.ensure_resources_available(self._resource_gate)
            self._record_resources(snapshot)
            last_check = time.monotonic()

            def monitor(_received: int, _total: int) -> None:
                nonlocal last_check
                if time.monotonic() - last_check < 3.0:
                    return
                last_check = time.monotonic()
                try:
                    current, _ = remote.ensure_resources_available(self._resource_gate)
                except ResourcePaused:
                    return
                self._record_resources(current)

            self.cache.download_atomic(
                remote,
                str(pair.reconstruction),
                target,
                callback=monitor,
            )
        self._measure_pair(job_id, pair, target)
        return target, False

    def _measure_pair(self, job_id: str, pair: ImagePair, reconstruction: Path) -> None:
        if pair.original is None or not pair.original.is_file():
            return
        key = (job_id, pair.index)
        with self._lock:
            if key in self._quality:
                return
            history = [metrics for (current_job, _), (metrics, _) in self._quality.items() if current_job == job_id]
        metrics = measure_quality(pair.original, reconstruction)
        verdict = is_color_noise(metrics, history)
        with self._lock:
            self._quality[key] = (metrics, asdict(verdict))

    def pull(self, job_id: str, index: int) -> dict[str, Any]:
        _, cached = self._download_pair(job_id, index)
        return {
            "status": "ok",
            "job_id": job_id,
            "index": index,
            "cached": cached,
            "original_url": f"/api/image/original?job_id={job_id}&index={index}",
            "reconstruction_url": f"/api/image/reconstruction?job_id={job_id}&index={index}",
            "quality": self._quality_payload(job_id, index),
        }

    def set_quality_assistance(self, enabled: bool, job_id: str = "") -> dict[str, Any]:
        with self._lock:
            self._quality_assistance = bool(enabled)
            self._scan_generation += 1
            generation = self._scan_generation
        if enabled and job_id:
            self.job_detail(job_id)
            self._worker.submit(self._scan_job, job_id, generation)
        return self.public_state()

    def _scan_job(self, job_id: str, generation: int) -> None:
        pairs = list(self._pairs.get(job_id, []))
        for pair in pairs:
            with self._lock:
                if generation != self._scan_generation or not self._quality_assistance:
                    return
            if pair.reconstruction is None:
                continue
            try:
                self._download_pair(job_id, pair.index)
            except ResourcePaused:
                time.sleep(3.0)
            except (ResourceAborted, RuntimeError, FileNotFoundError):
                return

    def _quality_payload(self, job_id: str, index: int) -> dict[str, Any] | None:
        with self._lock:
            record = self._quality.get((job_id, index))
        if record is None:
            return None
        metrics, verdict = record
        return {**_quality_metrics_payload(metrics), **verdict}

    def original_path(self, job_id: str, index: int) -> Path:
        _, pair = self._pair(job_id, index)
        if pair.original is None or not pair.original.is_file():
            raise FileNotFoundError("original image is unavailable")
        return pair.original

    def reconstruction_path(self, job_id: str, index: int) -> Path:
        job, pair = self._pair(job_id, index)
        if pair.reconstruction is None:
            raise FileNotFoundError("reconstruction image is unavailable")
        path = self.cache.path_for(
            self._require_config().board_host,
            job.path,
            str(pair.reconstruction),
        )
        if not path.is_file():
            raise FileNotFoundError("reconstruction image has not been pulled")
        return path

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._scan_generation += 1
            remote = self._remote
            self._remote = None
        self._worker.shutdown(wait=False, cancel_futures=True)
        if remote is not None:
            remote.close()


class ComparisonRequestHandler(SimpleHTTPRequestHandler):
    server: "ComparisonHTTPServer"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def _json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _send_image(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self._json(HTTPStatus.OK, {"status": "ok"})
                return
            if parsed.path == "/api/config":
                self._json(HTTPStatus.OK, self.server.state.public_config())
                return
            if parsed.path == "/api/jobs":
                self._json(HTTPStatus.OK, {"jobs": self.server.state.list_jobs()})
                return
            if parsed.path == "/api/job":
                self._json(HTTPStatus.OK, self.server.state.job_detail(params.get("id", [""])[0]))
                return
            if parsed.path == "/api/state":
                self._json(HTTPStatus.OK, self.server.state.public_state())
                return
            if parsed.path == "/api/image/original":
                self._send_image(
                    self.server.state.original_path(
                        params.get("job_id", [""])[0],
                        int(params.get("index", ["-1"])[0]),
                    )
                )
                return
            if parsed.path == "/api/image/reconstruction":
                self._send_image(
                    self.server.state.reconstruction_path(
                        params.get("job_id", [""])[0],
                        int(params.get("index", ["-1"])[0]),
                    )
                )
                return
            if parsed.path == "/":
                self.path = "/index.html"
            super().do_GET()
        except (KeyError, FileNotFoundError) as error:
            self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(error)})
        except Exception as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "message": str(error)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/config":
                config = ComparisonConfig(
                    board_host=str(payload.get("board_host", "")),
                    board_user=str(payload.get("board_user", "")),
                    board_password=str(payload.get("board_password", "")),
                    board_port=int(payload.get("board_port", 22)),
                    original_dir=Path(str(payload.get("original_dir", ""))).resolve(),
                    remote_root=str(payload.get("remote_root", "")),
                    manifest_root=(
                        Path(str(payload["manifest_root"])).resolve()
                        if payload.get("manifest_root")
                        else None
                    ),
                )
                self._json(HTTPStatus.OK, self.server.state.configure(config))
                return
            if parsed.path == "/api/pull":
                result = self.server.state.pull(str(payload.get("job_id", "")), int(payload.get("index", -1)))
                self._json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/quality-scan":
                result = self.server.state.set_quality_assistance(
                    bool(payload.get("enabled", False)),
                    str(payload.get("job_id", "")),
                )
                self._json(HTTPStatus.OK, result)
                return
            self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "not found"})
        except ResourcePaused as error:
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"status": "paused", "message": str(error)})
        except ResourceAborted as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "aborted", "message": str(error)})
        except (KeyError, FileNotFoundError) as error:
            self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": str(error)})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(error)})
        except Exception as error:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "message": str(error)})


class ComparisonHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, state: ComparisonServiceState) -> None:
        super().__init__(server_address, ComparisonRequestHandler)
        self.state = state


def create_http_server(host: str, port: int, state: ComparisonServiceState) -> ComparisonHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("comparison service must bind to loopback")
    return ComparisonHTTPServer((host, port), state)
