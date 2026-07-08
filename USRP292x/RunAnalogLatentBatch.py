#!/usr/bin/env python3
"""Batch runner for analog latent-IQ USRP292x transport.

The output layout intentionally matches RunQpskFileBatchSpoolArq.py:

  run_dir/image_0000/merged_round0.bin

so existing usrp_runtime.py remote decode staging can keep scanning
image_*/merged_round*.bin without knowing the PHY changed.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALOG_LINK = PROJECT_ROOT / "USRP292x" / "AnalogLatentLink.py"
DEFAULT_INPUT = PROJECT_ROOT / "USRP292x" / "payloads" / "source_latent_wire_blob.bin"
DEFAULT_RUN_ROOT = PROJECT_ROOT / "USRP292x" / "analog_latent_runs"
CHILD_THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _thread_env_name, _thread_env_value in CHILD_THREAD_ENV.items():
    os.environ.setdefault(_thread_env_name, _thread_env_value)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from USRP292x import AnalogLatentLink as analog_link  # noqa: E402


@dataclass
class ImageRecord:
    index: int
    input_path: Path
    image_dir: Path
    passed: bool = False
    status: int = 0
    error: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw is None or str(raw).strip() == "" else float(raw)


def env_optional_float(name: str) -> float | None:
    raw = os.environ.get(name)
    return None if raw is None or str(raw).strip() == "" else float(raw)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None or str(raw).strip() == "" else int(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="USRP292x analog latent-IQ batch runner.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, default=None)
    source.add_argument("--input-list", type=Path, default=None)
    source.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--pattern", default="*.bin")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--cycle-inputs", action="store_true")
    parser.add_argument("--run-id", default=time.strftime("analog_%Y%m%d_%H%M%S"))
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--artifact-mode", choices=("minimal", "full", "board"), default=os.environ.get("USRP_ARTIFACT_MODE", "minimal"))
    parser.add_argument(
        "--in-process-local-codec",
        dest="in_process_local_codec",
        action="store_true",
        default=os.environ.get("ANALOG_IN_PROCESS_LOCAL_CODEC", "1") != "0",
        help="Run local AnalogLatentLink make/decode in this process instead of spawning Python per image.",
    )
    parser.add_argument(
        "--subprocess-local-codec",
        dest="in_process_local_codec",
        action="store_false",
        help="Use the older subprocess-per-stage local codec path.",
    )
    parser.add_argument(
        "--warmup-local-codec",
        dest="warmup_local_codec",
        action="store_true",
        default=os.environ.get("ANALOG_WARMUP_LOCAL_CODEC", "1") != "0",
        help="Preload the first local latent before per-image timing to keep setup out of transport metrics.",
    )
    parser.add_argument(
        "--no-warmup-local-codec",
        dest="warmup_local_codec",
        action="store_false",
        help="Include first-use latent loader/import setup in the first image timing.",
    )

    # Compatibility arguments accepted from usrp_runtime.py/QPSK runner.
    parser.add_argument("--max-arq-rounds", type=int, default=0)
    parser.add_argument("--decode-backend", default="python")
    parser.add_argument("--cpp-sync-mode", default="header")
    parser.add_argument("--decode-workers", type=int, default=1)
    parser.add_argument("--chunk-bytes", type=int, default=0)
    parser.add_argument("--fast-arq-profile", action="store_true")
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--rx-capture-mode", choices=("local", "remote-pull", "remote-decode"), default=os.environ.get("RX_CAPTURE_MODE", "local"))
    parser.add_argument("--remote-rx-ssh-target", default=os.environ.get("REMOTE_RX_SSH_TARGET", ""))
    parser.add_argument("--remote-rx-run-root", default=os.environ.get("REMOTE_RX_RUN_ROOT", "/tmp/usrp292x_remote_runs"))
    parser.add_argument("--remote-decode-bin", default=os.environ.get("REMOTE_DECODE_BIN", ""))

    parser.add_argument("--rx-control-host", default=os.environ.get("RX_CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--rx-control-port", type=int, default=env_int("RX_CONTROL_PORT", 29220))
    parser.add_argument("--tx-control-host", default=os.environ.get("TX_CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--tx-control-port", type=int, default=env_int("TX_CONTROL_PORT", 29221))
    parser.add_argument(
        "--tx-file-path-prefix-from",
        default=os.environ.get("TX_FILE_PATH_PREFIX_FROM", ""),
        help="local path prefix to rewrite before sending TX file paths to a containerized TX server.",
    )
    parser.add_argument(
        "--tx-file-path-prefix-to",
        default=os.environ.get("TX_FILE_PATH_PREFIX_TO", ""),
        help="TX server-visible replacement prefix for --tx-file-path-prefix-from.",
    )
    parser.add_argument("--tx-delay-sec", type=float, default=env_float("PERSISTENT_RX_TX_DELAY", 0.010))
    parser.add_argument("--rx-tail-sec", type=float, default=env_float("ANALOG_RX_TAIL_SEC", 0.300))
    parser.add_argument("--rx-timeout-sec", type=float, default=env_float("BATCH_RX_TIMEOUT_SEC", 30.0))
    parser.add_argument("--tx-timeout-sec", type=float, default=env_float("BATCH_TX_TIMEOUT_SEC", 30.0))

    parser.add_argument("--rate", type=float, default=env_float("RATE", 5_000_000.0))
    parser.add_argument("--sps", type=int, default=env_int("ANALOG_SPS", 4))
    parser.add_argument("--rrc-beta", type=float, default=env_float("ANALOG_RRC_BETA", 0.35))
    parser.add_argument("--rrc-span", type=int, default=env_int("ANALOG_RRC_SPAN", 8))
    parser.add_argument("--amp", type=int, default=env_int("AMPLITUDE", 3000))
    parser.add_argument("--zero-guard-samples", type=int, default=env_int("ANALOG_ZERO_GUARD_SAMPLES", 4096))
    parser.add_argument("--tail-guard-samples", type=int, default=env_int("ANALOG_TAIL_GUARD_SAMPLES", 4096))
    parser.add_argument("--cfo-pilot-symbols", type=int, default=env_int("ANALOG_CFO_PILOT_SYMBOLS", 1024))
    parser.add_argument("--sync-pilot-symbols", type=int, default=env_int("ANALOG_SYNC_PILOT_SYMBOLS", 1024))
    parser.add_argument("--data-block-symbols", type=int, default=env_int("ANALOG_DATA_BLOCK_SYMBOLS", 4096))
    parser.add_argument("--mid-pilot-symbols", type=int, default=env_int("ANALOG_MID_PILOT_SYMBOLS", 128))
    parser.add_argument("--cfo-seed", type=int, default=env_int("ANALOG_CFO_SEED", 1001))
    parser.add_argument("--sync-seed", type=int, default=env_int("ANALOG_SYNC_SEED", 1002))
    parser.add_argument("--mid-pilot-seed", type=int, default=env_int("ANALOG_MID_PILOT_SEED", 1003))
    parser.add_argument("--capture-margin-samples", type=int, default=env_int("ANALOG_CAPTURE_MARGIN_SAMPLES", 20_000))
    parser.add_argument("--rx-post-quantize", dest="rx_post_quantize", action="store_true", default=os.environ.get("ANALOG_RX_POST_QUANTIZE", "1") != "0")
    parser.add_argument("--no-rx-post-quantize", dest="rx_post_quantize", action="store_false")
    parser.add_argument("--scramble-key", default=os.environ.get("ANALOG_SCRAMBLE_KEY", ""))
    parser.add_argument("--scramble-key-hex", default=os.environ.get("ANALOG_SCRAMBLE_KEY_HEX", ""))
    parser.add_argument("--scramble-context", default=os.environ.get("ANALOG_SCRAMBLE_CONTEXT", ""))

    parser.add_argument("--sim-cfo-hz", type=float, default=env_float("ANALOG_SIM_CFO_HZ", 0.0))
    parser.add_argument("--sim-snr-db", type=float, default=env_optional_float("ANALOG_SIM_SNR_DB"))
    parser.add_argument("--sim-gain", type=float, default=env_float("ANALOG_SIM_GAIN", 1.0))
    parser.add_argument("--sim-phase-deg", type=float, default=env_float("ANALOG_SIM_PHASE_DEG", 0.0))
    parser.add_argument("--sim-phase-drift-deg", type=float, default=env_float("ANALOG_SIM_PHASE_DRIFT_DEG", 0.0))
    parser.add_argument("--sim-dc-real", type=float, default=env_float("ANALOG_SIM_DC_REAL", 0.0))
    parser.add_argument("--sim-dc-imag", type=float, default=env_float("ANALOG_SIM_DC_IMAG", 0.0))
    parser.add_argument("--sim-seed", type=int, default=env_int("ANALOG_SIM_SEED", 1))
    parser.add_argument("--sync-candidates", type=int, default=env_int("ANALOG_SYNC_CANDIDATES", 12))
    parser.add_argument("--min-sync-metric", type=float, default=env_float("ANALOG_MIN_SYNC_METRIC", 0.25))
    parser.add_argument("--robust-sync", dest="robust_sync", action="store_true", default=os.environ.get("ANALOG_ROBUST_SYNC", "1") != "0")
    parser.add_argument("--no-robust-sync", dest="robust_sync", action="store_false")
    parser.add_argument("--robust-cfo-max-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_MAX_HZ", 8000.0))
    parser.add_argument("--robust-cfo-step-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_STEP_HZ", 500.0))
    args = parser.parse_args()
    if args.count < 1:
        raise RuntimeError("--count must be positive")
    return args


def _validate_rx_capture_config(args: argparse.Namespace) -> None:
    """Sanity-check rx-capture-mode against rx-control-host before doing work.

    Catch the common mistake of selecting --rx-capture-mode=remote-pull/remote-decode
    but forgetting to override --rx-control-host away from 127.0.0.1, which would
    send the CAPTURE command to a local RX server with a remote-only file path.
    """
    mode = str(getattr(args, "rx_capture_mode", "local") or "local").strip().lower()
    if mode == "local":
        return
    host = str(getattr(args, "rx_control_host", "") or "").strip().lower()
    local_hosts = {"127.0.0.1", "localhost", "::1", ""}
    if host in local_hosts:
        raise SystemExit(
            f"--rx-capture-mode={mode} requires --rx-control-host to point at the "
            f"remote RX host (got {host or '<empty>'!r}). "
            f"Override with --rx-control-host <board-ip> or RX_CONTROL_HOST env."
        )


def load_inputs(args: argparse.Namespace) -> list[Path]:
    if args.input is not None:
        paths = [args.input]
    elif args.input_list is not None:
        paths = [
            Path(line.strip())
            for line in args.input_list.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    elif args.input_dir is not None:
        paths = sorted(path for path in args.input_dir.rglob(args.pattern) if path.is_file())
    else:
        paths = [DEFAULT_INPUT]

    if not paths:
        raise RuntimeError("no analog latent inputs found")
    resolved = [path.resolve() for path in paths]
    missing = [str(path) for path in resolved if not path.is_file()]
    if missing:
        raise RuntimeError(f"input payload not found: {missing[:3]}")

    if len(resolved) >= args.count:
        return resolved[:args.count]
    if len(resolved) == 1:
        return [resolved[0] for _ in range(args.count)]
    if args.cycle_inputs:
        return [resolved[idx % len(resolved)] for idx in range(args.count)]
    raise RuntimeError(f"count={args.count} requires {args.count} inputs, got {len(resolved)}")


def warmup_local_codec(args: argparse.Namespace, inputs: list[Path]) -> float:
    if not bool(getattr(args, "in_process_local_codec", False)):
        return 0.0
    if not bool(getattr(args, "warmup_local_codec", True)):
        return 0.0
    if not inputs:
        return 0.0
    started = time.monotonic()
    analog_link.load_latent(inputs[0])
    return time.monotonic() - started


def run_command(cmd: list[str], log_path: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")
    return proc


def send_tcp_command(host: str, port: int, line: str, timeout: float) -> str:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((line.rstrip() + "\n").encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data:
                    break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()
    except ConnectionRefusedError:
        return f"ERR_CONNECTION_REFUSED host={host} port={port}"
    except (socket.timeout, OSError):
        return f"ERR_TIMEOUT host={host} port={port}"


def run_control(host: str, port: int, line: str, log_path: Path, timeout: float) -> str:
    response = send_tcp_command(host, port, line, timeout)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(response + "\n", encoding="utf-8")
    if not response.startswith("OK"):
        raise RuntimeError(f"control command failed: {line}\n{response}")
    return response


def translate_tx_control_file_path(path: Path, prefix_from: str, prefix_to: str) -> str:
    source_text = str(prefix_from or "").strip()
    target_text = str(prefix_to or "").strip()
    if not source_text or not target_text:
        return str(path)
    try:
        source_root = Path(source_text).resolve()
        path_resolved = Path(path).resolve()
        relative = path_resolved.relative_to(source_root)
    except (OSError, ValueError):
        return str(path)
    target_root = target_text.rstrip("/\\")
    return f"{target_root}/{relative.as_posix()}"


# ── SSH/SCP helpers for remote-pull / remote-decode modes ──
# Mirrors RunQpskFileBatchSpoolArq.py: uses sshpass when SSHPASS is set,
# falls back to BatchMode=yes otherwise. Control master multiplexes auth.


def _ssh_base_args(timeout: int = 10, control_socket: str | None = None) -> list[str]:
    if os.environ.get("OPENAMP_SSH_RUNNER", "").strip().lower() == "docker":
        image = os.environ.get("OPENAMP_SSH_DOCKER_IMAGE", "iccomp-usrp-tx:latest")
        return [
            "docker",
            "run",
            "--rm",
            "-i",
            "-e",
            "SSHPASS",
            image,
            "sshpass",
            "-e",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "BatchMode=no",
            "-o",
            f"ConnectTimeout={timeout}",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
        ]
    sshpass = os.environ.get("SSHPASS")
    if sshpass is not None:
        args = [
            "sshpass",
            "-e",
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "BatchMode=no",
            "-o",
            f"ConnectTimeout={timeout}",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
        ]
    else:
        args = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            f"ConnectTimeout={timeout}",
        ]
    if control_socket:
        args += ["-o", f"ControlPath={control_socket}", "-o", "ControlMaster=no"]
    return args


def _scp_base_args(timeout: int = 10, control_socket: str | None = None) -> list[str]:
    sshpass = os.environ.get("SSHPASS")
    if sshpass is not None:
        args = [
            "sshpass",
            "-e",
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "BatchMode=no",
            "-o",
            f"ConnectTimeout={timeout}",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
        ]
    else:
        args = [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            f"ConnectTimeout={timeout}",
        ]
    if control_socket:
        args += ["-o", f"ControlPath={control_socket}", "-o", "ControlMaster=no"]
    return args


def _ssh_control_socket_path() -> str:
    return f"/tmp/usrp_analog_ssh_ctrl_{os.getpid()}"


def _ssh_start_control_master(target: str) -> subprocess.Popen | None:
    if (
        not target
        or os.environ.get("OPENAMP_SSH_RUNNER", "").strip().lower() == "docker"
        or os.environ.get("SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER", "").strip().lower()
        in {"1", "true", "yes", "on"}
    ):
        return None
    sock = _ssh_control_socket_path()
    subprocess.run(
        ["ssh", "-O", "exit", "-S", sock, target],
        capture_output=True,
        timeout=5,
    )
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass
    base = _ssh_base_args(timeout=15)
    cmd = base + [
        "-o", f"ControlPath={sock}",
        "-o", "ControlMaster=yes",
        "-o", "ControlPersist=300",
        "-o", "ServerAliveInterval=30",
        "-N",
        target,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if os.path.exists(sock):
            return proc
        time.sleep(0.1)
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    return None


def _run_external(cmd: list[str], log_path: Path, *, check: bool = True, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}"
        )
    return proc


def _remote_path(target: str, remote_path: str) -> str:
    return f"{target}:{remote_path}"


def push_file_to_remote(
    target: str,
    local_path: Path,
    remote_path: str,
    log_path: Path,
    *,
    control_socket: str | None = None,
    timeout: int = 30,
) -> None:
    if os.environ.get("OPENAMP_SSH_RUNNER", "").strip().lower() == "docker":
        remote_parent = str(PurePosixPath(remote_path).parent)
        remote_cmd = f"mkdir -p {shlex.quote(remote_parent)} && cat > {shlex.quote(remote_path)}"
        cmd = _ssh_base_args(timeout=timeout, control_socket=control_socket) + [target, remote_cmd]
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            input=local_path.read_bytes(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            check=False,
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text((proc.stdout or b"").decode("utf-8", errors="replace"), encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"remote file push failed ({proc.returncode}): {' '.join(cmd)}")
        return
    cmd = _scp_base_args(timeout=timeout, control_socket=control_socket)
    cmd += [str(local_path), _remote_path(target, remote_path)]
    _run_external(cmd, log_path, check=True, timeout=timeout + 5)


def pull_file_from_remote(
    target: str,
    remote_path: str,
    local_path: Path,
    log_path: Path,
    *,
    control_socket: str | None = None,
    timeout: int = 60,
) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("OPENAMP_SSH_RUNNER", "").strip().lower() == "docker":
        cmd = _ssh_base_args(timeout=timeout, control_socket=control_socket) + [
            target,
            f"cat {shlex.quote(remote_path)}",
        ]
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text((proc.stderr or b"").decode("utf-8", errors="replace"), encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(
                f"remote file pull failed ({proc.returncode}): {' '.join(cmd)}\n"
                f"{(proc.stderr or b'').decode('utf-8', errors='replace')}"
            )
        local_path.write_bytes(proc.stdout or b"")
        return
    cmd = _scp_base_args(timeout=timeout, control_socket=control_socket)
    cmd += [_remote_path(target, remote_path), str(local_path)]
    _run_external(cmd, log_path, check=True, timeout=timeout + 5)
    if not local_path.is_file():
        raise RuntimeError(f"remote pull succeeded but local file missing: {local_path}")


def run_remote_command(
    target: str,
    remote_argv: list[str],
    log_path: Path,
    *,
    control_socket: str | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run a shell-quoted command on the remote host via SSH."""
    remote_cmd = " ".join(shlex.quote(arg) for arg in remote_argv)
    full = _ssh_base_args(control_socket=control_socket) + [target, remote_cmd]
    return _run_external(full, log_path, check=True, timeout=timeout)


