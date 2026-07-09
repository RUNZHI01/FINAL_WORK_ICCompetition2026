from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
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
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping

from board_access import (
    BoardAccessConfig,
    current_input_source_mode,
    current_jscc_link_mode,
    input_source_mode_label,
)


def _discover_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    candidates = [
        script_path.parents[4],
        Path.cwd(),
    ]
    candidates.extend(script_path.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "USRP292x").is_dir():
            return resolved

    return script_path.parents[4]


REPO_ROOT = _discover_repo_root()
ROOT_SCRIPTS = REPO_ROOT / "scripts"
if str(ROOT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ROOT_SCRIPTS))
SESSION_SCRIPTS = REPO_ROOT / "Semantic-Communication" / "session_bootstrap" / "scripts"
if str(SESSION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SESSION_SCRIPTS))

from latent_transport import (  # noqa: E402
    build_transport_blob,
    unpack_transport_frame,
)
from openamp_control_wrapper import resolve_bash_executable  # noqa: E402

DEFAULT_RUNNER = REPO_ROOT / "USRP292x" / "RunQpskFileBatchSpoolArq.py"
DEFAULT_ANALOG_RUNNER = REPO_ROOT / "USRP292x" / "RunAnalogLatentBatch.py"
DEFAULT_INPUT_DIR = REPO_ROOT / "USRP292x" / "payloads" / "finalwork_webp5"
DEFAULT_INPUT_FILE = REPO_ROOT / "USRP292x" / "payloads" / "source_latent_wire_blob.bin"
DEFAULT_RUN_ROOT = REPO_ROOT / "USRP292x" / "qpsk_batch_spool_arq_runs"
DEFAULT_ANALOG_RUN_ROOT = REPO_ROOT / "USRP292x" / "analog_latent_runs"
LINK_MODE_QPSK = "qpsk"
LINK_MODE_IQ_DIRECT = "iq-direct"
DEFAULT_IQ_DIRECT_SPS = 2
DEFAULT_IQ_DIRECT_AMPLITUDE = 6000
DEFAULT_IQ_DIRECT_MIN_SYNC_METRIC = 0.05
DEFAULT_IQ_DIRECT_ROBUST_SYNC = False
DEFAULT_IQ_DIRECT_SYNC_SEARCH_WINDOW_SYMBOLS = 4096
LINK_MODE_KEYS = ("JSCC_LINK_MODE", "OPENAMP_DEMO_LINK_MODE")
SSH_HELPER = (
    REPO_ROOT
    / "Semantic-Communication"
    / "session_bootstrap"
    / "scripts"
    / "ssh_with_password.sh"
)

RUNNER_SCRIPT_KEYS = ("MLKEM_USRP_RUNNER_SCRIPT", "USRP_RUNNER_SCRIPT")
INPUT_DIR_KEYS = ("MLKEM_USRP_INPUT_DIR", "USRP_INPUT_DIR")
INPUT_FILE_KEYS = ("MLKEM_USRP_INPUT_FILE", "USRP_INPUT_FILE")
RUN_ROOT_KEYS = ("MLKEM_USRP_RUN_ROOT", "USRP_RUN_ROOT")
MAX_ARQ_ROUNDS_KEYS = ("MLKEM_USRP_MAX_ARQ_ROUNDS", "USRP_MAX_ARQ_ROUNDS")
DECODE_BACKEND_KEYS = ("QPSK_DECODE_BACKEND",)
CPP_SYNC_MODE_KEYS = ("QPSK_CPP_SYNC_MODE",)
TX_DOCKER_MOUNT_TARGET_KEYS = ("OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET", "USRP_TX_DOCKER_MOUNT_TARGET")
TX_FILE_PATH_PREFIX_FROM_KEYS = ("OPENAMP_USRP_TX_FILE_PATH_PREFIX_FROM", "USRP_TX_FILE_PATH_PREFIX_FROM")
TX_FILE_PATH_PREFIX_TO_KEYS = ("OPENAMP_USRP_TX_FILE_PATH_PREFIX_TO", "USRP_TX_FILE_PATH_PREFIX_TO")
ARTIFACT_MODE_KEYS = ("USRP_ARTIFACT_MODE",)
BATCH_SIZE_KEYS = ("BATCH_SIZE",)
DECODE_WORKERS_KEYS = ("BATCH_DECODE_WORKERS",)
CHUNK_BYTES_KEYS = ("CHUNK_BYTES",)
FAST_ARQ_PROFILE_KEYS = ("USRP_FAST_ARQ_PROFILE",)
STOP_ON_FAIL_KEYS = ("USRP_STOP_ON_FAIL",)
# ── IQ 直传 (AnalogLatentLink) 参数 KEYS ──
ANALOG_SPS_KEYS = ("ANALOG_SPS",)
ANALOG_RRC_BETA_KEYS = ("ANALOG_RRC_BETA",)
ANALOG_RRC_SPAN_KEYS = ("ANALOG_RRC_SPAN",)
ANALOG_AMP_KEYS = ("AMPLITUDE", "ANALOG_AMPLITUDE")
ANALOG_ZERO_GUARD_KEYS = ("ANALOG_ZERO_GUARD_SAMPLES",)
ANALOG_TAIL_GUARD_KEYS = ("ANALOG_TAIL_GUARD_SAMPLES",)
ANALOG_CFO_PILOT_KEYS = ("ANALOG_CFO_PILOT_SYMBOLS",)
ANALOG_SYNC_PILOT_KEYS = ("ANALOG_SYNC_PILOT_SYMBOLS",)
ANALOG_DATA_BLOCK_KEYS = ("ANALOG_DATA_BLOCK_SYMBOLS",)
ANALOG_MID_PILOT_KEYS = ("ANALOG_MID_PILOT_SYMBOLS",)
ANALOG_CAPTURE_MARGIN_KEYS = ("ANALOG_CAPTURE_MARGIN_SAMPLES",)
ANALOG_RX_POST_QUANTIZE_KEYS = ("ANALOG_RX_POST_QUANTIZE",)
ANALOG_ROBUST_SYNC_KEYS = ("ANALOG_ROBUST_SYNC",)
ANALOG_MIN_SYNC_METRIC_KEYS = ("ANALOG_MIN_SYNC_METRIC",)
ANALOG_ROBUST_CFO_MAX_HZ_KEYS = ("ANALOG_ROBUST_CFO_MAX_HZ",)
ANALOG_ROBUST_CFO_STEP_HZ_KEYS = ("ANALOG_ROBUST_CFO_STEP_HZ",)
ANALOG_SYNC_CANDIDATES_KEYS = ("ANALOG_SYNC_CANDIDATES",)
ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS_KEYS = ("ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS",)
ANALOG_PIPELINE_DEPTH_KEYS = ("ANALOG_PIPELINE_DEPTH",)
ANALOG_REMOTE_DECODE_RESULT_MODE_KEYS = ("ANALOG_REMOTE_DECODE_RESULT_MODE",)
ANALOG_REMOTE_DECODED_OUTPUT_DIR_KEYS = ("ANALOG_REMOTE_DECODED_OUTPUT_DIR",)
ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_KEYS = ("ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_SEC",)
ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_KEYS = ("ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC",)
ANALOG_SCRAMBLE_KEY_KEYS = ("ANALOG_SCRAMBLE_KEY",)
ANALOG_SCRAMBLE_KEY_HEX_KEYS = ("ANALOG_SCRAMBLE_KEY_HEX",)
ANALOG_SCRAMBLE_CONTEXT_KEYS = ("ANALOG_SCRAMBLE_CONTEXT",)
ANALOG_SIM_CFO_HZ_KEYS = ("ANALOG_SIM_CFO_HZ",)
ANALOG_SIM_SNR_DB_KEYS = ("ANALOG_SIM_SNR_DB",)
ANALOG_SIM_GAIN_KEYS = ("ANALOG_SIM_GAIN",)
ANALOG_SIM_PHASE_DEG_KEYS = ("ANALOG_SIM_PHASE_DEG",)
ANALOG_SIM_PHASE_DRIFT_DEG_KEYS = ("ANALOG_SIM_PHASE_DRIFT_DEG",)
ANALOG_SIM_DC_REAL_KEYS = ("ANALOG_SIM_DC_REAL",)
ANALOG_SIM_DC_IMAG_KEYS = ("ANALOG_SIM_DC_IMAG",)
ANALOG_SIM_SEED_KEYS = ("ANALOG_SIM_SEED",)
TIMEOUT_SEC_KEYS = ("USRP_JOB_TIMEOUT_SEC", "MLKEM_USRP_JOB_TIMEOUT_SEC")
LOCAL_LATENT_DIR_KEYS = ("OPENAMP_DEMO_LOCAL_LATENT_DIR", "MLKEM_USRP_SOURCE_LATENT_DIR", "USRP_SOURCE_LATENT_DIR")
LOCAL_LATENT_PATTERN_KEYS = ("OPENAMP_DEMO_LOCAL_LATENT_PATTERN", "USRP_SOURCE_LATENT_PATTERN")
LOCAL_IMAGE_DIR_KEYS = ("OPENAMP_DEMO_LOCAL_IMAGE_DIR", "USRP_SOURCE_IMAGE_DIR")
LOCAL_IMAGE_TO_LATENT_ENABLED_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED", "USRP_IMAGE_TO_LATENT_ENABLED")
LOCAL_IMAGE_TO_LATENT_SCRIPT_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_SCRIPT", "USRP_IMAGE_TO_LATENT_SCRIPT")
LOCAL_IMAGE_TO_LATENT_OUTPUT_DIR_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_OUTPUT_DIR", "USRP_IMAGE_TO_LATENT_OUTPUT_DIR")
LOCAL_IMAGE_TO_LATENT_DEVICE_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_DEVICE", "USRP_IMAGE_TO_LATENT_DEVICE")
LOCAL_IMAGE_TO_LATENT_CONFIG_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_CONFIG", "USRP_IMAGE_TO_LATENT_CONFIG")
LOCAL_IMAGE_TO_LATENT_SNR_KEYS = ("OPENAMP_DEMO_IMAGE_TO_LATENT_SNR", "USRP_IMAGE_TO_LATENT_SNR")
PAYLOAD_CODEC_KEYS = ("OPENAMP_DEMO_USRP_PAYLOAD_CODEC", "USRP_PAYLOAD_CODEC")
WIRE_PREPARE_WORKERS_KEYS = ("USRP_WIRE_PREPARE_WORKERS", "OPENAMP_DEMO_USRP_WIRE_PREPARE_WORKERS")
WIRE_CACHE_ENABLED_KEYS = ("USRP_WIRE_CACHE_ENABLED", "OPENAMP_DEMO_USRP_WIRE_CACHE_ENABLED")
WIRE_CACHE_DIR_KEYS = ("USRP_WIRE_CACHE_DIR", "OPENAMP_DEMO_USRP_WIRE_CACHE_DIR")
REMOTE_USRP_RX_ROOT_KEYS = ("REMOTE_USRP_RX_DIR",)
RX_CONTROL_HOST_KEYS = ("RX_CONTROL_HOST", "USRP_RX_CONTROL_HOST")
RX_CONTROL_PORT_KEYS = ("RX_CONTROL_PORT", "USRP_RX_CONTROL_PORT")
TX_CONTROL_HOST_KEYS = ("TX_CONTROL_HOST", "USRP_TX_CONTROL_HOST")
TX_CONTROL_PORT_KEYS = ("TX_CONTROL_PORT", "USRP_TX_CONTROL_PORT")
RX_CAPTURE_MODE_KEYS = ("RX_CAPTURE_MODE", "USRP_RX_CAPTURE_MODE")
REMOTE_RX_SSH_TARGET_KEYS = ("REMOTE_RX_SSH_TARGET", "USRP_REMOTE_RX_SSH_TARGET")
REMOTE_RX_RUN_ROOT_KEYS = ("REMOTE_RX_RUN_ROOT", "USRP_REMOTE_RX_RUN_ROOT")
REMOTE_USRP_PROJECT_ROOT_KEYS = ("REMOTE_USRP_PROJECT_ROOT", "USRP_REMOTE_PROJECT_ROOT")
USRP_AUTO_START_CONTROL_KEYS = ("USRP_AUTO_START_CONTROL", "OPENAMP_DEMO_USRP_AUTO_START_CONTROL")
SHUTDOWN_AFTER_TRANSPORT_KEYS = (
    "OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT",
    "USRP_SHUTDOWN_CONTROL_AFTER_TRANSPORT",
)
REMOTE_DECODE_PYTHON_KEYS = (
    "OPENAMP_DEMO_REMOTE_DECODE_PYTHON",
    "REMOTE_USRP_DECODE_PYTHON",
    "REMOTE_TVM_PYTHON",
    "MLKEM_REMOTE_PYTHON",
)
REMOTE_DECODE_BIN_KEYS = ("REMOTE_DECODE_BIN", "USRP_REMOTE_DECODE_BIN")
INFERENCE_ENGINE_KEYS = ("OPENAMP_DEMO_USRP_INFERENCE_ENGINE", "USRP_INFERENCE_ENGINE")
INFERENCE_ENGINE_NONE = "none"
INFERENCE_ENGINE_TVM = "tvm"
INFERENCE_ENGINE_MNN = "mnn"
DEFAULT_RX_CONTROL_PORT = "29220"
DEFAULT_TX_CONTROL_PORT = "29221"
DEFAULT_TX_DOCKER_MOUNT_TARGET = "/host_workspace"
DEFAULT_REMOTE_USRP_PROJECT_ROOT = "/home/user"
DEFAULT_REMOTE_RX_RUN_ROOT = "/tmp/usrp292x_remote_runs"
DEFAULT_RATE = "5000000"
DEFAULT_FREQ = "500000000"
DEFAULT_TX_ARGS = "addr=192.168.10.2"
DEFAULT_RX_ARGS = "addr=192.168.10.22"
DEFAULT_TX_GAIN = "25"
DEFAULT_RX_GAIN = "15"
DEFAULT_RX_ANT = "RX2"
DEFAULT_BIND_ADDR = "0.0.0.0"
DEFAULT_WIRE_PREPARE_WORKERS = 2
WIRE_CACHE_VERSION = 1
HOST_IMAGE_LATENT_MANIFEST = "host_image_to_latent_manifest.json"
HOST_IMAGE_LATENT_MANIFEST_VERSION = 1
CONTROL_PING_TIMEOUT_SEC = 2.0
CONTROL_START_TIMEOUT_SEC = 15.0
CONTROL_SHUTDOWN_TIMEOUT_SEC = 5.0
CHILD_PROCESS_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}

