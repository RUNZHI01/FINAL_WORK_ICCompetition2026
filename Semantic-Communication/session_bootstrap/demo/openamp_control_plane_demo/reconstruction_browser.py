from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.request import ProxyHandler, Request, build_opener


@dataclass(frozen=True)
class ReconstructionBrowserConfig:
    board_host: str
    board_user: str
    board_password: str
    board_port: int
    original_dir: Path
    sources: tuple[dict[str, Any], ...]
    default_source: str
    manifest_root: Path | None = None
    pytorch_manifest: Path | None = None


class ProcessLike(Protocol):
    def poll(self): ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None): ...

    def kill(self) -> None: ...


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 1.0,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    opener = build_opener(ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("comparison service returned a non-object response")
    return result


class ReconstructionBrowserManager:
    def __init__(
        self,
        *,
        script_path: Path,
        cache_root: Path,
        host: str = "127.0.0.1",
        port: int = 8786,
        process_factory: Callable[[list[str]], ProcessLike] | None = None,
        http_json: Callable[..., dict[str, Any]] = _http_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("reconstruction browser must bind to loopback")
        self.script_path = Path(script_path)
        self.cache_root = Path(cache_root)
        self.host = host
        self.port = int(port)
        self.base_url = f"http://{host}:{self.port}/"
        self._process_factory = process_factory or self._spawn
        self._http_json = http_json
        self._sleep = sleep
        self._process: ProcessLike | None = None
        self._lock = threading.Lock()

    def _spawn(self, command: list[str]) -> ProcessLike:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.Popen(
            command,
            cwd=str(self.script_path.parent.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    def _healthy(self) -> bool:
        try:
            payload = self._http_json("GET", f"{self.base_url}api/health", timeout=0.5)
        except Exception:
            return False
        return payload.get("status") == "ok"

    def _start_if_needed(self) -> None:
        if self._healthy():
            return
        if self._process is not None and self._process.poll() is None:
            self._stop_owned_process()
        command = [
            sys.executable,
            "-m",
            "scripts.board_image_compare_server",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--cache-root",
            str(self.cache_root),
        ]
        self._process = self._process_factory(command)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self._healthy():
                return
            if self._process.poll() is not None:
                break
            self._sleep(0.1)
        self._stop_owned_process()
        raise RuntimeError("reconstruction comparison service failed to start")

    def open(self, config: ReconstructionBrowserConfig) -> str:
        with self._lock:
            self._start_if_needed()
            payload = {
                "board_host": config.board_host,
                "board_user": config.board_user,
                "board_password": config.board_password,
                "board_port": config.board_port,
                "original_dir": str(config.original_dir),
                "sources": list(config.sources),
                "default_source": config.default_source,
                "manifest_root": str(config.manifest_root) if config.manifest_root else "",
                "pytorch_manifest": str(config.pytorch_manifest) if config.pytorch_manifest else "",
            }
            self._http_json("POST", f"{self.base_url}api/config", payload=payload, timeout=5.0)
            return self.base_url

    def _stop_owned_process(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def close(self) -> None:
        with self._lock:
            self._stop_owned_process()