def cleanup_remote_file(
    target: str,
    remote_path: str,
    log_path: Path,
    *,
    control_socket: str | None = None,
) -> bool:
    if not remote_path:
        return False
    remote_cmd = "bash -lc " + shlex.quote(f"rm -f {shlex.quote(remote_path)}")
    full = _ssh_base_args(control_socket=control_socket) + [target, remote_cmd]
    try:
        _run_external(full, log_path, check=True, timeout=15.0)
        return True
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def build_remote_run_dir(args: argparse.Namespace, image: ImageRecord) -> str:
    """Remote directory under --remote-rx-run-root for this image."""
    root = str(args.remote_rx_run_root).rstrip("/")
    return f"{root}/{args.run_id}/image_{image.index:04d}"


def remote_python_for_decode(args: argparse.Namespace) -> str:
    """Pick the Python interpreter for remote AnalogLatentLink decode.

    Order: REMOTE_DECODE_PYTHON env → /usr/bin/python3 → python3.
    """
    py = os.environ.get("REMOTE_DECODE_PYTHON", "").strip()
    if py:
        return py
    return "python3"


def remote_analog_link_path(args: argparse.Namespace) -> str:
    """Remote path to AnalogLatentLink.py for remote-decode mode.

    Defaults to <REMOTE_USRP_PROJECT_ROOT>/USRP292x/AnalogLatentLink.py.
    Override with REMOTE_ANALOG_LINK_PATH env for ad-hoc testing.
    """
    env_override = os.environ.get("REMOTE_ANALOG_LINK_PATH", "").strip()
    if env_override:
        return env_override
    project_root = os.environ.get(
        "REMOTE_USRP_PROJECT_ROOT", "/home/user/iccomp_repo_selfcontained"
    ).rstrip("/")
    return f"{project_root}/USRP292x/AnalogLatentLink.py"


