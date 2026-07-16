from __future__ import annotations

import hashlib
import os
import shlex
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol

import paramiko

from .core import GateDecision, ResourceGate, ResourceSnapshot, natural_key


SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


class ResourcePaused(RuntimeError):
    pass


class ResourceAborted(RuntimeError):
    pass


@dataclass(frozen=True)
class BoardConnectionConfig:
    host: str
    user: str
    password: str
    port: int = 22


@dataclass(frozen=True)
class RemoteJob:
    id: str
    name: str
    path: str
    modified_at: float


class SshClientLike(Protocol):
    def exec_command(self, command: str, timeout: float | None = None): ...

    def open_sftp(self): ...

    def close(self) -> None: ...


def _cpu_fields(line: str) -> tuple[float, float]:
    fields = line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("invalid /proc/stat cpu line")
    values = [float(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0.0)
    return sum(values), idle


def calculate_cpu_percent(previous: str, current: str) -> float:
    previous_total, previous_idle = _cpu_fields(previous.splitlines()[0])
    current_total, current_idle = _cpu_fields(current.splitlines()[0])
    total_delta = current_total - previous_total
    idle_delta = current_idle - previous_idle
    if total_delta <= 0.0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def parse_meminfo_percent(meminfo: str) -> float:
    values: dict[str, float] = {}
    for line in meminfo.splitlines():
        name, separator, remainder = line.partition(":")
        if not separator:
            continue
        token = remainder.strip().split()[0] if remainder.strip() else ""
        if token:
            values[name] = float(token)
    total = values.get("MemTotal", 0.0)
    available = values.get("MemAvailable", 0.0)
    if total <= 0.0:
        raise ValueError("MemTotal is missing from /proc/meminfo")
    return max(0.0, min(100.0, 100.0 * (total - available) / total))


def _default_ssh_factory(config: BoardConnectionConfig) -> SshClientLike:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config.host,
        port=config.port,
        username=config.user,
        password=config.password,
        timeout=8.0,
        banner_timeout=8.0,
        auth_timeout=8.0,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


class BoardSftpClient:
    def __init__(
        self,
        config: BoardConnectionConfig,
        *,
        ssh_factory: Callable[[BoardConnectionConfig], SshClientLike] = _default_ssh_factory,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._ssh_factory = ssh_factory
        self._sleep = sleep
        self._ssh: SshClientLike | None = None
        self._sftp = None
        self._lock = threading.RLock()

    def _connect(self) -> SshClientLike:
        if self._ssh is None:
            self._ssh = self._ssh_factory(self.config)
        return self._ssh

    def _exec(self, command: str, *, timeout: float = 10.0) -> str:
        with self._lock:
            _, stdout, stderr = self._connect().exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")
            status = stdout.channel.recv_exit_status()
        if status != 0:
            raise RuntimeError(error.strip() or f"remote command failed with status {status}")
        return output

    def list_jobs(self, remote_root: str) -> list[RemoteJob]:
        root = shlex.quote(str(PurePosixPath(remote_root)))
        output = self._exec(
            f"for candidate in {root}/*/reconstructions; do "
            "[ -d \"$candidate\" ] || continue; "
            "stat -c '%Y|%n' \"$candidate\"; "
            "done 2>/dev/null"
        )
        jobs: list[RemoteJob] = []
        for line in output.splitlines():
            modified, separator, path = line.partition("|")
            if not separator or not path.strip():
                continue
            normalized = str(PurePosixPath(path.strip()))
            parent = PurePosixPath(normalized).parent.name
            job_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
            jobs.append(RemoteJob(job_id, parent, normalized, float(modified)))
        return sorted(jobs, key=lambda item: (-item.modified_at, natural_key(item.name)))

    def list_job_images(self, job_path: str) -> list[PurePosixPath]:
        quoted_path = shlex.quote(str(PurePosixPath(job_path)))
        output = self._exec(
            f"find {quoted_path} -mindepth 1 -maxdepth 1 -type f -printf '%p\\n' 2>/dev/null"
        )
        images = [
            PurePosixPath(line.strip())
            for line in output.splitlines()
            if PurePosixPath(line.strip()).suffix.casefold() in SUPPORTED_IMAGE_EXTENSIONS
        ]
        return sorted(images, key=lambda path: natural_key(path.name))

    def read_text(self, remote_path: str, *, max_bytes: int = 1024 * 1024) -> str:
        with self._lock:
            if self._sftp is None:
                self._sftp = self._connect().open_sftp()
            with self._sftp.open(remote_path, "rb") as stream:
                return stream.read(max_bytes).decode("utf-8", errors="replace")

    def sample_resources(self) -> ResourceSnapshot:
        command = "head -n 1 /proc/stat; cat /proc/meminfo"
        previous = self._exec(command, timeout=5.0)
        self._sleep(0.25)
        current = self._exec(command, timeout=5.0)
        return ResourceSnapshot(
            cpu_percent=calculate_cpu_percent(previous, current),
            memory_percent=parse_meminfo_percent(current),
        )

    def ensure_resources_available(self, gate: ResourceGate) -> tuple[ResourceSnapshot, GateDecision]:
        snapshot = self.sample_resources()
        decision = gate.evaluate(snapshot)
        if decision.action == "abort":
            raise ResourceAborted(decision.reason)
        if decision.action == "pause":
            raise ResourcePaused(decision.reason)
        return snapshot, decision

    def download(
        self,
        remote_path: str,
        local_path: Path,
        *,
        callback: Callable[[int, int], None] | None = None,
    ) -> None:
        with self._lock:
            if self._sftp is None:
                self._sftp = self._connect().open_sftp()
            self._sftp.get(remote_path, str(local_path), callback=callback)

    def close(self) -> None:
        with self._lock:
            if self._sftp is not None:
                self._sftp.close()
                self._sftp = None
            if self._ssh is not None:
                self._ssh.close()
                self._ssh = None


class ImageCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, host: str, job_path: str, remote_file: str) -> Path:
        cache_key = hashlib.sha256(f"{host}\0{job_path}".encode("utf-8")).hexdigest()[:20]
        safe_host = "".join(character if character.isalnum() or character in ".-" else "_" for character in host)
        return self.root / safe_host / cache_key / PurePosixPath(remote_file).name

    def download_atomic(
        self,
        client: BoardSftpClient,
        remote_file: str,
        target: Path,
        *,
        callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        target = Path(target)
        if target.is_file():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        partial.unlink(missing_ok=True)
        try:
            client.download(remote_file, partial, callback=callback)
            os.replace(partial, target)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return target