_IQ_DECODE_ASSET_SYNC_CACHE: dict[tuple[str, str, str, str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}

BOARD_DECODE_SCRIPT = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUPPORT_DIR = Path(__file__).resolve().parent / "_support"
sys.path.insert(0, str(SUPPORT_DIR))

from latent_transport import decode_transport_payload, save_decoded_npz, unpack_transport_frame  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Decode USRP wire blobs into board-side latent npz files.")
    parser.add_argument("--wire-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    wire_dir = Path(args.wire_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    decoded_files = []
    for bin_path in sorted(wire_dir.glob("*.bin")):
        meta, payload_bytes = unpack_transport_frame(bin_path.read_bytes())
        decoded = decode_transport_payload(meta, payload_bytes)
        job_id = str(meta.get("job_id") or bin_path.stem)
        unique_stem = f"{bin_path.stem}_{job_id}" if bin_path.stem != job_id else job_id
        target = output_dir / f"{unique_stem}.npz"
        save_decoded_npz(decoded, target)
        decoded_files.append(
            {
                "source_bin": str(bin_path),
                "target_npz": str(target),
                "job_id": job_id,
                "payload_codec": str(meta.get("payload_codec") or ""),
                "storage_format": decoded.storage_format,
            }
        )

    if not decoded_files:
        raise SystemExit(f"ERROR: no wire blobs found in {wire_dir}")

    manifest = {
        "wire_dir": str(wire_dir),
        "output_dir": str(output_dir),
        "decode_location": "board",
        "decoded_count": len(decoded_files),
        "files": decoded_files,
    }
    (output_dir / "usrp_rx_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
'''


def _first_value(env_values: dict[str, str], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = str(env_values.get(key, "") or "").strip()
        if value:
            return value
    return default


def _resolve_existing_path(raw_value: str) -> Path | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    else:
        path = path.resolve()
    try:
        if path.exists():
            return path
    except OSError:
        return None
    return None


def _parse_int(raw_value: str, default: int) -> int:
    text = str(raw_value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _parse_float(raw_value: str, default: float) -> float:
    text = str(raw_value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_bool(raw_value: str, default: bool = False) -> bool:
    text = str(raw_value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _default_shutdown_after_transport(env_values: dict[str, str]) -> bool:
    return current_jscc_link_mode(env_values) != LINK_MODE_IQ_DIRECT


def resolve_shutdown_after_transport(env_values: dict[str, str]) -> bool:
    default = _default_shutdown_after_transport(env_values)
    return _parse_bool(_first_value(env_values, SHUTDOWN_AFTER_TRANSPORT_KEYS), default)


def _read_log_tail(path: Path, *, max_lines: int = 40) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(line.rstrip() for line in lines[-max_lines:] if line.strip())


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _resolve_optional_path(raw_value: str) -> Path | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def _sanitize_shell_value(value: str) -> str:
    return str(value or "").strip()


def _remote_ssh_target(access: BoardAccessConfig, env_values: dict[str, str]) -> str:
    configured = _first_value(env_values, REMOTE_RX_SSH_TARGET_KEYS)
    if configured:
        return configured
    if access.user and access.host:
        return f"{access.user}@{access.host}"
    return ""


def _remote_usrp_project_root(env_values: dict[str, str]) -> str:
    return _first_value(env_values, REMOTE_USRP_PROJECT_ROOT_KEYS, DEFAULT_REMOTE_USRP_PROJECT_ROOT)


def _tcp_control_command(host: str, port: str, line: str, *, timeout: float = CONTROL_PING_TIMEOUT_SEC) -> str:
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
    except (OSError, ValueError) as exc:
        return f"ERR_CONNECT host={host} port={port} error={type(exc).__name__}:{exc}"


def _control_is_ready(host: str, port: str) -> tuple[bool, str]:
    response = _tcp_control_command(host, port, "PING")
    return response.startswith("OK"), response


def _tx_server_uses_docker(env_values: dict[str, str]) -> bool:
    runner = _first_value(env_values, ("OPENAMP_USRP_TX_RUNNER", "USRP_TX_RUNNER")).lower()
    local_binary = REPO_ROOT / "USRP292x" / "OtaTxPersistentServer"
    force_local = runner in {"local", "host", "bash"}
    return runner == "docker" or (not force_local and not local_binary.exists() and shutil.which("docker") is not None)


def _start_local_tx_server(env_values: dict[str, str], *, log_dir: Path, tx_port: str) -> dict[str, Any]:
    script = REPO_ROOT / "USRP292x" / "OtaTxPersistentServer.sh"
    if not script.is_file():
        return {"status": "error", "message": f"TX persistent server 脚本不存在: {script}"}
    use_docker = _tx_server_uses_docker(env_values)
    if use_docker:
        image = _first_value(env_values, ("OPENAMP_USRP_TX_DOCKER_IMAGE", "USRP_TX_DOCKER_IMAGE"), "iccomp-usrp-tx:latest")
        mount_target = _first_value(env_values, TX_DOCKER_MOUNT_TARGET_KEYS, DEFAULT_TX_DOCKER_MOUNT_TARGET)
        command = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--mount",
            f"type=bind,source={REPO_ROOT},target={mount_target}",
            "-p",
            f"127.0.0.1:{tx_port}:{tx_port}",
            "-e",
            f"DEVICE_ARGS={_first_value(env_values, ('TX_ARGS',), DEFAULT_TX_ARGS)}",
            "-e",
            f"RATE={_first_value(env_values, ('RATE',), DEFAULT_RATE)}",
            "-e",
            f"FREQ={_first_value(env_values, ('FREQ',), DEFAULT_FREQ)}",
            "-e",
            f"GAIN={_first_value(env_values, ('TX_GAIN',), DEFAULT_TX_GAIN)}",
            "-e",
            f"ANT={_first_value(env_values, ('TX_ANT',), 'TX/RX')}",
            "-e",
            "BIND_ADDR=0.0.0.0",
            "-e",
            f"PORT={tx_port}",
            image,
            "bash",
            "/workspace/USRP292x/OtaTxPersistentServer.sh",
        ]
        result = subprocess.run(command, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
        if result.returncode != 0:
            return {
                "status": "error",
                "runner": "docker",
                "message": (result.stderr or result.stdout or f"docker rc={result.returncode}").strip(),
            }
        return {
            "status": "started",
            "runner": "docker",
            "container_id": (result.stdout or "").strip(),
            "image": image,
            "port": str(tx_port),
        }
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"tx_persistent_cockpit_{int(time.time())}.log"
    env = os.environ.copy()
    env.update({
        "DEVICE_ARGS": _first_value(env_values, ("TX_ARGS",), DEFAULT_TX_ARGS),
        "RATE": _first_value(env_values, ("RATE",), DEFAULT_RATE),
        "FREQ": _first_value(env_values, ("FREQ",), DEFAULT_FREQ),
        "GAIN": _first_value(env_values, ("TX_GAIN",), DEFAULT_TX_GAIN),
        "ANT": _first_value(env_values, ("TX_ANT",), "TX/RX"),
        "BIND_ADDR": _first_value(env_values, ("TX_BIND_ADDR", "BIND_ADDR"), "127.0.0.1"),
        "PORT": str(tx_port),
    })
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.Popen(
                [resolve_bash_executable(), str(script)],
                cwd=REPO_ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            return {
                "status": "error",
                "message": f"TX persistent server 启动失败: {type(exc).__name__}: {exc}",
                "log_path": str(log_path),
            }
    return {"status": "started", "pid": proc.pid, "log_path": str(log_path)}


def _run_remote_command(
    access: BoardAccessConfig,
    command: str,
    *,
    timeout: float = 20.0,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    cmd = [
        resolve_bash_executable(),
        str(SSH_HELPER),
        "--host",
        access.host,
        "--user",
        access.user,
        "--pass",
        access.password,
        "--port",
        access.port,
        "--",
        command,
    ]
    env = os.environ.copy()
    env.setdefault("OPENAMP_SSH_TIMEOUT_SEC", str(max(1.0, timeout)))
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    proc: subprocess.Popen[bytes] | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as stdout_file, tempfile.NamedTemporaryFile(delete=False) as stderr_file:
            stdout_path = Path(stdout_file.name)
            stderr_path = Path(stderr_file.name)
            proc = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
            )
            if input_data is not None and proc.stdin is not None:
                try:
                    proc.stdin.write(input_data)
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            returncode = proc.wait(timeout=timeout)
        stdout = stdout_path.read_bytes() if stdout_path is not None and stdout_path.exists() else b""
        stderr = stderr_path.read_bytes() if stderr_path is not None and stderr_path.exists() else b""
        return subprocess.CompletedProcess(cmd, int(returncode or 0), stdout=stdout, stderr=stderr)
    except subprocess.TimeoutExpired as exc:
        try:
            if os.name == "nt" and proc is not None:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(getattr(proc, "pid", ""))],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            elif proc is not None:
                proc.kill()
        except Exception:
            pass
        try:
            if proc is not None:
                proc.wait(timeout=5)
        except Exception:
            pass
        stdout = stdout_path.read_bytes() if stdout_path is not None and stdout_path.exists() else b""
        stderr = stderr_path.read_bytes() if stderr_path is not None and stderr_path.exists() else b""
        detail = f"TimeoutExpired: remote command timed out after {timeout:.1f}s".encode("utf-8")
        stderr = (stderr + b"\n" + detail).strip()
        return subprocess.CompletedProcess(cmd, 124, stdout=stdout, stderr=stderr)
    finally:
        for path in (stdout_path, stderr_path):
            if path is None:
                continue
            try:
                path.unlink()
            except OSError:
                pass


def _start_remote_rx_server(
    access: BoardAccessConfig,
    env_values: dict[str, str],
    *,
    rx_port: str,
    remote_run_root: str,
    remote_project_root: str,
) -> dict[str, Any]:
    if not SSH_HELPER.is_file():
        return {"status": "error", "message": f"ssh helper 不存在: {SSH_HELPER}"}
    remote_log_dir = f"{remote_run_root.rstrip('/')}/server_logs"
    remote_log = f"{remote_log_dir}/rx_persistent_cockpit_{int(time.time())}.log"
    remote_cmd = "bash -lc " + shlex.quote(
        "set -e; "
        f"cd {shlex.quote(remote_project_root)}; "
        f"mkdir -p {shlex.quote(remote_log_dir)}; "
        "nohup env "
        f"DEVICE_ARGS={shlex.quote(_first_value(env_values, ('RX_ARGS',), DEFAULT_RX_ARGS))} "
        f"RATE={shlex.quote(_first_value(env_values, ('RATE',), DEFAULT_RATE))} "
        f"FREQ={shlex.quote(_first_value(env_values, ('FREQ',), DEFAULT_FREQ))} "
        f"GAIN={shlex.quote(_first_value(env_values, ('RX_GAIN',), DEFAULT_RX_GAIN))} "
        f"ANT={shlex.quote(_first_value(env_values, ('RX_ANT',), DEFAULT_RX_ANT))} "
        f"BIND_ADDR={shlex.quote(_first_value(env_values, ('RX_BIND_ADDR', 'BIND_ADDR'), DEFAULT_BIND_ADDR))} "
        f"PORT={shlex.quote(str(rx_port))} "
        "./USRP292x/OtaRxPersistentServer.sh "
        f"> {shlex.quote(remote_log)} 2>&1 < /dev/null & "
        "sleep 1"
    )
    proc = _run_remote_command(access, remote_cmd, timeout=60.0)
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        return {
            "status": "error",
            "message": stderr or stdout or f"ssh rc={proc.returncode}",
            "remote_log": remote_log,
        }
    return {"status": "started", "remote_log": remote_log}


def _ensure_usrp_control_servers(
    access: BoardAccessConfig,
    env_values: dict[str, str],
    *,
    rx_host: str,
    rx_port: str,
    tx_host: str,
    tx_port: str,
    remote_run_root: str,
    remote_project_root: str,
    auto_start: bool,
    log_dir: Path,
) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {
        "rx_control": {"host": rx_host, "port": rx_port},
        "tx_control": {"host": tx_host, "port": tx_port},
        "auto_start": auto_start,
    }
    rx_ready, rx_response = _control_is_ready(rx_host, rx_port)
    tx_ready, tx_response = _control_is_ready(tx_host, tx_port)
    details["rx_control"]["initial_response"] = rx_response
    details["tx_control"]["initial_response"] = tx_response

    if auto_start and not rx_ready and access.connection_ready and rx_host == access.host:
        details["rx_start"] = _start_remote_rx_server(
            access,
            env_values,
            rx_port=rx_port,
            remote_run_root=remote_run_root,
            remote_project_root=remote_project_root,
        )
    if auto_start and not tx_ready and tx_host in {"127.0.0.1", "localhost", "::1"}:
        details["tx_start"] = _start_local_tx_server(env_values, log_dir=log_dir, tx_port=tx_port)

    deadline = time.monotonic() + CONTROL_START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        rx_ready, rx_response = _control_is_ready(rx_host, rx_port)
        tx_ready, tx_response = _control_is_ready(tx_host, tx_port)
        if rx_ready and tx_ready:
            break
        time.sleep(0.25)

    details["rx_control"]["ready"] = rx_ready
    details["rx_control"]["final_response"] = rx_response
    details["tx_control"]["ready"] = tx_ready
    details["tx_control"]["final_response"] = tx_response
    return rx_ready and tx_ready, details


def _shutdown_usrp_control_servers(
    *,
    rx_host: str,
    rx_port: str,
    tx_host: str,
    tx_port: str,
    enabled: bool,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "enabled": enabled,
        "rx_control": {"host": rx_host, "port": rx_port},
        "tx_control": {"host": tx_host, "port": tx_port},
    }
    if not enabled:
        details["status"] = "skipped"
        details["reason"] = "disabled_by_env"
        return details

    tx_quit = _tcp_control_command(tx_host, tx_port, "QUIT", timeout=CONTROL_SHUTDOWN_TIMEOUT_SEC)
    rx_stop = _tcp_control_command(rx_host, rx_port, "STOP", timeout=CONTROL_SHUTDOWN_TIMEOUT_SEC)
    rx_quit = _tcp_control_command(rx_host, rx_port, "QUIT", timeout=CONTROL_SHUTDOWN_TIMEOUT_SEC)
    details["tx_control"]["quit_response"] = tx_quit
    details["rx_control"]["stop_response"] = rx_stop
    details["rx_control"]["quit_response"] = rx_quit
    details["status"] = "completed" if tx_quit.startswith("OK") and rx_quit.startswith("OK") else "partial"
    return details


def _usrp_control_server_params(access: BoardAccessConfig, env_values: dict[str, str]) -> dict[str, Any]:
    rx_host = _first_value(env_values, RX_CONTROL_HOST_KEYS, access.host)
    rx_port = _first_value(env_values, RX_CONTROL_PORT_KEYS, DEFAULT_RX_CONTROL_PORT)
    tx_host = _first_value(env_values, TX_CONTROL_HOST_KEYS, "127.0.0.1")
    tx_port = _first_value(env_values, TX_CONTROL_PORT_KEYS, DEFAULT_TX_CONTROL_PORT)
    remote_run_root = _first_value(env_values, REMOTE_RX_RUN_ROOT_KEYS, DEFAULT_REMOTE_RX_RUN_ROOT)
    remote_project_root = _remote_usrp_project_root(env_values)
    auto_start = _parse_bool(_first_value(env_values, USRP_AUTO_START_CONTROL_KEYS, "1"), True)
    shutdown_after_transport = resolve_shutdown_after_transport(env_values)
    return {
        "rx_host": rx_host,
        "rx_port": rx_port,
        "tx_host": tx_host,
        "tx_port": tx_port,
        "remote_run_root": remote_run_root,
        "remote_project_root": remote_project_root,
        "auto_start": auto_start,
        "shutdown_after_transport": shutdown_after_transport,
    }


def inspect_usrp_control_servers(
    access: BoardAccessConfig,
    *,
    env_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    current_env = dict(env_values or access.build_env())
    params = _usrp_control_server_params(access, current_env)
    rx_host = str(params["rx_host"])
    rx_port = str(params["rx_port"])
    tx_host = str(params["tx_host"])
    tx_port = str(params["tx_port"])
    rx_ready, rx_response = _control_is_ready(rx_host, rx_port)
    tx_ready, tx_response = _control_is_ready(tx_host, tx_port)
    return {
        "status": "ready" if rx_ready and tx_ready else "not_ready",
        "rx_control": {
            "host": rx_host,
            "port": rx_port,
            "ready": rx_ready,
            "response": rx_response,
            "status": _tcp_control_command(rx_host, rx_port, "STATUS") if rx_ready else "",
        },
        "tx_control": {
            "host": tx_host,
            "port": tx_port,
            "ready": tx_ready,
            "response": tx_response,
            "status": _tcp_control_command(tx_host, tx_port, "STATUS") if tx_ready else "",
        },
        "auto_start": bool(params["auto_start"]),
        "shutdown_after_transport": bool(params["shutdown_after_transport"]),
    }


def ensure_usrp_control_servers_started(
    access: BoardAccessConfig,
    *,
    env_values: dict[str, str] | None = None,
    auto_start: bool | None = None,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    current_env = dict(env_values or access.build_env())
    params = _usrp_control_server_params(access, current_env)
    control_ready, details = _ensure_usrp_control_servers(
        access,
        current_env,
        rx_host=str(params["rx_host"]),
        rx_port=str(params["rx_port"]),
        tx_host=str(params["tx_host"]),
        tx_port=str(params["tx_port"]),
        remote_run_root=str(params["remote_run_root"]),
        remote_project_root=str(params["remote_project_root"]),
        auto_start=bool(params["auto_start"]) if auto_start is None else bool(auto_start),
        log_dir=log_dir or (REPO_ROOT / "USRP292x" / "server_logs"),
    )
    details["status"] = "ready" if control_ready else "error"
    details["shutdown_after_transport"] = bool(params["shutdown_after_transport"])
    if control_ready:
        details["message"] = "USRP persistent TX/RX 已就绪。"
    else:
        details["message"] = "USRP persistent TX/RX 未就绪。"
    return details


def shutdown_usrp_control_servers_now(
    access: BoardAccessConfig,
    *,
    env_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    current_env = dict(env_values or access.build_env())
    params = _usrp_control_server_params(access, current_env)
    details = _shutdown_usrp_control_servers(
        rx_host=str(params["rx_host"]),
        rx_port=str(params["rx_port"]),
        tx_host=str(params["tx_host"]),
        tx_port=str(params["tx_port"]),
        enabled=True,
    )
    if details.get("status") == "completed":
        details["message"] = "USRP persistent TX/RX 已关闭。"
    elif details.get("status") == "partial":
        details["message"] = "USRP persistent TX/RX 部分关闭，请检查响应。"
    else:
        details["message"] = "USRP persistent TX/RX 关闭已跳过。"
    return details


def _runner_failure_hint(log_text: str, summary: dict[str, Any], *, rc: int) -> str:
    text = str(log_text or "")
    patterns = (
        r"ERR_CONNECTION_REFUSED[^\n]*",
        r"ERR_TIMEOUT[^\n]*",
        r"RuntimeError:[^\n]*",
        r"command failed[^\n]*",
        r"remote RX pull[^\n]*",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    fail_count = int(summary.get("fail_count") or 0)
    if fail_count > 0:
        return f"fail_count={fail_count}"
    return f"rc={rc}"


def _split_local_latent_patterns(pattern: str) -> list[str]:
    text = str(pattern or "").strip()
    if not text:
        return ["*.npz", "*.pt"]
    patterns = [
        item.strip()
        for chunk in text.split(",")
        for item in chunk.split(";")
        if item.strip()
    ]
    return patterns or ["*.npz", "*.pt"]


def _collect_local_latent_files(input_dir: Path, pattern: str) -> list[Path]:
    files: list[Path] = []
    for item in _split_local_latent_patterns(pattern):
        files.extend(
            path
            for path in input_dir.rglob(item)
            if path.is_file() and ".usrp_wire_cache" not in path.parts
        )
    files = list({path.resolve(): path for path in files}.values())
    files.sort(key=lambda path: path.relative_to(input_dir).as_posix())
    return files


def _collect_local_image_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(path for path in input_dir.rglob(pattern) if path.is_file())
    files = list({path.resolve(): path for path in files}.values())
    files.sort(key=lambda path: path.relative_to(input_dir).as_posix())
    return files


def _host_image_latent_manifest_path(output_dir: Path) -> Path:
    return output_dir / HOST_IMAGE_LATENT_MANIFEST


def _host_latent_name_for_image(image_path: Path) -> str:
    return f"{hashlib.sha256(image_path.stem.encode()).hexdigest()}_latent.pt"


def _host_image_record(image_dir: Path, output_dir: Path, image_path: Path) -> dict[str, Any]:
    image_stat = image_path.stat()
    latent_path = output_dir / _host_latent_name_for_image(image_path)
    return {
        "source_image": str(image_path),
        "source_image_rel": image_path.relative_to(image_dir).as_posix(),
        "source_image_sha256": _sha256_file(image_path),
        "source_image_size": int(image_stat.st_size),
        "source_image_mtime_ns": int(image_stat.st_mtime_ns),
        "original_filename": image_path.stem,
        "latent": str(latent_path),
        "latent_rel": latent_path.relative_to(output_dir).as_posix(),
    }


def _host_image_records(image_dir: Path, output_dir: Path, count: int) -> tuple[list[dict[str, Any]], int]:
    images = _collect_local_image_files(image_dir)
    records = [_host_image_record(image_dir, output_dir, image_path) for image_path in images[:count]]
    return records, len(images)


def _write_host_image_latent_manifest(
    *,
    output_dir: Path,
    image_dir: Path,
    files: list[dict[str, Any]],
    config_str: str,
    snr: str,
    device: str,
    elapsed_sec: float,
    available_image_count: int | None = None,
    command: list[str] | None = None,
    log_path: Path | None = None,
    status: str = "encoded",
) -> dict[str, Any]:
    for item in files:
        latent_path = Path(str(item.get("latent") or ""))
        if not latent_path.is_file():
            continue
        latent_stat = latent_path.stat()
        item["latent_sha256"] = _sha256_file(latent_path)
        item["latent_size"] = int(latent_stat.st_size)
        item["latent_mtime_ns"] = int(latent_stat.st_mtime_ns)

    manifest = {
        "version": HOST_IMAGE_LATENT_MANIFEST_VERSION,
        "status": status,
        "source": "image_dir",
        "image_dir": str(image_dir),
        "latent_dir": str(output_dir),
        "count": len(files),
        "used_count": len(files),
        "available_image_count": int(available_image_count if available_image_count is not None else len(files)),
        "config_str": str(config_str),
        "snr": str(snr),
        "device": str(device),
        "elapsed_sec": round(elapsed_sec, 3),
        "files": files,
    }
    if command is not None:
        manifest["command"] = command
    if log_path is not None:
        manifest["log_path"] = str(log_path)
    _atomic_write_json(_host_image_latent_manifest_path(output_dir), manifest)
    return manifest


def _host_image_latent_cache_valid(
    *,
    image_dir: Path,
    output_dir: Path,
    expected_count: int,
    config_str: str,
    snr: str,
    device: str,
) -> tuple[dict[str, Any], list[Path]] | None:
    manifest_path = _host_image_latent_manifest_path(output_dir)
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if int(manifest.get("version") or 0) != HOST_IMAGE_LATENT_MANIFEST_VERSION:
        return None
    if Path(str(manifest.get("image_dir") or "")).resolve() != image_dir.resolve():
        return None
    if Path(str(manifest.get("latent_dir") or "")).resolve() != output_dir.resolve():
        return None
    if str(manifest.get("config_str") or "") != str(config_str):
        return None
    if str(manifest.get("snr") or "") != str(snr):
        return None
    if str(manifest.get("device") or "") != str(device):
        return None

    files = list(manifest.get("files") or [])
    if len(files) < expected_count:
        return None
    current_records, available_count = _host_image_records(image_dir, output_dir, expected_count)
    if available_count < expected_count:
        return None

    latent_files: list[Path] = []
    for saved, current in zip(files[:expected_count], current_records, strict=False):
        for key in (
            "source_image_rel",
            "source_image_sha256",
            "source_image_size",
            "source_image_mtime_ns",
            "latent_rel",
        ):
            if saved.get(key) != current.get(key):
                return None
        latent_path = Path(str(saved.get("latent") or ""))
        if not latent_path.is_file():
            return None
        if saved.get("latent_size") is not None and int(saved.get("latent_size") or -1) != latent_path.stat().st_size:
            return None
        if saved.get("latent_sha256") and str(saved.get("latent_sha256") or "") != _sha256_file(latent_path):
            return None
        latent_files.append(latent_path)

    manifest["status"] = "cache_hit"
    manifest["source"] = "image_manifest"
    manifest["used_count"] = expected_count
    manifest["available_image_count"] = available_count
    manifest["manifest_path"] = str(manifest_path)
    return manifest, latent_files


def _enrich_wire_manifest_with_host_images(
    manifest: dict[str, Any],
    host_manifest: dict[str, Any] | None,
    manifest_path: Path,
) -> dict[str, Any]:
    if not host_manifest:
        return manifest
    host_files = list(host_manifest.get("files") or [])
    if not host_files:
        return manifest

    by_latent: dict[str, dict[str, Any]] = {}
    for item in host_files:
        try:
            latent_key = str(Path(str(item.get("latent") or "")).resolve())
        except OSError:
            continue
        by_latent[latent_key] = item

    changed = False
    for item in list(manifest.get("files") or []):
        try:
            source_key = str(Path(str(item.get("source") or "")).resolve())
        except OSError:
            continue
        host_item = by_latent.get(source_key)
        if not host_item:
            continue
        item["source_image_path"] = str(host_item.get("source_image") or "")
        item["source_image_rel"] = str(host_item.get("source_image_rel") or "")
        item["source_image_sha256"] = str(host_item.get("source_image_sha256") or "")
        item["source_image_size"] = int(host_item.get("source_image_size") or 0)
        item["source_image_mtime_ns"] = int(host_item.get("source_image_mtime_ns") or 0)
        item["source_image"] = str(host_item.get("original_filename") or item.get("source_image") or "")
        changed = True
    if changed:
        _atomic_write_json(manifest_path, manifest)
    return manifest


def _default_image_to_latent_script() -> Path:
    return REPO_ROOT / "host_pic_to_latent" / "encode_latent.py"


def _default_image_to_latent_output_dir() -> Path:
    return REPO_ROOT / "host_pic_to_latent" / "encoder_outputs_airfield300"


def _safe_cache_codec_name(payload_codec: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(payload_codec or "default"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wire_cache_paths(source_dir: Path, source_path: Path, cache_dir: Path, payload_codec: str) -> tuple[Path, Path]:
    rel = source_path.relative_to(source_dir)
    cache_rel = rel.with_name(f"{rel.name}.{_safe_cache_codec_name(payload_codec)}.wire.bin")
    cache_blob = cache_dir / cache_rel
    return cache_blob, cache_blob.with_suffix(cache_blob.suffix + ".json")


def _wire_cache_signature(source_path: Path) -> dict[str, int]:
    stat = source_path.stat()
    return {
        "source_size": int(stat.st_size),
        "source_mtime_ns": int(stat.st_mtime_ns),
    }


def _wire_cache_valid(cache_blob: Path, cache_meta: Path, source_path: Path, payload_codec: str, job_id: str) -> dict[str, Any] | None:
    if not cache_blob.is_file() or not cache_meta.is_file():
        return None
    try:
        metadata = json.loads(cache_meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None

    signature = _wire_cache_signature(source_path)
    if int(metadata.get("cache_version") or 0) != WIRE_CACHE_VERSION:
        return None
    if str(metadata.get("payload_codec") or "") != str(payload_codec):
        return None
    if str(metadata.get("job_id") or "") != str(job_id):
        return None
    if int(metadata.get("source_size") or -1) != signature["source_size"]:
        return None
    if int(metadata.get("source_mtime_ns") or -1) != signature["source_mtime_ns"]:
        return None
    source_sha256 = _sha256_file(source_path)
    if str(metadata.get("source_sha256") or "") != source_sha256:
        return None
    return metadata


def _install_wire_blob(blob_path: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    try:
        os.link(blob_path, target)
    except OSError:
        shutil.copy2(blob_path, target)


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    tmp.write_bytes(payload)
    os.replace(tmp, target)


def _atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def _prepare_single_wire_input(task: dict[str, Any]) -> dict[str, Any]:
    source_dir = Path(str(task["source_dir"]))
    source_path = Path(str(task["source_path"]))
    target = Path(str(task["target"]))
    payload_codec = str(task["payload_codec"])
    job_id = str(task["job_id"])
    cache_dir_text = str(task.get("cache_dir") or "")
    cache_dir = Path(cache_dir_text) if cache_dir_text else None

    cache_hit = False
    cache_blob: Path | None = None
    cache_metadata: dict[str, Any] | None = None
    if cache_dir is not None:
        cache_blob, cache_meta = _wire_cache_paths(source_dir, source_path, cache_dir, payload_codec)
        cache_metadata = _wire_cache_valid(cache_blob, cache_meta, source_path, payload_codec, job_id)
        if cache_metadata is not None:
            _install_wire_blob(cache_blob, target)
            cache_hit = True

    if cache_hit and cache_metadata is not None:
        payload_bytes = int(cache_metadata.get("payload_bytes") or 0)
        blob_bytes = int(cache_metadata.get("blob_bytes") or target.stat().st_size)
        source_sha256 = str(cache_metadata.get("source_sha256") or _sha256_file(source_path))
        original_filename = str(cache_metadata.get("original_filename") or "")
    else:
        blob, meta, stats = build_transport_blob(
            str(source_path),
            job_id=job_id,
            payload_codec=payload_codec,
        )
        payload_bytes = int(stats.get("payload_bytes") or len(blob))
        blob_bytes = len(blob)
        source_sha256 = _sha256_file(source_path)
        original_filename = str(meta.get("original_filename") or stats.get("original_filename") or "")
        if cache_blob is not None:
            _atomic_write_bytes(cache_blob, blob)
            cache_metadata = {
                "cache_version": WIRE_CACHE_VERSION,
                "source": str(source_path),
                "source_rel": source_path.relative_to(source_dir).as_posix(),
                "source_sha256": source_sha256,
                "original_filename": original_filename,
                "job_id": str(meta.get("job_id") or job_id),
                "payload_codec": str(stats.get("payload_codec") or payload_codec),
                "payload_bytes": payload_bytes,
                "blob_bytes": blob_bytes,
                **_wire_cache_signature(source_path),
            }
            _atomic_write_json(cache_blob.with_suffix(cache_blob.suffix + ".json"), cache_metadata)
            _install_wire_blob(cache_blob, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)

    return {
        "source": str(source_path),
        "source_rel": source_path.relative_to(source_dir).as_posix(),
        "source_sha256": source_sha256,
        "source_image": original_filename,
        "original_filename": original_filename,
        "target": str(target),
        "job_id": job_id,
        "payload_codec": payload_codec,
        "payload_bytes": payload_bytes,
        "blob_bytes": blob_bytes,
        "cache_hit": cache_hit,
    }


def _prepare_wire_input_dir(
    *,
    source_dir: Path,
    output_dir: Path,
    payload_codec: str,
    pattern: str,
    max_files: int | None = None,
    cache_dir: Path | None = None,
    prepare_workers: int = 1,
    source_files: list[Path] | None = None,
) -> dict[str, Any]:
    files = list(source_files) if source_files is not None else _collect_local_latent_files(source_dir, pattern)
    if not files:
        patterns = ",".join(_split_local_latent_patterns(pattern))
        raise RuntimeError(f"未找到待发送 latent 文件: dir={source_dir} pattern={patterns}")
    available_count = len(_collect_local_latent_files(source_dir, pattern)) if source_files is not None else len(files)
    if source_files is None and max_files is not None and max_files > 0:
        files = files[:max_files]

    output_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[dict[str, Any]] = []
    for path in files:
        if not path.is_file():
            raise RuntimeError(f"待发送 latent 文件不存在: {path}")
        rel = path.relative_to(source_dir)
        target = output_dir / rel.with_suffix(rel.suffix + ".bin")
        tasks.append(
            {
                "source_dir": str(source_dir),
                "source_path": str(path),
                "target": str(target),
                "job_id": path.stem,
                "payload_codec": payload_codec,
                "cache_dir": str(cache_dir) if cache_dir is not None else "",
            }
        )

    workers = max(1, min(int(prepare_workers or 1), len(tasks)))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            prepared_files = list(pool.map(_prepare_single_wire_input, tasks))
    else:
        prepared_files = [_prepare_single_wire_input(task) for task in tasks]

    manifest = {
        "source_dir": str(source_dir),
        "pattern": pattern,
        "payload_codec": payload_codec,
        "available_count": available_count,
        "count": len(prepared_files),
        "selected_count": len(prepared_files),
        "prepare_workers": workers,
        "cache_enabled": cache_dir is not None,
        "cache_dir": str(cache_dir) if cache_dir is not None else "",
        "cache_hit_count": sum(1 for item in prepared_files if item.get("cache_hit")),
        "files": prepared_files,
    }
    (output_dir / "usrp_input_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _safe_rmtree(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError:
        pass


def _stage_merged_wire_blobs_for_remote_decode(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    wire_dir = output_dir / "_wire"
    support_dir = output_dir / "_support"
    wire_dir.mkdir(parents=True, exist_ok=True)
    support_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_SCRIPTS / "latent_transport.py", support_dir / "latent_transport.py")
    (output_dir / "decode_usrp_wire.py").write_text(BOARD_DECODE_SCRIPT, encoding="utf-8")

    staged_files: list[dict[str, Any]] = []

    image_dirs = sorted(path for path in run_dir.glob("image_*") if path.is_dir())
    for image_dir in image_dirs:
        merged_bins = sorted(image_dir.glob("merged_round*.bin"))
        if not merged_bins:
            continue
        merged_bin = merged_bins[-1]
        blob_bytes = merged_bin.read_bytes()
        meta, payload_bytes = unpack_transport_frame(blob_bytes)
        job_id = str(meta.get("job_id") or merged_bin.stem)
        target = wire_dir / f"{job_id}.bin"
        target.write_bytes(blob_bytes)
        staged_files.append(
            {
                "source_bin": str(merged_bin),
                "target_bin": str(target),
                "job_id": job_id,
                "payload_codec": str(meta.get("payload_codec") or ""),
                "payload_bytes": len(payload_bytes),
                "blob_bytes": len(blob_bytes),
            }
        )

    if not staged_files:
        raise RuntimeError(f"未找到可同步到板端解包的 merged wire blob: {run_dir}")

    manifest = {
        "run_dir": str(run_dir),
        "stage_dir": str(output_dir),
        "wire_dir": str(wire_dir),
        "staged_count": len(staged_files),
        "files": staged_files,
    }
    (output_dir / "usrp_wire_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _tar_directory_bytes(source_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            archive.add(path, arcname=path.relative_to(source_dir).as_posix())
    return buffer.getvalue()


def _sync_and_decode_wire_blobs_on_remote(
    *,
    local_stage_dir: Path,
    remote_root: str,
    remote_subdir: str,
    remote_python: str,
    access: BoardAccessConfig,
) -> dict[str, Any]:
    if not SSH_HELPER.is_file():
        raise RuntimeError(f"ssh helper 不存在: {SSH_HELPER}")
    if not access.connection_ready:
        raise RuntimeError("板端连接信息不完整，无法同步并解包 USRP RX 结果")

    remote_root_text = str(remote_root or "").strip().rstrip("/")
    if not remote_root_text:
        raise RuntimeError("REMOTE_USRP_RX_DIR 未配置")
    remote_dir = f"{remote_root_text}/{remote_subdir}".rstrip("/")
    remote_python_cmd = str(remote_python or "").strip() or "python3"
    payload = _tar_directory_bytes(local_stage_dir)
    local_tar_path: Path | None = None
    remote_tar_path = f"/tmp/cockpit_usrp_wire_{os.getpid()}_{int(time.time() * 1000)}.tar.gz"
    scp_env = os.environ.copy()
    scp_env.update(CHILD_PROCESS_ENV)
    scp_env["SSHPASS"] = access.password
    scp_command = [
        "sshpass",
        "-e",
        "scp",
        "-q",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "BatchMode=no",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-P",
        access.port,
    ]
    remote_command = (
        f"set -euo pipefail && mkdir -p {shlex.quote(remote_dir)} "
        f"&& tar xzf {shlex.quote(remote_tar_path)} -C {shlex.quote(remote_dir)} "
        f"&& rm -f {shlex.quote(remote_tar_path)} "
        f"&& cd {shlex.quote(remote_dir)} "
        f"&& {remote_python_cmd} decode_usrp_wire.py --wire-dir _wire --output-dir ."
    )
    command = [
        resolve_bash_executable(),
        str(SSH_HELPER),
        "--host",
        access.host,
        "--user",
        access.user,
        "--pass",
        access.password,
        "--port",
        access.port,
        "--",
        remote_command,
    ]
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
            tmp.write(payload)
            local_tar_path = Path(tmp.name)
        scp_result = subprocess.run(
            [
                *scp_command,
                str(local_tar_path),
                f"{access.user}@{access.host}:{remote_tar_path}",
            ],
            capture_output=True,
            cwd=REPO_ROOT,
            env=scp_env,
            check=False,
        )
        if scp_result.returncode != 0:
            stderr = scp_result.stderr.decode("utf-8", errors="ignore").strip()
            stdout = scp_result.stdout.decode("utf-8", errors="ignore").strip()
            detail = stderr or stdout or f"scp rc={scp_result.returncode}"
            raise RuntimeError(f"板端 USRP RX 目录上传失败: {detail}")
        result = subprocess.run(
            command,
            capture_output=True,
            cwd=REPO_ROOT,
            env=scp_env,
            check=False,
        )
    finally:
        if local_tar_path is not None:
            try:
                local_tar_path.unlink()
            except OSError:
                pass
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        stdout = result.stdout.decode("utf-8", errors="ignore").strip()
        detail = stderr or stdout or f"ssh helper rc={result.returncode}"
        raise RuntimeError(f"板端 USRP RX 目录同步/解包失败: {detail}")
    stdout = result.stdout.decode("utf-8", errors="ignore").strip()
    decode_manifest: dict[str, Any] = {}
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload_json = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload_json, dict):
            decode_manifest = payload_json
            break
    return {
        "remote_root": remote_root_text,
        "remote_dir": remote_dir,
        "remote_wire_dir": f"{remote_dir}/_wire",
        "decode_location": "board",
        "remote_python": remote_python_cmd,
        "uploaded_bytes": len(payload),
        "decode_manifest": decode_manifest,
    }


def _iq_remote_decode_stage_manifest_from_summary(summary: dict[str, Any]) -> dict[str, Any] | None:
    if str(summary.get("remote_decode_result_mode") or "").strip().lower() != "remote-dir":
        return None
    remote_dir = str(summary.get("remote_decoded_output_dir") or "").strip().rstrip("/")
    if not remote_dir:
        return None
    remote_files = [
        str(path or "").strip()
        for path in summary.get("remote_received_latent_npz_files", [])
        if str(path or "").strip()
    ]
    if not remote_files:
        images = summary.get("images") if isinstance(summary.get("images"), list) else []
        for image in images:
            if not isinstance(image, dict):
                continue
            records = image.get("round_records") if isinstance(image.get("round_records"), list) else []
            for record in records:
                if not isinstance(record, dict):
                    continue
                remote_npz = str(record.get("remote_received_latent_npz") or "").strip()
                if remote_npz:
                    remote_files.append(remote_npz)
    remote_root = remote_dir.rsplit("/", 1)[0] if "/" in remote_dir else remote_dir
    return {
        "remote_root": remote_root,
        "remote_dir": remote_dir,
        "remote_wire_dir": "",
        "decode_location": "board",
        "remote_python": "",
        "uploaded_bytes": 0,
        "decode_manifest": {
            "status": "ok",
            "source": "iq_remote_decode",
            "decoded_count": len(remote_files),
            "files": remote_files,
        },
    }


def _image_index_from_run_dir(image_dir: Path) -> int | None:
    match = re.fullmatch(r"image_(\d+)", image_dir.name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _iq_remote_decode_stage_manifest_from_image_dirs(run_dir: Path, remote_dir: str) -> dict[str, Any] | None:
    remote_dir = str(remote_dir or "").strip().rstrip("/")
    if not remote_dir:
        return None
    try:
        image_dirs = sorted(path for path in run_dir.glob("image_*") if path.is_dir())
    except OSError:
        return None

    decoded_images: list[dict[str, Any]] = []
    for image_dir in image_dirs:
        image_index = _image_index_from_run_dir(image_dir)
        if image_index is None:
            continue
        summary_path = image_dir / "decode_summary.json"
        if not summary_path.is_file():
            continue
        summary = _safe_read_json(summary_path)
        status_ok = str(summary.get("status") or "").strip().lower() in {"", "ok", "success"}
        frame_complete = bool(summary.get("frame_complete", True))
        if not (status_ok and frame_complete):
            continue
        remote_npz = str(
            summary.get("remote_received_latent_npz")
            or summary.get("target_npz")
            or summary.get("out_npz")
            or ""
        ).strip()
        if not remote_npz:
            remote_npz = f"{remote_dir}/{image_index:08d}.npz"
        decoded_images.append(
            {
                "index": image_index,
                "status": "decoded",
                "remote_npz": remote_npz,
                "decode_summary": str(summary_path),
            }
        )

    if not decoded_images:
        return None

    decoded_images.sort(key=lambda item: int(item["index"]))
    remote_files = [str(item["remote_npz"]) for item in decoded_images]
    remote_root = remote_dir.rsplit("/", 1)[0] if "/" in remote_dir else remote_dir
    return {
        "remote_root": remote_root,
        "remote_dir": remote_dir,
        "remote_wire_dir": "",
        "decode_location": "board",
        "remote_python": "",
        "uploaded_bytes": 0,
        "decode_manifest": {
            "status": "ok",
            "source": "iq_remote_decode_partial",
            "decoded_count": len(remote_files),
            "files": remote_files,
            "images": decoded_images,
        },
    }


def _sync_iq_decode_assets_on_remote(
    access: BoardAccessConfig,
    *,
    remote_project_root: str,
    probe_timeout_sec: float = 15.0,
    upload_timeout_sec: float = 90.0,
) -> dict[str, Any]:
    if not access.connection_ready:
        raise RuntimeError("板端连接信息不完整，无法同步 IQ remote-decode 资产")
    remote_root = str(remote_project_root or "").strip().rstrip("/") or DEFAULT_REMOTE_USRP_PROJECT_ROOT
    assets = (
        (REPO_ROOT / "USRP292x" / "AnalogLatentLink.py", "USRP292x/AnalogLatentLink.py"),
        (ROOT_SCRIPTS / "latent_transport.py", "scripts/latent_transport.py"),
    )
    missing = [str(path) for path, _ in assets if not path.is_file()]
    if missing:
        raise RuntimeError(f"IQ remote-decode 本地资产缺失: {', '.join(missing)}")

    local_hashes = {
        f"{remote_root}/{arcname}": hashlib.sha256(local_path.read_bytes()).hexdigest()
        for local_path, arcname in assets
    }
    cache_key = (
        access.host,
        access.user,
        str(access.port or "22"),
        remote_root,
        tuple(sorted(local_hashes.items())),
    )
    cached = _IQ_DECODE_ASSET_SYNC_CACHE.get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["status"] = "cached"
        result["cached_from_status"] = cached.get("status")
        result["uploaded_bytes"] = 0
        return result

    probe_timeout = max(1.0, float(probe_timeout_sec or 15.0))
    upload_timeout = max(1.0, float(upload_timeout_sec or 90.0))
    probe_command = (
        "if command -v sha256sum >/dev/null 2>&1; then "
        + "sha256sum "
        + " ".join(shlex.quote(path) for path in local_hashes)
        + " 2>/dev/null || true; fi"
    )
    probe_result = _run_remote_command(access, probe_command, timeout=probe_timeout)
    if probe_result.returncode == 0:
        remote_hashes: dict[str, str] = {}
        for line in probe_result.stdout.decode("utf-8", errors="ignore").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                remote_hashes[parts[1].strip()] = parts[0].strip().lower()
        if local_hashes and all(remote_hashes.get(path) == digest for path, digest in local_hashes.items()):
            result = {
                "status": "current",
                "remote_project_root": remote_root,
                "uploaded_bytes": 0,
                "files": [arcname for _, arcname in assets],
            }
            _IQ_DECODE_ASSET_SYNC_CACHE[cache_key] = dict(result)
            return result

    payload_buffer = io.BytesIO()
    with tarfile.open(fileobj=payload_buffer, mode="w:gz") as archive:
        for local_path, arcname in assets:
            archive.add(local_path, arcname=arcname)
    payload = payload_buffer.getvalue()
    remote_tar_path = f"/tmp/cockpit_iq_decode_assets_{os.getpid()}_{int(time.time() * 1000)}.tar.gz"
    upload_command = (
        f"set -e; mkdir -p {shlex.quote(remote_root)}; "
        f"cat > {shlex.quote(remote_tar_path)}; "
        f"tar xzf {shlex.quote(remote_tar_path)} -C {shlex.quote(remote_root)}; "
        f"rm -f {shlex.quote(remote_tar_path)}"
    )
    ssh_result = _run_remote_command(access, upload_command, timeout=upload_timeout, input_data=payload)
    if ssh_result.returncode != 0:
        detail = (
            ssh_result.stderr.decode("utf-8", errors="ignore").strip()
            or ssh_result.stdout.decode("utf-8", errors="ignore").strip()
            or f"ssh rc={ssh_result.returncode}"
        )
        raise RuntimeError(f"IQ remote-decode 资产上传/解包失败: {detail}")
    result = {
        "status": "uploaded",
        "remote_project_root": remote_root,
        "uploaded_bytes": len(payload),
        "files": [arcname for _, arcname in assets],
    }
    _IQ_DECODE_ASSET_SYNC_CACHE[cache_key] = dict(result)
    return result


def _normalize_inference_engine(raw_value: str) -> str:
    value = str(raw_value or "").strip().lower()
    if not value:
        return INFERENCE_ENGINE_NONE
    if value in {"none", "off", "disabled", "0"}:
        return INFERENCE_ENGINE_NONE
    if value in {"tvm", "current"}:
        return INFERENCE_ENGINE_TVM
    if value in {"mnn"}:
        return INFERENCE_ENGINE_MNN
    return INFERENCE_ENGINE_NONE


def _extract_progress_count(payload: dict[str, Any], *, fallback_total: int) -> tuple[int, int]:
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    completed_raw = progress.get("completed_count") if progress else payload.get("processed_count")
    total_raw = progress.get("expected_count") if progress else payload.get("selected_input_count")
    try:
        completed = int(completed_raw or 0)
    except (TypeError, ValueError):
        completed = 0
    try:
        total = int(total_raw or fallback_total or 1)
    except (TypeError, ValueError):
        total = max(1, int(fallback_total or 1))
    return max(0, completed), max(1, total)


def _tvm_benchmark_from_runner_summary(summary: dict[str, Any]) -> dict[str, Any]:
    samples = summary.get("run_samples_ms") if isinstance(summary.get("run_samples_ms"), list) else []
    values: list[float] = []
    for item in samples:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue

    def metric_from_values(items: list[float]) -> dict[str, Any] | None:
        if not items:
            return None
        ordered = sorted(items)
        n = len(ordered)
        return {
            "n": n,
            "min_ms": round(ordered[0], 2),
            "max_ms": round(ordered[-1], 2),
            "mean_ms": round(sum(ordered) / n, 2),
            "median_ms": round(ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0, 2),
            "p95_ms": round(ordered[int(n * 0.95)], 2) if n >= 20 else None,
        }

    metric = metric_from_values(values)
    return {
        "handshake_ms": None,
        "encrypt_ms": None,
        "decrypt_ms": None,
        "inference_ms": metric,
        "total_ms": metric,
    }


def _mnn_benchmark_from_runner_summary(summary: dict[str, Any]) -> dict[str, Any]:
    sample_stats = summary.get("sample_stats") if isinstance(summary, dict) else {}
    sample_stats = sample_stats if isinstance(sample_stats, dict) else {}

    def metric(raw: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        try:
            count = int(raw.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return None
        return {
            "n": count,
            "min_ms": round(float(raw.get("min_ms") or 0.0), 2),
            "max_ms": round(float(raw.get("max_ms") or 0.0), 2),
            "mean_ms": round(float(raw.get("mean_ms") or 0.0), 2),
            "median_ms": round(float(raw.get("median_ms") or 0.0), 2),
            "p95_ms": None,
        }

    return {
        "handshake_ms": None,
        "encrypt_ms": None,
        "decrypt_ms": None,
        "inference_ms": metric(sample_stats.get("run_ms")),
        "total_ms": metric(sample_stats.get("total_ms")),
    }


def _single_metric_from_value(value: float | int | None, *, n: int) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0:
        return None
    rounded = round(numeric, 2)
    return {
        "n": max(1, int(n)),
        "min_ms": rounded,
        "max_ms": rounded,
        "mean_ms": rounded,
        "median_ms": rounded,
        "p95_ms": None,
    }


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


def _float_from_mapping(mapping: Mapping[str, Any], key: str) -> float:
    try:
        return float(mapping.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _transport_benchmark_from_iq_round_records(summary: dict[str, Any]) -> dict[str, Any] | None:
    images = summary.get("images") if isinstance(summary, dict) else None
    if not isinstance(images, list):
        return None

    total_ms_values: list[float] = []
    airtime_ms_values: list[float] = []
    decode_ms_values: list[float] = []
    merge_ms_values: list[float] = []
    rx_pull_ms_values: list[float] = []
    cleanup_ms_values: list[float] = []
    other_ms_values: list[float] = []
    for image in images:
        if not isinstance(image, dict):
            continue
        records = image.get("round_records")
        if not isinstance(records, list) or not records:
            continue
        total_sec = 0.0
        airtime_ms = 0.0
        decode_sec = 0.0
        merge_sec = 0.0
        rx_pull_sec = 0.0
        cleanup_sec = 0.0
        for record in records:
            if not isinstance(record, dict):
                continue
            total_sec += _float_from_mapping(record, "total_wall_sec")
            airtime_ms += _float_from_mapping(record, "detected_airtime_ms")
            decode_sec += _float_from_mapping(record, "decode_wall_sec")
            merge_sec += _float_from_mapping(record, "merge_wall_sec")
            rx_pull_sec += _float_from_mapping(record, "rx_pull_wall_sec")
            cleanup_sec += _float_from_mapping(record, "remote_cleanup_wall_sec")
        if total_sec <= 0.0:
            continue
        total_ms_values.append(total_sec * 1000.0)
        if airtime_ms >= 0.0:
            airtime_ms_values.append(airtime_ms)
        decode_ms_values.append(decode_sec * 1000.0)
        merge_ms_values.append(merge_sec * 1000.0)
        rx_pull_ms_values.append(rx_pull_sec * 1000.0)
        cleanup_ms_values.append(cleanup_sec * 1000.0)
        other_sec = max(
            0.0,
            total_sec - (airtime_ms / 1000.0) - decode_sec - merge_sec - rx_pull_sec - cleanup_sec,
        )
        other_ms_values.append(other_sec * 1000.0)

    if not total_ms_values:
        return None
    return {
        "radio_airtime_ms": _metric_from_ms_values(airtime_ms_values),
        "decode_ms": _metric_from_ms_values(decode_ms_values),
        "merge_ms": _metric_from_ms_values(merge_ms_values),
        "rx_pull_ms": _metric_from_ms_values(rx_pull_ms_values),
        "remote_cleanup_ms": _metric_from_ms_values(cleanup_ms_values),
        "other_wall_ms": _metric_from_ms_values(other_ms_values),
        "total_ms": _metric_from_ms_values(total_ms_values),
    }


def _iq_stage_benchmark_from_summary(summary: dict[str, Any]) -> dict[str, Any] | None:
    existing = summary.get("iq_stage_benchmark") if isinstance(summary, dict) else None
    if isinstance(existing, dict) and existing:
        return existing
    images = summary.get("images") if isinstance(summary, dict) else None
    if not isinstance(images, list):
        return None

    field_map = (
        ("tx_control_ms", "tx_wall_sec"),
        ("rx_capture_ms", "rx_capture_wall_sec"),
        ("remote_decode_ms", "decode_wall_sec"),
        ("remote_dir_publish_ms", "remote_dir_publish_wall_sec"),
        ("retry_wait_ms", "retry_wait_wall_sec"),
        ("total_transport_ms", "total_wall_sec"),
    )
    stage_values: dict[str, list[float]] = {metric_name: [] for metric_name, _ in field_map}
    for image in images:
        if not isinstance(image, dict):
            continue
        records = image.get("round_records")
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            for metric_name, record_field in field_map:
                if record_field not in record:
                    continue
                try:
                    value = float(record.get(record_field) or 0.0)
                except (TypeError, ValueError):
                    continue
                if value >= 0.0:
                    stage_values[metric_name].append(value * 1000.0)

    benchmark: dict[str, Any] = {}
    for metric_name, values in stage_values.items():
        metric = _metric_from_ms_values(values)
        if metric is not None:
            benchmark[metric_name] = metric
    return benchmark or None


def _transport_benchmark_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    record_benchmark = _transport_benchmark_from_iq_round_records(summary)
    if record_benchmark is not None:
        return record_benchmark
    count = max(1, int(summary.get("pass_count") or summary.get("completed_count") or summary.get("target_count") or 1))
    per_image_sec = float(summary.get("per_image_sec") or 0.0)
    payload_airtime_ms_mean = float(summary.get("payload_airtime_ms_mean") or 0.0)
    decode_total_wall_sec_mean = float(summary.get("decode_total_wall_sec_mean") or 0.0)
    merge_wall_sec_mean = float(summary.get("merge_wall_sec_mean") or 0.0)
    rx_pull_wall_sec_mean = float(summary.get("rx_pull_wall_sec_mean") or 0.0)
    remote_cleanup_wall_sec_mean = float(summary.get("remote_cleanup_wall_sec_mean") or 0.0)
    other_sec_mean = float(summary.get("estimated_non_airtime_non_decode_non_merge_wall_sec_mean") or 0.0)
    air_ms = payload_airtime_ms_mean if payload_airtime_ms_mean > 0 else None
    decode_ms = decode_total_wall_sec_mean * 1000.0 if decode_total_wall_sec_mean > 0 else None
    merge_ms = merge_wall_sec_mean * 1000.0 if merge_wall_sec_mean > 0 else None
    rx_pull_ms = rx_pull_wall_sec_mean * 1000.0 if rx_pull_wall_sec_mean > 0 else None
    remote_cleanup_ms = remote_cleanup_wall_sec_mean * 1000.0 if remote_cleanup_wall_sec_mean > 0 else None
    other_ms = other_sec_mean * 1000.0 if other_sec_mean > 0 else None
    total_ms = per_image_sec * 1000.0 if per_image_sec > 0 else None
    return {
        "radio_airtime_ms": _single_metric_from_value(air_ms, n=count),
        "decode_ms": _single_metric_from_value(decode_ms, n=count),
        "merge_ms": _single_metric_from_value(merge_ms, n=count),
        "rx_pull_ms": _single_metric_from_value(rx_pull_ms, n=count),
        "remote_cleanup_ms": _single_metric_from_value(remote_cleanup_ms, n=count),
        "other_wall_ms": _single_metric_from_value(other_ms, n=count),
        "total_ms": _single_metric_from_value(total_ms, n=count),
    }


def _aggregate_iq_radio_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    """Aggregate IQ-direct PHY metrics (sync_metric / evm_rms / estimated_cfo_hz /
    estimated_snr_db / rx_clipping_ratio / latent_mse_vs_tx) across all images
    in an AnalogLatentLink batch_spool_summary.json.

    Returns {} if no IQ round records are found. Mean and max are reported so
    the cockpit can show both typical and worst-case link health.
    """
    images = summary.get("images") if isinstance(summary, dict) else None
    if not isinstance(images, list):
        return {}

    field_names = (
        "sync_metric",
        "evm_rms",
        "estimated_cfo_hz",
        "estimated_snr_db",
        "rx_clipping_ratio",
        "latent_mse_vs_tx",
    )
    collected: dict[str, list[float]] = {name: [] for name in field_names}
    sync_success_count = 0
    total_records = 0

    for image in images:
        if not isinstance(image, dict):
            continue
        records = image.get("round_records")
        if not isinstance(records, list):
            # IQ runner may put fields directly on the image record
            records = [image]
        for record in records:
            if not isinstance(record, dict):
                continue
            total_records += 1
            if record.get("sync_success"):
                sync_success_count += 1
            for name in field_names:
                value = record.get(name)
                if value is None:
                    continue
                try:
                    collected[name].append(float(value))
                except (TypeError, ValueError):
                    pass

    if total_records == 0:
        return {}

    def _mean(values: list[float]) -> float | None:
        return (sum(values) / len(values)) if values else None

    def _max(values: list[float]) -> float | None:
        return max(values) if values else None

    metrics: dict[str, Any] = {
        "sample_count": total_records,
        "sync_success_count": sync_success_count,
        "sync_success_ratio": round(sync_success_count / total_records, 4),
    }
    for name in field_names:
        values = collected[name]
        if not values:
            metrics[name] = {"mean": None, "max": None}
            continue
        # Truncate to avoid floating-point noise on the wire
        mean_v = _mean(values)
        max_v = _max(values)
        metrics[name] = {
            "mean": round(mean_v, 6) if mean_v is not None else None,
            "max": round(max_v, 6) if max_v is not None else None,
        }
    return metrics


def _count_processed_from_results(results: list[dict[str, Any]]) -> int:
    processed = 0
    for item in results:
        rounds = int(item.get("rounds", 0) or 0)
        merge_summary = str(item.get("merge_summary") or "").strip()
        if rounds > 0 or merge_summary:
            processed += 1
    return processed


def _count_progress_from_image_dirs(run_dir: Path) -> dict[str, int]:
    processed = 0
    passed = 0
    try:
        image_dirs = sorted(path for path in run_dir.glob("image_*") if path.is_dir())
    except OSError:
        return {"processed": 0, "pass_count": 0}

    for image_dir in image_dirs:
        summary_path = image_dir / "decode_summary.json"
        if not summary_path.is_file():
            continue
        processed += 1
        summary = _safe_read_json(summary_path)
        status_ok = str(summary.get("status") or "").strip().lower() in {"", "ok", "success"}
        has_payload = (
            (image_dir / "received_latent.npz").is_file()
            or (image_dir / "merged_round0.bin").is_file()
            or bool(summary.get("frame_complete"))
        )
        if status_ok and has_payload:
            passed += 1
    return {"processed": processed, "pass_count": passed}


def _parse_progress_from_log(log_path: Path, *, fallback_target: int) -> dict[str, int]:
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {
            "processed": 0,
            "pass_count": 0,
            "pending": fallback_target,
            "target": fallback_target,
        }

    progress_match = None
    for match in re.finditer(
        r"batch_progress\s+round=\d+\s+batch=\d+/\d+\s+processed=(\d+)/(\d+)\s+pass=(\d+)\s+pending=(\d+)",
        text,
    ):
        progress_match = match

    if progress_match is None:
        return {
            "processed": 0,
            "pass_count": 0,
            "pending": fallback_target,
            "target": fallback_target,
        }

    return {
        "processed": int(progress_match.group(1)),
        "target": int(progress_match.group(2)),
        "pass_count": int(progress_match.group(3)),
        "pending": int(progress_match.group(4)),
    }


def _merge_log_progress_into_summary(summary: dict[str, Any], log_path: Path, *, fallback_target: int) -> dict[str, Any]:
    merged = dict(summary or {})
    progress = _parse_progress_from_log(log_path, fallback_target=fallback_target)
    processed = int(progress.get("processed") or 0)
    pass_count = int(progress.get("pass_count") or 0)
    target = max(1, int(progress.get("target") or merged.get("target_count") or fallback_target))
    if processed <= 0 and pass_count <= 0:
        merged.setdefault("target_count", target)
        return merged

    summary_completed = int(merged.get("completed_count") or 0)
    summary_pass = int(merged.get("pass_count") or 0)
    completed = max(summary_completed, processed)
    passed = max(summary_pass, pass_count)
    merged["target_count"] = max(1, int(merged.get("target_count") or target))
    merged["completed_count"] = completed
    merged["pass_count"] = passed
    merged["fail_count"] = max(0, completed - passed)
    merged["pending_count"] = max(0, merged["target_count"] - completed)
    merged["all_pass"] = completed == merged["target_count"] and passed == merged["target_count"]
    return merged


def _resolve_usrp_job_timeout_sec(env_values: dict[str, str], *, expected_outputs: int) -> float:
    configured_timeout = _parse_float(_first_value(env_values, TIMEOUT_SEC_KEYS), 0.0)
    if configured_timeout > 0.0:
        return max(120.0, configured_timeout)
    return max(300.0, float(max(1, int(expected_outputs))) * 5.0)


def _resolve_link_mode(env_values: dict[str, str]) -> str:
    """Return normalized link mode: 'qpsk' (default) or 'iq-direct'.

    Reads JSCC_LINK_MODE / OPENAMP_DEMO_LINK_MODE. Accepts case-insensitive
    variants like 'iq', 'analog', 'iq-direct', 'qpsk', 'baseline'. Any unknown
    value falls back to qpsk baseline (safe default — preserves prior behavior).
    """
    raw = str(_first_value(env_values, LINK_MODE_KEYS) or "").strip().lower()
    if raw in ("iq-direct", "iq_direct", "iq", "analog", "analog-iq"):
        return LINK_MODE_IQ_DIRECT
    return LINK_MODE_QPSK


def _is_iq_direct_mode(env_values: dict[str, str]) -> bool:
    return _resolve_link_mode(env_values) == LINK_MODE_IQ_DIRECT


class UsrpBatchSpoolJob:
    def __init__(
        self,
        access: BoardAccessConfig,
        *,
        variant: str,
        max_inputs: int,
        control_transport: str = "mlkem",
        control_preflight: dict[str, Any] | None = None,
        inference_engine: str = INFERENCE_ENGINE_NONE,
        inference_callback: Callable[[dict[str, Any], Callable[[int, int], None]], dict[str, Any]] | None = None,
    ) -> None:
        self.job_id = f"usrp-{int(time.time())}"
        self.variant = variant
        self._expected_outputs = max(1, int(max_inputs))
        self._control_transport = str(control_transport or "mlkem").strip().lower() or "mlkem"
        self._inference_engine = _normalize_inference_engine(inference_engine)
        self._inference_callback = inference_callback
        self._control_preflight = dict(control_preflight) if isinstance(control_preflight, dict) else None
        self._lock = threading.Lock()
        self._final_snapshot: dict[str, Any] | None = None
        self._process: subprocess.Popen[str] | None = None
        self._timed_out = False
        self._access = access

        env_values = access.build_env()
        self._input_source_mode = current_input_source_mode(env_values)
        self._input_source_label = input_source_mode_label(self._input_source_mode)
        self._remote_usrp_rx_root = _first_value(env_values, REMOTE_USRP_RX_ROOT_KEYS)
        self._remote_decode_python = _first_value(env_values, REMOTE_DECODE_PYTHON_KEYS, "python3")
        self._iq_remote_decoded_output_dir = ""
        self._prepared_input_manifest: dict[str, Any] | None = None
        self._wire_stage_manifest: dict[str, Any] | None = None
        self._remote_stage_manifest: dict[str, Any] | None = None
        self._control_server_diagnostics: dict[str, Any] = {}
        self._rx_control_host = ""
        self._rx_control_port = DEFAULT_RX_CONTROL_PORT
        self._tx_control_host = ""
        self._tx_control_port = DEFAULT_TX_CONTROL_PORT
        self._shutdown_after_transport = resolve_shutdown_after_transport(env_values)
        self._phase = "starting"
        self._host_preprocess_completed = 0
        self._host_preprocess_total = self._expected_outputs
        self._host_preprocess_state = "pending"
        self._host_preprocess_manifest: dict[str, Any] | None = None
        self._host_latent_files: list[Path] | None = None
        self._transport_completed = 0
        self._transport_total = self._expected_outputs
        self._inference_completed = 0
        self._inference_total = self._expected_outputs
        self._inference_summary: dict[str, Any] | None = None
        runner_path = _resolve_existing_path(_first_value(env_values, RUNNER_SCRIPT_KEYS)) or DEFAULT_RUNNER
        input_dir = _resolve_existing_path(_first_value(env_values, INPUT_DIR_KEYS)) or DEFAULT_INPUT_DIR
        input_file = _resolve_existing_path(_first_value(env_values, INPUT_FILE_KEYS)) or DEFAULT_INPUT_FILE
        run_root = _resolve_existing_path(_first_value(env_values, RUN_ROOT_KEYS)) or DEFAULT_RUN_ROOT
        run_id = f"cockpit_usrp_{self.job_id}"
        self._run_dir = Path(run_root) / run_id
        self._summary_path = self._run_dir / "batch_spool_summary.json"
        self._log_path = self._run_dir / "cockpit_usrp.log"
        self._runner_path = Path(runner_path)
        self._link_mode = _resolve_link_mode(env_values)
        if self._link_mode == LINK_MODE_IQ_DIRECT and not _first_value(env_values, RUNNER_SCRIPT_KEYS):
            self._runner_path = DEFAULT_ANALOG_RUNNER
        self._timeout_sec = _resolve_usrp_job_timeout_sec(env_values, expected_outputs=self._expected_outputs)

        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._env_values = dict(env_values)
        self._input_dir = Path(input_dir)
        self._input_file = Path(input_file)
        self._run_root = Path(run_root)
        self._run_id = run_id
        self._runner_command: list[str] = []
        self._runner_env: dict[str, str] = {}
        self._log_handle: Any = None
        self._worker_thread = threading.Thread(target=self._start_and_watch, daemon=True)
        self._worker_thread.start()

    def _start_and_watch(self) -> None:
        env_values = self._env_values
        access = self._access
        if self._input_source_mode == "usrp":
            if not self._remote_usrp_rx_root:
                self._final_snapshot = self._build_terminal_snapshot(
                    status="config_error",
                    status_category="config_error",
                    message="USRP 传输模式缺少板端 REMOTE_USRP_RX_DIR 配置。",
                )
                return
            if not access.connection_ready:
                self._final_snapshot = self._build_terminal_snapshot(
                    status="config_error",
                    status_category="config_error",
                    message="USRP 传输模式缺少完整板端连接信息，无法同步 RX 结果。",
                )
                return
            local_latent_dir = _resolve_optional_path(_first_value(env_values, LOCAL_LATENT_DIR_KEYS))
            if local_latent_dir is None:
                local_latent_dir = _default_image_to_latent_output_dir()
            if not local_latent_dir.is_dir():
                local_latent_dir.mkdir(parents=True, exist_ok=True)
            try:
                local_latent_dir = self._ensure_host_latents(env_values, local_latent_dir)
            except Exception as exc:
                self._final_snapshot = self._build_terminal_snapshot(
                    status="config_error",
                    status_category="config_error",
                    message=f"USRP 上位机图片到 latent 准备失败: {exc}",
                )
                return
            payload_codec = _first_value(env_values, PAYLOAD_CODEC_KEYS, "webp-lossless")
            pattern = _first_value(env_values, LOCAL_LATENT_PATTERN_KEYS, "*.npz,*.pt")
            prepared_dir = self._run_dir / "prepared_usrp_inputs"
            wire_cache_enabled = _parse_bool(_first_value(env_values, WIRE_CACHE_ENABLED_KEYS, "1"), True)
            wire_cache_dir = _resolve_optional_path(_first_value(env_values, WIRE_CACHE_DIR_KEYS))
            if wire_cache_dir is None:
                wire_cache_dir = local_latent_dir / ".usrp_wire_cache"
            if not wire_cache_enabled:
                wire_cache_dir = None
            wire_prepare_workers = max(
                1,
                _parse_int(
                    _first_value(env_values, WIRE_PREPARE_WORKERS_KEYS),
                    DEFAULT_WIRE_PREPARE_WORKERS,
                ),
            )
            try:
                with self._lock:
                    self._phase = "wire_prepare"
                self._prepared_input_manifest = _prepare_wire_input_dir(
                    source_dir=local_latent_dir,
                    output_dir=prepared_dir,
                    payload_codec=payload_codec,
                    pattern=pattern,
                    max_files=self._expected_outputs,
                    cache_dir=wire_cache_dir,
                    prepare_workers=wire_prepare_workers,
                    source_files=self._host_latent_files,
                )
                self._prepared_input_manifest = _enrich_wire_manifest_with_host_images(
                    self._prepared_input_manifest,
                    self._host_preprocess_manifest,
                    prepared_dir / "usrp_input_manifest.json",
                )
            except Exception as exc:
                self._final_snapshot = self._build_terminal_snapshot(
                    status="config_error",
                    status_category="config_error",
                    message=f"USRP 输入准备失败: {exc}",
                )
                return
            self._input_path = prepared_dir
            rx_host = _first_value(env_values, RX_CONTROL_HOST_KEYS, access.host)
            rx_port = _first_value(env_values, RX_CONTROL_PORT_KEYS, DEFAULT_RX_CONTROL_PORT)
            tx_host = _first_value(env_values, TX_CONTROL_HOST_KEYS, "127.0.0.1")
            tx_port = _first_value(env_values, TX_CONTROL_PORT_KEYS, DEFAULT_TX_CONTROL_PORT)
            self._rx_control_host = rx_host
            self._rx_control_port = rx_port
            self._tx_control_host = tx_host
            self._tx_control_port = tx_port
            if rx_host == access.host:
                default_rx_capture_mode = "remote-decode"
            else:
                default_rx_capture_mode = "local"
            rx_capture_mode = _first_value(env_values, RX_CAPTURE_MODE_KEYS, default_rx_capture_mode)
            remote_rx_target = _remote_ssh_target(access, env_values)
            remote_run_root = _first_value(env_values, REMOTE_RX_RUN_ROOT_KEYS, DEFAULT_REMOTE_RX_RUN_ROOT)
            remote_project_root = _remote_usrp_project_root(env_values)
            remote_decode_bin = _first_value(
                env_values,
                REMOTE_DECODE_BIN_KEYS,
                f"{remote_project_root.rstrip('/')}/USRP292x/QpskFileDecode",
            )
            iq_decode_asset_sync: dict[str, Any] | None = None
            if self._link_mode == LINK_MODE_IQ_DIRECT and rx_capture_mode == "remote-decode":
                asset_probe_timeout = _parse_float(
                    _first_value(env_values, ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_KEYS),
                    15.0,
                )
                asset_sync_timeout = _parse_float(
                    _first_value(env_values, ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_KEYS),
                    90.0,
                )
                try:
                    iq_decode_asset_sync = _sync_iq_decode_assets_on_remote(
                        access,
                        remote_project_root=remote_project_root,
                        probe_timeout_sec=max(1.0, asset_probe_timeout),
                        upload_timeout_sec=max(1.0, asset_sync_timeout),
                    )
                except Exception as exc:
                    self._final_snapshot = self._build_terminal_snapshot(
                        status="config_error",
                        status_category="config_error",
                        message=f"IQ remote-decode 资产同步失败: {exc}",
                    )
                    return
            auto_start_control = _parse_bool(_first_value(env_values, USRP_AUTO_START_CONTROL_KEYS, "1"), True)
            control_ready, control_diagnostics = _ensure_usrp_control_servers(
                access,
                env_values,
                rx_host=rx_host,
                rx_port=rx_port,
                tx_host=tx_host,
                tx_port=tx_port,
                remote_run_root=remote_run_root,
                remote_project_root=remote_project_root,
                auto_start=auto_start_control,
                log_dir=REPO_ROOT / "USRP292x" / "server_logs",
            )
            self._control_server_diagnostics = control_diagnostics
            if iq_decode_asset_sync is not None:
                self._control_server_diagnostics["iq_decode_asset_sync"] = iq_decode_asset_sync
            if not control_ready:
                rx_response = str(control_diagnostics.get("rx_control", {}).get("final_response") or "")
                tx_response = str(control_diagnostics.get("tx_control", {}).get("final_response") or "")
                self._final_snapshot = self._build_terminal_snapshot(
                    status="config_error",
                    status_category="config_error",
                    message=(
                        "USRP 控制端未就绪："
                        f"RX {rx_host}:{rx_port} -> {rx_response or 'not ready'}；"
                        f"TX {tx_host}:{tx_port} -> {tx_response or 'not ready'}。"
                        "请确认板端 OtaRxPersistentServer 与本机 OtaTxPersistentServer 已启动。"
                    ),
                )
                return
        else:
            self._input_path = self._input_dir if self._input_dir.exists() else self._input_file
            rx_host = _first_value(env_values, RX_CONTROL_HOST_KEYS, "127.0.0.1")
            rx_port = _first_value(env_values, RX_CONTROL_PORT_KEYS, DEFAULT_RX_CONTROL_PORT)
            tx_host = _first_value(env_values, TX_CONTROL_HOST_KEYS, "127.0.0.1")
            tx_port = _first_value(env_values, TX_CONTROL_PORT_KEYS, DEFAULT_TX_CONTROL_PORT)
            self._rx_control_host = rx_host
            self._rx_control_port = rx_port
            self._tx_control_host = tx_host
            self._tx_control_port = tx_port
            rx_capture_mode = _first_value(env_values, RX_CAPTURE_MODE_KEYS, "local")
            remote_rx_target = _remote_ssh_target(access, env_values)
            remote_run_root = _first_value(env_values, REMOTE_RX_RUN_ROOT_KEYS, DEFAULT_REMOTE_RX_RUN_ROOT)
            remote_project_root = _remote_usrp_project_root(env_values)
            remote_decode_bin = _first_value(
                env_values,
                REMOTE_DECODE_BIN_KEYS,
                f"{remote_project_root.rstrip('/')}/USRP292x/QpskFileDecode",
            )

        if not self._runner_path.is_file():
            self._final_snapshot = self._build_terminal_snapshot(
                status="config_error",
                status_category="config_error",
                message=f"USRP runner 不存在: {self._runner_path}",
            )
            return
        if not self._input_path.exists():
            self._final_snapshot = self._build_terminal_snapshot(
                status="config_error",
                status_category="config_error",
                message=f"USRP 输入不存在: {self._input_path}",
            )
            return

        command = [sys.executable, str(self._runner_path)]
        if self._input_path.is_dir():
            command.extend(["--input-dir", str(self._input_path), "--cycle-inputs"])
        else:
            command.extend(["--input", str(self._input_path)])
        command.extend([
            "--count",
            str(self._expected_outputs),
            "--run-id",
            self._run_id,
            "--run-root",
            str(self._run_root),
            "--artifact-mode",
            _first_value(env_values, ARTIFACT_MODE_KEYS, "minimal"),
            "--rx-control-host",
            rx_host,
            "--rx-control-port",
            rx_port,
            "--tx-control-host",
            tx_host,
            "--tx-control-port",
            tx_port,
            "--rx-capture-mode",
            rx_capture_mode,
            "--remote-rx-run-root",
            remote_run_root,
            "--remote-decode-bin",
            remote_decode_bin,
        ])
        if remote_rx_target:
            command.extend(["--remote-rx-ssh-target", remote_rx_target])

        batch_size = _parse_int(_first_value(env_values, BATCH_SIZE_KEYS), 0)
        if batch_size > 0:
            command.extend(["--batch-size", str(batch_size)])
        decode_workers = _parse_int(_first_value(env_values, DECODE_WORKERS_KEYS), 0)
        if decode_workers > 0:
            command.extend(["--decode-workers", str(decode_workers)])
        chunk_bytes = _parse_int(_first_value(env_values, CHUNK_BYTES_KEYS), 0)
        if chunk_bytes > 0:
            command.extend(["--chunk-bytes", str(chunk_bytes)])
        if _parse_bool(_first_value(env_values, STOP_ON_FAIL_KEYS), False):
            command.append("--stop-on-fail")

        if self._link_mode == LINK_MODE_IQ_DIRECT:
            command.extend([
                "--max-arq-rounds",
                str(max(0, _parse_int(_first_value(env_values, MAX_ARQ_ROUNDS_KEYS), 2))),
            ])
            command.extend(self._build_analog_link_args(env_values))
            remote_decode_result_mode = str(
                _first_value(env_values, ANALOG_REMOTE_DECODE_RESULT_MODE_KEYS) or ""
            ).strip().lower()
            if (
                not remote_decode_result_mode
                and str(rx_capture_mode or "").strip().lower() == "remote-decode"
                and self._inference_engine != INFERENCE_ENGINE_NONE
            ):
                remote_decode_result_mode = "remote-dir"
            if remote_decode_result_mode:
                command.extend(["--remote-decode-result-mode", remote_decode_result_mode])
            if remote_decode_result_mode == "remote-dir":
                remote_decoded_output_dir = str(
                    _first_value(env_values, ANALOG_REMOTE_DECODED_OUTPUT_DIR_KEYS) or ""
                ).strip().rstrip("/")
                if not remote_decoded_output_dir:
                    remote_decoded_output_dir = f"{str(self._remote_usrp_rx_root or '').rstrip('/')}/{self._run_id}_rx"
                with self._lock:
                    self._iq_remote_decoded_output_dir = remote_decoded_output_dir
                command.extend(["--remote-decoded-output-dir", remote_decoded_output_dir])
            tx_path_prefix_from = _first_value(env_values, TX_FILE_PATH_PREFIX_FROM_KEYS)
            tx_path_prefix_to = _first_value(env_values, TX_FILE_PATH_PREFIX_TO_KEYS)
            if _tx_server_uses_docker(env_values):
                tx_path_prefix_from = tx_path_prefix_from or str(REPO_ROOT)
                tx_path_prefix_to = tx_path_prefix_to or _first_value(
                    env_values,
                    TX_DOCKER_MOUNT_TARGET_KEYS,
                    DEFAULT_TX_DOCKER_MOUNT_TARGET,
                )
            if tx_path_prefix_from and tx_path_prefix_to:
                command.extend([
                    "--tx-file-path-prefix-from",
                    tx_path_prefix_from,
                    "--tx-file-path-prefix-to",
                    tx_path_prefix_to,
                ])
        else:
            command.extend([
                "--max-arq-rounds",
                str(max(0, _parse_int(_first_value(env_values, MAX_ARQ_ROUNDS_KEYS), 2))),
                "--decode-backend",
                _first_value(env_values, DECODE_BACKEND_KEYS, "python"),
                "--cpp-sync-mode",
                _first_value(env_values, CPP_SYNC_MODE_KEYS, "header"),
            ])
            tx_path_prefix_from = _first_value(env_values, TX_FILE_PATH_PREFIX_FROM_KEYS)
            tx_path_prefix_to = _first_value(env_values, TX_FILE_PATH_PREFIX_TO_KEYS)
            if _tx_server_uses_docker(env_values):
                tx_path_prefix_from = tx_path_prefix_from or str(REPO_ROOT)
                tx_path_prefix_to = tx_path_prefix_to or _first_value(
                    env_values,
                    TX_DOCKER_MOUNT_TARGET_KEYS,
                    DEFAULT_TX_DOCKER_MOUNT_TARGET,
                )
            if tx_path_prefix_from and tx_path_prefix_to:
                command.extend([
                    "--tx-file-path-prefix-from",
                    tx_path_prefix_from,
                    "--tx-file-path-prefix-to",
                    tx_path_prefix_to,
                ])
            if _parse_bool(_first_value(env_values, FAST_ARQ_PROFILE_KEYS), False):
                command.append("--fast-arq-profile")

        env = access.build_subprocess_env()
        env["PYTHONUNBUFFERED"] = "1"
        env.setdefault("REMOTE_USRP_PROJECT_ROOT", remote_project_root)
        env.setdefault("USRP_REMOTE_PROJECT_ROOT", remote_project_root)
        remote_decode_python = _first_value(env_values, REMOTE_DECODE_PYTHON_KEYS)
        if remote_decode_python:
            env.setdefault("REMOTE_DECODE_PYTHON", remote_decode_python)
        if access.password:
            env.setdefault("SSHPASS", access.password)

        with self._lock:
            self._phase = "transport"
            self._runner_command = list(command)
            self._runner_env = dict(env)
        self._log_handle = self._log_path.open("w", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                env=env,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            self._log_handle.close()
            self._final_snapshot = self._build_terminal_snapshot(
                status="launch_error",
                status_category="launch_error",
                message=f"USRP runner 启动失败: {exc}",
            )
            return

        self._wait_for_completion()

    def _build_analog_link_args(self, env_values: dict[str, str]) -> list[str]:
        """Build CLI args for RunAnalogLatentBatch.py (IQ-direct mode).

        Reads ANALOG_* / AMPLITUDE / SIM_* env vars. IQ-direct emits the
        verified OTA defaults when no explicit override is provided.
        """
        args: list[str] = []
        sps = _first_value(env_values, ANALOG_SPS_KEYS)
        if sps:
            args.extend(["--sps", str(_parse_int(sps, 4))])
        elif self._link_mode == LINK_MODE_IQ_DIRECT:
            args.extend(["--sps", str(DEFAULT_IQ_DIRECT_SPS)])
        rrc_beta = _first_value(env_values, ANALOG_RRC_BETA_KEYS)
        if rrc_beta:
            args.extend(["--rrc-beta", str(_parse_float(rrc_beta, 0.35))])
        rrc_span = _first_value(env_values, ANALOG_RRC_SPAN_KEYS)
        if rrc_span:
            args.extend(["--rrc-span", str(_parse_int(rrc_span, 8))])
        amp = _first_value(env_values, ANALOG_AMP_KEYS)
        if amp:
            args.extend(["--amp", str(_parse_int(amp, 3000))])
        elif self._link_mode == LINK_MODE_IQ_DIRECT:
            args.extend(["--amp", str(DEFAULT_IQ_DIRECT_AMPLITUDE)])
        zero_guard = _first_value(env_values, ANALOG_ZERO_GUARD_KEYS)
        if zero_guard:
            args.extend(["--zero-guard-samples", str(_parse_int(zero_guard, 4096))])
        tail_guard = _first_value(env_values, ANALOG_TAIL_GUARD_KEYS)
        if tail_guard:
            args.extend(["--tail-guard-samples", str(_parse_int(tail_guard, 4096))])
        cfo_pilot = _first_value(env_values, ANALOG_CFO_PILOT_KEYS)
        if cfo_pilot:
            args.extend(["--cfo-pilot-symbols", str(_parse_int(cfo_pilot, 1024))])
        sync_pilot = _first_value(env_values, ANALOG_SYNC_PILOT_KEYS)
        if sync_pilot:
            args.extend(["--sync-pilot-symbols", str(_parse_int(sync_pilot, 1024))])
        data_block = _first_value(env_values, ANALOG_DATA_BLOCK_KEYS)
        if data_block:
            args.extend(["--data-block-symbols", str(_parse_int(data_block, 4096))])
        mid_pilot = _first_value(env_values, ANALOG_MID_PILOT_KEYS)
        if mid_pilot:
            args.extend(["--mid-pilot-symbols", str(_parse_int(mid_pilot, 128))])
        margin = _first_value(env_values, ANALOG_CAPTURE_MARGIN_KEYS)
        if margin:
            args.extend(["--capture-margin-samples", str(_parse_int(margin, 20000))])

        rx_post_quantize_raw = _first_value(env_values, ANALOG_RX_POST_QUANTIZE_KEYS)
        if rx_post_quantize_raw:
            if _parse_bool(rx_post_quantize_raw, True):
                args.append("--rx-post-quantize")
            else:
                args.append("--no-rx-post-quantize")

        sync_candidates = _first_value(env_values, ANALOG_SYNC_CANDIDATES_KEYS)
        if sync_candidates:
            args.extend(["--sync-candidates", str(_parse_int(sync_candidates, 12))])
        min_sync_metric = _first_value(env_values, ANALOG_MIN_SYNC_METRIC_KEYS)
        if min_sync_metric:
            args.extend(["--min-sync-metric", str(_parse_float(min_sync_metric, 0.25))])
        elif self._link_mode == LINK_MODE_IQ_DIRECT:
            args.extend(["--min-sync-metric", str(DEFAULT_IQ_DIRECT_MIN_SYNC_METRIC)])
        robust_sync_raw = _first_value(env_values, ANALOG_ROBUST_SYNC_KEYS)
        if robust_sync_raw:
            if _parse_bool(robust_sync_raw, True):
                args.append("--robust-sync")
            else:
                args.append("--no-robust-sync")
        elif self._link_mode == LINK_MODE_IQ_DIRECT:
            args.append("--robust-sync" if DEFAULT_IQ_DIRECT_ROBUST_SYNC else "--no-robust-sync")
        robust_cfo_max = _first_value(env_values, ANALOG_ROBUST_CFO_MAX_HZ_KEYS)
        if robust_cfo_max:
            args.extend(["--robust-cfo-max-hz", str(_parse_float(robust_cfo_max, 8000.0))])
        robust_cfo_step = _first_value(env_values, ANALOG_ROBUST_CFO_STEP_HZ_KEYS)
        if robust_cfo_step:
            args.extend(["--robust-cfo-step-hz", str(_parse_float(robust_cfo_step, 500.0))])
        sync_search_window = _first_value(env_values, ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS_KEYS)
        if sync_search_window:
            args.extend([
                "--sync-search-window-symbols",
                str(_parse_int(sync_search_window, DEFAULT_IQ_DIRECT_SYNC_SEARCH_WINDOW_SYMBOLS)),
            ])
        elif self._link_mode == LINK_MODE_IQ_DIRECT:
            args.extend(["--sync-search-window-symbols", str(DEFAULT_IQ_DIRECT_SYNC_SEARCH_WINDOW_SYMBOLS)])
        pipeline_depth = _first_value(env_values, ANALOG_PIPELINE_DEPTH_KEYS)
        if pipeline_depth:
            args.extend(["--pipeline-depth", str(max(1, _parse_int(pipeline_depth, 1)))])

        scramble_key = _first_value(env_values, ANALOG_SCRAMBLE_KEY_KEYS)
        if scramble_key:
            args.extend(["--scramble-key", str(scramble_key)])
        scramble_key_hex = _first_value(env_values, ANALOG_SCRAMBLE_KEY_HEX_KEYS)
        if scramble_key_hex:
            args.extend(["--scramble-key-hex", str(scramble_key_hex)])
        scramble_ctx = _first_value(env_values, ANALOG_SCRAMBLE_CONTEXT_KEYS)
        if scramble_ctx:
            args.extend(["--scramble-context", str(scramble_ctx)])

        sim_cfo = _first_value(env_values, ANALOG_SIM_CFO_HZ_KEYS)
        if sim_cfo:
            args.extend(["--sim-cfo-hz", str(_parse_float(sim_cfo, 0.0))])
        sim_snr = _first_value(env_values, ANALOG_SIM_SNR_DB_KEYS)
        if sim_snr:
            args.extend(["--sim-snr-db", str(_parse_float(sim_snr, 0.0))])
        sim_gain = _first_value(env_values, ANALOG_SIM_GAIN_KEYS)
        if sim_gain:
            args.extend(["--sim-gain", str(_parse_float(sim_gain, 1.0))])
        sim_phase = _first_value(env_values, ANALOG_SIM_PHASE_DEG_KEYS)
        if sim_phase:
            args.extend(["--sim-phase-deg", str(_parse_float(sim_phase, 0.0))])
        sim_drift = _first_value(env_values, ANALOG_SIM_PHASE_DRIFT_DEG_KEYS)
        if sim_drift:
            args.extend(["--sim-phase-drift-deg", str(_parse_float(sim_drift, 0.0))])
        sim_dc_real = _first_value(env_values, ANALOG_SIM_DC_REAL_KEYS)
        if sim_dc_real:
            args.extend(["--sim-dc-real", str(_parse_float(sim_dc_real, 0.0))])
        sim_dc_imag = _first_value(env_values, ANALOG_SIM_DC_IMAG_KEYS)
        if sim_dc_imag:
            args.extend(["--sim-dc-imag", str(_parse_float(sim_dc_imag, 0.0))])
        sim_seed = _first_value(env_values, ANALOG_SIM_SEED_KEYS)
        if sim_seed:
            args.extend(["--sim-seed", str(_parse_int(sim_seed, 1))])

        return args

    def _set_transport_progress(self, summary: dict[str, Any]) -> None:
        self._transport_total = max(1, int(summary.get("target_count") or self._expected_outputs))
        self._transport_completed = max(
            int(summary.get("completed_count") or 0),
            int(summary.get("pass_count") or 0),
        )

    def _set_host_preprocess_progress(self, completed: int, total: int, state: str) -> None:
        with self._lock:
            self._host_preprocess_total = max(1, int(total))
            self._host_preprocess_completed = max(0, min(int(completed), self._host_preprocess_total))
            self._host_preprocess_state = str(state or "running")

    def _ensure_host_latents(self, env_values: dict[str, str], local_latent_dir: Path) -> Path:
        enabled = _parse_bool(_first_value(env_values, LOCAL_IMAGE_TO_LATENT_ENABLED_KEYS, "1"), True)
        pattern = _first_value(env_values, LOCAL_LATENT_PATTERN_KEYS, "*.npz,*.pt")
        existing = _collect_local_latent_files(local_latent_dir, pattern) if local_latent_dir.is_dir() else []
        output_dir = _resolve_optional_path(_first_value(env_values, LOCAL_IMAGE_TO_LATENT_OUTPUT_DIR_KEYS)) or local_latent_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        image_dir = _resolve_optional_path(_first_value(env_values, LOCAL_IMAGE_DIR_KEYS))
        device = _first_value(env_values, LOCAL_IMAGE_TO_LATENT_DEVICE_KEYS, "cpu")
        config_str = _first_value(env_values, LOCAL_IMAGE_TO_LATENT_CONFIG_KEYS, "6_6_6_6_6_6_6")
        snr = _first_value(env_values, LOCAL_IMAGE_TO_LATENT_SNR_KEYS, "10")

        if image_dir is not None and image_dir.is_dir():
            cache = _host_image_latent_cache_valid(
                image_dir=image_dir,
                output_dir=output_dir,
                expected_count=self._expected_outputs,
                config_str=config_str,
                snr=snr,
                device=device,
            )
            if cache is not None:
                manifest, latent_files = cache
                self._host_latent_files = latent_files
                self._set_host_preprocess_progress(self._expected_outputs, self._expected_outputs, "completed")
                self._host_preprocess_manifest = manifest
                return output_dir

        if len(existing) >= self._expected_outputs and (image_dir is None or not image_dir.is_dir() or not enabled):
            self._host_latent_files = existing[: self._expected_outputs]
            self._set_host_preprocess_progress(self._expected_outputs, self._expected_outputs, "completed")
            self._host_preprocess_manifest = {
                "status": "cache_hit",
                "source": "latent_cache",
                "latent_dir": str(local_latent_dir),
                "count": len(existing),
                "used_count": self._expected_outputs,
                "image_dir": _first_value(env_values, LOCAL_IMAGE_DIR_KEYS),
                "elapsed_sec": 0.0,
            }
            return local_latent_dir
        if not enabled:
            self._set_host_preprocess_progress(len(existing), self._expected_outputs, "fallback")
            raise RuntimeError(f"本地 latent 缓存不足: dir={local_latent_dir} count={len(existing)} required={self._expected_outputs}")

        if image_dir is None or not image_dir.is_dir():
            self._set_host_preprocess_progress(len(existing), self._expected_outputs, "fallback")
            raise RuntimeError(
                f"本地 latent 缓存不足且图片目录不可用: latent_dir={local_latent_dir} "
                f"image_dir={image_dir or ''} count={len(existing)} required={self._expected_outputs}"
            )
        images = _collect_local_image_files(image_dir)
        if len(images) < self._expected_outputs:
            self._set_host_preprocess_progress(len(existing), self._expected_outputs, "fallback")
            raise RuntimeError(f"图片数量不足: dir={image_dir} count={len(images)} required={self._expected_outputs}")

        with self._lock:
            self._phase = "host_preprocess"
        script = _resolve_existing_path(_first_value(env_values, LOCAL_IMAGE_TO_LATENT_SCRIPT_KEYS)) or _default_image_to_latent_script()
        if not script.is_file():
            self._set_host_preprocess_progress(len(existing), self._expected_outputs, "fallback")
            raise RuntimeError(f"图片到 latent 编码脚本不存在: {script}")

        expected_records, available_image_count = _host_image_records(image_dir, output_dir, self._expected_outputs)
        command = [
            sys.executable,
            str(script),
            "--image_dir",
            str(image_dir),
            "--output_dir",
            str(output_dir),
            "--test_num",
            str(self._expected_outputs),
            "--device",
            device,
            "--config_str",
            config_str,
            "--snr",
            snr,
            "--progress_jsonl",
        ]
        self._set_host_preprocess_progress(0, self._expected_outputs, "running")
        started = time.monotonic()
        proc = subprocess.Popen(
            command,
            cwd=script.parent,
            env=self._access.build_subprocess_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        encode_log = self._run_dir / "host_image_to_latent.log"
        last_error = ""
        with encode_log.open("w", encoding="utf-8") as log_handle:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                log_handle.write(raw_line)
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("event") == "encoded":
                    self._set_host_preprocess_progress(
                        int(event.get("completed") or 0),
                        int(event.get("total") or self._expected_outputs),
                        "running",
                    )
                elif event.get("event") == "error":
                    last_error = str(event.get("error") or "")
        rc = proc.wait()
        elapsed = time.monotonic() - started
        final_files = [Path(str(record["latent"])) for record in expected_records if Path(str(record["latent"])).is_file()]
        if rc != 0 or len(final_files) < self._expected_outputs:
            self._set_host_preprocess_progress(len(final_files), self._expected_outputs, "fallback")
            detail = last_error or f"encoder rc={rc}, latent_count={len(final_files)}"
            raise RuntimeError(f"图片到 latent 编码失败: {detail}")

        self._host_latent_files = final_files[: self._expected_outputs]
        self._set_host_preprocess_progress(self._expected_outputs, self._expected_outputs, "completed")
        self._host_preprocess_manifest = _write_host_image_latent_manifest(
            output_dir=output_dir,
            image_dir=image_dir,
            files=expected_records,
            config_str=config_str,
            snr=snr,
            device=device,
            elapsed_sec=elapsed,
            available_image_count=available_image_count,
            command=command,
            log_path=encode_log,
        )
        return output_dir

    def _set_inference_progress(self, completed: int, total: int) -> None:
        with self._lock:
            self._phase = "inference"
            self._inference_total = max(1, int(total))
            self._inference_completed = max(0, min(int(completed), self._inference_total))

    def _shutdown_control_servers_after_transport(self) -> None:
        if not self._rx_control_host or not self._tx_control_host:
            return
        shutdown = _shutdown_usrp_control_servers(
            rx_host=self._rx_control_host,
            rx_port=self._rx_control_port,
            tx_host=self._tx_control_host,
            tx_port=self._tx_control_port,
            enabled=self._shutdown_after_transport,
        )
        self._control_server_diagnostics["shutdown_after_transport"] = shutdown

    def _artifact_paths(self) -> dict[str, str]:
        payload = {
            "run_dir": str(self._run_dir),
            "summary_path": str(self._summary_path),
            "runner_log_path": str(self._log_path),
        }
        if self._prepared_input_manifest:
            payload["prepared_input_dir"] = str(self._run_dir / "prepared_usrp_inputs")
        if self._host_preprocess_manifest:
            payload["host_preprocess"] = str(self._host_preprocess_manifest.get("log_path") or "")
        if self._wire_stage_manifest:
            payload["wire_stage_dir"] = str(self._run_dir / "board_wire_decode_stage")
        if self._remote_stage_manifest:
            payload["remote_rx_dir"] = str(self._remote_stage_manifest.get("remote_dir") or "")
        if self._inference_summary:
            payload["inference_summary"] = str(self._inference_summary.get("summary_json") or "")
        return payload

    def _build_progress_payload(
        self,
        *,
        state: str,
        label: str,
        percent: int,
        completed_count: int,
        expected_count: int,
        event_log: list[str] | None = None,
    ) -> dict[str, Any]:
        expected = max(1, int(expected_count))
        completed = max(0, min(int(completed_count), expected))
        return {
            "state": state,
            "label": label,
            "tone": "online" if state in {"running", "completed"} else "degraded",
            "percent": percent,
            "phase_percent": percent,
            "completed_count": completed,
            "expected_count": expected,
            "remaining_count": max(0, expected - completed),
            "completion_ratio": round(completed / expected, 4),
            "count_source": "usrp_batch_spool",
            "count_label": f"{completed} / {expected}",
            "current_stage": f"USRP 数据面 {completed}/{expected}",
            "stages": [
                {
                    "key": "usrp_batch_spool",
                    "label": "USRP batch-spool",
                    "status": "current" if state == "running" else ("done" if state == "completed" else "error"),
                    "detail": f"已完成 {completed}/{expected}",
                }
            ],
            "event_log": list(event_log or []),
        }

    def _build_terminal_snapshot(
        self,
        *,
        status: str,
        status_category: str,
        message: str,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary = dict(summary or {})
        target_count = max(1, int(summary.get("target_count") or self._expected_outputs))
        pass_count = int(summary.get("pass_count") or 0)
        all_pass = bool(summary.get("all_pass")) if summary else False
        per_image_sec = float(summary.get("per_image_sec") or 0.0)
        payload_airtime_ms_mean = float(summary.get("payload_airtime_ms_mean") or 0.0)
        decode_total_wall_sec_mean = float(summary.get("decode_total_wall_sec_mean") or 0.0)
        merge_wall_sec_mean = float(summary.get("merge_wall_sec_mean") or 0.0)
        rx_pull_wall_sec_mean = float(summary.get("rx_pull_wall_sec_mean") or 0.0)
        remote_cleanup_wall_sec_mean = float(summary.get("remote_cleanup_wall_sec_mean") or 0.0)
        diagnostics = {
            "transport_mode": "usrp_batch_spool",
            "link_mode": self._link_mode,
            "input_source_mode": self._input_source_mode,
            "input_source_label": self._input_source_label,
            "summary_path": str(self._summary_path),
            "runner_log_path": str(self._log_path),
        }
        if self._host_preprocess_manifest:
            diagnostics["host_preprocess"] = self._host_preprocess_manifest
        if self._prepared_input_manifest:
            diagnostics["prepared_input"] = self._prepared_input_manifest
        if self._wire_stage_manifest:
            diagnostics["wire_stage"] = self._wire_stage_manifest
        if self._remote_stage_manifest:
            diagnostics["board_decode"] = self._remote_stage_manifest
        if self._inference_summary:
            diagnostics["inference_summary"] = self._inference_summary
        if self._control_server_diagnostics:
            diagnostics["usrp_control_servers"] = self._control_server_diagnostics
        if self._control_preflight:
            diagnostics["control_preflight"] = self._control_preflight
        if summary:
            diagnostics["usrp_summary"] = summary

        transport_benchmark = _transport_benchmark_from_summary(summary)
        iq_stage_benchmark = _iq_stage_benchmark_from_summary(summary)
        inference_benchmark = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else None
        inference_pipeline = summary.get("pipeline") if isinstance(summary.get("pipeline"), dict) else {}
        runner_summary = {
            "processed_count": (
                int(self._inference_summary.get("processed_count") or 0)
                if self._inference_summary
                else (pass_count if all_pass else int(summary.get("pass_count") or 0))
            ),
            "input_count": target_count,
            "max_inputs": target_count,
            "pipeline": {
                "load_ms": inference_pipeline.get("load_ms"),
                "vm_init_ms": inference_pipeline.get("vm_init_ms"),
                "ms_per_image": inference_pipeline.get("ms_per_image"),
                "run_mean_ms": inference_pipeline.get("run_mean_ms"),
                "run_median_ms": inference_pipeline.get("run_median_ms"),
            },
        }
        if inference_benchmark is not None:
            runner_summary["benchmark"] = inference_benchmark
        wrapper_summary = {
            "result": "success" if status == "success" else "runner_failed",
            "transport_mode": "usrp_batch_spool",
            "per_image_ms": (
                inference_pipeline.get("ms_per_image")
                or inference_pipeline.get("run_median_ms")
                or inference_pipeline.get("run_mean_ms")
            ),
            "transport_per_image_ms": round(per_image_sec * 1000.0, 3) if per_image_sec > 0 else None,
            "radio_metrics": {
                "payload_airtime_ms_mean": round(payload_airtime_ms_mean, 3),
                "decode_total_wall_sec_mean": round(decode_total_wall_sec_mean * 1000.0, 3),
                "merge_wall_sec_mean": round(merge_wall_sec_mean * 1000.0, 3),
                "rx_pull_wall_sec_mean": round(rx_pull_wall_sec_mean * 1000.0, 3),
                "remote_cleanup_wall_sec_mean": round(remote_cleanup_wall_sec_mean * 1000.0, 3),
                "estimated_non_airtime_non_decode_non_merge_wall_sec_mean": round(
                    float(summary.get("estimated_non_airtime_non_decode_non_merge_wall_sec_mean") or 0.0) * 1000.0,
                    3,
                ),
                "compared_transmitted_bytes_mean": round(float(summary.get("compared_transmitted_bytes_mean") or 0.0), 3),
            },
            "radio_sample_count": int(summary.get("pass_count") or 0),
            "transport_benchmark": transport_benchmark,
            "inference_benchmark": inference_benchmark,
            "link_mode": self._link_mode,
        }
        if self._link_mode == LINK_MODE_IQ_DIRECT:
            wrapper_summary["iq_radio_metrics"] = _aggregate_iq_radio_metrics(summary)
            if iq_stage_benchmark is not None:
                wrapper_summary["iq_stage_benchmark"] = iq_stage_benchmark
        if self._inference_summary:
            wrapper_summary["inference_engine"] = self._inference_engine
            wrapper_summary["inference_summary"] = self._inference_summary
            if self._inference_engine == INFERENCE_ENGINE_MNN:
                runner_summary["inference_engine"] = INFERENCE_ENGINE_MNN
            elif self._inference_engine == INFERENCE_ENGINE_TVM:
                runner_summary["inference_engine"] = INFERENCE_ENGINE_TVM
        progress = self._build_progress_payload(
            state="completed" if status == "success" else "fallback",
            label="USRP + 推理完成" if status == "success" else "USRP / 推理失败",
            percent=100 if status == "success" else int(round((max(pass_count, self._inference_completed) / target_count) * 100)),
            completed_count=max(pass_count, self._inference_completed),
            expected_count=target_count,
            event_log=[],
        )
        host_preprocess_progress = self._build_progress_payload(
            state=self._host_preprocess_state,
            label="上位机图片→latent",
            percent=int(round((self._host_preprocess_completed / max(1, self._host_preprocess_total)) * 100)),
            completed_count=self._host_preprocess_completed,
            expected_count=self._host_preprocess_total,
            event_log=[],
        )
        transport_progress = self._build_progress_payload(
            state="completed" if bool(summary.get("all_pass")) else ("fallback" if status != "success" else "completed"),
            label="USRP 传输/解包",
            percent=100 if bool(summary.get("all_pass")) else int(round((pass_count / target_count) * 100)),
            completed_count=pass_count,
            expected_count=target_count,
            event_log=[],
        )
        infer_done = status == "success" and self._inference_engine != INFERENCE_ENGINE_NONE
        inference_progress = self._build_progress_payload(
            state="completed" if infer_done else ("fallback" if status != "success" else "completed"),
            label=f"{self._inference_engine.upper()} 板端推理" if self._inference_engine != INFERENCE_ENGINE_NONE else "板端推理",
            percent=100 if infer_done else int(round((self._inference_completed / max(1, self._inference_total)) * 100)),
            completed_count=self._inference_completed if self._inference_engine != INFERENCE_ENGINE_NONE else pass_count,
            expected_count=self._inference_total if self._inference_engine != INFERENCE_ENGINE_NONE else target_count,
            event_log=[],
        )
        stage_progress = {
            "phase": self._phase,
            "host_preprocess": host_preprocess_progress,
            "transport": transport_progress,
            "inference": inference_progress,
        }
        return {
            "status": status,
            "request_state": "completed",
            "status_category": status_category,
            "execution_mode": "live" if status == "success" else "fallback",
            "variant": self.variant,
            "message": message,
            "control_transport": self._control_transport,
            "data_transport": "usrp",
            "control_handshake_complete": self._control_transport != "none",
            "runner_summary": runner_summary,
            "wrapper_summary": wrapper_summary,
            "diagnostics": diagnostics,
            "progress": progress,
            "stage_progress": stage_progress,
            "artifacts": self._artifact_paths(),
        }

    def _wait_for_completion(self) -> None:
        assert self._process is not None
        try:
            rc = self._process.wait(timeout=self._timeout_sec)
        except subprocess.TimeoutExpired:
            self._timed_out = True
            self._process.kill()
            rc = self._process.wait()
        finally:
            self._log_handle.close()

        summary = _merge_log_progress_into_summary(
            _safe_read_json(self._summary_path),
            self._log_path,
            fallback_target=self._expected_outputs,
        )
        self._set_transport_progress(summary)
        log_tail = _read_log_tail(self._log_path)
        if self._timed_out:
            snapshot = self._build_terminal_snapshot(
                status="fallback",
                status_category="timeout",
                message=f"USRP 数据面批处理超时（{self._input_source_label}），已回退到归档样例。",
                summary=summary,
            )
        elif rc == 0 and bool(summary.get("all_pass")):
            try:
                self._phase = "transport_shutdown"
                self._shutdown_control_servers_after_transport()
                if self._input_source_mode == "usrp":
                    if self._link_mode == LINK_MODE_IQ_DIRECT:
                        self._remote_stage_manifest = _iq_remote_decode_stage_manifest_from_summary(summary)
                        if (
                            self._remote_stage_manifest is None
                            and self._inference_engine != INFERENCE_ENGINE_NONE
                        ):
                            raise RuntimeError(
                                "IQ-direct remote-decode 缺少 remote-dir 板端输出目录；"
                                "为避免 USRP 数据面绕行 Tailscale，拒绝通过控制面重传 wire blob。"
                            )
                    else:
                        self._phase = "board_decode"
                        wire_stage_dir = self._run_dir / "board_wire_decode_stage"
                        self._wire_stage_manifest = _stage_merged_wire_blobs_for_remote_decode(
                            self._run_dir,
                            wire_stage_dir,
                        )
                        self._remote_stage_manifest = _sync_and_decode_wire_blobs_on_remote(
                            local_stage_dir=wire_stage_dir,
                            remote_root=self._remote_usrp_rx_root,
                            remote_subdir=f"{self._run_dir.name}_rx",
                            remote_python=self._remote_decode_python,
                            access=self._access,
                        )
                if self._inference_engine != INFERENCE_ENGINE_NONE:
                    if self._inference_callback is None:
                        raise RuntimeError(f"未配置 {self._inference_engine.upper()} 推理回调")
                    self._phase = "inference"
                    inference_summary = self._inference_callback(
                        self._remote_stage_manifest or {},
                        self._set_inference_progress,
                    )
                    self._inference_summary = dict(inference_summary or {})
                    status_text = str(self._inference_summary.get("status") or "").lower()
                    if status_text not in {"ok", "success"}:
                        errors = self._inference_summary.get("errors")
                        if isinstance(errors, list) and errors:
                            detail = str(errors[0])
                        else:
                            detail = str(self._inference_summary.get("message") or "unknown inference error")
                        raise RuntimeError(f"{self._inference_engine.upper()} 推理失败: {detail}")
                    completed, total = _extract_progress_count(self._inference_summary, fallback_total=self._expected_outputs)
                    self._set_inference_progress(completed, total)
                    if self._inference_engine == INFERENCE_ENGINE_TVM:
                        summary["pipeline"] = {
                            "load_ms": self._inference_summary.get("load_ms"),
                            "vm_init_ms": self._inference_summary.get("vm_init_ms"),
                            "ms_per_image": self._inference_summary.get("run_median_ms")
                            or self._inference_summary.get("run_mean_ms"),
                            "run_mean_ms": self._inference_summary.get("run_mean_ms"),
                            "run_median_ms": self._inference_summary.get("run_median_ms"),
                        }
                        summary["benchmark"] = _tvm_benchmark_from_runner_summary(self._inference_summary)
                    elif self._inference_engine == INFERENCE_ENGINE_MNN:
                        sample_stats = self._inference_summary.get("sample_stats") if isinstance(self._inference_summary.get("sample_stats"), dict) else {}
                        run_ms = sample_stats.get("run_ms") if isinstance(sample_stats, dict) else {}
                        summary["pipeline"] = {
                            "load_ms": 0.0,
                            "vm_init_ms": 0.0,
                            "ms_per_image": run_ms.get("median_ms") if isinstance(run_ms, dict) else None,
                            "run_mean_ms": run_ms.get("mean_ms") if isinstance(run_ms, dict) else None,
                            "run_median_ms": run_ms.get("median_ms") if isinstance(run_ms, dict) else None,
                        }
                        summary["benchmark"] = _mnn_benchmark_from_runner_summary(self._inference_summary)
                snapshot = self._build_terminal_snapshot(
                    status="success",
                    status_category="success",
                    message=(
                        f"混合链路模式已完成 USRP 数据面传输与 {self._inference_engine.upper()} 板端推理；"
                        "wire bin 已进入板端 RX 目录并在板端解包为 latent .npz。"
                        if self._inference_engine != INFERENCE_ENGINE_NONE and self._input_source_mode == "usrp"
                        else (
                            f"混合链路模式已完成 USRP 数据面传输；当前为{self._input_source_label}，"
                            "wire bin 已进入板端 RX 目录并在板端解包为 latent .npz。"
                            if self._input_source_mode == "usrp"
                            else "混合链路模式已完成 USRP 数据面传输；图像对比继续使用归档样例，链路指标来自当前 2922 批处理结果。"
                        )
                    ),
                    summary=summary,
                )
            except Exception as exc:
                self._inference_summary = self._inference_summary or {
                    "status": "error",
                    "errors": [traceback.format_exc(limit=5)],
                }
                snapshot = self._build_terminal_snapshot(
                    status="fallback",
                    status_category="error",
                    message=f"USRP 数据面已完成，但后续板端解包/推理失败: {exc}",
                    summary=summary,
                )
        else:
            fail_count = int(summary.get("fail_count") or 0)
            detail = _runner_failure_hint(log_tail, summary, rc=rc)
            snapshot = self._build_terminal_snapshot(
                status="fallback",
                status_category="error",
                message=(
                    f"USRP 数据面批处理未全部成功（{detail}，{self._input_source_label}），"
                    "已回退到归档样例。"
                ),
                summary=summary,
            )
            snapshot.setdefault("diagnostics", {})["runner_log_tail"] = log_tail

        with self._lock:
            self._final_snapshot = snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._final_snapshot is not None:
                return dict(self._final_snapshot)

        summary = _safe_read_json(self._summary_path)
        target_count = max(1, int(summary.get("target_count") or self._expected_outputs))
        results = summary.get("results") if isinstance(summary.get("results"), list) else []
        processed_count = _count_processed_from_results(results) if results else 0
        pass_count = int(summary.get("pass_count") or 0)

        log_progress = _parse_progress_from_log(self._log_path, fallback_target=target_count)
        processed_count = max(processed_count, int(log_progress.get("processed") or 0))
        pass_count = max(pass_count, int(log_progress.get("pass_count") or 0))
        image_dir_progress = _count_progress_from_image_dirs(self._run_dir)
        processed_count = max(processed_count, int(image_dir_progress.get("processed") or 0))
        pass_count = max(pass_count, int(image_dir_progress.get("pass_count") or 0))
        percent = int(round((processed_count / target_count) * 100)) if target_count > 0 else 0
        with self._lock:
            phase = self._phase
            inference_completed = self._inference_completed
            inference_total = self._inference_total
            host_preprocess_completed = self._host_preprocess_completed
            host_preprocess_total = self._host_preprocess_total
            host_preprocess_state = self._host_preprocess_state
            iq_remote_decoded_output_dir = self._iq_remote_decoded_output_dir
        transport_done = phase in {"transport_shutdown", "board_decode", "inference"}
        host_preprocess_done = phase not in {"starting", "host_preprocess"} and host_preprocess_state == "completed"
        decoding = phase in {"transport_shutdown", "board_decode"}
        progress_label = (
            "板端推理中"
            if phase == "inference"
            else (
                "USRP 传输完成，正在释放/解包"
                if decoding
                else ("上位机图片到 latent 转换中" if phase in {"starting", "host_preprocess"} else "USRP 数据面传输中")
            )
        )

        diagnostics = {
            "transport_mode": "usrp_batch_spool",
            "link_mode": self._link_mode,
            "input_source_mode": self._input_source_mode,
            "input_source_label": self._input_source_label,
            "summary_path": str(self._summary_path),
            "runner_log_path": str(self._log_path),
        }
        if self._host_preprocess_manifest:
            diagnostics["host_preprocess"] = self._host_preprocess_manifest
        if self._prepared_input_manifest:
            diagnostics["prepared_input"] = self._prepared_input_manifest
        if self._control_server_diagnostics:
            diagnostics["usrp_control_servers"] = self._control_server_diagnostics
        if self._control_preflight:
            diagnostics["control_preflight"] = self._control_preflight

        wrapper_summary: dict[str, Any] = {}
        if self._link_mode == LINK_MODE_IQ_DIRECT and self._inference_engine != INFERENCE_ENGINE_NONE:
            remote_decoded_output_dir = str(iq_remote_decoded_output_dir or "").strip().rstrip("/")
            if not remote_decoded_output_dir and self._remote_usrp_rx_root:
                remote_decoded_output_dir = f"{str(self._remote_usrp_rx_root).rstrip('/')}/{self._run_id}_rx"
            iq_manifest = _iq_remote_decode_stage_manifest_from_image_dirs(
                self._run_dir,
                remote_decoded_output_dir,
            )
            if iq_manifest is not None:
                wrapper_summary["iq_remote_decode_manifest"] = iq_manifest
                diagnostics["board_decode_partial"] = iq_manifest

        return {
            "status": "running",
            "request_state": "running",
            "status_category": "running",
            "execution_mode": "live",
            "variant": self.variant,
            "message": (
                f"USRP 数据面 batch-spool 正在推进；当前为{self._input_source_label}，"
                "界面继续使用归档样例图，无线链路指标来自当前 2922 运行时。"
            ),
            "control_transport": self._control_transport,
            "data_transport": "usrp",
            "control_handshake_complete": self._control_transport != "none",
            "runner_summary": {},
            "wrapper_summary": wrapper_summary,
            "diagnostics": diagnostics,
            "progress": self._build_progress_payload(
                state="running",
                label=progress_label,
                percent=int(round((inference_completed / max(1, inference_total)) * 100)) if phase == "inference" else percent,
                completed_count=inference_completed if phase == "inference" else processed_count,
                expected_count=target_count,
                event_log=[],
            ),
            "stage_progress": {
                "phase": phase,
                "host_preprocess": self._build_progress_payload(
                    state="completed" if host_preprocess_done else host_preprocess_state,
                    label="上位机图片→latent",
                    percent=int(round((host_preprocess_completed / max(1, host_preprocess_total)) * 100)),
                    completed_count=host_preprocess_completed,
                    expected_count=host_preprocess_total,
                    event_log=[],
                ),
                "transport": self._build_progress_payload(
                    state="completed" if transport_done else "running",
                    label="USRP 传输/解包",
                    percent=100 if transport_done else percent,
                    completed_count=target_count if transport_done else processed_count,
                    expected_count=target_count,
                    event_log=[],
                ),
                "inference": self._build_progress_payload(
                    state="running" if phase == "inference" else "pending",
                    label=f"{self._inference_engine.upper()} 板端推理" if self._inference_engine != INFERENCE_ENGINE_NONE else "板端推理",
                    percent=int(round((inference_completed / max(1, inference_total)) * 100)),
                    completed_count=inference_completed,
                    expected_count=inference_total,
                    event_log=[],
                ),
            },
            "artifacts": self._artifact_paths(),
        }


def launch_local_usrp_reconstruction_job(
    access: BoardAccessConfig,
    *,
    variant: str,
    max_inputs: int,
    control_transport: str = "mlkem",
    control_preflight: dict[str, Any] | None = None,
    inference_engine: str = INFERENCE_ENGINE_NONE,
    inference_callback: Callable[[dict[str, Any], Callable[[int, int], None]], dict[str, Any]] | None = None,
) -> UsrpBatchSpoolJob:
    return UsrpBatchSpoolJob(
        access,
        variant=variant,
        max_inputs=max_inputs,
        control_transport=control_transport,
        control_preflight=control_preflight,
        inference_engine=inference_engine,
        inference_callback=inference_callback,
    )