def remote_pythonpath_for_decode(args: argparse.Namespace) -> str:
    override = os.environ.get("REMOTE_ANALOG_PYTHONPATH", "").strip()
    if override:
        return override
    project_root = os.environ.get(
        "REMOTE_USRP_PROJECT_ROOT", "/home/user/iccomp_repo_selfcontained"
    ).rstrip("/")
    return f"{project_root}/scripts:{project_root}"


def analog_make_args(args: argparse.Namespace, image: ImageRecord, tx_sc16: Path, manifest: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "make",
        "--input",
        str(image.input_path),
        "--out-sc16",
        str(tx_sc16),
        "--manifest",
        str(manifest),
        "--job-id",
        f"image_{image.index:04d}",
        "--rate",
        str(args.rate),
        "--sps",
        str(args.sps),
        "--rrc-beta",
        str(args.rrc_beta),
        "--rrc-span",
        str(args.rrc_span),
        "--amp",
        str(args.amp),
        "--zero-guard-samples",
        str(args.zero_guard_samples),
        "--tail-guard-samples",
        str(args.tail_guard_samples),
        "--cfo-pilot-symbols",
        str(args.cfo_pilot_symbols),
        "--sync-pilot-symbols",
        str(args.sync_pilot_symbols),
        "--data-block-symbols",
        str(args.data_block_symbols),
        "--mid-pilot-symbols",
        str(args.mid_pilot_symbols),
        "--cfo-seed",
        str(getattr(args, "cfo_seed", 1001)),
        "--sync-seed",
        str(getattr(args, "sync_seed", 1002)),
        "--mid-pilot-seed",
        str(getattr(args, "mid_pilot_seed", 1003)),
        "--capture-margin-samples",
        str(args.capture_margin_samples),
        "--rx-post-quantize" if args.rx_post_quantize else "--no-rx-post-quantize",
    ]
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def analog_make_namespace(args: argparse.Namespace, image: ImageRecord, tx_sc16: Path, manifest: Path) -> argparse.Namespace:
    return argparse.Namespace(
        input=str(image.input_path),
        out_sc16=str(tx_sc16),
        manifest=str(manifest),
        job_id=f"image_{image.index:04d}",
        rate=float(args.rate),
        sps=int(args.sps),
        rrc_beta=float(args.rrc_beta),
        rrc_span=int(args.rrc_span),
        amp=int(args.amp),
        zero_guard_samples=int(args.zero_guard_samples),
        tail_guard_samples=int(args.tail_guard_samples),
        cfo_pilot_symbols=int(args.cfo_pilot_symbols),
        sync_pilot_symbols=int(args.sync_pilot_symbols),
        data_block_symbols=int(args.data_block_symbols),
        mid_pilot_symbols=int(args.mid_pilot_symbols),
        cfo_seed=int(getattr(args, "cfo_seed", 1001)),
        sync_seed=int(getattr(args, "sync_seed", 1002)),
        mid_pilot_seed=int(getattr(args, "mid_pilot_seed", 1003)),
        capture_margin_samples=int(args.capture_margin_samples),
        rx_post_quantize=bool(args.rx_post_quantize),
        scramble_key=str(getattr(args, "scramble_key", "") or ""),
        scramble_key_hex=str(getattr(args, "scramble_key_hex", "") or ""),
        scramble_context=str(getattr(args, "scramble_context", "") or ""),
    )


