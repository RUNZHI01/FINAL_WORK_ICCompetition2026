#!/usr/bin/env python3
"""Batch runner for analog latent-IQ USRP292x transport.

The output layout intentionally matches RunQpskFileBatchSpoolArq.py:

  run_dir/image_0000/merged_round0.bin

so existing usrp_runtime.py remote decode staging can keep scanning
image_*/merged_round*.bin without knowing the PHY changed.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import queue
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
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


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


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
    parser.add_argument(
        "--remote-cleanup-mode",
        choices=("sync", "async", "skip"),
        default=os.environ.get("ANALOG_REMOTE_CLEANUP_MODE", "async"),
        help="How to remove temporary RX files from the board after remote-pull/remote-decode.",
    )
    parser.add_argument("--remote-rx-ssh-target", default=os.environ.get("REMOTE_RX_SSH_TARGET", ""))
    parser.add_argument("--remote-rx-run-root", default=os.environ.get("REMOTE_RX_RUN_ROOT", "/tmp/usrp292x_remote_runs"))
    parser.add_argument("--remote-decode-bin", default=os.environ.get("REMOTE_DECODE_BIN", ""))
    parser.add_argument(
        "--remote-decode-result-mode",
        choices=("pull", "remote-dir"),
        default=os.environ.get("ANALOG_REMOTE_DECODE_RESULT_MODE", "pull"),
        help="pull all remote decode outputs locally, or publish decoded latent files on the board and pull only summaries.",
    )
    parser.add_argument(
        "--remote-decoded-output-dir",
        default=os.environ.get("ANALOG_REMOTE_DECODED_OUTPUT_DIR", ""),
        help="Board-side flat directory for --remote-decode-result-mode=remote-dir decoded latent .npz files.",
    )

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
    parser.add_argument(
        "--pipeline-depth",
        type=int,
        default=env_int("ANALOG_PIPELINE_DEPTH", 1),
        help="Number of IQ remote-decode slots to keep in flight. Depth 1 preserves serial behavior.",
    )

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
    parser.add_argument("--sync-profile", default=os.environ.get("ANALOG_SYNC_PROFILE", ""))
    parser.add_argument("--sync-candidates", type=int, default=env_int("ANALOG_SYNC_CANDIDATES", 12))
    parser.add_argument("--fast-sync-candidates", type=int, default=env_int("ANALOG_FAST_SYNC_CANDIDATES", 4))
    parser.add_argument(
        "--fast-sync-search-window-symbols",
        type=int,
        default=env_int("ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS", 1024),
    )
    parser.add_argument("--fallback-sync-candidates", type=int, default=env_int("ANALOG_FALLBACK_SYNC_CANDIDATES", 12))
    parser.add_argument(
        "--fallback-sync-search-window-symbols",
        type=int,
        default=env_int("ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS", 4096),
    )
    parser.add_argument("--min-sync-metric", type=float, default=env_float("ANALOG_MIN_SYNC_METRIC", 0.25))
    parser.add_argument("--robust-sync", dest="robust_sync", action="store_true", default=os.environ.get("ANALOG_ROBUST_SYNC", "1") != "0")
    parser.add_argument("--no-robust-sync", dest="robust_sync", action="store_false")
    parser.add_argument("--robust-cfo-max-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_MAX_HZ", 8000.0))
    parser.add_argument("--robust-cfo-step-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_STEP_HZ", 500.0))
    parser.add_argument("--sync-search-window-symbols", type=int, default=env_int("ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS", 4096))
    args = parser.parse_args()
    if args.count < 1:
        raise RuntimeError("--count must be positive")
    return args


def sync_search_center_symbol(args: argparse.Namespace) -> int:
    delay_symbols = int(round(float(getattr(args, "tx_delay_sec", 0.0)) * float(args.rate) / float(args.sps)))
    guard_symbols = int(getattr(args, "zero_guard_samples", 0)) // max(int(args.sps), 1)
    cfo_symbols = 2 * int(getattr(args, "cfo_pilot_symbols", 0))
    return max(0, delay_symbols + guard_symbols + cfo_symbols)


def append_sync_search_window_args(cmd: list[str], args: argparse.Namespace) -> None:
    window_symbols = int(getattr(args, "sync_search_window_symbols", 0) or 0)
    if window_symbols <= 0 or bool(getattr(args, "dry_run", False)):
        return
    cmd.extend(["--sync-search-window-symbols", str(window_symbols)])


def sync_profile_value(args: argparse.Namespace) -> str:
    return str(getattr(args, "sync_profile", "") or "").strip()


def append_fast_first_sync_args(cmd: list[str], args: argparse.Namespace) -> None:
    sync_profile = sync_profile_value(args)
    if not sync_profile:
        return
    cmd.extend(["--sync-profile", sync_profile])
    cmd.extend(["--fast-sync-candidates", str(int(getattr(args, "fast_sync_candidates", 4) or 4))])
    cmd.extend([
        "--fast-sync-search-window-symbols",
        str(int(getattr(args, "fast_sync_search_window_symbols", 1024) or 1024)),
    ])
    cmd.extend(["--fallback-sync-candidates", str(int(getattr(args, "fallback_sync_candidates", 12) or 12))])
    cmd.extend([
        "--fallback-sync-search-window-symbols",
        str(int(getattr(args, "fallback_sync_search_window_symbols", 4096) or 4096)),
    ])


def fast_first_sync_request_fields(args: argparse.Namespace) -> dict[str, Any]:
    sync_profile = sync_profile_value(args)
    if not sync_profile:
        return {}
    return {
        "sync_profile": sync_profile,
        "fast_sync_candidates": int(getattr(args, "fast_sync_candidates", 4) or 4),
        "fast_sync_search_window_symbols": int(getattr(args, "fast_sync_search_window_symbols", 1024) or 1024),
        "fallback_sync_candidates": int(getattr(args, "fallback_sync_candidates", 12) or 12),
        "fallback_sync_search_window_symbols": int(getattr(args, "fallback_sync_search_window_symbols", 4096) or 4096),
    }


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
            "LogLevel=ERROR",
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
            "LogLevel=ERROR",
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
            "LogLevel=ERROR",
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
            "LogLevel=ERROR",
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
            "LogLevel=ERROR",
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
    stdout_path: Path | None = None
    proc: subprocess.Popen[Any] | None = None
    timed_out = False
    try:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", errors="replace", delete=False) as stdout_file:
            stdout_path = Path(stdout_file.name)
            proc = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
            )
            try:
                returncode = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(getattr(proc, "pid", ""))],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    else:
                        proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                returncode = 124
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
    finally:
        if stdout_path is not None:
            try:
                stdout_path.unlink()
            except OSError:
                pass
    if timed_out:
        stdout = (stdout + f"\nTimeoutExpired: command timed out after {timeout:.1f}s\n").lstrip()
    proc = subprocess.CompletedProcess(cmd, int(returncode or 0), stdout=stdout, stderr="")
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
    remote_parent = str(PurePosixPath(remote_path).parent)
    if remote_parent and remote_parent != ".":
        run_remote_command(
            target,
            ["mkdir", "-p", remote_parent],
            log_path.with_name(f"{log_path.stem}_mkdir.log"),
            control_socket=control_socket,
            timeout=timeout,
        )
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


def pull_files_from_remote_tar(
    target: str,
    remote_dir: str,
    remote_to_local: dict[str, Path],
    log_path: Path,
    *,
    control_socket: str | None = None,
    timeout: int = 60,
) -> None:
    if not remote_to_local:
        return
    for local_path in remote_to_local.values():
        local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_names = list(remote_to_local)
    remote_cmd = (
        f"cd {shlex.quote(remote_dir)} && "
        f"tar czf - {' '.join(shlex.quote(name) for name in remote_names)}"
    )
    full = _ssh_base_args(timeout=timeout, control_socket=control_socket) + [target, remote_cmd]
    proc = subprocess.run(
        full,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=timeout + 5,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text((proc.stderr or b"").decode("utf-8", errors="replace"), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"remote tar pull failed ({proc.returncode}): {' '.join(full)}\n"
            f"{(proc.stderr or b'').decode('utf-8', errors='replace')}"
        )
    with tarfile.open(fileobj=io.BytesIO(proc.stdout or b""), mode="r:gz") as archive:
        members = {PurePosixPath(member.name).name: member for member in archive.getmembers() if member.isfile()}
        missing = [name for name in remote_names if name not in members]
        if missing:
            raise RuntimeError(f"remote tar pull missing files: {', '.join(missing)}")
        for remote_name, local_path in remote_to_local.items():
            extracted = archive.extractfile(members[remote_name])
            if extracted is None:
                raise RuntimeError(f"remote tar member is not readable: {remote_name}")
            local_path.write_bytes(extracted.read())


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


def cleanup_remote_file_async(
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
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("wb") as log_handle:
            subprocess.Popen(
                full,
                cwd=PROJECT_ROOT,
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
            )
        return True
    except OSError as exc:
        log_path.write_text(str(exc), encoding="utf-8")
        return False


def _remote_cleanup_command(remote_paths: list[str]) -> str:
    return "bash -lc " + shlex.quote("rm -f -- " + " ".join(shlex.quote(path) for path in remote_paths if path))


def cleanup_remote_files(
    target: str,
    remote_paths: list[str],
    log_path: Path,
    *,
    control_socket: str | None = None,
) -> bool:
    paths = [path for path in remote_paths if path]
    if not paths:
        return False
    full = _ssh_base_args(control_socket=control_socket) + [target, _remote_cleanup_command(paths)]
    try:
        _run_external(full, log_path, check=True, timeout=15.0)
        return True
    except (RuntimeError, subprocess.TimeoutExpired):
        return False


def cleanup_remote_files_async(
    target: str,
    remote_paths: list[str],
    log_path: Path,
    *,
    control_socket: str | None = None,
) -> bool:
    paths = [path for path in remote_paths if path]
    if not paths:
        return False
    full = _ssh_base_args(control_socket=control_socket) + [target, _remote_cleanup_command(paths)]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("wb") as log_handle:
            subprocess.Popen(
                full,
                cwd=PROJECT_ROOT,
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
            )
        return True
    except OSError as exc:
        log_path.write_text(str(exc), encoding="utf-8")
        return False


def build_remote_run_dir(args: argparse.Namespace, image: ImageRecord) -> str:
    """Remote directory under --remote-rx-run-root for this image."""
    root = str(args.remote_rx_run_root).rstrip("/")
    return f"{root}/{args.run_id}/image_{image.index:04d}"


def remote_python_for_decode(args: argparse.Namespace) -> str:
    """Pick the Python interpreter for remote AnalogLatentLink decode.

    Keep this as a single executable path. TVM-style composite values such as
    "env FOO=1 /path/python" are command fragments, not argv[0] here.
    """
    py = os.environ.get("REMOTE_DECODE_PYTHON", "").strip()
    if py and not py.startswith("-") and len(shlex.split(py)) == 1:
        return py
    return "/home/user/venv/bin/python"


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


class RemoteAnalogDecodeWorker:
    def __init__(
        self,
        proc: subprocess.Popen[str],
        stderr_handle: Any,
        response_queue: queue.Queue[str],
        reader_thread: threading.Thread,
        ready_response: dict[str, Any],
        startup_wall_sec: float,
    ) -> None:
        self.proc = proc
        self._stderr_handle = stderr_handle
        self._responses = response_queue
        self._reader_thread = reader_thread
        self.ready_response = ready_response
        self.startup_wall_sec = startup_wall_sec

    @classmethod
    def start(
        cls,
        target: str,
        args: argparse.Namespace,
        log_path: Path,
        *,
        control_socket: str | None = None,
    ) -> "RemoteAnalogDecodeWorker":
        startup_started = time.monotonic()
        amp = int(getattr(args, "amp", 3000) or 3000)
        remote_env = [
            f"PYTHONPATH={remote_pythonpath_for_decode(args)}",
            f"ANALOG_DECODE_PIPELINE_WARMUP={os.environ.get('ANALOG_DECODE_PIPELINE_WARMUP', '1') or '1'}",
            f"ANALOG_DECODE_WARMUP_SHAPE={os.environ.get('ANALOG_DECODE_WARMUP_SHAPE', '1,32,32,32') or '1,32,32,32'}",
            f"RATE={float(getattr(args, 'rate', 5_000_000.0) or 5_000_000.0)}",
            f"ANALOG_SPS={int(getattr(args, 'sps', 4) or 4)}",
            f"ANALOG_AMPLITUDE={amp}",
            f"AMPLITUDE={amp}",
            f"ANALOG_RRC_BETA={float(getattr(args, 'rrc_beta', 0.35) or 0.35)}",
            f"ANALOG_RRC_SPAN={int(getattr(args, 'rrc_span', 8) or 8)}",
            f"ANALOG_ZERO_GUARD_SAMPLES={int(getattr(args, 'zero_guard_samples', 4096) or 4096)}",
            f"ANALOG_TAIL_GUARD_SAMPLES={int(getattr(args, 'tail_guard_samples', 4096) or 4096)}",
            f"ANALOG_CFO_PILOT_SYMBOLS={int(getattr(args, 'cfo_pilot_symbols', 1024) or 1024)}",
            f"ANALOG_SYNC_PILOT_SYMBOLS={int(getattr(args, 'sync_pilot_symbols', 1024) or 1024)}",
            f"ANALOG_DATA_BLOCK_SYMBOLS={int(getattr(args, 'data_block_symbols', 4096) or 4096)}",
            f"ANALOG_MID_PILOT_SYMBOLS={int(getattr(args, 'mid_pilot_symbols', 128) or 128)}",
            f"ANALOG_CAPTURE_MARGIN_SAMPLES={int(getattr(args, 'capture_margin_samples', 20000) or 20000)}",
            f"ANALOG_RX_POST_QUANTIZE={'1' if bool(getattr(args, 'rx_post_quantize', True)) else '0'}",
            f"ANALOG_SYNC_PROFILE={sync_profile_value(args)}",
            f"ANALOG_SYNC_CANDIDATES={int(getattr(args, 'sync_candidates', 12) or 12)}",
            f"ANALOG_FAST_SYNC_CANDIDATES={int(getattr(args, 'fast_sync_candidates', 4) or 4)}",
            f"ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS={int(getattr(args, 'fast_sync_search_window_symbols', 1024) or 1024)}",
            f"ANALOG_FALLBACK_SYNC_CANDIDATES={int(getattr(args, 'fallback_sync_candidates', 12) or 12)}",
            f"ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS={int(getattr(args, 'fallback_sync_search_window_symbols', 4096) or 4096)}",
            f"ANALOG_MIN_SYNC_METRIC={float(getattr(args, 'min_sync_metric', 0.25) or 0.25)}",
            f"ANALOG_ROBUST_SYNC={'1' if bool(getattr(args, 'robust_sync', True)) else '0'}",
            f"ANALOG_ROBUST_CFO_MAX_HZ={float(getattr(args, 'robust_cfo_max_hz', 8000.0) or 8000.0)}",
            f"ANALOG_ROBUST_CFO_STEP_HZ={float(getattr(args, 'robust_cfo_step_hz', 500.0) or 500.0)}",
            f"ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS={int(getattr(args, 'sync_search_window_symbols', 0) or 0)}",
        ]
        remote_argv = [
            "env",
            *remote_env,
            remote_python_for_decode(args),
            "-u",
            remote_analog_link_path(args),
            "decode-server",
        ]
        remote_cmd = " ".join(shlex.quote(arg) for arg in remote_argv)
        full = _ssh_base_args(timeout=15, control_socket=control_socket) + [target, remote_cmd]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_handle = log_path.open("ab")
        proc = subprocess.Popen(
            full,
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_handle,
            text=True,
            bufsize=1,
            shell=False,
        )
        responses: queue.Queue[str] = queue.Queue()

        def reader() -> None:
            if proc.stdout is None:
                return
            for stdout_line in proc.stdout:
                responses.put(stdout_line)

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()
        timeout = float(os.environ.get("ANALOG_REMOTE_DECODE_WORKER_START_TIMEOUT_SEC", "120") or "120")
        deadline = time.monotonic() + timeout
        ready_line = ""
        ready_response: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                candidate_line = responses.get(timeout=remaining)
            except queue.Empty as exc:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                stderr_handle.close()
                raise RuntimeError(f"remote decode worker did not become ready after {timeout:.1f}s") from exc
            if candidate_line.strip():
                try:
                    candidate_response = json.loads(candidate_line)
                except json.JSONDecodeError:
                    if proc.poll() is not None:
                        stderr_handle.close()
                        raise RuntimeError(f"remote decode worker exited before ready with status {proc.returncode}")
                    continue
                if not isinstance(candidate_response, dict):
                    if proc.poll() is not None:
                        stderr_handle.close()
                        raise RuntimeError(f"remote decode worker exited before ready with status {proc.returncode}")
                    continue
                ready_line = candidate_line
                ready_response = candidate_response
                break
            if proc.poll() is not None:
                stderr_handle.close()
                raise RuntimeError(f"remote decode worker exited before ready with status {proc.returncode}")
        if not ready_line or ready_response is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            stderr_handle.close()
            raise RuntimeError(f"remote decode worker did not become ready after {timeout:.1f}s")
        startup_wall_sec = time.monotonic() - startup_started
        if str(ready_response.get("status") or "").lower() != "ready":
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            stderr_handle.close()
            raise RuntimeError(f"remote decode worker did not return ready status: {ready_line.strip()}")
        return cls(proc, stderr_handle, responses, reader_thread, ready_response, startup_wall_sec)

    def decode(
        self,
        request: dict[str, Any],
        log_path: Path,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        if self.proc.poll() is not None:
            raise RuntimeError(f"remote decode worker exited with status {self.proc.returncode}")
        if self.proc.stdin is None:
            raise RuntimeError("remote decode worker stdin is closed")
        self.proc.stdin.write(json.dumps(request, ensure_ascii=True) + "\n")
        self.proc.stdin.flush()
        try:
            line = self._responses.get(timeout=timeout)
        except queue.Empty as exc:
            self.close(kill=True)
            raise RuntimeError(f"remote decode worker timed out after {timeout:.1f}s") from exc
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(line, encoding="utf-8")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"remote decode worker returned invalid JSON: {line.strip()}") from exc
        if str(response.get("status") or "").lower() != "ok":
            raise RuntimeError(str(response.get("error") or "remote decode worker failed"))
        return subprocess.CompletedProcess(args=["decode-server"], returncode=0, stdout=line, stderr="")

    def close(self, *, kill: bool = False) -> None:
        try:
            if self.proc.poll() is None and self.proc.stdin is not None and not kill:
                self.proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except OSError:
            pass
        if kill and self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        try:
            self._stderr_handle.close()
        except OSError:
            pass


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
    append_fast_first_sync_args(cmd, args)
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
    append_fast_first_sync_args(cmd, args)
    append_sync_search_window_args(cmd, args)
    cmd.append("--robust-sync" if args.robust_sync else "--no-robust-sync")
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def remote_analog_decode_request(
    args: argparse.Namespace,
    remote_batch_rx: str,
    remote_manifest: str,
    remote_npz: str,
    remote_wire: str,
    remote_summary: str,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "cmd": "decode",
        "rx_sc16": remote_batch_rx,
        "manifest": remote_manifest,
        "out_npz": remote_npz,
        "out_wire": remote_wire,
        "summary_json": remote_summary,
        "sync_candidates": int(args.sync_candidates),
        "min_sync_metric": float(args.min_sync_metric),
        "robust_cfo_max_hz": float(args.robust_cfo_max_hz),
        "robust_cfo_step_hz": float(args.robust_cfo_step_hz),
        "robust_sync": bool(args.robust_sync),
        "sync_search_window_symbols": 0
        if bool(getattr(args, "dry_run", False))
        else int(getattr(args, "sync_search_window_symbols", 0) or 0),
        "scramble_key": str(getattr(args, "scramble_key", "") or ""),
        "scramble_key_hex": str(getattr(args, "scramble_key_hex", "") or ""),
        "scramble_context": str(getattr(args, "scramble_context", "") or ""),
    }
    request.update(fast_first_sync_request_fields(args))
    return request


def remote_decoded_output_dir(args: argparse.Namespace) -> str:
    configured = str(getattr(args, "remote_decoded_output_dir", "") or "").strip().rstrip("/")
    if configured:
        return configured
    return f"{str(getattr(args, 'remote_rx_run_root', '/tmp/usrp292x_remote_runs')).rstrip('/')}/{args.run_id}_rx"


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
        sync_profile=sync_profile_value(args),
        sync_candidates=int(args.sync_candidates),
        fast_sync_candidates=int(getattr(args, "fast_sync_candidates", 4) or 4),
        fast_sync_search_window_symbols=int(getattr(args, "fast_sync_search_window_symbols", 1024) or 1024),
        fallback_sync_candidates=int(getattr(args, "fallback_sync_candidates", 12) or 12),
        fallback_sync_search_window_symbols=int(getattr(args, "fallback_sync_search_window_symbols", 4096) or 4096),
        min_sync_metric=float(args.min_sync_metric),
        robust_sync=bool(args.robust_sync),
        robust_cfo_max_hz=float(args.robust_cfo_max_hz),
        robust_cfo_step_hz=float(args.robust_cfo_step_hz),
        sync_search_center_symbol=-1,
        sync_search_window_symbols=0
        if bool(getattr(args, "dry_run", False))
        else int(getattr(args, "sync_search_window_symbols", 0) or 0),
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
    image.status = 0
    image.passed = False
    image.error = ""
    image.image_dir.mkdir(parents=True, exist_ok=True)
    tx_sc16 = image.image_dir / "tx_analog.sc16"
    batch_rx = image.image_dir / "batch_rx.sc16"
    manifest_path = image.image_dir / "manifest.json"
    out_npz = image.image_dir / "received_latent.npz"
    out_wire = image.image_dir / "merged_round0.bin"
    decode_summary = image.image_dir / "decode_summary.json"

    shared_ssh_control_socket = str(getattr(args, "ssh_control_socket", "") or "").strip()
    ssh_control_socket: str | None = shared_ssh_control_socket or None
    ssh_master_proc: subprocess.Popen | None = None
    remote_target = str(getattr(args, "remote_rx_ssh_target", "") or "").strip()
    use_in_process_local_codec = bool(getattr(args, "in_process_local_codec", False))
    rx_pull_wall_sec = 0.0
    remote_cleanup_wall_sec = 0.0
    merge_wall_sec = 0.0
    remote_cleanup_mode = str(
        getattr(args, "remote_cleanup_mode", os.environ.get("ANALOG_REMOTE_CLEANUP_MODE", "sync")) or "sync"
    ).strip().lower()
    if remote_cleanup_mode not in {"sync", "async", "skip"}:
        remote_cleanup_mode = "sync"
    remote_decode_result_mode = str(
        getattr(args, "remote_decode_result_mode", os.environ.get("ANALOG_REMOTE_DECODE_RESULT_MODE", "pull")) or "pull"
    ).strip().lower()
    if remote_decode_result_mode not in {"pull", "remote-dir"}:
        remote_decode_result_mode = "pull"
    remote_decoded_dir = remote_decoded_output_dir(args) if remote_decode_result_mode == "remote-dir" else ""
    remote_received_npz = ""
    remote_dir_publish_wall_sec = 0.0
    retry_wait_wall_sec = 0.0

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
                if not ssh_control_socket:
                    ssh_master_proc = _ssh_start_control_master(remote_target)
                    ssh_control_socket = _ssh_control_socket_path() if ssh_master_proc else None

            capture_nsamps = int(manifest["capture_nsamps"])
            capture_duration = max(
                0.001,
                float(args.tx_delay_sec) + (capture_nsamps / float(args.rate)) + float(args.rx_tail_sec),
            )
            capture_timeout = max(args.rx_timeout_sec, capture_nsamps / float(args.rate) + 5.0)

            # Stage only what the selected RX mode consumes on the remote host.
            # remote-pull captures remotely but decodes locally, so only the
            # RX output path needs to exist on the board.
            if mode in ("remote-pull", "remote-decode"):
                remote_run_dir = build_remote_run_dir(args, image)
                remote_batch_rx = f"{remote_run_dir}/batch_rx.sc16"
                remote_tx = ""
                remote_manifest = f"{remote_run_dir}/manifest.json" if mode == "remote-decode" else ""
                remote_decode_worker = getattr(args, "remote_decode_worker", None)
                if mode == "remote-decode" and remote_decode_worker is None:
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
                pull_started = time.monotonic()
                pull_file_from_remote(
                    remote_target, remote_batch_rx, batch_rx,
                    image.image_dir / "rx_pull.log",
                    control_socket=ssh_control_socket,
                    timeout=int(capture_timeout + 60),
                )
                rx_pull_wall_sec = time.monotonic() - pull_started

            decode_started = time.monotonic()
            if mode == "remote-decode":
                # Run AnalogLatentLink.py decode on the remote host, then pull results back.
                if remote_decode_result_mode == "remote-dir":
                    remote_npz = f"{remote_decoded_dir}/{image.index:08d}.npz"
                    remote_wire = ""
                    remote_received_npz = remote_npz
                else:
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
                remote_request = remote_analog_decode_request(
                    args,
                    remote_batch_rx,
                    remote_manifest,
                    remote_npz,
                    remote_wire,
                    remote_summary,
                )
                remote_decode_worker = getattr(args, "remote_decode_worker", None)
                if remote_decode_worker is not None:
                    remote_request["manifest_json"] = manifest
                # NB: remote argv ignores rx_post_quantize on the wire — RX-side quantization
                # happens at capture time, not decode time. Remote decode reads what was captured.
                worker_response: dict[str, Any] = {}
                if remote_decode_worker is not None:
                    worker_proc = remote_decode_worker.decode(
                        remote_request,
                        image.image_dir / "remote_decode.log",
                        timeout=max(120.0, capture_timeout),
                    )
                    try:
                        worker_response = json.loads(str(worker_proc.stdout or "{}"))
                    except json.JSONDecodeError:
                        worker_response = {}
                else:
                    run_remote_command(
                        remote_target,
                        remote_argv,
                        image.image_dir / "remote_decode.log",
                        control_socket=ssh_control_socket,
                        timeout=max(120.0, capture_timeout),
                    )
                # Pull only what the selected result mode needs locally. Persistent
                # worker responses already carry the summary, avoiding another SSH
                # transfer in the hot path.
                publish_started = time.monotonic()
                response_summary = worker_response.get("summary") if isinstance(worker_response, dict) else None
                if remote_decode_result_mode == "remote-dir" and isinstance(response_summary, dict):
                    write_json(decode_summary, response_summary)
                else:
                    remote_outputs = (
                        {"decode_summary.json": decode_summary}
                        if remote_decode_result_mode == "remote-dir"
                        else {
                            "received_latent.npz": out_npz,
                            "merged_round0.bin": out_wire,
                            "decode_summary.json": decode_summary,
                        }
                    )
                    pull_files_from_remote_tar(
                        remote_target,
                        remote_run_dir,
                        remote_outputs,
                        image.image_dir / "remote_pull_outputs.log",
                        control_socket=ssh_control_socket,
                        timeout=60,
                    )
                if remote_decode_result_mode == "remote-dir":
                    remote_dir_publish_wall_sec = time.monotonic() - publish_started
                decode_wall_sec = time.monotonic() - decode_started
                if remote_decode_result_mode == "remote-dir":
                    pulled_summary = read_json(decode_summary) if decode_summary.is_file() else {}
                    status_ok = str(pulled_summary.get("status") or "").strip().lower() in {"", "ok", "success"}
                    image.status = 0 if (decode_summary.is_file() and status_ok and bool(pulled_summary.get("frame_complete", True))) else 1
                    image.passed = image.status == 0
                else:
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
                cleanup_started = time.monotonic()
                if remote_cleanup_mode != "skip":
                    remote_files = [path for path in (
                        remote_batch_rx, remote_tx, remote_manifest,
                        remote_npz if mode == "remote-decode" and remote_decode_result_mode != "remote-dir" else "",
                        remote_wire if mode == "remote-decode" and remote_decode_result_mode != "remote-dir" else "",
                        remote_summary if mode == "remote-decode" else "",
                    ) if path]
                    if remote_cleanup_mode == "async":
                        cleanup_remote_files_async(
                            remote_target,
                            remote_files,
                            image.image_dir / "remote_cleanup_batch.log",
                            control_socket=ssh_control_socket,
                        )
                    else:
                        cleanup_remote_files(
                            remote_target,
                            remote_files,
                            image.image_dir / "remote_cleanup_batch.log",
                            control_socket=ssh_control_socket,
                        )
                remote_cleanup_wall_sec = time.monotonic() - cleanup_started

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
            "remote_decode_result_mode": remote_decode_result_mode if str(args.rx_capture_mode) == "remote-decode" else None,
            "remote_decoded_output_dir": remote_decoded_dir or None,
            "remote_received_latent_npz": remote_received_npz or None,
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
            "rx_pull_wall_sec": rx_pull_wall_sec,
            "decode_wall_sec": decode_wall_sec,
            "remote_dir_publish_wall_sec": remote_dir_publish_wall_sec,
            "retry_wait_wall_sec": retry_wait_wall_sec,
            "merge_wall_sec": merge_wall_sec,
            "remote_cleanup_wall_sec": remote_cleanup_wall_sec,
            "remote_cleanup_mode": remote_cleanup_mode,
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


def _append_pipeline_error_record(
    image: ImageRecord,
    exc: Exception,
    *,
    started: float,
    attempt_index: int,
    max_attempts: int,
    slot_index: int,
    pipeline_depth: int,
) -> ImageRecord:
    image.status = 1
    image.passed = False
    image.error = str(exc)
    image.records.append({
        "round": attempt_index,
        "attempt": attempt_index + 1,
        "max_attempts": max_attempts,
        "input": str(image.input_path),
        "error": image.error,
        "pipeline_depth": pipeline_depth,
        "pipeline_slot": slot_index,
        "total_wall_sec": time.monotonic() - started,
        "payload_is_bit_exact": False,
    })
    return image


def _capture_remote_decode_pipeline_attempt(
    args: argparse.Namespace,
    image: ImageRecord,
    *,
    attempt_index: int,
    max_attempts: int,
    slot_index: int,
    pipeline_depth: int,
) -> dict[str, Any]:
    started = time.monotonic()
    image.status = 0
    image.passed = False
    image.error = ""
    image.image_dir.mkdir(parents=True, exist_ok=True)
    tx_sc16 = image.image_dir / "tx_analog.sc16"
    batch_rx = image.image_dir / "batch_rx.sc16"
    manifest_path = image.image_dir / "manifest.json"
    out_npz = image.image_dir / "received_latent.npz"
    out_wire = image.image_dir / "merged_round0.bin"
    decode_summary = image.image_dir / "decode_summary.json"

    remote_target = str(getattr(args, "remote_rx_ssh_target", "") or "").strip()
    if not remote_target:
        raise RuntimeError("--rx-capture-mode=remote-decode requires --remote-rx-ssh-target")
    ssh_control_socket = str(getattr(args, "ssh_control_socket", "") or "").strip() or None
    use_in_process_local_codec = bool(getattr(args, "in_process_local_codec", False))
    remote_cleanup_mode = str(
        getattr(args, "remote_cleanup_mode", os.environ.get("ANALOG_REMOTE_CLEANUP_MODE", "sync")) or "sync"
    ).strip().lower()
    if remote_cleanup_mode not in {"sync", "async", "skip"}:
        remote_cleanup_mode = "sync"
    remote_decode_result_mode = str(
        getattr(args, "remote_decode_result_mode", os.environ.get("ANALOG_REMOTE_DECODE_RESULT_MODE", "pull")) or "pull"
    ).strip().lower()
    if remote_decode_result_mode not in {"pull", "remote-dir"}:
        remote_decode_result_mode = "pull"
    remote_decoded_dir = remote_decoded_output_dir(args) if remote_decode_result_mode == "remote-dir" else ""

    make_started = time.monotonic()
    if use_in_process_local_codec:
        manifest = run_in_process_make(args, image, tx_sc16, manifest_path, image.image_dir / "make.log")
    else:
        run_command(analog_make_args(args, image, tx_sc16, manifest_path), image.image_dir / "make.log")
        manifest = read_json(manifest_path)
    make_wall_sec = time.monotonic() - make_started

    remote_run_dir = build_remote_run_dir(args, image)
    remote_batch_rx = f"{remote_run_dir}/batch_rx.sc16"
    remote_manifest = f"{remote_run_dir}/manifest.json"
    remote_decode_worker = getattr(args, "remote_decode_worker", None)
    if remote_decode_worker is None:
        push_file_to_remote(
            remote_target,
            manifest_path,
            remote_manifest,
            image.image_dir / "remote_push_manifest.log",
            control_socket=ssh_control_socket,
        )

    capture_nsamps = int(manifest["capture_nsamps"])
    capture_duration = max(
        0.001,
        float(args.tx_delay_sec) + (capture_nsamps / float(args.rate)) + float(args.rx_tail_sec),
    )
    capture_timeout = max(args.rx_timeout_sec, capture_nsamps / float(args.rate) + 5.0)

    rx_started = time.monotonic()
    run_control(
        args.rx_control_host,
        args.rx_control_port,
        f"CAPTURE file={remote_batch_rx} duration={capture_duration:.6f} nsamps=0",
        image.image_dir / "rx_capture.log",
        capture_timeout,
    )
    time.sleep(max(0.0, float(args.tx_delay_sec)))
    tx_started = time.monotonic()
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

    return {
        "image": image,
        "attempt_index": attempt_index,
        "max_attempts": max_attempts,
        "slot_index": slot_index,
        "pipeline_depth": pipeline_depth,
        "started": started,
        "tx_sc16": tx_sc16,
        "batch_rx": batch_rx,
        "manifest_path": manifest_path,
        "out_npz": out_npz,
        "out_wire": out_wire,
        "decode_summary": decode_summary,
        "manifest": manifest,
        "make_wall_sec": make_wall_sec,
        "tx_wall_sec": tx_wall_sec,
        "rx_capture_wall_sec": rx_capture_wall_sec,
        "rx_pull_wall_sec": 0.0,
        "merge_wall_sec": 0.0,
        "remote_cleanup_wall_sec": 0.0,
        "remote_cleanup_mode": remote_cleanup_mode,
        "remote_decode_result_mode": remote_decode_result_mode,
        "remote_decoded_dir": remote_decoded_dir,
        "remote_received_npz": "",
        "remote_target": remote_target,
        "ssh_control_socket": ssh_control_socket,
        "remote_run_dir": remote_run_dir,
        "remote_batch_rx": remote_batch_rx,
        "remote_tx": "",
        "remote_manifest": remote_manifest,
        "capture_timeout": capture_timeout,
        "slot_wait_wall_sec": 0.0,
    }


def _finalize_remote_decode_pipeline_attempt(args: argparse.Namespace, ctx: dict[str, Any]) -> ImageRecord:
    image = ctx["image"]
    started = float(ctx["started"])
    decode_wall_sec = 0.0
    remote_dir_publish_wall_sec = 0.0
    remote_cleanup_wall_sec = 0.0
    remote_received_npz = ""
    remote_npz = ""
    remote_wire = ""
    remote_summary = ""
    try:
        decode_started = time.monotonic()
        remote_decode_result_mode = str(ctx["remote_decode_result_mode"])
        if remote_decode_result_mode == "remote-dir":
            remote_npz = f"{ctx['remote_decoded_dir']}/{image.index:08d}.npz"
            remote_wire = ""
            remote_received_npz = remote_npz
        else:
            remote_npz = f"{ctx['remote_run_dir']}/received_latent.npz"
            remote_wire = f"{ctx['remote_run_dir']}/merged_round0.bin"
        remote_summary = f"{ctx['remote_run_dir']}/decode_summary.json"
        remote_argv = remote_analog_decode_args(
            args,
            str(ctx["remote_batch_rx"]),
            str(ctx["remote_manifest"]),
            remote_npz,
            remote_wire,
            remote_summary,
        )
        remote_request = remote_analog_decode_request(
            args,
            str(ctx["remote_batch_rx"]),
            str(ctx["remote_manifest"]),
            remote_npz,
            remote_wire,
            remote_summary,
        )
        remote_decode_worker = getattr(args, "remote_decode_worker", None)
        if remote_decode_worker is not None:
            remote_request["manifest_json"] = ctx["manifest"]
        worker_response: dict[str, Any] = {}
        if remote_decode_worker is not None:
            worker_proc = remote_decode_worker.decode(
                remote_request,
                image.image_dir / "remote_decode.log",
                timeout=max(120.0, float(ctx["capture_timeout"])),
            )
            try:
                worker_response = json.loads(str(worker_proc.stdout or "{}"))
            except json.JSONDecodeError:
                worker_response = {}
        else:
            run_remote_command(
                str(ctx["remote_target"]),
                remote_argv,
                image.image_dir / "remote_decode.log",
                control_socket=ctx["ssh_control_socket"],
                timeout=max(120.0, float(ctx["capture_timeout"])),
            )

        publish_started = time.monotonic()
        response_summary = worker_response.get("summary") if isinstance(worker_response, dict) else None
        if remote_decode_result_mode == "remote-dir" and isinstance(response_summary, dict):
            write_json(ctx["decode_summary"], response_summary)
        else:
            remote_outputs = (
                {"decode_summary.json": ctx["decode_summary"]}
                if remote_decode_result_mode == "remote-dir"
                else {
                    "received_latent.npz": ctx["out_npz"],
                    "merged_round0.bin": ctx["out_wire"],
                    "decode_summary.json": ctx["decode_summary"],
                }
            )
            pull_files_from_remote_tar(
                str(ctx["remote_target"]),
                str(ctx["remote_run_dir"]),
                remote_outputs,
                image.image_dir / "remote_pull_outputs.log",
                control_socket=ctx["ssh_control_socket"],
                timeout=60,
            )
        if remote_decode_result_mode == "remote-dir":
            remote_dir_publish_wall_sec = time.monotonic() - publish_started
        decode_wall_sec = time.monotonic() - decode_started

        if remote_decode_result_mode == "remote-dir":
            pulled_summary = read_json(ctx["decode_summary"]) if ctx["decode_summary"].is_file() else {}
            status_ok = str(pulled_summary.get("status") or "").strip().lower() in {"", "ok", "success"}
            image.status = 0 if (ctx["decode_summary"].is_file() and status_ok and bool(pulled_summary.get("frame_complete", True))) else 1
            image.passed = image.status == 0
        else:
            image.status = 0 if (ctx["out_wire"].is_file() and ctx["decode_summary"].is_file()) else 1
            image.passed = ctx["out_wire"].is_file() and ctx["decode_summary"].is_file()
        image.error = "" if image.passed else "remote decode completed but expected outputs are missing"

        cleanup_started = time.monotonic()
        if str(ctx["remote_cleanup_mode"]) != "skip":
            remote_files = [path for path in (
                str(ctx["remote_batch_rx"]),
                str(ctx["remote_tx"]),
                str(ctx["remote_manifest"]),
                remote_npz if remote_decode_result_mode != "remote-dir" else "",
                remote_wire if remote_decode_result_mode != "remote-dir" else "",
                remote_summary,
            ) if path]
            if str(ctx["remote_cleanup_mode"]) == "async":
                cleanup_remote_files_async(
                    str(ctx["remote_target"]),
                    remote_files,
                    image.image_dir / "remote_cleanup_batch.log",
                    control_socket=ctx["ssh_control_socket"],
                )
            else:
                cleanup_remote_files(
                    str(ctx["remote_target"]),
                    remote_files,
                    image.image_dir / "remote_cleanup_batch.log",
                    control_socket=ctx["ssh_control_socket"],
                )
        remote_cleanup_wall_sec = time.monotonic() - cleanup_started

        summary_data = read_json(ctx["decode_summary"]) if ctx["decode_summary"].is_file() else {}
        image.records.append({
            "round": int(ctx["attempt_index"]),
            "attempt": int(ctx["attempt_index"]) + 1,
            "max_attempts": int(ctx["max_attempts"]),
            "input": str(image.input_path),
            "tx_sc16": str(ctx["tx_sc16"]),
            "batch_rx": str(ctx["batch_rx"]),
            "manifest": str(ctx["manifest_path"]),
            "merged_bin": str(ctx["out_wire"]),
            "decode_summary": str(ctx["decode_summary"]),
            "rx_capture_mode": "remote-decode",
            "in_process_local_codec": bool(getattr(args, "in_process_local_codec", False)),
            "remote_rx_ssh_target": str(ctx["remote_target"]) or None,
            "remote_decode_result_mode": remote_decode_result_mode,
            "remote_decoded_output_dir": str(ctx["remote_decoded_dir"]) or None,
            "remote_received_latent_npz": remote_received_npz or None,
            "waveform_samples": int(ctx["manifest"].get("tx_waveform_samples") or 0),
            "capture_nsamps": int(ctx["manifest"].get("capture_nsamps") or 0),
            "detected_airtime_ms": summary_data.get("detected_airtime_ms"),
            "sync_success": summary_data.get("sync_success"),
            "sync_search_mode": summary_data.get("sync_search_mode"),
            "sync_metric": summary_data.get("sync_metric"),
            "estimated_cfo_hz": summary_data.get("estimated_cfo_hz"),
            "evm_rms": summary_data.get("evm_rms"),
            "estimated_snr_db": summary_data.get("estimated_snr_db"),
            "rx_clipping_ratio": summary_data.get("rx_clipping_ratio"),
            "simulated_cfo_hz": None,
            "simulated_snr_db": None,
            "make_wall_sec": float(ctx["make_wall_sec"]),
            "tx_wall_sec": float(ctx["tx_wall_sec"]),
            "rx_capture_wall_sec": float(ctx["rx_capture_wall_sec"]),
            "rx_pull_wall_sec": float(ctx["rx_pull_wall_sec"]),
            "decode_wall_sec": decode_wall_sec,
            "remote_dir_publish_wall_sec": remote_dir_publish_wall_sec,
            "retry_wait_wall_sec": 0.0,
            "merge_wall_sec": float(ctx["merge_wall_sec"]),
            "remote_cleanup_wall_sec": remote_cleanup_wall_sec,
            "remote_cleanup_mode": str(ctx["remote_cleanup_mode"]),
            "pipeline_depth": int(ctx["pipeline_depth"]),
            "pipeline_slot": int(ctx["slot_index"]),
            "slot_wait_wall_sec": float(ctx.get("slot_wait_wall_sec") or 0.0),
            "total_wall_sec": time.monotonic() - started,
            "payload_is_bit_exact": False,
        })
    except Exception as exc:
        return _append_pipeline_error_record(
            image,
            exc,
            started=started,
            attempt_index=int(ctx["attempt_index"]),
            max_attempts=int(ctx["max_attempts"]),
            slot_index=int(ctx["slot_index"]),
            pipeline_depth=int(ctx["pipeline_depth"]),
        )
    return image


def _process_images_remote_decode_pipeline(
    args: argparse.Namespace,
    images: list[ImageRecord],
    *,
    pipeline_depth: int,
) -> tuple[list[ImageRecord], dict[str, Any]]:
    depth = max(1, int(pipeline_depth))
    max_attempts = max(1, 1 + int(getattr(args, "max_arq_rounds", 0) or 0))
    available_slots = list(range(depth))
    ready_contexts: list[dict[str, Any]] = []
    completed: list[ImageRecord] = []
    next_image_index = 0
    max_inflight = 0
    slot_wait_wall_sec = 0.0
    decode_future: tuple[dict[str, Any], Future[ImageRecord]] | None = None

    def occupied_count() -> int:
        return len(ready_contexts) + (1 if decode_future is not None else 0)

    def update_max_inflight() -> None:
        nonlocal max_inflight
        max_inflight = max(max_inflight, occupied_count())

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="iq-remote-decode") as executor:
        while next_image_index < len(images) or ready_contexts or decode_future is not None:
            if decode_future is None:
                if ready_contexts:
                    ctx = ready_contexts.pop(0)
                    decode_future = (ctx, executor.submit(_finalize_remote_decode_pipeline_attempt, args, ctx))
                    update_max_inflight()
                elif next_image_index < len(images) and available_slots:
                    slot_index = available_slots.pop(0)
                    image = images[next_image_index]
                    next_image_index += 1
                    try:
                        ctx = _capture_remote_decode_pipeline_attempt(
                            args,
                            image,
                            attempt_index=0,
                            max_attempts=max_attempts,
                            slot_index=slot_index,
                            pipeline_depth=depth,
                        )
                    except Exception as exc:
                        completed.append(
                            _append_pipeline_error_record(
                                image,
                                exc,
                                started=time.monotonic(),
                                attempt_index=0,
                                max_attempts=max_attempts,
                                slot_index=slot_index,
                                pipeline_depth=depth,
                            )
                        )
                        available_slots.append(slot_index)
                        available_slots.sort()
                        continue
                    decode_future = (ctx, executor.submit(_finalize_remote_decode_pipeline_attempt, args, ctx))
                    update_max_inflight()
                else:
                    break

            while next_image_index < len(images) and occupied_count() < depth and available_slots:
                slot_index = available_slots.pop(0)
                image = images[next_image_index]
                next_image_index += 1
                try:
                    ctx = _capture_remote_decode_pipeline_attempt(
                        args,
                        image,
                        attempt_index=0,
                        max_attempts=max_attempts,
                        slot_index=slot_index,
                        pipeline_depth=depth,
                    )
                except Exception as exc:
                    completed.append(
                        _append_pipeline_error_record(
                            image,
                            exc,
                            started=time.monotonic(),
                            attempt_index=0,
                            max_attempts=max_attempts,
                            slot_index=slot_index,
                            pipeline_depth=depth,
                        )
                    )
                    available_slots.append(slot_index)
                    available_slots.sort()
                    continue
                ready_contexts.append(ctx)
                update_max_inflight()

            if decode_future is None:
                continue

            ctx, future = decode_future
            waiting_for_slot = next_image_index < len(images) and not available_slots
            wait_started = time.monotonic()
            result = future.result()
            if waiting_for_slot:
                slot_wait_wall_sec += time.monotonic() - wait_started
            decode_future = None
            slot_index = int(ctx["slot_index"])
            attempt_index = int(ctx["attempt_index"])
            if result.passed or attempt_index + 1 >= max_attempts:
                completed.append(result)
                available_slots.append(slot_index)
                available_slots.sort()
                continue

            try:
                retry_ctx = _capture_remote_decode_pipeline_attempt(
                    args,
                    result,
                    attempt_index=attempt_index + 1,
                    max_attempts=max_attempts,
                    slot_index=slot_index,
                    pipeline_depth=depth,
                )
            except Exception as exc:
                completed.append(
                    _append_pipeline_error_record(
                        result,
                        exc,
                        started=time.monotonic(),
                        attempt_index=attempt_index + 1,
                        max_attempts=max_attempts,
                        slot_index=slot_index,
                        pipeline_depth=depth,
                    )
                )
                available_slots.append(slot_index)
                available_slots.sort()
                continue
            decode_future = (retry_ctx, executor.submit(_finalize_remote_decode_pipeline_attempt, args, retry_ctx))
            update_max_inflight()

    completed.sort(key=lambda item: item.index)
    return completed, {
        "pipeline_depth": depth,
        "max_inflight": max_inflight,
        "slot_wait_wall_sec": slot_wait_wall_sec,
    }


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


def _metric_from_ms_values(values: list[float]) -> dict[str, Any] | None:
    numeric_values = sorted(float(value) for value in values if float(value) >= 0.0)
    if not numeric_values:
        return None
    count = len(numeric_values)
    mid = count // 2
    if count % 2:
        median = numeric_values[mid]
    else:
        median = (numeric_values[mid - 1] + numeric_values[mid]) / 2.0
    p95_index = max(0, min(count - 1, math.ceil(0.95 * count) - 1))
    return {
        "n": count,
        "min_ms": round(numeric_values[0], 2),
        "max_ms": round(numeric_values[-1], 2),
        "mean_ms": round(sum(numeric_values) / count, 2),
        "median_ms": round(median, 2),
        "p95_ms": round(numeric_values[p95_index], 2),
    }


def _record_ms_values(images: list[ImageRecord], field_name: str) -> list[float]:
    values: list[float] = []
    for image in images:
        for record in image.records:
            if field_name not in record:
                continue
            try:
                value = float(record.get(field_name) or 0.0)
            except (TypeError, ValueError):
                continue
            if value >= 0.0:
                values.append(value * 1000.0)
    return values


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


def build_iq_stage_benchmark(images: list[ImageRecord]) -> dict[str, Any]:
    fields = (
        ("tx_control_ms", "tx_wall_sec"),
        ("rx_capture_ms", "rx_capture_wall_sec"),
        ("remote_decode_ms", "decode_wall_sec"),
        ("remote_dir_publish_ms", "remote_dir_publish_wall_sec"),
        ("retry_wait_ms", "retry_wait_wall_sec"),
        ("total_transport_ms", "total_wall_sec"),
    )
    benchmark: dict[str, Any] = {}
    for metric_name, record_field in fields:
        metric = _metric_from_ms_values(_record_ms_values(images, record_field))
        if metric is not None:
            benchmark[metric_name] = metric
    return benchmark


def build_transport_metrics(images: list[ImageRecord]) -> dict[str, Any]:
    total_values = _record_float_values(images, "total_wall_sec")
    make_values = _record_float_values(images, "make_wall_sec")
    tx_values = _record_float_values(images, "tx_wall_sec")
    rx_values = _record_float_values(images, "rx_capture_wall_sec")
    rx_pull_values = _record_float_values(images, "rx_pull_wall_sec")
    decode_values = _record_float_values(images, "decode_wall_sec")
    merge_values = _record_float_values(images, "merge_wall_sec")
    cleanup_values = _record_float_values(images, "remote_cleanup_wall_sec")
    airtime_ms_values = _record_float_values(images, "detected_airtime_ms")
    total_mean = _mean(total_values)
    decode_mean = _mean(decode_values)
    rx_pull_mean = _mean(rx_pull_values)
    cleanup_mean = _mean(cleanup_values)
    airtime_sec_mean = _mean(airtime_ms_values) / 1000.0 if airtime_ms_values else 0.0
    merge_mean = _mean(merge_values)
    return {
        "per_image_sec": total_mean,
        "total_wall_sec_mean": total_mean,
        "make_wall_sec_mean": _mean(make_values),
        "tx_wall_sec_mean": _mean(tx_values),
        "rx_capture_wall_sec_mean": _mean(rx_values),
        "rx_pull_wall_sec_mean": rx_pull_mean,
        "decode_total_wall_sec_mean": decode_mean,
        "merge_wall_sec_mean": merge_mean,
        "remote_cleanup_wall_sec_mean": cleanup_mean,
        "payload_airtime_ms_mean": _mean(airtime_ms_values),
        "estimated_non_airtime_non_decode_non_merge_wall_sec_mean": max(
            0.0,
            total_mean - airtime_sec_mean - decode_mean - merge_mean - rx_pull_mean - cleanup_mean,
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
    configured_pipeline_depth = max(1, int(getattr(args, "pipeline_depth", 1) or 1))
    pipeline_stats: dict[str, Any] = {
        "pipeline_depth": configured_pipeline_depth,
        "pipeline_enabled": False,
        "max_inflight": 0,
        "slot_wait_wall_sec": 0.0,
    }
    remote_decode_worker: RemoteAnalogDecodeWorker | None = None
    shared_ssh_master_proc: subprocess.Popen | None = None
    shared_ssh_control_socket: str | None = None
    remote_mode = str(getattr(args, "rx_capture_mode", "") or "").strip().lower()
    remote_target = str(getattr(args, "remote_rx_ssh_target", "") or "").strip()
    try:
        if (
            remote_mode in {"remote-pull", "remote-decode"}
            and not bool(getattr(args, "dry_run", False))
            and remote_target
        ):
            shared_ssh_master_proc = _ssh_start_control_master(remote_target)
            shared_ssh_control_socket = _ssh_control_socket_path() if shared_ssh_master_proc else None
        if (
            remote_mode == "remote-decode"
            and not bool(getattr(args, "dry_run", False))
            and env_bool("ANALOG_REMOTE_DECODE_WORKER", True)
        ):
            if remote_target:
                remote_decode_worker = RemoteAnalogDecodeWorker.start(
                    remote_target,
                    args,
                    run_dir / "remote_decode_worker.log",
                    control_socket=shared_ssh_control_socket,
                )
        setattr(args, "remote_decode_worker", remote_decode_worker)
        setattr(args, "ssh_control_socket", shared_ssh_control_socket or "")
        remote_decode_result_mode = str(
            getattr(args, "remote_decode_result_mode", os.environ.get("ANALOG_REMOTE_DECODE_RESULT_MODE", "pull")) or "pull"
        ).strip().lower()
        pipeline_enabled = (
            configured_pipeline_depth > 1
            and remote_mode == "remote-decode"
            and not bool(getattr(args, "dry_run", False))
            and remote_decode_worker is not None
            and remote_decode_result_mode == "remote-dir"
            and not bool(getattr(args, "stop_on_fail", False))
        )
        if pipeline_enabled:
            completed, pipeline_stats = _process_images_remote_decode_pipeline(
                args,
                images,
                pipeline_depth=configured_pipeline_depth,
            )
            pipeline_stats["pipeline_enabled"] = True
        else:
            for image in images:
                max_attempts = max(1, 1 + int(getattr(args, "max_arq_rounds", 0) or 0))
                result = image
                for attempt_index in range(max_attempts):
                    result = process_image(args, image)
                    if result.records:
                        result.records[-1]["round"] = attempt_index
                        result.records[-1]["attempt"] = attempt_index + 1
                        result.records[-1]["max_attempts"] = max_attempts
                    if result.passed:
                        break
                completed.append(result)
                if args.stop_on_fail and not result.passed:
                    break
            pipeline_stats["max_inflight"] = 1 if completed else 0
    finally:
        if remote_decode_worker is not None:
            remote_decode_worker.close()
        if shared_ssh_master_proc is not None:
            try:
                shared_ssh_master_proc.terminate()
                shared_ssh_master_proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    shared_ssh_master_proc.kill()
                except OSError:
                    pass
    passed_count = sum(1 for image in completed if image.passed)
    failed_count = sum(1 for image in completed if not image.passed)
    remote_decoded_dirs = sorted({
        str(record.get("remote_decoded_output_dir") or "")
        for image in completed
        for record in image.records
        if str(record.get("remote_decoded_output_dir") or "").strip()
    })
    remote_received_npz_files = [
        str(record.get("remote_received_latent_npz") or "")
        for image in completed
        for record in image.records
        if str(record.get("remote_received_latent_npz") or "").strip()
    ]

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
        "remote_decode_worker_enabled": remote_decode_worker is not None,
        "remote_decode_worker_startup_wall_sec": (
            float(remote_decode_worker.startup_wall_sec) if remote_decode_worker is not None else 0.0
        ),
        "remote_decode_worker_ready": (
            remote_decode_worker.ready_response if remote_decode_worker is not None else {}
        ),
        "remote_decode_result_mode": str(getattr(args, "remote_decode_result_mode", "") or "pull"),
        "remote_decoded_output_dir": remote_decoded_dirs[0] if len(remote_decoded_dirs) == 1 else "",
        "remote_decoded_output_dirs": remote_decoded_dirs,
        "remote_received_latent_npz_files": remote_received_npz_files,
        "codec_warmup_wall_sec": codec_warmup_wall_sec,
        "pipeline_depth": int(pipeline_stats.get("pipeline_depth") or configured_pipeline_depth),
        "pipeline_enabled": bool(pipeline_stats.get("pipeline_enabled")),
        "max_inflight": int(pipeline_stats.get("max_inflight") or 0),
        "slot_wait_ms": round(float(pipeline_stats.get("slot_wait_wall_sec") or 0.0) * 1000.0, 3),
        "channel_mode": os.environ.get("JSCC_CHANNEL_MODE", ""),
        "iq_stage_benchmark": build_iq_stage_benchmark(completed),
        "rate": float(args.rate),
        "sps": int(args.sps),
        "rx_post_quantize": bool(args.rx_post_quantize),
        "robust_sync": bool(args.robust_sync),
        "sync_profile": sync_profile_value(args),
        "sync_candidates": int(args.sync_candidates),
        "fast_sync_candidates": int(getattr(args, "fast_sync_candidates", 4) or 4),
        "fast_sync_search_window_symbols": int(getattr(args, "fast_sync_search_window_symbols", 1024) or 1024),
        "fallback_sync_candidates": int(getattr(args, "fallback_sync_candidates", 12) or 12),
        "fallback_sync_search_window_symbols": int(getattr(args, "fallback_sync_search_window_symbols", 4096) or 4096),
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