def analog_decode_args(args: argparse.Namespace, batch_rx: Path, manifest: Path, out_npz: Path, out_wire: Path, summary: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "decode",
        "--rx-sc16",
        str(batch_rx),
        "--manifest",
        str(manifest),
        "--out-npz",
        str(out_npz),
        "--out-wire",
        str(out_wire),
        "--summary-json",
        str(summary),
        "--sync-candidates",
        str(args.sync_candidates),
        "--min-sync-metric",
        str(args.min_sync_metric),
        "--robust-cfo-max-hz",
        str(args.robust_cfo_max_hz),
        "--robust-cfo-step-hz",
        str(args.robust_cfo_step_hz),
    ]
    cmd.append("--robust-sync" if args.robust_sync else "--no-robust-sync")
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def remote_analog_decode_args(
    args: argparse.Namespace,
    remote_batch_rx: str,
    remote_manifest: str,
    remote_npz: str,
    remote_wire: str,
    remote_summary: str,
) -> list[str]:
    cmd = [
        "env",
        f"PYTHONPATH={remote_pythonpath_for_decode(args)}",
        remote_python_for_decode(args),
        remote_analog_link_path(args),
        "decode",
        "--rx-sc16",
        remote_batch_rx,
        "--manifest",
        remote_manifest,
        "--out-npz",
        remote_npz,
        "--out-wire",
        remote_wire,
        "--summary-json",
        remote_summary,
        "--sync-candidates",
        str(args.sync_candidates),
        "--min-sync-metric",
        str(args.min_sync_metric),
        "--robust-cfo-max-hz",
        str(args.robust_cfo_max_hz),
        "--robust-cfo-step-hz",
        str(args.robust_cfo_step_hz),
    ]
    cmd.append("--robust-sync" if args.robust_sync else "--no-robust-sync")
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def analog_decode_namespace(
    args: argparse.Namespace,
    batch_rx: Path,
    manifest: Path,
    out_npz: Path,
    out_wire: Path,
    summary: Path,
) -> argparse.Namespace:
    return argparse.Namespace(
        rx_sc16=str(batch_rx),
        manifest=str(manifest),
        out_npz=str(out_npz),
        out_wire=str(out_wire),
        summary_json=str(summary),
        sync_candidates=int(args.sync_candidates),
        min_sync_metric=float(args.min_sync_metric),
        robust_sync=bool(args.robust_sync),
        robust_cfo_max_hz=float(args.robust_cfo_max_hz),
        robust_cfo_step_hz=float(args.robust_cfo_step_hz),
        scramble_key=str(getattr(args, "scramble_key", "") or ""),
        scramble_key_hex=str(getattr(args, "scramble_key_hex", "") or ""),
        scramble_context=str(getattr(args, "scramble_context", "") or ""),
    )


def simulated_channel_enabled(args: argparse.Namespace) -> bool:
    return (
        abs(float(args.sim_cfo_hz)) > 0.0
        or args.sim_snr_db is not None
        or abs(float(args.sim_gain) - 1.0) > 0.0
        or abs(float(args.sim_phase_deg)) > 0.0
        or abs(float(args.sim_phase_drift_deg)) > 0.0
        or abs(float(args.sim_dc_real)) > 0.0
        or abs(float(args.sim_dc_imag)) > 0.0
    )


def analog_simulate_args(args: argparse.Namespace, tx_sc16: Path, manifest: Path, batch_rx: Path, summary: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "simulate-channel",
        "--tx-sc16",
        str(tx_sc16),
        "--manifest",
        str(manifest),
        "--out-sc16",
        str(batch_rx),
        "--cfo-hz",
        str(args.sim_cfo_hz),
        "--gain",
        str(args.sim_gain),
        "--phase-deg",
        str(args.sim_phase_deg),
        "--phase-drift-deg",
        str(args.sim_phase_drift_deg),
        "--dc-real",
        str(args.sim_dc_real),
        "--dc-imag",
        str(args.sim_dc_imag),
        "--seed",
        str(args.sim_seed),
        "--summary-json",
        str(summary),
    ]
    if args.sim_snr_db is not None:
        cmd.extend(["--snr-db", str(args.sim_snr_db)])
    return cmd


def analog_simulate_namespace(args: argparse.Namespace, tx_sc16: Path, manifest: Path, batch_rx: Path, summary: Path) -> argparse.Namespace:
    return argparse.Namespace(
        tx_sc16=str(tx_sc16),
        manifest=str(manifest),
        out_sc16=str(batch_rx),
        cfo_hz=float(args.sim_cfo_hz),
        snr_db=None if args.sim_snr_db is None else float(args.sim_snr_db),
        gain=float(args.sim_gain),
        phase_deg=float(args.sim_phase_deg),
        phase_drift_deg=float(args.sim_phase_drift_deg),
        dc_real=float(args.sim_dc_real),
        dc_imag=float(args.sim_dc_imag),
        seed=int(args.sim_seed),
        summary_json=str(summary),
    )


def run_in_process_make(args: argparse.Namespace, image: ImageRecord, tx_sc16: Path, manifest_path: Path, log_path: Path) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        manifest = analog_link.make_waveform(analog_make_namespace(args, image, tx_sc16, manifest_path))
    except Exception:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    write_json(log_path, {
        "status": "ok",
        "mode": "in-process",
        "manifest": str(manifest_path),
        "out_sc16": str(tx_sc16),
        "tx_waveform_samples": manifest["tx_waveform_samples"],
        "capture_nsamps": manifest["capture_nsamps"],
    })
    return manifest


def run_in_process_simulate(args: argparse.Namespace, tx_sc16: Path, manifest_path: Path, batch_rx: Path, summary: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sim_summary = analog_link.simulate_channel(analog_simulate_namespace(args, tx_sc16, manifest_path, batch_rx, summary))
    except Exception:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    write_json(log_path, {
        "status": "ok",
        "mode": "in-process",
        "out_sc16": str(batch_rx),
        "simulated_cfo_hz": sim_summary["simulated_cfo_hz"],
        "simulated_snr_db": sim_summary["simulated_snr_db"],
    })


def run_in_process_decode(
    args: argparse.Namespace,
    batch_rx: Path,
    manifest_path: Path,
    out_npz: Path,
    out_wire: Path,
    decode_summary: Path,
    log_path: Path,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        summary = analog_link.decode_waveform(analog_decode_namespace(args, batch_rx, manifest_path, out_npz, out_wire, decode_summary))
    except Exception:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    write_json(log_path, {
        "status": "ok",
        "mode": "in-process",
        "summary_json": str(decode_summary),
        "sync_metric": summary["sync_metric"],
        "estimated_cfo_hz": summary["estimated_cfo_hz"],
    })
    return 0


def process_image(args: argparse.Namespace, image: ImageRecord) -> ImageRecord:
    started = time.monotonic()
    image.image_dir.mkdir(parents=True, exist_ok=True)
    tx_sc16 = image.image_dir / "tx_analog.sc16"
    batch_rx = image.image_dir / "batch_rx.sc16"
    manifest_path = image.image_dir / "manifest.json"
    out_npz = image.image_dir / "received_latent.npz"
    out_wire = image.image_dir / "merged_round0.bin"
    decode_summary = image.image_dir / "decode_summary.json"

    ssh_control_socket: str | None = None
    ssh_master_proc: subprocess.Popen | None = None
    remote_target = str(getattr(args, "remote_rx_ssh_target", "") or "").strip()
    use_in_process_local_codec = bool(getattr(args, "in_process_local_codec", False))

    try:
        make_started = time.monotonic()
        if use_in_process_local_codec:
            manifest = run_in_process_make(args, image, tx_sc16, manifest_path, image.image_dir / "make.log")
        else:
            run_command(analog_make_args(args, image, tx_sc16, manifest_path), image.image_dir / "make.log")
            manifest = read_json(manifest_path)
        make_wall_sec = time.monotonic() - make_started

        if args.dry_run:
            if simulated_channel_enabled(args):
                if use_in_process_local_codec:
                    run_in_process_simulate(
                        args,
                        tx_sc16,
                        manifest_path,
                        batch_rx,
                        image.image_dir / "simulate_channel_summary.json",
                        image.image_dir / "simulate_channel.log",
                    )
                else:
                    run_command(
                        analog_simulate_args(args, tx_sc16, manifest_path, batch_rx, image.image_dir / "simulate_channel_summary.json"),
                        image.image_dir / "simulate_channel.log",
                    )
            else:
                shutil.copy2(tx_sc16, batch_rx)
            rx_capture_wall_sec = 0.0
            tx_wall_sec = 0.0
            decode_started = time.monotonic()
            if use_in_process_local_codec:
                returncode = run_in_process_decode(
                    args,
                    batch_rx,
                    manifest_path,
                    out_npz,
                    out_wire,
                    decode_summary,
                    image.image_dir / "decode.log",
                )
            else:
                proc = run_command(
                    analog_decode_args(args, batch_rx, manifest_path, out_npz, out_wire, decode_summary),
                    image.image_dir / "decode.log",
                    check=False,
                )
                returncode = int(proc.returncode)
            decode_wall_sec = time.monotonic() - decode_started
            image.status = int(returncode)
            image.passed = returncode == 0 and out_wire.is_file() and decode_summary.is_file()
            if not image.passed:
                image.error = f"analog decode failed with status {returncode}"
        else:
            mode = str(args.rx_capture_mode or "local").strip().lower()
            if mode not in ("local", "remote-pull", "remote-decode"):
                raise RuntimeError(f"unsupported --rx-capture-mode: {mode}")
            if mode in ("remote-pull", "remote-decode"):
                if not remote_target:
                    raise RuntimeError(
                        f"--rx-capture-mode={mode} requires --remote-rx-ssh-target (e.g. user@100.x.y.z)"
                    )
                ssh_master_proc = _ssh_start_control_master(remote_target)
                ssh_control_socket = _ssh_control_socket_path() if ssh_master_proc else None

            capture_nsamps = int(manifest["capture_nsamps"])
            capture_duration = max(
                0.001,
                float(args.tx_delay_sec) + (capture_nsamps / float(args.rate)) + float(args.rx_tail_sec),
            )
            capture_timeout = max(args.rx_timeout_sec, capture_nsamps / float(args.rate) + 5.0)

            # Stage tx_sc16 + manifest on the remote RX host if needed
            if mode in ("remote-pull", "remote-decode"):
                remote_run_dir = build_remote_run_dir(args, image)
                remote_tx = f"{remote_run_dir}/tx_analog.sc16"
                remote_manifest = f"{remote_run_dir}/manifest.json"
                remote_batch_rx = f"{remote_run_dir}/batch_rx.sc16"
                run_remote_command(
                    remote_target,
                    ["mkdir", "-p", remote_run_dir],
                    image.image_dir / "remote_mkdir.log",
                    control_socket=ssh_control_socket,
                    timeout=20.0,
                )
                push_file_to_remote(
                    remote_target, tx_sc16, remote_tx,
                    image.image_dir / "remote_push_tx.log",
                    control_socket=ssh_control_socket,
                )
                push_file_to_remote(
                    remote_target, manifest_path, remote_manifest,
                    image.image_dir / "remote_push_manifest.log",
                    control_socket=ssh_control_socket,
                )
            else:
                remote_batch_rx = str(batch_rx)

            rx_started = time.monotonic()
            # Tell RX-side OtaRxPersistentServer to capture (rx_control_host points at RX)
            run_control(
                args.rx_control_host,
                args.rx_control_port,
                f"CAPTURE file={remote_batch_rx if mode != 'local' else batch_rx} duration={capture_duration:.6f} nsamps=0",
                image.image_dir / "rx_capture.log",
                capture_timeout,
            )
            time.sleep(max(0.0, float(args.tx_delay_sec)))
            tx_started = time.monotonic()
            # TX is always local — local OtaTxPersistentServer sends the locally-generated tx_sc16
            tx_control_file = translate_tx_control_file_path(
                tx_sc16,
                args.tx_file_path_prefix_from,
                args.tx_file_path_prefix_to,
            )
            run_control(
                args.tx_control_host,
                args.tx_control_port,
                f"SEND file={tx_control_file}",
                image.image_dir / "tx_send.log",
                args.tx_timeout_sec,
            )
            tx_wall_sec = time.monotonic() - tx_started
            run_control(
                args.rx_control_host,
                args.rx_control_port,
                f"WAIT timeout={capture_timeout:.6f}",
                image.image_dir / "rx_wait.log",
                capture_timeout,
            )
            rx_capture_wall_sec = time.monotonic() - rx_started

            if mode == "remote-pull":
                pull_file_from_remote(
                    remote_target, remote_batch_rx, batch_rx,
                    image.image_dir / "rx_pull.log",
                    control_socket=ssh_control_socket,
                    timeout=int(capture_timeout + 60),
                )

            decode_started = time.monotonic()
            if mode == "remote-decode":
                # Run AnalogLatentLink.py decode on the remote host, then pull results back.
                remote_npz = f"{remote_run_dir}/received_latent.npz"
                remote_wire = f"{remote_run_dir}/merged_round0.bin"
                remote_summary = f"{remote_run_dir}/decode_summary.json"
                remote_argv = remote_analog_decode_args(
                    args,
                    remote_batch_rx,
                    remote_manifest,
                    remote_npz,
                    remote_wire,
                    remote_summary,
                )
                # NB: remote argv ignores rx_post_quantize on the wire — RX-side quantization
                # happens at capture time, not decode time. Remote decode reads what was captured.
                run_remote_command(
                    remote_target,
                    remote_argv,
                    image.image_dir / "remote_decode.log",
                    control_socket=ssh_control_socket,
                    timeout=max(120.0, capture_timeout),
                )
                # Pull npz/wire/summary back to local image_dir paths
                pull_file_from_remote(
                    remote_target, remote_npz, out_npz,
                    image.image_dir / "remote_pull_npz.log",
                    control_socket=ssh_control_socket,
                    timeout=60,
                )
                pull_file_from_remote(
                    remote_target, remote_wire, out_wire,
                    image.image_dir / "remote_pull_wire.log",
                    control_socket=ssh_control_socket,
                    timeout=60,
                )
                pull_file_from_remote(
                    remote_target, remote_summary, decode_summary,
                    image.image_dir / "remote_pull_summary.log",
                    control_socket=ssh_control_socket,
                    timeout=30,
                )
                decode_wall_sec = time.monotonic() - decode_started
                image.status = 0 if (out_wire.is_file() and decode_summary.is_file()) else 1
                image.passed = out_wire.is_file() and decode_summary.is_file()
                if not image.passed:
                    image.error = "remote decode completed but expected outputs are missing"
            else:
                # local + remote-pull: decode locally
                if use_in_process_local_codec:
                    returncode = run_in_process_decode(
                        args,
                        batch_rx,
                        manifest_path,
                        out_npz,
                        out_wire,
                        decode_summary,
                        image.image_dir / "decode.log",
                    )
                else:
                    proc = run_command(
                        analog_decode_args(args, batch_rx, manifest_path, out_npz, out_wire, decode_summary),
                        image.image_dir / "decode.log",
                        check=False,
                    )
                    returncode = int(proc.returncode)
                decode_wall_sec = time.monotonic() - decode_started
                image.status = int(returncode)
                image.passed = returncode == 0 and out_wire.is_file() and decode_summary.is_file()
                if not image.passed:
                    image.error = f"analog decode failed with status {returncode}"

            # Remote cleanup — best effort, do not fail the run on cleanup errors
            if mode in ("remote-pull", "remote-decode"):
                for remote_file in (
                    remote_batch_rx, remote_tx, remote_manifest,
                    remote_npz if mode == "remote-decode" else "",
                    remote_wire if mode == "remote-decode" else "",
                    remote_summary if mode == "remote-decode" else "",
                ):
                    if remote_file:
                        cleanup_remote_file(
                            remote_target, remote_file,
                            image.image_dir / f"remote_cleanup_{PurePosixPath(remote_file).name}.log",
                            control_socket=ssh_control_socket,
                        )

        summary_data = read_json(decode_summary) if decode_summary.is_file() else {}
        image.records.append({
            "round": 0,
            "input": str(image.input_path),
            "tx_sc16": str(tx_sc16),
            "batch_rx": str(batch_rx),
            "manifest": str(manifest_path),
            "merged_bin": str(out_wire),
            "decode_summary": str(decode_summary),
            "rx_capture_mode": str(args.rx_capture_mode),
            "in_process_local_codec": use_in_process_local_codec,
            "remote_rx_ssh_target": remote_target or None,
            "waveform_samples": int(manifest.get("tx_waveform_samples") or 0),
            "capture_nsamps": int(manifest.get("capture_nsamps") or 0),
            "detected_airtime_ms": summary_data.get("detected_airtime_ms"),
            "sync_success": summary_data.get("sync_success"),
            "sync_search_mode": summary_data.get("sync_search_mode"),
            "sync_metric": summary_data.get("sync_metric"),
            "estimated_cfo_hz": summary_data.get("estimated_cfo_hz"),
            "evm_rms": summary_data.get("evm_rms"),
            "estimated_snr_db": summary_data.get("estimated_snr_db"),
            "rx_clipping_ratio": summary_data.get("rx_clipping_ratio"),
            "simulated_cfo_hz": float(args.sim_cfo_hz) if args.dry_run and simulated_channel_enabled(args) else None,
            "simulated_snr_db": float(args.sim_snr_db) if args.dry_run and simulated_channel_enabled(args) and args.sim_snr_db is not None else None,
            "make_wall_sec": make_wall_sec,
            "tx_wall_sec": tx_wall_sec,
            "rx_capture_wall_sec": rx_capture_wall_sec,
            "decode_wall_sec": decode_wall_sec,
            "total_wall_sec": time.monotonic() - started,
            "payload_is_bit_exact": False,
        })
    except Exception as exc:
        image.status = 1
        image.passed = False
        image.error = str(exc)
        image.records.append({
            "round": 0,
            "input": str(image.input_path),
            "error": image.error,
            "total_wall_sec": time.monotonic() - started,
            "payload_is_bit_exact": False,
        })
    finally:
        if ssh_master_proc is not None:
            try:
                ssh_master_proc.terminate()
                ssh_master_proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    ssh_master_proc.kill()
                except OSError:
                    pass
    return image


def _record_float_values(images: list[ImageRecord], field_name: str) -> list[float]:
    values: list[float] = []
    for image in images:
        for record in image.records:
            value = record.get(field_name)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
    return values


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _mean_transmitted_bytes(images: list[ImageRecord]) -> float:
    values: list[float] = []
    for image in images:
        for record in image.records:
            waveform_samples = int(record.get("waveform_samples") or 0)
            if waveform_samples > 0:
                values.append(float(waveform_samples * 4))
                continue
            tx_path = Path(str(record.get("tx_sc16") or ""))
            if tx_path.is_file():
                values.append(float(tx_path.stat().st_size))
    return _mean(values)


def build_transport_metrics(images: list[ImageRecord]) -> dict[str, Any]:
    total_values = _record_float_values(images, "total_wall_sec")
    make_values = _record_float_values(images, "make_wall_sec")
    tx_values = _record_float_values(images, "tx_wall_sec")
    rx_values = _record_float_values(images, "rx_capture_wall_sec")
    decode_values = _record_float_values(images, "decode_wall_sec")
    airtime_ms_values = _record_float_values(images, "detected_airtime_ms")
    total_mean = _mean(total_values)
    decode_mean = _mean(decode_values)
    airtime_sec_mean = _mean(airtime_ms_values) / 1000.0 if airtime_ms_values else 0.0
    merge_mean = 0.0
    return {
        "per_image_sec": total_mean,
        "total_wall_sec_mean": total_mean,
        "make_wall_sec_mean": _mean(make_values),
        "tx_wall_sec_mean": _mean(tx_values),
        "rx_capture_wall_sec_mean": _mean(rx_values),
        "decode_total_wall_sec_mean": decode_mean,
        "merge_wall_sec_mean": merge_mean,
        "payload_airtime_ms_mean": _mean(airtime_ms_values),
        "estimated_non_airtime_non_decode_non_merge_wall_sec_mean": max(
            0.0,
            total_mean - airtime_sec_mean - decode_mean - merge_mean,
        ),
        "compared_transmitted_bytes_mean": _mean_transmitted_bytes(images),
    }


def main() -> int:
    args = parse_args()
    _validate_rx_capture_config(args)
    inputs = load_inputs(args)
    run_dir = args.run_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    codec_warmup_wall_sec = warmup_local_codec(args, inputs)

    images = [
        ImageRecord(index=idx, input_path=path, image_dir=run_dir / f"image_{idx:04d}")
        for idx, path in enumerate(inputs)
    ]

    started = time.monotonic()
    completed: list[ImageRecord] = []
    for image in images:
        result = process_image(args, image)
        completed.append(result)
        if args.stop_on_fail and not result.passed:
            break
    passed_count = sum(1 for image in completed if image.passed)
    failed_count = sum(1 for image in completed if not image.passed)

    summary = {
        "version": 1,
        "phy": "analog-latent-iq",
        "runner": str(Path(__file__).resolve()),
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "target_count": int(args.count),
        "completed_count": len(completed),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_count": passed_count,
        "fail_count": failed_count,
        "pending_count": max(0, int(args.count) - len(completed)),
        "all_pass": len(completed) == int(args.count) and failed_count == 0,
        "payload_is_bit_exact": False,
        "dry_run": bool(args.dry_run),
        "in_process_local_codec": bool(getattr(args, "in_process_local_codec", False)),
        "codec_warmup_wall_sec": codec_warmup_wall_sec,
        "channel_mode": os.environ.get("JSCC_CHANNEL_MODE", ""),
        "rate": float(args.rate),
        "sps": int(args.sps),
        "rx_post_quantize": bool(args.rx_post_quantize),
        "robust_sync": bool(args.robust_sync),
        "sync_candidates": int(args.sync_candidates),
        "min_sync_metric": float(args.min_sync_metric),
        "robust_cfo_max_hz": float(args.robust_cfo_max_hz),
        "robust_cfo_step_hz": float(args.robust_cfo_step_hz),
        "scrambling_enabled": bool(args.scramble_key or args.scramble_key_hex),
        "simulated_channel": {
            "enabled": bool(args.dry_run and simulated_channel_enabled(args)),
            "cfo_hz": float(args.sim_cfo_hz),
            "snr_db": None if args.sim_snr_db is None else float(args.sim_snr_db),
            "gain": float(args.sim_gain),
            "phase_deg": float(args.sim_phase_deg),
            "phase_drift_deg": float(args.sim_phase_drift_deg),
            "dc_real": float(args.sim_dc_real),
            "dc_imag": float(args.sim_dc_imag),
            "seed": int(args.sim_seed),
        },
        "wall_sec": time.monotonic() - started,
        **build_transport_metrics(completed),
        "images": [
            {
                "index": image.index,
                "input": str(image.input_path),
                "image_dir": str(image.image_dir),
                "passed": image.passed,
                "status": image.status,
                "error": image.error,
                "rounds": len(image.records),
                "round_records": image.records,
            }
            for image in completed
        ],
    }
    write_json(run_dir / "batch_spool_summary.json", summary)
    print(json.dumps({
        "status": "ok" if summary["failed_count"] == 0 else "failed",
        "run_dir": str(run_dir),
        "passed_count": summary["passed_count"],
        "failed_count": summary["failed_count"],
    }, ensure_ascii=False))
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
