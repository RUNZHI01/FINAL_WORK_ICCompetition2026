#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import queue
import re
import shutil
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import build_opener, ProxyHandler, Request, urlopen
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SESSION_SCRIPTS_ROOT = REPO_ROOT / "session_bootstrap" / "scripts"
if str(SESSION_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SESSION_SCRIPTS_ROOT))

from aircraft_position_bridge import FIELD_PATH_CANDIDATES, build_config_from_env_values, fetch_normalized_payload
from archive_replay import ArchiveSessionNotFoundError, list_archive_sessions, load_archive_session
from board_access import (
    BoardAccessConfig,
    build_board_access_config,
    build_demo_default_board_access,
    current_input_source_mode,
    load_env_file,
    normalize_jscc_link_mode,
    normalize_transport_mode,
)
from board_probe import DEFAULT_LIVE_PROBE_OUTPUT, is_successful_probe, load_probe_output, run_live_probe, write_probe_output
from crypto_runtime import (
    DEFAULT_CIPHER_SUITE,
    DEFAULT_CRYPTO_PORT,
    DEFAULT_STATUS_PORT,
    LOCAL_TONGSUO_BRIDGE_KEYS,
    OQS_INSTALL_KEYS,
    REMOTE_PROJECT_ROOT_KEYS,
    REMOTE_SERVER_SCRIPT_KEYS,
    REMOTE_TVM_PYTHON_KEYS,
    STATUS_PORT_KEYS,
    SUITE_KEYS,
    _derive_remote_server_script,
    _detect_local_tongsuo_bridge,
    _normalize_remote_tvm_python,
    MlkemSessionManager,
    build_local_crypto_client_command,
    build_remote_crypto_server_command,
    first_config_value,
    inspect_local_crypto_client_capabilities,
    local_control_transport_mode,
    local_crypto_transport_mode,
    parse_int_config,
    resolve_local_crypto_client,
    resolve_local_mlkem_runtime_root,
    resolve_local_oqs_install,
    resolve_local_crypto_server,
    run_scp_file,
    run_ssh_command,
)
from demo_data import (
    PROJECT_ROOT,
    build_aircraft_position_snapshot,
    build_fault_replay,
    build_job_manifest_contract_snapshot,
    build_link_director_catalog,
    build_original_gallery_snapshot,
    build_prerecorded_inference_result,
    build_recover_replay,
    build_snapshot,
    now_iso,
    read_text,
    repo_relative,
    resolve_repo_path,
)
from fault_injector import query_live_status, run_fault_action, run_recover_action
from event_spine import CONTROL_MODE_SCOPE, DATA_MODE_SCOPE, DemoEventSpine, MODE_BOUNDARY_NOTE, default_event_archive_root
from inference_runner import (
    DEFAULT_MAX_INPUTS,
    DEMO_ADMISSION_MODE_ENV,
    DEMO_BASELINE_ADMISSION_MODE_ENV,
    DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV,
    DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV,
    DEMO_MAX_INPUTS_ENV,
    DEMO_MODE_ENV,
    DEMO_SIGNED_MANIFEST_FILE_ENV,
    DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV,
    describe_demo_admission,
    describe_demo_variant_support,
    expected_sha_for_variant,
    generate_live_job_id,
    launch_remote_reconstruction_job,
    load_signed_manifest_summary,
)
from openamp_control_wrapper import resolve_bash_executable
from usrp_runtime import (
    DEFAULT_RX_CONTROL_PORT,
    DEFAULT_TX_CONTROL_PORT,
    INFERENCE_ENGINE_MNN,
    INFERENCE_ENGINE_NONE,
    INFERENCE_ENGINE_TVM,
    RX_CONTROL_HOST_KEYS,
    RX_CONTROL_PORT_KEYS,
    SHUTDOWN_AFTER_TRANSPORT_KEYS,
    TX_CONTROL_HOST_KEYS,
    TX_CONTROL_PORT_KEYS,
    USRP_AUTO_START_CONTROL_KEYS,
    ensure_usrp_control_servers_started,
    inspect_usrp_control_servers,
    launch_local_usrp_reconstruction_job,
    resolve_shutdown_after_transport,
    shutdown_usrp_control_servers_now,
)


STATIC_ROOT = Path(__file__).resolve().parent / "static"
PACKAGE_ROOT = REPO_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parents[2] if len(REPO_ROOT.parents) > 2 else PACKAGE_ROOT
DEFAULT_MNN_BATCH_ENV_FILE = REPO_ROOT / "session_bootstrap" / "config" / "mnn_benchmark.phytium_pi.example.env"
REMOTE_MNN_RECONSTRUCTION_SCRIPT = REPO_ROOT / "session_bootstrap" / "scripts" / "run_remote_mnn_reconstruction.sh"
REMOTE_TVM_RECONSTRUCTION_SCRIPT = REPO_ROOT / "session_bootstrap" / "scripts" / "run_remote_current_real_reconstruction.sh"
BIG_LITTLE_PIPELINE_SCRIPT = REPO_ROOT / "session_bootstrap" / "scripts" / "run_big_little_pipeline.sh"
DEFAULT_USRP_REMOTE_OUTPUT_ROOT = "/home/user/Downloads/jscc-test-usrp"
USRP_REMOTE_OUTPUT_ROOT_KEYS = ("OPENAMP_DEMO_USRP_OUTPUT_ROOT", "USRP_REMOTE_OUTPUT_ROOT")
DEFAULT_LOCAL_USRP_LATENT_DIR_CANDIDATES = (
    PACKAGE_ROOT / "usrp_latent_input",
    WORKSPACE_ROOT / "jscc-test" / "encoder_outputs",
    PACKAGE_ROOT / "host_pic_to_latent" / "encoder_outputs_airfield300",
    PACKAGE_ROOT / "host_pic_to_latent" / "encoder_outputs",
    PACKAGE_ROOT / "artifacts" / "host_pic_to_latent_300_smoke" / "encoder_outputs",
    PACKAGE_ROOT / "artifacts" / "host_pic_to_latent_smoke" / "encoder_outputs",
)
DEFAULT_LOCAL_USRP_IMAGE_DIR_CANDIDATES = (
    PACKAGE_ROOT / "host_pic_to_latent" / "airfield300",
    PACKAGE_ROOT / "host_pic_to_latent" / "airfield",
    WORKSPACE_ROOT / "原始图像",
)
MLKEM_MODERN_INPUT_BYTES = 1 * 32 * 32 * 32 * 4
MLKEM_LEGACY_INPUT_BYTES = 1 * 3 * 64 * 64 * 4
MLKEM_AUTH_ENABLED_KEYS = ("MLKEM_AUTH_ENABLED",)
MLKEM_AUTH_SERVER_ID_KEYS = ("MLKEM_AUTH_SERVER_ID",)
MLKEM_AUTH_SIG_POLICY_KEYS = ("MLKEM_AUTH_SIG_POLICY",)
DEFAULT_MLKEM_AUTH_SERVER_ID = "phytium-board"
DEFAULT_MLKEM_AUTH_SIG_POLICY = "DUAL_REQUIRED"
SUPPORTED_MLKEM_AUTH_SIG_POLICIES = ("DUAL_REQUIRED", "SM2_ONLY", "MLDSA_ONLY")
BOARD_TELEMETRY_TTL_SEC = 5.0
BOARD_POSITION_API_TTL_SEC = 5.0
USRP_CONTROL_STATUS_TTL_SEC = 2.0
AIRCRAFT_POSITION_UPSTREAM_DISCOVERY_TTL_SEC = 15.0
DEFAULT_BOARD_POSITION_API_REMOTE_ROOT = "~/.openamp-demo/board_position_api_service"
BOARD_POSITION_API_REMOTE_ROOT_KEYS = ("BOARD_POSITION_API_REMOTE_ROOT",)
BOARD_POSITION_API_SERVICE_NAME = "board-position-api.service"
BOARD_POSITION_API_ENV_FILE_NAME = "board_position_api_service.env"
BOARD_POSITION_API_SCRIPT_NAME = "board_position_api_service.py"
BOARD_POSITION_API_RUNNER_NAME = "run_board_position_api_service.sh"
BOARD_POSITION_API_LOG_NAME = "board_position_api_service.log"
BOARD_POSITION_API_USER_SERVICE_PATH = f"~/.config/systemd/user/{BOARD_POSITION_API_SERVICE_NAME}"
BOARD_POSITION_API_RUNTIME_ENV_KEYS = (
    "BOARD_POSITION_API_BIND_HOST",
    "BOARD_POSITION_API_PORT",
    "BOARD_POSITION_API_GPSD_HOST",
    "BOARD_POSITION_API_GPSD_PORT",
    "BOARD_POSITION_API_SOURCE_ORDER",
    "BOARD_POSITION_API_SAMPLE_TIMEOUT_SEC",
    "BOARD_POSITION_API_NMEA_DEVICE",
    "BOARD_POSITION_API_NMEA_BAUDRATE",
    "BOARD_POSITION_API_HTTP_UPSTREAM_URL",
    "BOARD_POSITION_API_HTTP_HEADERS_JSON",
    "BOARD_POSITION_API_HTTP_TIMEOUT_SEC",
    "BOARD_POSITION_API_HTTP_LATITUDE_PATH",
    "BOARD_POSITION_API_HTTP_LONGITUDE_PATH",
    "BOARD_POSITION_API_HTTP_ALTITUDE_M_PATH",
    "BOARD_POSITION_API_HTTP_GROUND_SPEED_KPH_PATH",
    "BOARD_POSITION_API_HTTP_HEADING_DEG_PATH",
    "BOARD_POSITION_API_HTTP_VERTICAL_SPEED_MPS_PATH",
    "BOARD_POSITION_API_HTTP_FIX_TYPE_PATH",
    "BOARD_POSITION_API_HTTP_CONFIDENCE_M_PATH",
    "BOARD_POSITION_API_HTTP_SATELLITES_PATH",
    "BOARD_POSITION_API_HTTP_CAPTURED_AT_PATH",
    "BOARD_POSITION_API_HTTP_SEQUENCE_PATH",
    "BOARD_POSITION_API_HTTP_GROUND_SPEED_SCALE",
    "BOARD_POSITION_API_HTTP_ALTITUDE_SCALE",
    "BOARD_POSITION_API_HTTP_VERTICAL_SPEED_SCALE",
    "AIRCRAFT_POSITION_UPSTREAM_URL",
    "AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON",
    "AIRCRAFT_POSITION_SOURCE_LABEL",
    "AIRCRAFT_POSITION_SOURCE_NOTE",
    "AIRCRAFT_POSITION_PRODUCER_ID",
    "AIRCRAFT_POSITION_TRANSPORT",
    "AIRCRAFT_POSITION_AIRCRAFT_ID",
    "AIRCRAFT_POSITION_MISSION_CALL_SIGN",
    "AIRCRAFT_POSITION_TIMEOUT_SEC",
    "AIRCRAFT_POSITION_GROUND_SPEED_SCALE",
    "AIRCRAFT_POSITION_ALTITUDE_SCALE",
    "AIRCRAFT_POSITION_VERTICAL_SPEED_SCALE",
    *(f"AIRCRAFT_POSITION_{field_name.upper()}_PATH" for field_name in FIELD_PATH_CANDIDATES),
    "BOARD_POSITION_API_REMOTE_ROOT",
)
DEFAULT_AIRCRAFT_POSITION_REMOTE_ROOT = "~/.openamp-demo/aircraft_position_bridge"
AIRCRAFT_POSITION_REMOTE_ROOT_KEYS = ("AIRCRAFT_POSITION_REMOTE_ROOT",)
AIRCRAFT_POSITION_EXECUTION_MODE_KEYS = ("AIRCRAFT_POSITION_EXECUTION_MODE",)
AIRCRAFT_POSITION_UPSTREAM_URL_KEYS = ("AIRCRAFT_POSITION_UPSTREAM_URL",)
AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON_KEYS = ("AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON",)
AIRCRAFT_POSITION_BACKEND_BASE_URL_KEYS = ("AIRCRAFT_POSITION_BACKEND_BASE_URL",)
AIRCRAFT_POSITION_SERVICE_NAME = "aircraft-position-bridge.service"
AIRCRAFT_POSITION_ENV_FILE_NAME = "aircraft_position_bridge.env"
AIRCRAFT_POSITION_SCRIPT_NAME = "aircraft_position_bridge.py"
AIRCRAFT_POSITION_RUNNER_NAME = "run_aircraft_position_bridge.sh"
AIRCRAFT_POSITION_LOG_NAME = "aircraft_position_bridge.log"
AIRCRAFT_POSITION_USER_SERVICE_PATH = f"~/.config/systemd/user/{AIRCRAFT_POSITION_SERVICE_NAME}"
AIRCRAFT_POSITION_RUNTIME_ENV_KEYS = (
    "AIRCRAFT_POSITION_EXECUTION_MODE",
    "AIRCRAFT_POSITION_UPSTREAM_URL",
    "AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON",
    "AIRCRAFT_POSITION_BACKEND_BASE_URL",
    "AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON",
    "AIRCRAFT_POSITION_BACKEND_HEADERS_JSON",
    "AIRCRAFT_POSITION_SOURCE_LABEL",
    "AIRCRAFT_POSITION_SOURCE_NOTE",
    "AIRCRAFT_POSITION_PRODUCER_ID",
    "AIRCRAFT_POSITION_TRANSPORT",
    "AIRCRAFT_POSITION_AIRCRAFT_ID",
    "AIRCRAFT_POSITION_MISSION_CALL_SIGN",
    "AIRCRAFT_POSITION_INTERVAL_SEC",
    "AIRCRAFT_POSITION_TIMEOUT_SEC",
    "AIRCRAFT_POSITION_GROUND_SPEED_SCALE",
    "AIRCRAFT_POSITION_ALTITUDE_SCALE",
    "AIRCRAFT_POSITION_VERTICAL_SPEED_SCALE",
    "AIRCRAFT_POSITION_REMOTE_ROOT",
) + tuple(
    f"AIRCRAFT_POSITION_{field_name.upper()}_PATH" for field_name in FIELD_PATH_CANDIDATES
)
DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATE_PORTS = (9000, 9527, 8080)
DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATE_PATHS = (
    "/gps",
    "/position",
    "/location",
    "/api/gps",
    "/api/position",
    "/api/location",
    "/api/v1/gps",
    "/api/v1/position",
    "/api/v1/location",
)
DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES = tuple(
    f"http://127.0.0.1:{port}{path}"
    for port in DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATE_PORTS
    for path in DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATE_PATHS
)
DEFAULT_DEMO_AIRCRAFT_POSITION_LOCAL_OVERRIDES: dict[str, str] = {
    "AIRCRAFT_POSITION_EXECUTION_MODE": "local",
    "AIRCRAFT_POSITION_UPSTREAM_URL": (
        "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json"
        "&ak=3D0tEY1XnQ3upQjcLR1f3OtvJRe4RlbS"
    ),
    "AIRCRAFT_POSITION_SOURCE_LABEL": "上位机位置（百度IP）",
    "AIRCRAFT_POSITION_SOURCE_NOTE": "当前演示使用上位机本机公网出口 IP 调用百度服务端定位。",
    "AIRCRAFT_POSITION_PRODUCER_ID": "baidu-ip-location-bridge",
    "AIRCRAFT_POSITION_TRANSPORT": "baidu_http_get",
    # Keep the public-IP positioning bridge conservative by default so the demo
    # does not burn through upstream quota while the UI polls cached samples.
    "AIRCRAFT_POSITION_INTERVAL_SEC": "30.0",
    "AIRCRAFT_POSITION_TIMEOUT_SEC": "3.0",
    "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
    "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
}


def fetch_json_direct(url: str, *, timeout: float) -> dict[str, Any]:
    """Fetch JSON directly from the target without honoring host-wide HTTP proxies."""
    req = Request(url, headers={"Accept": "application/json"})
    opener = build_opener(ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _is_loopback_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    return normalized in {"", "127.0.0.1", "localhost", "::1", "[::1]"}


def _tailscale_ipv4() -> str:
    if not shutil.which("tailscale"):
        return ""
    try:
        output = subprocess.check_output(["tailscale", "ip", "-4"], text=True, timeout=2.0)
    except (OSError, subprocess.SubprocessError):
        return ""
    for raw_line in output.splitlines():
        candidate = raw_line.strip()
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", candidate):
            return candidate
    return ""


def _default_backend_base_url_for_board(*, remote_host: str, bind_host: str, bind_port: int) -> str:
    normalized_bind_host = str(bind_host or "").strip()
    if _is_loopback_host(normalized_bind_host):
        return ""

    publish_host = normalized_bind_host
    if normalized_bind_host in {"0.0.0.0", "::", "[::]"}:
        remote_host_text = str(remote_host or "").strip()
        if remote_host_text.startswith("100."):
            publish_host = _tailscale_ipv4()
        if not publish_host or publish_host in {"0.0.0.0", "::", "[::]"}:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((remote_host_text or "8.8.8.8", 1))
                    publish_host = sock.getsockname()[0]
            except OSError:
                publish_host = ""

    if _is_loopback_host(publish_host) or publish_host in {"0.0.0.0", "::", "[::]"}:
        return ""
    return f"http://{publish_host}:{int(bind_port)}"


def _parse_json_dict_text(raw_value: str) -> dict[str, str]:
    value = str(raw_value or "").strip()
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    parsed: dict[str, str] = {}
    for key, item in payload.items():
        name = str(key or "").strip()
        text = str(item or "").strip()
        if not name or not text:
            continue
        parsed[name] = text
    return parsed


def _parse_aircraft_position_upstream_candidates(raw_value: str) -> list[str]:
    value = str(raw_value or "").strip()
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        payload = None

    candidates: list[str] = []
    if isinstance(payload, str):
        candidates.append(payload)
    elif isinstance(payload, list):
        candidates.extend(str(item or "").strip() for item in payload)
    else:
        candidates.extend(part.strip() for part in value.replace("\n", ",").split(","))

    deduped: list[str] = []
    seen: set[str] = set()
    for raw_candidate in candidates:
        candidate = str(raw_candidate or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _board_position_api_local_assets() -> dict[str, Path]:
    return {
        "service_script": PROJECT_ROOT / "session_bootstrap/demo/openamp_control_plane_demo/board_position_api_service.py",
        "runner_script": PROJECT_ROOT / "session_bootstrap/scripts/run_board_position_api_service.sh",
    }


def _board_position_api_remote_paths(remote_root: str) -> dict[str, str]:
    root = remote_root.rstrip("/")
    return {
        "remote_root": root,
        "service_script": f"{root}/{BOARD_POSITION_API_SCRIPT_NAME}",
        "runner_script": f"{root}/{BOARD_POSITION_API_RUNNER_NAME}",
        "env_file": f"{root}/{BOARD_POSITION_API_ENV_FILE_NAME}",
        "log_file": f"{root}/{BOARD_POSITION_API_LOG_NAME}",
        "user_service": BOARD_POSITION_API_USER_SERVICE_PATH,
    }


def _remote_sudo_bash_command(command: str, password: str) -> str:
    sudo_inner = (
        f"printf '%s\\n' {shlex.quote(password)} | "
        f"sudo -S -k bash -lc {shlex.quote(command)}"
    )
    return f"/usr/bin/env bash -lc {shlex.quote(sudo_inner)}"


def _board_position_api_runtime(board_access: BoardAccessConfig) -> dict[str, Any]:
    env_values = board_access.build_env()
    runtime_env = {
        key: str(env_values.get(key, "") or "").strip()
        for key in BOARD_POSITION_API_RUNTIME_ENV_KEYS
        if str(env_values.get(key, "") or "").strip()
    }
    runtime_env.setdefault("BOARD_POSITION_API_BIND_HOST", "127.0.0.1")
    runtime_env.setdefault("BOARD_POSITION_API_PORT", "9000")
    has_http_upstream = bool(
        runtime_env.get("BOARD_POSITION_API_HTTP_UPSTREAM_URL") or runtime_env.get("AIRCRAFT_POSITION_UPSTREAM_URL")
    )
    runtime_env.setdefault("BOARD_POSITION_API_SOURCE_ORDER", "http,gpsd,nmea" if has_http_upstream else "gpsd,nmea")
    runtime_env.setdefault("BOARD_POSITION_API_SAMPLE_TIMEOUT_SEC", "2.0")
    if has_http_upstream:
        inherited_http_timeout = str(runtime_env.get("AIRCRAFT_POSITION_TIMEOUT_SEC") or "").strip()
        if inherited_http_timeout and not runtime_env.get("BOARD_POSITION_API_HTTP_TIMEOUT_SEC"):
            runtime_env["BOARD_POSITION_API_HTTP_TIMEOUT_SEC"] = inherited_http_timeout
    remote_root = first_config_value(
        env_values,
        keys=BOARD_POSITION_API_REMOTE_ROOT_KEYS,
        default=DEFAULT_BOARD_POSITION_API_REMOTE_ROOT,
    )
    return {
        "remote_root": remote_root,
        "runtime_env": runtime_env,
    }


def _aircraft_position_bridge_local_assets() -> dict[str, Path]:
    return {
        "bridge_script": PROJECT_ROOT / "session_bootstrap/demo/openamp_control_plane_demo/aircraft_position_bridge.py",
        "runner_script": PROJECT_ROOT / "session_bootstrap/scripts/run_aircraft_position_bridge.sh",
    }


def _aircraft_position_bridge_remote_paths(remote_root: str) -> dict[str, str]:
    root = remote_root.rstrip("/")
    return {
        "remote_root": root,
        "bridge_script": f"{root}/{AIRCRAFT_POSITION_SCRIPT_NAME}",
        "runner_script": f"{root}/{AIRCRAFT_POSITION_RUNNER_NAME}",
        "env_file": f"{root}/{AIRCRAFT_POSITION_ENV_FILE_NAME}",
        "log_file": f"{root}/{AIRCRAFT_POSITION_LOG_NAME}",
        "user_service": AIRCRAFT_POSITION_USER_SERVICE_PATH,
    }


def _aircraft_position_bridge_runtime(
    board_access: BoardAccessConfig,
    *,
    bind_host: str = "127.0.0.1",
    bind_port: int = 8079,
    discovered_upstream_url: str = "",
) -> dict[str, Any]:
    env_values = board_access.build_env()
    runtime_env = {
        key: str(env_values.get(key, "") or "").strip()
        for key in AIRCRAFT_POSITION_RUNTIME_ENV_KEYS
        if str(env_values.get(key, "") or "").strip()
    }
    execution_mode = first_config_value(env_values, keys=AIRCRAFT_POSITION_EXECUTION_MODE_KEYS).lower()
    upstream_url = first_config_value(env_values, keys=AIRCRAFT_POSITION_UPSTREAM_URL_KEYS)
    upstream_url_source = "env" if upstream_url else ""
    if not upstream_url and discovered_upstream_url:
        upstream_url = str(discovered_upstream_url).strip()
        upstream_url_source = "auto_discovered"
        if upstream_url:
            runtime_env["AIRCRAFT_POSITION_UPSTREAM_URL"] = upstream_url
    raw_candidate_config = first_config_value(env_values, keys=AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON_KEYS)
    candidate_urls = _parse_aircraft_position_upstream_candidates(raw_candidate_config)
    candidate_url_source = "env" if candidate_urls else "defaults"
    if not candidate_urls:
        candidate_urls = list(DEFAULT_AIRCRAFT_POSITION_UPSTREAM_CANDIDATES)
    backend_base_url = first_config_value(env_values, keys=AIRCRAFT_POSITION_BACKEND_BASE_URL_KEYS)
    if not backend_base_url and execution_mode == "local":
        backend_base_url = f"http://127.0.0.1:{int(bind_port)}"
        runtime_env["AIRCRAFT_POSITION_BACKEND_BASE_URL"] = backend_base_url
    if not backend_base_url:
        backend_base_url = _default_backend_base_url_for_board(
            remote_host=board_access.host,
            bind_host=bind_host,
            bind_port=bind_port,
        )
        if backend_base_url:
            runtime_env["AIRCRAFT_POSITION_BACKEND_BASE_URL"] = backend_base_url
    remote_root = first_config_value(
        env_values,
        keys=AIRCRAFT_POSITION_REMOTE_ROOT_KEYS,
        default=DEFAULT_AIRCRAFT_POSITION_REMOTE_ROOT,
    )
    missing_env: list[str] = []
    if not upstream_url:
        missing_env.append(AIRCRAFT_POSITION_UPSTREAM_URL_KEYS[0])
    if not backend_base_url:
        missing_env.append(AIRCRAFT_POSITION_BACKEND_BASE_URL_KEYS[0])
    return {
        "configured": not missing_env,
        "missing_env": missing_env,
        "execution_mode": execution_mode,
        "remote_root": remote_root,
        "runtime_env": runtime_env,
        "upstream_url": upstream_url,
        "upstream_url_source": upstream_url_source,
        "candidate_urls": candidate_urls,
        "candidate_url_source": candidate_url_source,
        "backend_base_url": backend_base_url,
    }


def _aircraft_position_bridge_execution_mode_for_runtime(
    board_access: BoardAccessConfig,
    runtime: dict[str, Any],
) -> str:
    explicit_mode = str(runtime.get("execution_mode") or "").strip().lower()
    if explicit_mode in {"local", "board"}:
        return explicit_mode

    upstream_url = str(runtime.get("upstream_url") or "").strip()
    if not upstream_url:
        return "board"
    if str(runtime.get("upstream_url_source") or "").strip() == "auto_discovered":
        return "board"

    upstream_host = str(urlparse(upstream_url).hostname or "").strip().lower()
    board_host = str(urlparse(f"ssh://{board_access.host}").hostname or "").strip().lower() if board_access.host else ""
    if not upstream_host or _is_loopback_host(upstream_host) or (board_host and upstream_host == board_host):
        return "board"
    return "local"


def _board_aircraft_position_probe_remote_command(
    *,
    candidate_urls: list[str],
    upstream_headers: dict[str, str],
    timeout_sec: float,
) -> str:
    latitude_paths = list(FIELD_PATH_CANDIDATES["latitude"])
    longitude_paths = list(FIELD_PATH_CANDIDATES["longitude"])
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        "$PY - <<'PY'\n"
        "import json\n"
        "from urllib.error import HTTPError, URLError\n"
        "from urllib.request import Request, urlopen\n"
        f"CANDIDATES = {json.dumps(candidate_urls, ensure_ascii=True)}\n"
        f"HEADERS = {json.dumps(upstream_headers, ensure_ascii=True)}\n"
        f"TIMEOUT_SEC = {float(timeout_sec)!r}\n"
        f"LAT_PATHS = {json.dumps(latitude_paths, ensure_ascii=True)}\n"
        f"LON_PATHS = {json.dumps(longitude_paths, ensure_ascii=True)}\n"
        "def extract(payload, path):\n"
        "    current = payload\n"
        "    for part in path.split('.'):\n"
        "        if isinstance(current, dict):\n"
        "            if part not in current:\n"
        "                return None\n"
        "            current = current[part]\n"
        "            continue\n"
        "        if isinstance(current, list):\n"
        "            try:\n"
        "                index = int(part)\n"
        "            except ValueError:\n"
        "                return None\n"
        "            if index < 0 or index >= len(current):\n"
        "                return None\n"
        "            current = current[index]\n"
        "            continue\n"
        "        return None\n"
        "    return current\n"
        "def first_present(payload, paths):\n"
        "    for path in paths:\n"
        "        value = extract(payload, path)\n"
        "        if value not in (None, ''):\n"
        "            return value\n"
        "    return None\n"
        "results = []\n"
        "for url in CANDIDATES:\n"
        "    item = {'url': url}\n"
        "    try:\n"
        "        request = Request(url, headers=dict(HEADERS))\n"
        "        with urlopen(request, timeout=TIMEOUT_SEC) as response:\n"
        "            item['http_status'] = getattr(response, 'status', 200)\n"
        "            body = response.read().decode('utf-8').strip()\n"
        "        payload = json.loads(body) if body else None\n"
        "        if not isinstance(payload, dict):\n"
        "            item['error'] = 'invalid_json_object'\n"
        "            results.append(item)\n"
        "            continue\n"
        "        latitude = first_present(payload, LAT_PATHS)\n"
        "        longitude = first_present(payload, LON_PATHS)\n"
        "        item['has_coordinates'] = latitude not in (None, '') and longitude not in (None, '')\n"
        "        item['sample_keys'] = sorted(str(key) for key in payload.keys())[:8]\n"
        "        if item['has_coordinates']:\n"
        "            print(json.dumps({'status': 'detected', 'selected_url': url, 'results': results + [item]}, ensure_ascii=False))\n"
        "            raise SystemExit(0)\n"
        "        item['error'] = 'missing_coordinates'\n"
        "    except HTTPError as exc:\n"
        "        item['http_status'] = exc.code\n"
        "        item['error'] = f'http_error:{exc.code}'\n"
        "    except URLError as exc:\n"
        "        item['error'] = f'url_error:{exc.reason}'\n"
        "    except Exception as exc:\n"
        "        item['error'] = f'{type(exc).__name__}:{exc}'\n"
        "    results.append(item)\n"
        "print(json.dumps({'status': 'not_found', 'selected_url': '', 'results': results}, ensure_ascii=False))\n"
        "PY"
    )


def query_board_aircraft_position_upstream(
    board_access: BoardAccessConfig,
    *,
    candidate_urls: list[str],
    upstream_headers: dict[str, str] | None = None,
    timeout_sec: float = 6.0,
) -> dict[str, Any]:
    if not candidate_urls:
        return {
            "status": "disabled",
            "selected_url": "",
            "candidate_urls": [],
            "results": [],
            "checked_at": now_iso(),
        }
    proc = run_ssh_command(
        host=board_access.host,
        user=board_access.user,
        password=board_access.password,
        port=board_access.port,
        remote_command=_board_aircraft_position_probe_remote_command(
            candidate_urls=candidate_urls,
            upstream_headers=dict(upstream_headers or {}),
            timeout_sec=max(min(timeout_sec / max(len(candidate_urls), 1), 2.0), 0.8),
        ),
        timeout=max(timeout_sec, 2.0),
    )
    if proc.returncode != 0:
        error_output = (proc.stderr or proc.stdout or "board aircraft-position probe failed").strip()
        raise RuntimeError(error_output)
    payload = json.loads((proc.stdout or "").strip() or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("board aircraft-position probe returned invalid JSON")
    payload.setdefault("status", "unknown")
    payload.setdefault("selected_url", "")
    payload.setdefault("results", [])
    payload["candidate_urls"] = list(candidate_urls)
    payload["checked_at"] = now_iso()
    return payload


def _aircraft_position_bridge_status(
    board_access: BoardAccessConfig,
    *,
    aircraft_position_payload: dict[str, Any],
    bind_host: str = "127.0.0.1",
    bind_port: int = 8079,
    discovered_upstream_url: str = "",
    upstream_probe: dict[str, Any] | None = None,
    local_runtime_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime = _aircraft_position_bridge_runtime(
        board_access,
        bind_host=bind_host,
        bind_port=bind_port,
        discovered_upstream_url=discovered_upstream_url,
    )
    execution_mode = _aircraft_position_bridge_execution_mode_for_runtime(board_access, runtime)
    source_kind = str(aircraft_position_payload.get("source_kind") or "").strip()
    source_status = str(aircraft_position_payload.get("source_status") or "").strip()
    live_feed_active = source_kind == "upper_computer_gps" and source_status == "live"
    local_state = dict(local_runtime_state or {})

    if live_feed_active:
        status = "live"
        if execution_mode == "local":
            note = "本机外部定位 bridge 已驱动当前 aircraft-position live contract。"
        else:
            note = "定位 bridge 已驱动当前 aircraft-position live contract。"
    elif execution_mode == "local" and runtime["configured"]:
        local_status = str(local_state.get("status") or "").strip()
        last_error = str(local_state.get("last_error") or "").strip()
        if local_status == "error" and last_error:
            status = "local_error"
            note = f"本机外部定位 bridge 调用上游失败：{last_error}"
        else:
            status = "armed_local"
            note = "本机外部定位 bridge 配置已存在；demo 启动后会直接在本机轮询上游并更新 aircraft-position。"
    elif runtime["configured"] and runtime["upstream_url_source"] == "auto_discovered":
        status = "autodiscovered"
        note = "已自动探测到板卡定位 API 候选；保存会话后会尝试用发现到的 URL 启动定位 bridge。"
    elif not runtime["configured"]:
        probe_status = str((upstream_probe or {}).get("status") or "").strip()
        if probe_status == "not_found":
            status = "upstream_not_found"
            note = "已探测常见板卡定位 API 候选，但当前没有发现可用上游；当前仍是 stub/fallback 合同。"
        elif probe_status == "error":
            status = "upstream_probe_error"
            note = "板卡定位上游探测失败；当前仍是 stub/fallback 合同。"
        else:
            status = "config_missing"
            note = "缺少定位 bridge 上游 URL 或 backend 回推地址；当前仍是 stub/fallback 合同。"
    elif not board_access.connection_ready:
        status = "waiting_session"
        note = "定位 bridge 配置已存在，但当前板卡会话未补齐。"
    else:
        status = "armed"
        note = "定位 bridge 配置已存在；保存会话后会尝试自动部署并启动。"

    return {
        "status": status,
        "note": note,
        "configured": runtime["configured"],
        "missing_env": list(runtime["missing_env"]),
        "execution_mode": execution_mode,
        "connection_ready": board_access.connection_ready,
        "upstream_url": runtime["upstream_url"],
        "upstream_url_source": runtime["upstream_url_source"],
        "candidate_urls": list(runtime["candidate_urls"]),
        "candidate_url_source": runtime["candidate_url_source"],
        "backend_base_url": runtime["backend_base_url"],
        "remote_root": runtime["remote_root"],
        "live_feed_active": live_feed_active,
        "upstream_probe": dict(upstream_probe or {}),
        "local_runtime_state": local_state,
    }


def _render_aircraft_position_bridge_env_file(runtime_env: dict[str, str]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# Generated by the OpenAMP demo backend. Do not edit on the board.",
        "set -euo pipefail",
    ]
    for key in sorted(runtime_env):
        lines.append(f"export {key}={shlex.quote(runtime_env[key])}")
    return "\n".join(lines) + "\n"


def _render_board_position_api_env_file(runtime_env: dict[str, str]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# Generated by the OpenAMP demo backend. Do not edit on the board.",
        "set -euo pipefail",
    ]
    for key in sorted(runtime_env):
        lines.append(f"export {key}={shlex.quote(runtime_env[key])}")
    return "\n".join(lines) + "\n"


def _render_aircraft_position_bridge_user_service(remote_root: str) -> str:
    paths = _aircraft_position_bridge_remote_paths(remote_root)
    working_directory = (
        f"%h/{paths['remote_root'][2:]}" if paths["remote_root"].startswith("~/") else paths["remote_root"]
    )
    return "\n".join(
        [
            "[Unit]",
            "Description=Aircraft Position Bridge",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={working_directory}",
            (
                "ExecStart=/usr/bin/env bash -lc "
                f"\"set -a; . {paths['env_file']}; set +a; "
                f"exec {paths['runner_script']} >> {paths['log_file']} 2>&1\""
            ),
            "Restart=always",
            "RestartSec=2",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def _render_board_position_api_user_service(remote_root: str) -> str:
    paths = _board_position_api_remote_paths(remote_root)
    working_directory = (
        f"%h/{paths['remote_root'][2:]}" if paths["remote_root"].startswith("~/") else paths["remote_root"]
    )
    return "\n".join(
        [
            "[Unit]",
            "Description=Board Position API Service",
            "After=network-online.target",
            "Wants=network-online.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={working_directory}",
            (
                "ExecStart=/usr/bin/env bash -lc "
                f"\"set -a; . {paths['env_file']}; set +a; "
                f"exec {paths['runner_script']} >> {paths['log_file']} 2>&1\""
            ),
            "Restart=always",
            "RestartSec=2",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def _build_remote_text_write_command(remote_path: str, content: str, mode: int) -> str:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        "$PY - <<'PY'\n"
        "import base64\n"
        "import os\n"
        "from pathlib import Path\n"
        f"path = Path({json.dumps(remote_path)}).expanduser()\n"
        "path.parent.mkdir(parents=True, exist_ok=True)\n"
        f"path.write_bytes(base64.b64decode({json.dumps(encoded)}))\n"
        f"os.chmod(path, {mode})\n"
        "PY"
    )


def _build_remote_python_exec_command(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    python_command = (
        "import base64; "
        f'exec(base64.b64decode("{encoded}").decode("utf-8"))'
    )
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        f"$PY -c {shlex.quote(python_command)}"
    )


def _build_remote_file_copy_prepare_command(remote_temp_path: str) -> str:
    script = "\n".join(
        [
            "from pathlib import Path",
            f"path = Path({json.dumps(remote_temp_path)}).expanduser()",
            "path.parent.mkdir(parents=True, exist_ok=True)",
        ]
    )
    return _build_remote_python_exec_command(script)


def _build_remote_file_copy_finalize_command(remote_temp_path: str, remote_path: str, mode: int) -> str:
    script = "\n".join(
        [
            "import os",
            "from pathlib import Path",
            f"tmp = Path({json.dumps(remote_temp_path)}).expanduser()",
            f"dest = Path({json.dumps(remote_path)}).expanduser()",
            "dest.parent.mkdir(parents=True, exist_ok=True)",
            "os.replace(tmp, dest)",
            f"os.chmod(dest, {int(mode)})",
        ]
    )
    return _build_remote_python_exec_command(script)


def _remote_http_wait_command(
    url: str,
    *,
    attempts: int = 12,
    sleep_sec: float = 0.4,
    timeout_sec: float = 1.0,
) -> str:
    script = "\n".join(
        [
            "import sys",
            "import time",
            "from urllib.error import HTTPError, URLError",
            "from urllib.request import Request, urlopen",
            f"URL = {json.dumps(url, ensure_ascii=True)}",
            f"ATTEMPTS = {max(int(attempts), 1)!r}",
            f"SLEEP_SEC = {max(float(sleep_sec), 0.05)!r}",
            f"TIMEOUT_SEC = {max(float(timeout_sec), 0.2)!r}",
            "last_error = 'http_wait_failed'",
            "for _ in range(ATTEMPTS):",
            "    try:",
            "        request = Request(URL, headers={'Accept': 'application/json'})",
            "        with urlopen(request, timeout=TIMEOUT_SEC) as response:",
            "            status = int(getattr(response, 'status', 200))",
            "            if status == 200:",
            "                raise SystemExit(0)",
            "            last_error = f'http_status:{status}'",
            "    except HTTPError as exc:",
            "        last_error = f'http_error:{exc.code}'",
            "    except URLError as exc:",
            "        last_error = f'url_error:{exc.reason}'",
            "    except Exception as exc:",
            "        last_error = f'{type(exc).__name__}:{exc}'",
            "    time.sleep(SLEEP_SEC)",
            "sys.stderr.write(last_error)",
            "raise SystemExit(1)",
        ]
    )
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    python_command = (
        "import base64; "
        f'exec(base64.b64decode("{encoded}").decode("utf-8"))'
    )
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        f"$PY -c {shlex.quote(python_command)}"
    )


def _remote_http_json_probe_command(url: str, *, timeout_sec: float = 2.0) -> str:
    script = "\n".join(
        [
            "import json",
            "from urllib.error import HTTPError, URLError",
            "from urllib.request import Request, urlopen",
            f"URL = {json.dumps(url, ensure_ascii=True)}",
            f"TIMEOUT_SEC = {max(float(timeout_sec), 0.2)!r}",
            "result = {'status': 'error', 'url': URL, 'http_status': None, 'payload': None, 'body': '', 'error': ''}",
            "try:",
            "    request = Request(URL, headers={'Accept': 'application/json'})",
            "    with urlopen(request, timeout=TIMEOUT_SEC) as response:",
            "        body = response.read().decode('utf-8', errors='ignore')",
            "        payload = json.loads(body) if body else None",
            "        result.update(status='ok', http_status=int(getattr(response, 'status', 200)), body=body[:2000])",
            "        if isinstance(payload, dict):",
            "            result['payload'] = payload",
            "except HTTPError as exc:",
            "    body = exc.read().decode('utf-8', errors='ignore')",
            "    payload = None",
            "    try:",
            "        payload = json.loads(body) if body else None",
            "    except json.JSONDecodeError:",
            "        payload = None",
            "    result.update(status='http_error', http_status=int(exc.code), body=body[:2000], error=str(exc))",
            "    if isinstance(payload, dict):",
            "        result['payload'] = payload",
            "except URLError as exc:",
            "    result.update(status='url_error', error=str(exc.reason))",
            "except Exception as exc:",
            "    result.update(status=type(exc).__name__, error=str(exc))",
            "print(json.dumps(result, ensure_ascii=False))",
        ]
    )
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    python_command = (
        "import base64; "
        f'exec(base64.b64decode("{encoded}").decode("utf-8"))'
    )
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        f"$PY -c {shlex.quote(python_command)}"
    )


def _remote_terminate_matching_processes_command(pattern: str) -> str:
    script = "\n".join(
        [
            "import os",
            "import signal",
            "import subprocess",
            f"PATTERN = {json.dumps(pattern, ensure_ascii=True)}",
            "current_pid = os.getpid()",
            "parent_pid = os.getppid()",
            "try:",
            "    output = subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True)",
            "except Exception:",
            "    raise SystemExit(0)",
            "for raw_line in output.splitlines():",
            "    line = raw_line.strip()",
            "    if not line:",
            "        continue",
            "    pid_text, _, args = line.partition(' ')",
            "    try:",
            "        pid = int(pid_text)",
            "    except ValueError:",
            "        continue",
            "    if pid in {current_pid, parent_pid}:",
            "        continue",
            "    if PATTERN not in args:",
            "        continue",
            "    try:",
            "        os.kill(pid, signal.SIGTERM)",
            "    except ProcessLookupError:",
            "        pass",
            "    except PermissionError:",
            "        pass",
        ]
    )
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    python_command = (
        "import base64; "
        f'exec(base64.b64decode("{encoded}").decode("utf-8"))'
    )
    return (
        "if command -v python3 >/dev/null 2>&1; then PY=python3; "
        "elif command -v python >/dev/null 2>&1; then PY=python; "
        "else echo 'python not found on remote host' >&2; exit 127; fi; "
        f"$PY -c {shlex.quote(python_command)}"
    )


def _board_position_api_health_url(runtime_env: dict[str, str]) -> str:
    bind_host = str(runtime_env.get("BOARD_POSITION_API_BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    if bind_host in {"0.0.0.0", "::", "[::]"}:
        bind_host = "127.0.0.1"
    bind_port = parse_int_config(runtime_env.get("BOARD_POSITION_API_PORT"), 9000)
    return f"http://{bind_host}:{bind_port}/health"


def _board_position_api_sample_url(runtime_env: dict[str, str]) -> str:
    bind_host = str(runtime_env.get("BOARD_POSITION_API_BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    if bind_host in {"0.0.0.0", "::", "[::]"}:
        bind_host = "127.0.0.1"
    bind_port = parse_int_config(runtime_env.get("BOARD_POSITION_API_PORT"), 9000)
    return f"http://{bind_host}:{bind_port}/api/v1/position"


def query_board_position_api_health(
    board_access: BoardAccessConfig,
    *,
    runtime_env: dict[str, str],
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    health_url = _board_position_api_health_url(runtime_env)
    proc = run_ssh_command(
        host=board_access.host,
        user=board_access.user,
        password=board_access.password,
        port=board_access.port,
        remote_command=_remote_http_json_probe_command(health_url, timeout_sec=timeout_sec),
        timeout=max(timeout_sec + 2.0, 4.0),
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "board position-api health probe failed").strip())
    payload = json.loads((proc.stdout or "").strip() or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("board position-api health probe returned invalid JSON")
    payload.setdefault("status", "error")
    payload.setdefault("url", health_url)
    return payload


def query_board_position_api_sample(
    board_access: BoardAccessConfig,
    *,
    runtime_env: dict[str, str],
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    sample_url = _board_position_api_sample_url(runtime_env)
    proc = run_ssh_command(
        host=board_access.host,
        user=board_access.user,
        password=board_access.password,
        port=board_access.port,
        remote_command=_remote_http_json_probe_command(sample_url, timeout_sec=timeout_sec),
        timeout=max(timeout_sec + 2.0, 4.0),
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "board position-api sample probe failed").strip())
    payload = json.loads((proc.stdout or "").strip() or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("board position-api sample probe returned invalid JSON")
    payload.setdefault("status", "error")
    payload.setdefault("url", sample_url)
    return payload


def _board_position_api_status(
    board_access: BoardAccessConfig,
    *,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    runtime = _board_position_api_runtime(board_access)
    status_payload = {
        "status": "waiting_session" if not board_access.connection_ready else "unknown",
        "note": "板卡会话未补齐，尚未探测板端定位 API 服务。" if not board_access.connection_ready else "",
        "service_reachable": False,
        "http_status": None,
        "health_url": _board_position_api_health_url(runtime["runtime_env"]),
        "remote_root": runtime["remote_root"],
        "sample_ready": False,
        "service_state": "",
        "last_error": "",
        "source_order": [],
        "sample": None,
    }
    if not board_access.connection_ready:
        return status_payload

    try:
        probe = query_board_position_api_health(board_access, runtime_env=runtime["runtime_env"], timeout_sec=timeout_sec)
    except Exception as exc:
        status_payload.update(
            {
                "status": "probe_error",
                "note": f"板端定位 API 健康探测失败: {exc}",
                "last_error": str(exc),
            }
        )
        return status_payload

    probe_status = str(probe.get("status") or "").strip()
    http_status = probe.get("http_status")
    payload = probe.get("payload") if isinstance(probe.get("payload"), dict) else {}
    service_state = str(payload.get("status") or "").strip()
    last_error = str(payload.get("last_error") or probe.get("error") or "").strip()
    sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else None
    sample_ready = isinstance(sample, dict)
    source_order = list(payload.get("source_order") or []) if isinstance(payload.get("source_order"), list) else []
    sample_probe: dict[str, Any] | None = None

    status_payload.update(
        {
            "service_reachable": probe_status == "ok",
            "http_status": http_status,
            "service_state": service_state,
            "last_error": last_error,
            "source_order": source_order,
            "sample": sample,
            "sample_ready": sample_ready,
        }
    )

    if probe_status == "ok" and not sample_ready:
        try:
            sample_probe = query_board_position_api_sample(
                board_access,
                runtime_env=runtime["runtime_env"],
                timeout_sec=timeout_sec,
            )
        except Exception as exc:
            sample_probe = {"status": "probe_error", "error": str(exc)}
        sample_probe_status = str(sample_probe.get("status") or "").strip()
        sample_probe_payload = sample_probe.get("payload") if isinstance(sample_probe.get("payload"), dict) else {}
        live_sample = sample_probe_payload if sample_probe_status == "ok" else None
        if isinstance(live_sample, dict):
            status_payload.update(
                {
                    "http_status": sample_probe.get("http_status"),
                    "service_state": str(live_sample.get("status") or service_state or "").strip(),
                    "last_error": "",
                    "sample": live_sample,
                    "sample_ready": True,
                }
            )
            sample = live_sample
            sample_ready = True
        elif sample_probe_status == "http_error":
            sample_error_payload = sample_probe_payload
            status_payload["http_status"] = sample_probe.get("http_status")
            status_payload["last_error"] = str(
                sample_error_payload.get("error") or sample_probe.get("error") or last_error or ""
            ).strip()

    if probe_status == "ok" and service_state == "ok" and sample_ready:
        status_payload["status"] = "live"
        status_payload["note"] = "板端定位 API 服务已返回 live sample。"
    elif probe_status == "ok" and sample_ready:
        status_payload["status"] = "live"
        status_payload["note"] = "板端定位 API 服务已返回 live sample。"
    elif probe_status == "ok":
        status_payload["status"] = "source_unavailable"
        status_payload["note"] = "板端定位 API 服务已启动，但当前没有拿到有效位置样本。"
    elif probe_status == "http_error":
        status_payload["status"] = "service_error"
        status_payload["note"] = "板端定位 API 服务返回了错误 HTTP 状态。"
    elif probe_status == "url_error":
        status_payload["status"] = "offline"
        status_payload["note"] = "板端定位 API 服务当前不可达。"
    else:
        status_payload["status"] = "probe_error"
        status_payload["note"] = "板端定位 API 健康探测未返回可用结果。"

    return status_payload


def _board_telemetry_remote_command() -> str:
    return (
        "sh -lc '"
        "cat /proc/meminfo; "
        "printf \"__BOARD_MEMINFO_END__\\n\"; "
        "cat /proc/stat; "
        "printf \"__BOARD_STAT1_END__\\n\"; "
        "sleep 0.1; "
        "cat /proc/stat; "
        "printf \"__BOARD_STAT2_END__\\n\"; "
        "cat /proc/loadavg; "
        "printf \"__BOARD_LOADAVG_END__\\n\"; "
        "(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 1)"
        "'"
    )


def _parse_marker_sections(stdout: str) -> dict[str, str]:
    marker_to_name = {
        "__BOARD_MEMINFO_END__": "meminfo",
        "__BOARD_STAT1_END__": "stat1",
        "__BOARD_STAT2_END__": "stat2",
        "__BOARD_LOADAVG_END__": "loadavg",
    }
    section_order = ["meminfo", "stat1", "stat2", "loadavg", "cpu_cores"]
    sections: dict[str, list[str]] = {name: [] for name in section_order}
    current_name = "meminfo"
    for raw_line in stdout.splitlines():
        marker_name = marker_to_name.get(raw_line.strip())
        if marker_name is not None:
            index = section_order.index(marker_name)
            current_name = section_order[index + 1]
            continue
        sections[current_name].append(raw_line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _parse_meminfo_kb(meminfo_text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in meminfo_text.splitlines():
        key, _, rest = line.partition(":")
        if not key or not rest:
            continue
        value_token = rest.strip().split(" ", 1)[0]
        try:
            result[key] = int(value_token)
        except ValueError:
            continue
    return result


def _parse_proc_stat_total_idle(stat_text: str) -> tuple[int, int]:
    for line in stat_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("cpu "):
            continue
        parts = stripped.split()
        values = [int(token) for token in parts[1:9]]
        idle = values[3] + values[4]
        total = sum(values)
        return total, idle
    raise ValueError("missing aggregate cpu line in /proc/stat")


def _memory_pct(used_kb: int, total_kb: int) -> float:
    if total_kb <= 0:
        return 0.0
    return round((used_kb * 100.0) / total_kb, 3)


def query_board_telemetry(board_access: BoardAccessConfig, *, timeout_sec: float = 3.0) -> dict[str, Any]:
    proc = run_ssh_command(
        host=board_access.host,
        user=board_access.user,
        password=board_access.password,
        port=board_access.port,
        remote_command=_board_telemetry_remote_command(),
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "board telemetry probe failed").strip())

    sections = _parse_marker_sections(proc.stdout or "")
    meminfo = _parse_meminfo_kb(sections["meminfo"])
    total1, idle1 = _parse_proc_stat_total_idle(sections["stat1"])
    total2, idle2 = _parse_proc_stat_total_idle(sections["stat2"])
    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    cpu_pct = 0.0 if total_delta <= 0 else round(((total_delta - idle_delta) * 100.0) / total_delta, 3)

    mem_total_kb = int(meminfo.get("MemTotal", 0))
    mem_available_kb = int(meminfo.get("MemAvailable", meminfo.get("MemFree", 0)))
    mem_used_kb = max(mem_total_kb - mem_available_kb, 0)
    loadavg_line = sections["loadavg"].split()
    loadavg_1m = round(float(loadavg_line[0]), 3) if loadavg_line else 0.0
    try:
        cpu_cores = max(int((sections["cpu_cores"] or "1").splitlines()[0].strip()), 1)
    except ValueError:
        cpu_cores = 1

    return {
        "status": "ok",
        "stale": False,
        "source": "ssh_procfs",
        "collected_at": now_iso(),
        "compute_label": "CPU",
        "compute_pct": cpu_pct,
        "memory_pct": _memory_pct(mem_used_kb, mem_total_kb),
        "memory_used_mb": round(mem_used_kb / 1024.0, 2),
        "memory_available_mb": round(mem_available_kb / 1024.0, 2),
        "memory_total_mb": round(mem_total_kb / 1024.0, 2),
        "loadavg_1m": loadavg_1m,
        "cpu_cores": cpu_cores,
    }


def _board_position_api_pending_status(
    board_access: BoardAccessConfig,
    *,
    status: str,
    note: str,
) -> dict[str, Any]:
    runtime = _board_position_api_runtime(board_access)
    return {
        "status": status,
        "note": note,
        "stale": True,
        "service_reachable": False,
        "http_status": None,
        "health_url": _board_position_api_health_url(runtime["runtime_env"]),
        "remote_root": runtime["remote_root"],
        "sample_ready": False,
        "service_state": "",
        "last_error": "",
        "source_order": [],
        "sample": None,
    }


def _board_telemetry_pending_status(*, status: str, note: str) -> dict[str, Any]:
    return {
        "status": status,
        "stale": True,
        "source": "ssh_procfs",
        "collected_at": "",
        "compute_label": "CPU",
        "compute_pct": None,
        "memory_pct": None,
        "memory_used_mb": None,
        "memory_available_mb": None,
        "memory_total_mb": None,
        "loadavg_1m": None,
        "cpu_cores": None,
        "note": note,
    }


def _aircraft_position_upstream_pending_status(
    runtime: dict[str, Any],
    *,
    status: str,
    note: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "selected_url": "",
        "selected_source": "",
        "candidate_urls": list(runtime["candidate_urls"]),
        "results": [],
        "checked_at": now_iso(),
        "stale": True,
        "note": note,
    }


def _first_env_value(env_values: dict[str, str], keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = str(env_values.get(key) or "").strip()
        if value:
            return value
    return default


def _env_bool_value(value: str | None, default: bool) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _usrp_control_status_placeholder(
    board_access: BoardAccessConfig,
    *,
    status: str,
    message: str,
) -> dict[str, Any]:
    env_values = board_access.build_env()
    rx_host = _first_env_value(env_values, RX_CONTROL_HOST_KEYS, board_access.host)
    rx_port = _first_env_value(env_values, RX_CONTROL_PORT_KEYS, DEFAULT_RX_CONTROL_PORT)
    tx_host = _first_env_value(env_values, TX_CONTROL_HOST_KEYS, "127.0.0.1")
    tx_port = _first_env_value(env_values, TX_CONTROL_PORT_KEYS, DEFAULT_TX_CONTROL_PORT)
    auto_start = _env_bool_value(
        _first_env_value(env_values, USRP_AUTO_START_CONTROL_KEYS, "1"),
        True,
    )
    shutdown_after_transport = resolve_shutdown_after_transport(env_values)
    return {
        "status": status,
        "stale": True,
        "message": message,
        "rx_control": {
            "host": rx_host,
            "port": rx_port,
            "ready": False,
            "response": "",
            "status": "",
        },
        "tx_control": {
            "host": tx_host,
            "port": tx_port,
            "ready": False,
            "response": "",
            "status": "",
        },
        "auto_start": auto_start,
        "shutdown_after_transport": shutdown_after_transport,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Feiteng semantic visual return demo dashboard.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host.")
    parser.add_argument("--port", type=int, default=8079, help="Bind port.")
    parser.add_argument(
        "--probe-env",
        default="",
        help="Optional env file for read-only SSH board probes.",
    )
    parser.add_argument(
        "--aircraft-position-env",
        default="",
        help="Optional env file for a local external aircraft-position provider.",
    )
    parser.add_argument(
        "--probe-timeout-sec",
        type=float,
        default=30.0,
        help="Timeout for the read-only SSH board probe.",
    )
    parser.add_argument(
        "--probe-startup",
        action="store_true",
        help="Run one read-only board probe during startup.",
    )
    parser.add_argument(
        "--demo-admission-mode",
        choices=("legacy_sha", "signed_manifest_v1"),
        default="",
        help="Optional current-demo admission mode override.",
    )
    parser.add_argument(
        "--signed-manifest-file",
        default="",
        help="Optional signed bundle path for the current demo artifact.",
    )
    parser.add_argument(
        "--signed-manifest-public-key",
        default="",
        help="Optional PEM public key used to verify --signed-manifest-file locally before launch.",
    )
    parser.add_argument(
        "--baseline-admission-mode",
        choices=("legacy_sha", "signed_manifest_v1"),
        default="",
        help="Optional baseline-demo admission mode override.",
    )
    parser.add_argument(
        "--baseline-signed-manifest-file",
        default="",
        help="Optional signed bundle path for the baseline demo artifact.",
    )
    parser.add_argument(
        "--baseline-signed-manifest-public-key",
        default="",
        help="Optional PEM public key used to verify --baseline-signed-manifest-file locally before launch.",
    )
    return parser.parse_args()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def recover_status_lamp(guard_state: str, last_fault_code: str) -> str:
    if str(guard_state or "").upper() != "READY":
        return "red"
    if str(last_fault_code or "").upper() == "NONE":
        return "green"
    return "yellow"


def recover_message(guard_state: str, last_fault_code: str) -> str:
    guard = str(guard_state or "").upper()
    fault = str(last_fault_code or "").upper()
    if guard == "READY" and fault == "NONE":
        return "已使用当前会话凭据执行 SAFE_STOP，板端已回到 READY。"
    if guard == "READY":
        return "已使用当前会话凭据执行 SAFE_STOP，板端已回到 READY；last_fault_code 保留最近故障证据，不宣称已清零。"
    return "已使用当前会话凭据执行 SAFE_STOP，请以当前 guard_state / last_fault_code 为准。"


def last_log_entry(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    for item in reversed(entries):
        text = str(item or "").strip()
        if text:
            return text
    return ""


def derive_safe_stop_state(
    *,
    guard_state: str,
    last_fault_code: str,
    last_fault: dict[str, Any] | None,
) -> tuple[str, str, str]:
    guard = str(guard_state or "").upper()
    fault = str(last_fault_code or "").upper()
    last_status = str((last_fault or {}).get("status") or "").lower()
    if last_status == "recovered":
        tone = "online" if fault == "NONE" else "degraded"
        return (
            "RECOVERED",
            tone,
            "最近一次 SAFE_STOP 收口结果已记录到当前面板镜像；物理 SAFE_STOP 仍由 RTOS/Bare Metal 执行。",
        )
    if fault not in {"", "NONE", "UNKNOWN"}:
        return (
            "FAULT",
            "offline",
            "当前 fault code 仍锁存在面板镜像；Linux UI 不宣称已清除 RTOS/Bare Metal 侧 SAFE_STOP/GPIO。",
        )
    if guard == "JOB_ACTIVE":
        return (
            "STANDBY",
            "degraded",
            "板端当前仍在 JOB_ACTIVE；面板只显示 SAFE_STOP 控制面镜像，不自动触发收口。",
        )
    if guard == "READY":
        return (
            "IDLE",
            "online",
            "当前 guard_state=READY，且没有新的 fault latch；面板显示 SAFE_STOP 待命镜像。",
        )
    return (
        "UNKNOWN",
        "neutral",
        "当前 SAFE_STOP 镜像态未知；请以 guard_state / last_fault_code 与正式证据为准。",
    )


def derive_latch_state(*, last_fault_code: str, total_fault_count: int) -> tuple[str, str, str]:
    fault = str(last_fault_code or "").upper()
    if fault in {"", "UNKNOWN"}:
        return (
            "UNKNOWN",
            "neutral",
            "当前没有足够的锁存信息；请以 status_source / status_note 为准。",
        )
    if fault != "NONE":
        return (
            "LATCHED",
            "offline",
            f"last_fault_code={fault} 仍保留在控制面镜像中；fault_count={total_fault_count}。",
        )
    if total_fault_count > 0:
        return (
            "CLEAR",
            "degraded",
            f"当前 last_fault_code 已回到 NONE，但 fault history 计数保留为 {total_fault_count}。",
        )
    return (
        "CLEAR",
        "online",
        "当前 last_fault_code=NONE，且没有额外 fault history 计数。",
    )


def build_safety_panel(
    *,
    guard_state: str,
    last_fault_code: str,
    total_fault_count: int,
    board_online: bool,
    status_source: str,
    status_note: str,
    last_fault: dict[str, Any] | None,
) -> dict[str, Any]:
    safe_stop_state, safe_stop_tone, safe_stop_note = derive_safe_stop_state(
        guard_state=guard_state,
        last_fault_code=last_fault_code,
        last_fault=last_fault,
    )
    latch_state, latch_tone, latch_note = derive_latch_state(
        last_fault_code=last_fault_code,
        total_fault_count=total_fault_count,
    )
    if safe_stop_state == "RECOVERED":
        panel_label = "SAFE_STOP 已执行"
        panel_tone = safe_stop_tone
    elif latch_state == "LATCHED":
        panel_label = "告警锁存"
        panel_tone = latch_tone
    elif board_online:
        panel_label = "无告警"
        panel_tone = "online"
    else:
        panel_label = "证据镜像"
        panel_tone = "degraded"

    last_fault_result: dict[str, Any] = {}
    if last_fault:
        fault_guard_state = str(last_fault.get("guard_state") or guard_state or "")
        fault_code = str(last_fault.get("last_fault_code") or last_fault_code or "")
        last_fault_result = {
            "status": str(last_fault.get("status") or ""),
            "execution_mode": str(last_fault.get("execution_mode") or ""),
            "source_label": str(last_fault.get("source_label") or ""),
            "message": str(last_fault.get("message") or ""),
            "guard_state": fault_guard_state,
            "last_fault_code": fault_code,
            "status_lamp": str(
                last_fault.get("status_lamp") or recover_status_lamp(fault_guard_state, fault_code)
            ),
            "log_tail": last_log_entry(last_fault.get("log_entries")),
        }

    ownership_note = (
        "RTOS/Bare Metal owns physical SAFE_STOP/GPIO; Linux UI is mirror/control surface only."
    )
    return {
        "panel_label": panel_label,
        "panel_tone": panel_tone,
        "safe_stop_state": safe_stop_state,
        "safe_stop_tone": safe_stop_tone,
        "safe_stop_note": safe_stop_note,
        "latch_state": latch_state,
        "latch_tone": latch_tone,
        "latch_note": latch_note,
        "guard_state": guard_state,
        "last_fault_code": last_fault_code,
        "total_fault_count": total_fault_count,
        "board_online": board_online,
        "status_source": status_source,
        "status_note": status_note,
        "last_fault_result": last_fault_result,
        "recover_action": {
            "action_id": "recover_safe_stop",
            "label": "SAFE_STOP 收口",
            "api_path": "/api/recover",
            "method": "POST",
            "note": "沿用现有 recover action，不新增 destructive 操作；Linux 只发起控制面 recover。",
        },
        "ownership_note": ownership_note,
    }


def cue_jump(label: str, *, target_id: str, act_id: str = "", primary: bool = False) -> dict[str, Any]:
    return {
        "label": label,
        "target_id": target_id,
        "act_id": act_id,
        "primary": primary,
    }


def cue_check(label: str, ready: bool, note: str, *, tone: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "ready": ready,
        "tone": tone or ("online" if ready else "degraded"),
        "note": note,
    }


def cue_scene(
    *,
    scene_id: str,
    number: str,
    eyebrow: str,
    title: str,
    status: str,
    tone: str,
    note: str,
    cue_line: str,
    jump: dict[str, Any],
    jump_hint: str,
    checks: list[dict[str, Any]],
    meta: list[str],
) -> dict[str, Any]:
    ready_count = sum(1 for item in checks if item.get("ready"))
    return {
        "scene_id": scene_id,
        "number": number,
        "eyebrow": eyebrow,
        "title": title,
        "status": status,
        "tone": tone,
        "note": note,
        "cue_line": cue_line,
        "jump": jump,
        "jump_hint": jump_hint,
        "checks": checks,
        "ready_count": ready_count,
        "total_checks": len(checks),
        "meta": meta + [f"{ready_count}/{len(checks)} ready"],
    }


def build_operator_cue(
    *,
    snapshot: dict[str, Any],
    board_access: dict[str, Any],
    live: dict[str, Any],
    active_inference: dict[str, Any],
    last_inference: dict[str, Any],
    safety_panel: dict[str, Any],
    gate: dict[str, Any],
    link_director: dict[str, Any],
    event_spine: dict[str, Any],
) -> dict[str, Any]:
    mission = snapshot.get("mission", {}) if isinstance(snapshot.get("mission"), dict) else {}
    guided_demo = snapshot.get("guided_demo", {}) if isinstance(snapshot.get("guided_demo"), dict) else {}
    compare_viewer = guided_demo.get("compare_viewer", {}) if isinstance(guided_demo.get("compare_viewer"), dict) else {}
    performance = snapshot.get("performance", {}) if isinstance(snapshot.get("performance"), dict) else {}

    access_ready = bool(board_access.get("connection_ready"))
    board_online = bool(live.get("board_online"))
    gate_allow = str(gate.get("verdict") or "").lower() == "allow"
    board_busy = str(live.get("guard_state") or "").upper() == "JOB_ACTIVE"
    current_running = bool(active_inference.get("running")) and str(active_inference.get("variant") or "") == "current"
    active_progress = active_inference.get("progress", {}) if isinstance(active_inference.get("progress"), dict) else {}
    current_count_label = str(active_progress.get("count_label") or "")
    current_stage = str(active_progress.get("current_stage") or "")
    last_variant = str(last_inference.get("variant") or "")
    current_result_visible = last_variant == "current"
    current_request_state = str(last_inference.get("request_state") or "")
    current_execution_mode = str(last_inference.get("execution_mode") or "")
    current_live_done = current_result_visible and current_request_state != "running" and current_execution_mode == "live"
    current_archive_only = current_result_visible and (
        str(last_inference.get("status") or "") == "fallback" or current_execution_mode == "prerecorded"
    )
    compare_ready = bool(compare_viewer.get("samples"))
    performance_ready = bool(performance.get("metrics"))
    archive_event_count = int(event_spine.get("event_count") or 0)
    archive_ready = archive_event_count > 0
    safety_recovered = str(safety_panel.get("safe_stop_state") or "").upper() == "RECOVERED"
    fault_latched = str(safety_panel.get("latch_state") or "").upper() == "LATCHED"
    recover_ready = bool((safety_panel.get("recover_action") or {}).get("api_path"))
    link_profile = str(link_director.get("selected_profile_label") or "正常链路")
    mode_boundary_note = str(mission.get("mode_split_note") or MODE_BOUNDARY_NOTE)
    operator_boundary_note = (
        "Operator-assist only: this cue layer recommends scene order, presenter copy, and page jumps. "
        "Probe, manifest preview, Current/PyTorch launch, fault injection, and SAFE_STOP remain manual operator actions."
    )

    if not access_ready:
        scene1_status = "待补全会话"
        scene1_tone = "degraded"
        scene1_note = "先补齐本场 SSH / 推理会话；页面只保存会话，不会自动推进后续动作。"
        scene1_cue = "先把第一幕立住：当前仍是 operator-assist，先补齐会话，再做探板和 gate 预检。"
        scene1_jump = cue_jump("跳到会话接入", target_id="credentialPanel")
    elif not board_online:
        scene1_status = "待探板"
        scene1_tone = "degraded"
        scene1_note = "会话已就绪，但还没有新的 live 探板；第一幕继续如实显示证据态。"
        scene1_cue = "先展示可信状态，再由操作员手动执行探板确认板端 READY。"
        scene1_jump = cue_jump("跳到第一幕探板", target_id="act1Panel", act_id="act1")
    elif not gate_allow:
        scene1_status = gate.get("verdict_label") or "待预检"
        scene1_tone = str(gate.get("tone") or "degraded")
        scene1_note = str(gate.get("message") or "当前 ticket 仍是草案或保守阻断态，不宣称已放行。")
        scene1_cue = "把 gate verdict 讲清楚：当前只展示预检结果，不伪造已放行。"
        scene1_jump = cue_jump("跳到任务票闸机", target_id="jobManifestGateShell", act_id="act1")
    else:
        scene1_status = "可信状态就绪"
        scene1_tone = "online"
        scene1_note = (
            f"会话、探板和 gate 已齐；当前 link director={link_profile}，"
            "但 live 控制面与证据读数仍保持如实显示。"
        )
        scene1_cue = "第一幕已经就绪：当前展示的是可信状态、gate verdict 和 live 控制面，不是自动化编排。"
        scene1_jump = cue_jump("跳到第一幕", target_id="jobManifestGateShell", act_id="act1")

    scene1_checks = [
        cue_check(
            "会话已录入",
            access_ready,
            "当前 demo 进程内已有可复用的板卡会话。" if access_ready else "仍需补齐 host/user/password 或推理 env。",
        ),
        cue_check(
            "只读探板可见",
            board_online,
            f"remoteproc={live.get('remoteproc_state') or 'unknown'} / guard={live.get('guard_state') or 'UNKNOWN'}"
            if board_online
            else "当前没有新的 live 探板，仍以证据态显示。",
        ),
        cue_check(
            "任务票 verdict",
            gate_allow,
            str(gate.get("verdict_label") or "待补全"),
            tone=str(gate.get("tone") or ("online" if gate_allow else "degraded")),
        ),
    ]

    current_launch_ready = access_ready and board_online and gate_allow and not board_busy and not fault_latched
    if current_running:
        scene2_status = str(active_progress.get("label") or "推进中")
        scene2_tone = str(active_progress.get("tone") or "online")
        scene2_note = (
            f"Current live 当前 {current_count_label or '进行中'}；"
            f"{current_stage or '界面正在跟随板端阶段。'}"
        )
        scene2_cue = "第二幕现在只做监看：Current 在线推进仍由操作员手动触发，页面不自动 SAFE_STOP 或重跑。"
    elif current_live_done:
        scene2_status = "Current live 已完成"
        scene2_tone = "online"
        scene2_note = str(
            last_inference.get("message")
            or "Current live 结果已经回到页面，接下来可以切第三幕做正式对照。"
        )
        scene2_cue = "第二幕已经完成：现在可以把同一轮 Current 结果带到第三幕做正式对照。"
    elif current_archive_only:
        scene2_status = "Current 仍是归档展示"
        scene2_tone = "degraded"
        scene2_note = str(
            last_inference.get("message")
            or "当前画面仍在归档 / fallback 态，不能把它说成刚刚完成的 live run。"
        )
        scene2_cue = "第二幕仍在归档态：要么保持诚实展示，要么由操作员重新手动发起 Current live。"
    elif current_launch_ready:
        scene2_status = "可手动启动"
        scene2_tone = "online"
        scene2_note = "第二幕已具备条件，但 Current 300 张图在线推进仍由操作员手动触发。"
        scene2_cue = "这里开始第二幕：由操作员手动启动 Current 300 张图，页面只负责显示进度和证据。"
    else:
        scene2_status = "等待第一幕条件"
        scene2_tone = "neutral" if not access_ready and not board_online else "degraded"
        scene2_note = "当前还不能进入 live run，先完成会话、探板、gate 和空闲态条件。"
        scene2_cue = "第二幕还没开始：先完成第一幕条件，不把等待态包装成已自动运行。"

    scene2_checks = [
        cue_check(
            "Current 允许启动",
            access_ready and board_online and gate_allow and not fault_latched,
            "会话、探板、gate 与安全镜像已经就绪。"
            if access_ready and board_online and gate_allow and not fault_latched
            else "仍需先完成会话 / 探板 / gate，且不能带着 fault latch 进入 live。",
        ),
        cue_check(
            "板端空闲",
            not board_busy,
            "guard_state=READY，可手动发起 Current live。" if not board_busy else "guard_state=JOB_ACTIVE，demo 保守阻断新的 live launch。",
            tone="online" if not board_busy else "degraded",
        ),
        cue_check(
            "Current 结果可讲",
            current_running or current_result_visible,
            current_count_label if current_running else (str(last_inference.get("source_label") or "等待本轮 Current 结果")),
            tone="online" if current_live_done or current_running else ("degraded" if current_archive_only else "neutral"),
        ),
    ]

    if current_live_done:
        scene3_status = "正式对照可讲"
        scene3_tone = "online"
        scene3_note = "同一样例已可直接讲 Current vs PyTorch reference，并把 headline performance / demo mode 边界分开。"
        scene3_cue = "第三幕要点是口径：Current 与 PyTorch 用同一样例对照，4-core headline 与 3-core demo 边界必须分开说。"
    elif compare_ready:
        scene3_status = "归档对照已备"
        scene3_tone = "degraded"
        scene3_note = "Compare viewer 与性能材料都已就位，但本轮 Current live 结果未必已经更新到本场页面。"
        scene3_cue = "第三幕可以先讲正式口径和归档 compare viewer，再明确说明本场 Current live 是否已经完成。"
    else:
        scene3_status = "等待样例上下文"
        scene3_tone = "neutral"
        scene3_note = "当前还没有可用 compare viewer 样例。"
        scene3_cue = "第三幕暂不建议展开，先保证样例和性能口径都可见。"

    scene3_checks = [
        cue_check(
            "Compare viewer 样例",
            compare_ready,
            "当前 compare viewer 已有归档样例与 provenance。" if compare_ready else "当前没有 compare viewer 样例。",
        ),
        cue_check(
            "Current 来源已标注",
            current_live_done or current_archive_only,
            str(last_inference.get("source_label") or "当前仍将沿用归档样例或等待 live 结果。"),
            tone="online" if current_live_done else ("degraded" if current_archive_only else "neutral"),
        ),
        cue_check(
            "4-core vs 3-core 边界",
            performance_ready and bool(mode_boundary_note),
            mode_boundary_note or "保持 4-core headline 与 3-core demo mode 的边界标注。",
        ),
    ]

    if fault_latched:
        scene4_status = "告警锁存"
        scene4_tone = str(safety_panel.get("panel_tone") or "offline")
        scene4_note = (
            f"last_fault_code={safety_panel.get('last_fault_code') or 'UNKNOWN'} 仍锁存在控制面镜像中；"
            "是否 SAFE_STOP 收口仍由操作员决定。"
        )
        scene4_cue = "第四幕现在应该展开：SAFE_STOP / fault latch 仍在，Linux UI 只显示镜像与 recover 入口，不宣称自动收口。"
    elif safety_recovered:
        scene4_status = "SAFE_STOP 已收口"
        scene4_tone = str(safety_panel.get("panel_tone") or "degraded")
        scene4_note = "SAFE_STOP 收口结果已经回写到面板镜像，但 Linux UI 不拥有物理 SAFE_STOP / GPIO 所有权。"
        scene4_cue = "第四幕可说明 SAFE_STOP 已收口，但这仍是 operator-driven 的恢复动作，不是假自动化。"
    elif archive_ready or recover_ready:
        scene4_status = "收口页待命"
        scene4_tone = "online" if archive_ready else "degraded"
        scene4_note = (
            f"archive session={event_spine.get('session_id') or 'pending'} / "
            f"{archive_event_count} events；当前页面可展示 blackbox timeline 与 recover 入口。"
        )
        scene4_cue = "第四幕保持待命：安全镜像、recover 入口和 blackbox timeline 已在页内，但动作仍需操作员手动触发。"
    else:
        scene4_status = "等待事件"
        scene4_tone = "neutral"
        scene4_note = "当前还没有 archive 事件写入，但安全镜像和 FIT 证据仍可展示。"
        scene4_cue = "第四幕暂以证据页为主，blackbox timeline 会在有事件写盘后补齐。"

    scene4_checks = [
        cue_check(
            "SAFE_STOP 镜像",
            bool(safety_panel.get("safe_stop_state")),
            f"safe_stop={safety_panel.get('safe_stop_state') or 'UNKNOWN'} / fault={safety_panel.get('last_fault_code') or 'UNKNOWN'}",
            tone=str(safety_panel.get("panel_tone") or "neutral"),
        ),
        cue_check(
            "Blackbox timeline",
            archive_ready,
            f"{archive_event_count} events / {event_spine.get('last_event_at') or '等待首次写盘'}"
            if archive_ready
            else "当前尚无 archive 事件，会先显示 mission fallback timeline。",
            tone="online" if archive_ready else "neutral",
        ),
        cue_check(
            "Recover 入口",
            recover_ready,
            f"{(safety_panel.get('recover_action') or {}).get('method') or 'POST'} {(safety_panel.get('recover_action') or {}).get('api_path') or '/api/recover'}"
            if recover_ready
            else "当前没有 recover action 绑定。",
            tone="online" if recover_ready else "neutral",
        ),
    ]

    scenes = [
        cue_scene(
            scene_id="scene1",
            number="01",
            eyebrow="可信状态",
            title="第一幕 / 板卡接入与 gate",
            status=scene1_status,
            tone=scene1_tone,
            note=scene1_note,
            cue_line=scene1_cue,
            jump=scene1_jump,
            jump_hint="会话 / 探板 / gate",
            checks=scene1_checks,
            meta=[
                f"link={link_profile}",
                f"admission={gate.get('admission_label') or '未设置'}",
            ],
        ),
        cue_scene(
            scene_id="scene2",
            number="02",
            eyebrow="语义回传",
            title="第二幕 / Current live",
            status=scene2_status,
            tone=scene2_tone,
            note=scene2_note,
            cue_line=scene2_cue,
            jump=cue_jump("跳到第二幕", target_id="act2Panel", act_id="act2"),
            jump_hint="Current 进度与样例画面",
            checks=scene2_checks,
            meta=[
                f"count={current_count_label or '0 / 300'}",
                f"mode={current_execution_mode or 'pending'}",
            ],
        ),
        cue_scene(
            scene_id="scene3",
            number="03",
            eyebrow="正式对照",
            title="第三幕 / Compare 与性能口径",
            status=scene3_status,
            tone=scene3_tone,
            note=scene3_note,
            cue_line=scene3_cue,
            jump=cue_jump("跳到第三幕", target_id="compareViewerShell", act_id="act3"),
            jump_hint="Compare viewer 与 performance",
            checks=scene3_checks,
            meta=[
                "同一样例 compare viewer",
                "4-core headline / 3-core demo",
            ],
        ),
        cue_scene(
            scene_id="scene4",
            number="04",
            eyebrow="故障收口",
            title="第四幕 / SAFE_STOP 与 archive",
            status=scene4_status,
            tone=scene4_tone,
            note=scene4_note,
            cue_line=scene4_cue,
            jump=cue_jump("跳到第四幕", target_id="act4Panel", act_id="act4"),
            jump_hint="fault / recover / blackbox timeline",
            checks=scene4_checks,
            meta=[
                f"SAFE_STOP={safety_panel.get('safe_stop_state') or 'UNKNOWN'}",
                f"archive={archive_event_count} events",
            ],
        ),
    ]

    if not access_ready:
        current_scene = scenes[0]
        next_action = cue_jump("跳到会话接入", target_id="credentialPanel", primary=True)
        next_step_note = "先补齐本场会话；之后再由操作员执行探板与 gate 预检。"
    elif not board_online:
        current_scene = scenes[0]
        next_action = cue_jump("跳到第一幕探板", target_id="act1Panel", act_id="act1", primary=True)
        next_step_note = "先做只读探板确认板端在线；页面不会自动刷新成真机状态。"
    elif fault_latched or safety_recovered:
        current_scene = scenes[3]
        next_action = cue_jump("跳到第四幕 SAFE_STOP", target_id="act4Panel", act_id="act4", primary=True)
        next_step_note = scene4_note
    elif not gate_allow:
        current_scene = scenes[0]
        next_action = cue_jump("跳到任务票闸机", target_id="jobManifestGateShell", act_id="act1", primary=True)
        next_step_note = str(gate.get("message") or "先看 gate verdict，再决定是否推进 live。")
    elif current_running or not current_live_done or current_archive_only:
        current_scene = scenes[1]
        next_action = cue_jump("跳到第二幕 Current", target_id="act2Panel", act_id="act2", primary=True)
        next_step_note = (
            "由操作员手动启动或继续监看 Current 300 张图在线推进；页面只做进度和证据展示。"
            if not current_live_done
            else scene2_note
        )
    elif compare_ready:
        current_scene = scenes[2]
        next_action = cue_jump("跳到第三幕 Compare", target_id="compareViewerShell", act_id="act3", primary=True)
        next_step_note = "用同一样例讲 Current / PyTorch 对照，并明确 4-core headline 与 3-core demo 边界。"
    else:
        current_scene = scenes[3]
        next_action = cue_jump("跳到第四幕 SAFE_STOP", target_id="act4Panel", act_id="act4", primary=True)
        next_step_note = scene4_note

    for item in scenes:
        item["recommended"] = item["scene_id"] == current_scene["scene_id"]

    return {
        "mode": "operator_assist_only",
        "status_label": current_scene["title"],
        "status_tone": current_scene["tone"],
        "current_scene_id": current_scene["scene_id"],
        "current_scene_label": current_scene["title"],
        "current_scene_tone": current_scene["tone"],
        "presenter_line": current_scene["cue_line"],
        "next_step_label": next_action["label"],
        "next_step_note": next_step_note,
        "next_action": next_action,
        "manual_boundary_note": operator_boundary_note,
        "boundary_note": mode_boundary_note,
        "quick_jumps": [
            cue_jump("Mission 总览", target_id="missionPanel"),
            cue_jump("会话接入", target_id="credentialPanel"),
            cue_jump("任务票闸机", target_id="jobManifestGateShell", act_id="act1"),
            cue_jump("第二幕 Current", target_id="act2Panel", act_id="act2"),
            cue_jump("第三幕 Compare", target_id="compareViewerShell", act_id="act3"),
            cue_jump("性能口径", target_id="performanceGrid"),
            cue_jump("第四幕 SAFE_STOP", target_id="act4Panel", act_id="act4"),
            cue_jump("Blackbox Timeline", target_id="archiveTimelineCard"),
        ],
        "scenes": scenes,
    }


def link_profile_catalog() -> dict[str, Any]:
    return build_link_director_catalog()


def link_profile_by_id(profile_id: str) -> dict[str, Any]:
    for profile in link_profile_catalog()["profiles"]:
        if str(profile.get("profile_id") or "") == profile_id:
            return dict(profile)
    raise KeyError(profile_id)


def default_link_director_state() -> dict[str, Any]:
    profile = link_profile_by_id("normal")
    return {
        "selected_profile_id": profile["profile_id"],
        "last_applied_at": "",
        "last_operator_action": "导演台尚未切换预案；当前默认按正常链路展示。",
        "apply_status": "idle",
        "backend_binding": "ui_scaffold_only",
    }


def _compute_benchmark(samples: dict[str, list[float]]) -> dict[str, Any]:
    """从样本列表计算 min/max/mean/median，用于 batch benchmark 汇总。"""
    import statistics

    result: dict[str, Any] = {}
    for key, values in samples.items():
        if not values:
            result[key] = None
            continue
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        result[key] = {
            "n": n,
            "min_ms": round(sorted_vals[0], 2),
            "max_ms": round(sorted_vals[-1], 2),
            "mean_ms": round(statistics.mean(sorted_vals), 2),
            "median_ms": round(statistics.median(sorted_vals), 2),
            "p95_ms": round(sorted_vals[int(n * 0.95)], 2) if n >= 20 else None,
        }
    return result


def _parse_json_stdout_payload(raw: str) -> dict[str, Any]:
    for line in reversed((raw or "").splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("runner produced no JSON payload")


def _current_tvm_batch_uses_big_little(env_values: dict[str, str]) -> bool:
    runner = str(env_values.get("OPENAMP_TVM_BATCH_RUNNER") or env_values.get("OPENAMP_DEMO_TVM_BATCH_RUNNER") or "").strip().lower()
    if runner in {"biglittle", "big_little", "big-little", "pipeline"}:
        return True
    command = str(env_values.get("INFERENCE_CURRENT_CMD") or "").strip().lower()
    return "run_big_little_pipeline.sh" in command


def _flatten_big_little_pipeline_payload(payload: dict[str, Any]) -> dict[str, Any]:
    pipeline = payload.get("pipeline") if isinstance(payload.get("pipeline"), dict) else None
    if not pipeline:
        return payload
    for key in (
        "processed_count",
        "input_count",
        "selected_input_count",
        "available_input_count",
        "load_ms",
        "vm_init_ms",
        "run_count",
        "run_samples_ms",
        "run_median_ms",
        "run_mean_ms",
        "run_min_ms",
        "run_max_ms",
        "run_variance_ms2",
        "output_shape",
        "output_dtype",
        "snr",
        "batch_size",
        "save_format",
        "seed",
        "max_inputs",
        "big_cores",
        "little_cores",
        "execution_mode",
        "backend",
    ):
        if key in pipeline and key not in payload:
            payload[key] = pipeline[key]
    if "selected_input_count" not in payload and "input_count" in pipeline:
        payload["selected_input_count"] = pipeline["input_count"]
    return payload


def _json_safe_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _metric_from_summary_stat(raw: dict[str, Any] | None) -> dict[str, Any] | None:
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


def _compute_mnn_benchmark(summary: dict[str, Any]) -> dict[str, Any]:
    sample_stats = summary.get("sample_stats") if isinstance(summary, dict) else {}
    sample_stats = sample_stats if isinstance(sample_stats, dict) else {}
    return {
        "handshake_ms": None,
        "encrypt_ms": None,
        "decrypt_ms": None,
        "inference_ms": _metric_from_summary_stat(sample_stats.get("run_ms")),
        "total_ms": _metric_from_summary_stat(sample_stats.get("total_ms")),
    }


def _metric_from_values(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    import statistics

    ordered = sorted(values)
    n = len(ordered)
    return {
        "n": n,
        "min_ms": round(ordered[0], 2),
        "max_ms": round(ordered[-1], 2),
        "mean_ms": round(statistics.mean(ordered), 2),
        "median_ms": round(statistics.median(ordered), 2),
        "p95_ms": round(ordered[int(n * 0.95)], 2) if n >= 20 else None,
    }


def _compute_tvm_benchmark(summary: dict[str, Any]) -> dict[str, Any]:
    payload = summary if isinstance(summary, dict) else {}
    for nested_key in ("inference_summary", "pipeline"):
        nested = payload.get(nested_key) if isinstance(payload, dict) else None
        if isinstance(nested, dict):
            payload = nested
    samples = payload.get("run_samples_ms") if isinstance(payload.get("run_samples_ms"), list) else []
    values: list[float] = []
    for item in samples:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue
    metric = _metric_from_values(values)
    if metric is None:
        run_summary = payload.get("run_summary") if isinstance(payload.get("run_summary"), dict) else None
        metric = _metric_from_summary_stat(run_summary)
    if metric is None:
        try:
            count = int(payload.get("run_count") or payload.get("processed_count") or 0)
            mean_ms = float(payload.get("run_mean_ms"))
            median_ms = float(payload.get("run_median_ms"))
            min_ms = float(payload.get("run_min_ms") or mean_ms)
            max_ms = float(payload.get("run_max_ms") or mean_ms)
        except (TypeError, ValueError):
            metric = None
        else:
            if count > 0:
                metric = {
                    "n": count,
                    "min_ms": round(min_ms, 2),
                    "max_ms": round(max_ms, 2),
                    "mean_ms": round(mean_ms, 2),
                    "median_ms": round(median_ms, 2),
                    "p95_ms": None,
                }
    return {
        "handshake_ms": None,
        "encrypt_ms": None,
        "decrypt_ms": None,
        "inference_ms": metric,
        "total_ms": metric,
    }


def _iq_index_from_remote_npz(remote_npz: str) -> int | None:
    name = PurePosixPath(str(remote_npz or "").strip()).name
    match = re.fullmatch(r"(\d+)\.npz", name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _iq_streaming_images_from_manifest(
    manifest: dict[str, Any] | None,
    *,
    total: int,
    inference_state: str = "pending",
    final_success: bool | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        return []
    try:
        total_count = max(1, int(total))
    except (TypeError, ValueError):
        total_count = 1

    decode_manifest = manifest.get("decode_manifest") if isinstance(manifest.get("decode_manifest"), dict) else {}
    decoded_by_index: dict[int, str] = {}
    manifest_images = decode_manifest.get("images") if isinstance(decode_manifest.get("images"), list) else []
    for item in manifest_images:
        if not isinstance(item, dict):
            continue
        try:
            image_index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not 0 <= image_index < total_count:
            continue
        remote_npz = str(item.get("remote_npz") or item.get("target_npz") or "").strip()
        if remote_npz:
            decoded_by_index[image_index] = remote_npz

    files = decode_manifest.get("files") if isinstance(decode_manifest.get("files"), list) else []
    for fallback_index, raw_path in enumerate(files):
        remote_npz = str(raw_path or "").strip()
        if not remote_npz:
            continue
        image_index = _iq_index_from_remote_npz(remote_npz)
        if image_index is None:
            image_index = fallback_index
        if 0 <= image_index < total_count:
            decoded_by_index.setdefault(image_index, remote_npz)

    if not decoded_by_index:
        return []

    normalized_inference_state = str(inference_state or "pending").strip().lower()
    images: list[dict[str, Any]] = []
    for image_index in range(total_count):
        remote_npz = decoded_by_index.get(image_index, "")
        if remote_npz:
            if final_success is True or normalized_inference_state == "completed":
                status = "done"
            elif final_success is False:
                status = "failed"
            elif normalized_inference_state == "running":
                status = "tvm_running"
            else:
                status = "decoded"
        else:
            status = "pending"
        images.append(
            {
                "index": image_index,
                "status": status,
                "remote_npz": remote_npz,
            }
        )
    return images


def _benchmark_metric_value(metric: dict[str, Any] | None) -> float | None:
    if not isinstance(metric, dict):
        return None
    for key in ("median_ms", "mean_ms", "min_ms", "max_ms"):
        try:
            value = metric.get(key)
            if value is not None:
                return round(float(value), 3)
        except (TypeError, ValueError):
            continue
    return None


class DashboardState:
    def __init__(
        self,
        probe_env: str | None,
        probe_timeout_sec: float,
        probe_cache_path: str | Path | None = DEFAULT_LIVE_PROBE_OUTPUT,
        demo_startup_env_overrides: dict[str, str] | None = None,
        event_archive_root: str | Path | None = None,
        bind_host: str = "127.0.0.1",
        bind_port: int = 8079,
    ) -> None:
        self._probe_env = probe_env or None
        self._probe_timeout_sec = probe_timeout_sec
        self._probe_cache_path = probe_cache_path
        self._event_archive_root = Path(event_archive_root).resolve() if event_archive_root is not None else None
        self._bind_host = str(bind_host or "127.0.0.1").strip() or "127.0.0.1"
        self._bind_port = int(bind_port)
        self._lock = Lock()
        self._board_access = build_demo_default_board_access(
            self._probe_env,
            startup_env_overrides=demo_startup_env_overrides,
        )
        self._last_control_status: dict[str, Any] | None = None
        self._last_control_probe_error: dict[str, Any] | None = None
        self._auto_control_probe_triggered: bool = False
        self._auto_control_probe_inflight: bool = False
        self._auto_control_probe_last_attempt_ts: float = 0.0
        self._last_inference_result: dict[str, Any] | None = None
        self._recent_inference_results: dict[str, dict[str, Any]] = {}
        self._last_fault_result: dict[str, Any] | None = None
        self._inference_jobs: dict[str, dict[str, Any]] = {}
        self._manifest_preview_count = 0
        self._link_director = default_link_director_state()
        self._aircraft_position = build_aircraft_position_snapshot()
        self._event_spine = DemoEventSpine(event_archive_root)
        self._crypto_status_cache: dict[str, Any] | None = None
        self._crypto_status_cache_ts: float = 0.0
        self._board_telemetry_cache: dict[str, Any] | None = None
        self._board_telemetry_cache_ts: float = 0.0
        self._board_telemetry_refreshing = False
        self._board_position_api_cache: dict[str, Any] | None = None
        self._board_position_api_cache_ts: float = 0.0
        self._board_position_api_refreshing = False
        self._usrp_control_status_cache: dict[str, Any] | None = None
        self._usrp_control_status_cache_ts: float = 0.0
        self._usrp_control_status_refreshing = False
        self._aircraft_position_upstream_probe_cache: dict[str, Any] | None = None
        self._aircraft_position_upstream_probe_cache_ts: float = 0.0
        self._aircraft_position_upstream_probe_refreshing = False
        self._local_aircraft_bridge_state: dict[str, Any] = {
            "status": "idle",
            "last_error": "",
            "last_success_at": "",
            "upstream_url": "",
        }
        self._local_aircraft_bridge_thread_started = False
        self._crypto_enabled: bool = (os.environ.get("MLKEM_AUTH_ENABLED", "") or "").strip().lower() in {"1", "true", "yes", "on"}
        self._last_crypto_test_result: dict[str, Any] | None = None
        self._last_soft_recover_ts: float = 0.0
        self._soft_recover_cooldown_sec: float = 45.0
        self._last_soft_recover_result: dict[str, Any] | None = None
        # ── 批量推理状态 ──
        self._batch_state: dict[str, Any] | None = None
        # ── ML-KEM 持久化会话 ──
        self._mlkem_session_mgr: MlkemSessionManager | None = None
        self._mlkem_remote_asset_signatures: dict[str, str] = {}
        self._mlkem_board_start_lock = Lock()

        cached_probe = load_probe_output(probe_cache_path) if probe_cache_path else None
        if is_successful_probe(cached_probe):
            self._last_live_probe = {**cached_probe, "_loaded_from_cache": True}
        else:
            self._last_live_probe = None

        initial_snapshot = build_snapshot(self._last_live_probe, aircraft_position=self._aircraft_position)
        self._trusted_current_sha = (
            self._resolve_current_trusted_sha(self._board_access)
            or initial_snapshot["project"]["trusted_current_sha"]
        )
        self._target_label = "cortex-a72 + neon"
        self._runtime_label = "tvm"
        self._ensure_local_aircraft_position_bridge_thread()

    def _resolve_current_trusted_sha(self, board_access: BoardAccessConfig) -> str:
        return str(expected_sha_for_variant(board_access, "current") or "").strip().lower()

    def _current_trusted_sha(self, board_access: BoardAccessConfig | None = None) -> str:
        access = board_access if board_access is not None else self._board_access
        return self._resolve_current_trusted_sha(access) or str(self._trusted_current_sha or "").strip().lower()

    def _live_board_access_for_variant(self, board_access: BoardAccessConfig, *, variant: str) -> BoardAccessConfig:
        if variant != "current" or not self._trusted_current_sha:
            return board_access
        current_expected_sha = expected_sha_for_variant(board_access, "current")
        if current_expected_sha:
            return board_access
        return board_access.with_env_overrides({"INFERENCE_CURRENT_EXPECTED_SHA256": self._trusted_current_sha})

    def _nontrusted_current_requires_signed_admission(
        self,
        *,
        variant: str,
        variant_expected_sha: str,
        variant_support: dict[str, Any],
    ) -> bool:
        if variant != "current":
            return False
        expected_sha = str(variant_expected_sha or "").strip().lower()
        trusted_sha = str(self._trusted_current_sha or "").strip().lower()
        if not expected_sha or not trusted_sha or expected_sha == trusted_sha:
            return False
        return str(variant_support.get("mode") or "").strip().lower() != "signed_manifest_v1"

    def _local_aircraft_position_bridge_config(self) -> tuple[dict[str, Any], Any] | None:
        with self._lock:
            board_access = self._board_access
        runtime = _aircraft_position_bridge_runtime(
            board_access,
            bind_host=self._bind_host,
            bind_port=self._bind_port,
        )
        if not runtime["configured"]:
            with self._lock:
                self._local_aircraft_bridge_state = {
                    **self._local_aircraft_bridge_state,
                    "status": "idle",
                    "last_error": "",
                    "upstream_url": "",
                }
            return None
        if _aircraft_position_bridge_execution_mode_for_runtime(board_access, runtime) != "local":
            with self._lock:
                self._local_aircraft_bridge_state = {
                    **self._local_aircraft_bridge_state,
                    "status": "idle",
                    "last_error": "",
                    "upstream_url": "",
                }
            return None
        try:
            config = build_config_from_env_values(
                runtime["runtime_env"],
                backend_base_url_default=runtime["backend_base_url"] or f"http://127.0.0.1:{self._bind_port}",
            )
        except ValueError as exc:
            with self._lock:
                self._local_aircraft_bridge_state = {
                    **self._local_aircraft_bridge_state,
                    "status": "error",
                    "last_error": str(exc),
                    "upstream_url": runtime["upstream_url"],
                }
            return None
        return runtime, config

    def _run_local_aircraft_position_bridge_once(self) -> bool:
        prepared = self._local_aircraft_position_bridge_config()
        if prepared is None:
            return False
        runtime, config = prepared
        with self._lock:
            self._local_aircraft_bridge_state = {
                **self._local_aircraft_bridge_state,
                "status": "running",
                "last_error": "",
                "upstream_url": runtime["upstream_url"],
            }
        try:
            normalized_payload = fetch_normalized_payload(config)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            with self._lock:
                self._local_aircraft_bridge_state = {
                    **self._local_aircraft_bridge_state,
                    "status": "error",
                    "last_error": str(exc),
                    "upstream_url": runtime["upstream_url"],
                }
            return False
        self.set_aircraft_position(normalized_payload)
        with self._lock:
            self._local_aircraft_bridge_state = {
                **self._local_aircraft_bridge_state,
                "status": "running",
                "last_error": "",
                "last_success_at": now_iso(),
                "upstream_url": runtime["upstream_url"],
            }
        return True

    def _local_aircraft_position_bridge_loop(self) -> None:
        while True:
            prepared = self._local_aircraft_position_bridge_config()
            if prepared is None:
                time.sleep(1.0)
                continue
            _runtime, config = prepared
            self._run_local_aircraft_position_bridge_once()
            time.sleep(config.interval_sec)

    def _ensure_local_aircraft_position_bridge_thread(self) -> None:
        if self._local_aircraft_position_bridge_config() is None:
            return
        with self._lock:
            if self._local_aircraft_bridge_thread_started:
                return
            self._local_aircraft_bridge_thread_started = True
        threading.Thread(
            target=self._local_aircraft_position_bridge_loop,
            daemon=True,
            name="local-aircraft-position-bridge",
        ).start()

    def _detach_mlkem_session_manager(self) -> MlkemSessionManager | None:
        with self._lock:
            mgr = self._mlkem_session_mgr
            self._mlkem_session_mgr = None
        return mgr

    def _close_mlkem_session_manager(self, mgr: MlkemSessionManager | None = None) -> bool:
        if mgr is None:
            mgr = self._detach_mlkem_session_manager()
        if mgr is None:
            return False
        try:
            mgr.close()
        except Exception:
            pass
        return True

    def reset_crypto_channel(self, *, restart_remote_server: bool = True) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
            crypto_enabled = self._crypto_enabled
            self._crypto_status_cache = None
            self._crypto_status_cache_ts = 0.0
            self._last_crypto_test_result = None
            mgr_to_close = self._mlkem_session_mgr
            self._mlkem_session_mgr = None

        session_closed = self._close_mlkem_session_manager(mgr_to_close)
        remote_restart_scheduled = False
        if (
            restart_remote_server
            and crypto_enabled
            and board_access
            and board_access.connection_ready
            and local_control_transport_mode(board_access.build_env()) == "tcp"
        ):
            threading.Thread(
                target=self._ensure_board_tcp_server,
                args=(board_access,),
                daemon=True,
                name="tcp-server-reset",
            ).start()
            remote_restart_scheduled = True

        message = "安全信道本地会话已重置，状态缓存已清空。"
        if remote_restart_scheduled:
            message += " 板端 tcp_server 将重新探测并按需拉起。"
        return {
            "status": "ok",
            "message": message,
            "session_closed": session_closed,
            "remote_restart_scheduled": remote_restart_scheduled,
        }

    def set_board_access(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            fallback = self._board_access
        config = build_board_access_config(payload, fallback=fallback)
        config_overrides: dict[str, str] = {}
        config_overrides.update(self._board_access_auth_overrides_from_payload(payload))
        config_overrides.update(self._board_access_runtime_overrides_from_payload(payload))
        if config_overrides:
            config = config.with_env_overrides(config_overrides)
        mgr_to_close: MlkemSessionManager | None = None
        with self._lock:
            self._board_access = config
            resolved_current_sha = self._resolve_current_trusted_sha(config)
            if resolved_current_sha:
                self._trusted_current_sha = resolved_current_sha
            self._crypto_status_cache = None
            self._crypto_status_cache_ts = 0.0
            if self._mlkem_session_mgr is not None:
                mgr_to_close = self._mlkem_session_mgr
                self._mlkem_session_mgr = None
            self._board_telemetry_cache = None
            self._board_telemetry_cache_ts = 0.0
            self._board_telemetry_refreshing = False
            self._board_position_api_cache = None
            self._board_position_api_cache_ts = 0.0
            self._board_position_api_refreshing = False
            self._usrp_control_status_cache = None
            self._usrp_control_status_cache_ts = 0.0
            self._usrp_control_status_refreshing = False
            self._aircraft_position_upstream_probe_cache = None
            self._aircraft_position_upstream_probe_cache_ts = 0.0
            self._aircraft_position_upstream_probe_refreshing = False
            self._last_control_probe_error = None
            self._auto_control_probe_triggered = False
            self._auto_control_probe_inflight = False
            self._auto_control_probe_last_attempt_ts = 0.0
            self._last_crypto_test_result = None
            crypto_enabled = self._crypto_enabled
        if mgr_to_close is not None:
            self._close_mlkem_session_manager(mgr_to_close)
        # 控制/认证面固定走 TCP/Tailscale；即使数据面切到 USRP，也需要维持 tcp_server。
        if config.connection_ready and local_control_transport_mode(config.build_env()) == "tcp":
            threading.Thread(
                target=self._ensure_board_tcp_server,
                args=(config,),
                daemon=True,
                name="tcp-server-autostart",
            ).start()
            runtime = _aircraft_position_bridge_runtime(
                config,
                bind_host=self._bind_host,
                bind_port=self._bind_port,
            )
            if _aircraft_position_bridge_execution_mode_for_runtime(config, runtime) == "board":
                threading.Thread(
                    target=self._autostart_board_aircraft_position_bridge,
                    args=(config,),
                    daemon=True,
                    name="aircraft-position-bridge-autostart",
                ).start()
        self._ensure_local_aircraft_position_bridge_thread()
        return config.to_public_dict()

    def get_usrp_control_status(self) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
        if not board_access.connection_ready:
            return {
                "status": "waiting_session",
                "message": "板卡会话未补齐，暂无法探测 USRP persistent TX/RX。",
            }
        payload = inspect_usrp_control_servers(board_access)
        with self._lock:
            self._usrp_control_status_cache = json.loads(json.dumps(payload, ensure_ascii=False))
            self._usrp_control_status_cache_ts = time.monotonic()
        return payload

    def _usrp_control_status_snapshot(
        self,
        board_access: BoardAccessConfig,
        *,
        defer_refresh: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            cached = (
                json.loads(json.dumps(self._usrp_control_status_cache, ensure_ascii=False))
                if self._usrp_control_status_cache is not None
                else None
            )
            cached_ts = self._usrp_control_status_cache_ts
            refreshing = self._usrp_control_status_refreshing

        age_sec = time.monotonic() - cached_ts if cached_ts > 0 else None
        if defer_refresh and cached is not None:
            cached["stale"] = True
            cached["message"] = "TVM live 推理进行中，暂缓 USRP control 状态刷新，继续展示最近一次缓存值。"
            return cached
        if cached is not None and age_sec is not None and age_sec <= USRP_CONTROL_STATUS_TTL_SEC:
            return cached
        if not board_access.connection_ready:
            if cached is not None:
                cached["stale"] = True
                cached["message"] = "当前板卡会话不完整，继续展示上一次 USRP control 缓存值。"
                return cached
            return {
                "status": "waiting_session",
                "stale": True,
                "message": "板卡会话未补齐，暂无法探测 USRP persistent TX/RX。",
            }
        if defer_refresh:
            return _usrp_control_status_placeholder(
                board_access,
                status="deferred",
                message="TVM live 推理进行中，暂缓 USRP control 状态刷新。",
            )

        self._start_usrp_control_status_refresh(board_access)
        if cached is not None:
            cached["stale"] = True
            cached["message"] = (
                "USRP control 状态后台刷新中，继续展示最近一次缓存值。"
                if not refreshing
                else "USRP control 状态仍在后台刷新，继续展示最近一次缓存值。"
            )
            return cached
        return _usrp_control_status_placeholder(
            board_access,
            status="refreshing",
            message="USRP control 状态后台刷新中，等待 RX/TX persistent server 首次探测结果。",
        )

    def _start_usrp_control_status_refresh(self, board_access: BoardAccessConfig) -> None:
        with self._lock:
            if self._usrp_control_status_refreshing:
                return
            self._usrp_control_status_refreshing = True

        def worker() -> None:
            try:
                payload = inspect_usrp_control_servers(board_access)
            except Exception as exc:
                payload = _usrp_control_status_placeholder(
                    board_access,
                    status="error",
                    message=f"USRP control 状态刷新失败: {exc}",
                )
            with self._lock:
                self._usrp_control_status_cache = json.loads(json.dumps(payload, ensure_ascii=False))
                self._usrp_control_status_cache_ts = time.monotonic()
                self._usrp_control_status_refreshing = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="usrp-control-status-refresh",
        ).start()

    def start_usrp_control(self) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
        if not board_access.connection_ready:
            return {
                "status": "config_error",
                "message": "板卡会话未补齐，无法启动 USRP persistent TX/RX。",
            }
        return ensure_usrp_control_servers_started(board_access, auto_start=True)

    def stop_usrp_control(self) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
        if not board_access.connection_ready:
            return {
                "status": "config_error",
                "message": "板卡会话未补齐，无法关闭 USRP persistent TX/RX。",
            }
        return shutdown_usrp_control_servers_now(board_access)

    def _merged_aircraft_position_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = json.loads(json.dumps(self._aircraft_position, ensure_ascii=False))
        merged = dict(current)

        for key in (
            "aircraft_id",
            "mission_call_sign",
            "source_kind",
            "source_status",
            "source_label",
            "source_note",
        ):
            value = payload.get(key)
            if value not in (None, ""):
                merged[key] = value

        position = dict(current.get("position") or {})
        if isinstance(payload.get("position"), dict):
            position.update(payload["position"])
        for key in ("latitude", "longitude"):
            value = payload.get(key)
            if value not in (None, ""):
                position[key] = value

        kinematics = dict(current.get("kinematics") or {})
        if isinstance(payload.get("kinematics"), dict):
            kinematics.update(payload["kinematics"])
        for key in ("altitude_m", "ground_speed_kph", "heading_deg", "vertical_speed_mps"):
            value = payload.get(key)
            if value not in (None, ""):
                kinematics[key] = value

        fix = dict(current.get("fix") or {})
        if isinstance(payload.get("fix"), dict):
            fix.update(payload["fix"])
        flat_fix = {
            "type": payload.get("fix_type"),
            "confidence_m": payload.get("confidence_m"),
            "satellites": payload.get("satellites"),
        }
        for key, value in flat_fix.items():
            if value not in (None, ""):
                fix[key] = value

        sample = dict(current.get("sample") or {})
        if isinstance(payload.get("sample"), dict):
            sample.update(payload["sample"])
        for key in ("captured_at", "sequence", "producer_id", "transport"):
            value = payload.get(key)
            if value not in (None, ""):
                sample[key] = value

        merged["position"] = position
        merged["kinematics"] = kinematics
        merged["fix"] = fix
        merged["updated_at"] = now_iso()

        position_changed = any(payload.get(key) not in (None, "") for key in ("latitude", "longitude")) or isinstance(
            payload.get("position"),
            dict,
        )
        if position_changed:
            merged.setdefault("source_kind", "upper_computer_gps")
            if not payload.get("source_kind"):
                merged["source_kind"] = "upper_computer_gps"
            if not payload.get("source_status"):
                merged["source_status"] = "live"
            if not payload.get("source_label"):
                merged["source_label"] = "上位机位置"
            if not payload.get("source_note"):
                merged["source_note"] = "当前定位展示来自上位机本机位置数据。"
            explicit_captured_at = payload.get("captured_at") not in (None, "") or (
                isinstance(payload.get("sample"), dict) and payload["sample"].get("captured_at") not in (None, "")
            )
            if not explicit_captured_at:
                sample["captured_at"] = merged["updated_at"]
            explicit_sequence = payload.get("sequence") not in (None, "") or (
                isinstance(payload.get("sample"), dict) and payload["sample"].get("sequence") not in (None, "")
            )
            if not explicit_sequence:
                sample["sequence"] = self._safe_int(current.get("sample", {}).get("sequence"), default=0) + 1
        merged["sample"] = sample
        return merged

    def current_aircraft_position(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._aircraft_position, ensure_ascii=False))

    def set_aircraft_position(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = self._merged_aircraft_position_payload(payload)
        aircraft_position = build_aircraft_position_snapshot(merged)
        with self._lock:
            self._aircraft_position = aircraft_position

        self._archive_event_snapshot(
            reason="aircraft_position_update",
            extra={
                "source_kind": aircraft_position["source_kind"],
                "source_status": aircraft_position["source_status"],
                "latitude": aircraft_position["position"]["latitude"],
                "longitude": aircraft_position["position"]["longitude"],
            },
        )
        return aircraft_position

    def set_link_director_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(payload.get("profile_id") or "").strip().lower()
        if not profile_id:
            raise ValueError("missing profile_id")
        try:
            profile = link_profile_by_id(profile_id)
        except KeyError as exc:
            raise ValueError("unsupported profile_id") from exc

        change_applied = False
        previous_profile_id = "normal"
        previous_profile_label = link_profile_by_id("normal")["label"]
        with self._lock:
            previous_profile_id = str(self._link_director.get("selected_profile_id") or "normal")
            try:
                previous_profile_label = link_profile_by_id(previous_profile_id)["label"]
            except KeyError:
                previous_profile_id = "normal"
                previous_profile_label = link_profile_by_id("normal")["label"]
            if previous_profile_id != profile["profile_id"]:
                action = (
                    f"导演台已切到 {profile['label']} 预案；当前仅更新操作员态势与后续绑定目标，"
                    "未执行 tc/netem 或物理弱网控制。"
                )
                self._link_director = {
                    "selected_profile_id": profile["profile_id"],
                    "last_applied_at": now_iso(),
                    "last_operator_action": action,
                    "apply_status": "staged",
                    "backend_binding": "ui_scaffold_only",
                }
                change_applied = True

        if not change_applied:
            status = self.current_link_director_status()
            status["change_applied"] = False
            status["status_message"] = (
                f"导演台已保持 {profile['label']} 预案；当前仍是 UI/control-plane scaffold，"
                "不会执行 tc/netem 或改写 live telemetry。"
            )
            status["previous_profile_id"] = previous_profile_id
            status["previous_profile_label"] = previous_profile_label
            return status

        status = self.current_link_director_status()
        status["change_applied"] = True
        status["status_message"] = str(status.get("last_operator_action") or "")
        status["previous_profile_id"] = previous_profile_id
        status["previous_profile_label"] = previous_profile_label
        self._event_spine.publish(
            "LINK_PROFILE_CHANGED",
            source="link_director",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=str(status.get("last_operator_action") or f"Link director switched to {profile['label']}."),
            data={
                "profile_id": profile["profile_id"],
                "profile_label": profile["label"],
                "previous_profile_id": previous_profile_id,
                "previous_profile_label": previous_profile_label,
                "backend_binding": str(status.get("backend_binding") or "ui_scaffold_only"),
            },
        )
        self._archive_event_snapshot(
            reason="link_profile_changed",
            extra={
                "profile_id": profile["profile_id"],
                "profile_label": profile["label"],
                "previous_profile_id": previous_profile_id,
                "previous_profile_label": previous_profile_label,
                "backend_binding": str(status.get("backend_binding") or "ui_scaffold_only"),
            },
        )
        return status

    def current_snapshot(self) -> dict[str, Any]:
        with self._lock:
            live_probe = self._last_live_probe
            aircraft_position = self._aircraft_position
        return build_snapshot(live_probe=live_probe, aircraft_position=aircraft_position)

    def _get_mlkem_session_manager(
        self, board_access: "BoardAccessConfig", env_values: dict,
    ) -> MlkemSessionManager | None:
        """获取或创建持久化 ML-KEM 会话管理器

        如果 host / port / suite / client script / transport 发生变化会关闭旧管理器。
        找不到 tcp_client.py 时返回 None（回退到子进程模式）。
        """
        if local_control_transport_mode(env_values) != "tcp":
            self._close_mlkem_session_manager()
            return None

        tcp_client, _ = resolve_local_crypto_client(env_values)
        if tcp_client is None:
            self._close_mlkem_session_manager()
            return None
        if not inspect_local_crypto_client_capabilities(tcp_client).get("supports_daemon"):
            self._close_mlkem_session_manager()
            return None

        mgr_to_close: MlkemSessionManager | None = None
        with self._lock:
            existing = self._mlkem_session_mgr
            if existing is not None:
                match_fn = getattr(existing, "matches_config", None)
                if callable(match_fn):
                    try:
                        if bool(match_fn(env_values, host=board_access.host, client_script=tcp_client)):
                            return existing
                    except Exception:
                        pass
                elif getattr(existing, "_host", None) == board_access.host:
                    return existing
                self._mlkem_session_mgr = None
                mgr_to_close = existing

        self._close_mlkem_session_manager(mgr_to_close)

        mgr = MlkemSessionManager(
            env_values, host=board_access.host, client_script=tcp_client)
        with self._lock:
            self._mlkem_session_mgr = mgr
        return mgr

    def _create_mlkem_input_file(self, client_script: Path) -> Path:
        """Create a temporary ML-KEM input file compatible with the discovered client."""
        import tempfile

        capabilities = inspect_local_crypto_client_capabilities(client_script)
        payload_size = (
            MLKEM_LEGACY_INPUT_BYTES
            if capabilities.get("legacy_single_input_only")
            else MLKEM_MODERN_INPUT_BYTES
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        try:
            tmp.write(b"\0" * payload_size)
        finally:
            tmp.close()
        return Path(tmp.name)

    def _idle_active_inference_summary(self) -> dict[str, Any]:
        return {
            "running": False,
            "job_id": "",
            "variant": "",
            "source": "demo_process",
            "queue_depth": 0,
            "request_state": "idle",
            "status_category": "idle",
            "message": "当前 demo 进程内没有活动中的 live 作业。",
            "progress": {
                "state": "idle",
                "label": "队列空闲",
                "tone": "neutral",
                "percent": 0,
                "phase_percent": 0,
                "completed_count": 0,
                "expected_count": DEFAULT_MAX_INPUTS,
                "remaining_count": DEFAULT_MAX_INPUTS,
                "completion_ratio": 0.0,
                "count_source": "demo_default",
                "count_label": "0 active / 0 queued",
                "current_stage": "等待操作员发起任务",
                "stages": [],
                "event_log": [],
            },
        }

    def _active_inference_summary(self) -> dict[str, Any]:
        record = self._running_inference_job_record()
        if record is not None:
            snapshot = record["snapshot"]
            progress = snapshot.get("progress") if isinstance(snapshot.get("progress"), dict) else {}
            return {
                "running": True,
                "job_id": record["job_id"],
                "variant": record["variant"],
                "source": "demo_process",
                "queue_depth": 1,
                "request_state": snapshot.get("request_state", "running"),
                "status_category": snapshot.get("status_category", "running"),
                "message": str(snapshot.get("message") or "当前 live 作业正在推进。"),
                "progress": progress,
            }

        with self._lock:
            control_status = dict(self._last_control_status or {})

        guard_state = str(control_status.get("guard_state") or "").upper()
        if guard_state != "JOB_ACTIVE":
            return self._idle_active_inference_summary()

        active_job_id = int(control_status.get("active_job_id") or 0)
        event_log = list(control_status.get("logs") or [])
        return {
            "running": True,
            "job_id": "",
            "variant": "unknown",
            "source": "board_status",
            "queue_depth": 1,
            "request_state": "running",
            "status_category": "board_busy",
            "message": "板端当前报告 guard_state=JOB_ACTIVE；demo 仅展示现有作业状态，不自动 SAFE_STOP。",
            "progress": {
                "state": "running",
                "label": "板端已有活动作业",
                "tone": "degraded",
                "percent": 0,
                "phase_percent": 0,
                "completed_count": 0,
                "expected_count": DEFAULT_MAX_INPUTS,
                "remaining_count": DEFAULT_MAX_INPUTS,
                "completion_ratio": 0.0,
                "count_source": "board_status",
                "count_label": f"active_job_id={active_job_id}" if active_job_id else "JOB_ACTIVE",
                "current_stage": "等待当前作业完成或人工 SAFE_STOP",
                "stages": [
                    {
                        "key": "job_active",
                        "label": "板端作业占用",
                        "status": "current",
                        "detail": "当前 board status 报告 guard_state=JOB_ACTIVE。",
                    }
                ],
                "event_log": event_log,
            },
        }

    def current_link_director_status(self) -> dict[str, Any]:
        catalog = link_profile_catalog()
        with self._lock:
            stored = dict(self._link_director)
        selected_id = str(stored.get("selected_profile_id") or "normal")
        try:
            selected = link_profile_by_id(selected_id)
        except KeyError:
            selected = link_profile_by_id("normal")
            selected_id = "normal"
        status = str(stored.get("apply_status") or "idle")
        tone = selected.get("tone", "neutral") if status != "idle" else "neutral"
        label = "导演台待命" if status == "idle" else f"{selected['label']} 预案已设定"
        profiles = [{**profile, "active": profile["profile_id"] == selected_id} for profile in catalog["profiles"]]
        return {
            "status": status,
            "label": label,
            "tone": tone,
            "backend_binding": str(stored.get("backend_binding") or catalog.get("backend_status") or "ui_scaffold_only"),
            "backend_status": catalog["backend_status"],
            "summary": catalog["summary"],
            "plane_split_note": catalog["plane_split_note"],
            "mode_boundary_note": MODE_BOUNDARY_NOTE,
            "truth_note": "当前仅记录导演台预案；live 控制面与证据读数继续如实显示。",
            "selected_profile_id": selected_id,
            "selected_profile_label": selected["label"],
            "selected_profile": selected,
            "profiles": profiles,
            "last_applied_at": str(stored.get("last_applied_at") or ""),
            "last_operator_action": str(stored.get("last_operator_action") or catalog["summary"]),
        }

    def _current_link_health_profile_id(self) -> str:
        with self._lock:
            profile_id = str(self._link_director.get("selected_profile_id") or "normal").strip().lower()
        try:
            link_profile_by_id(profile_id)
        except KeyError:
            return "normal"
        return profile_id

    def _signed_manifest_gate_details(self, access: BoardAccessConfig, *, variant: str) -> dict[str, Any]:
        try:
            return load_signed_manifest_summary(access.build_env(), variant=variant, require_public_key=False)
        except ValueError:
            return {}

    def _next_manifest_preview_job_id(self, *, variant: str) -> str:
        with self._lock:
            self._manifest_preview_count += 1
            sequence = self._manifest_preview_count
        return f"manifest-preview-{variant}-{sequence:04d}"

    def _job_manifest_gate_status(
        self,
        *,
        board_access: BoardAccessConfig,
        admission: dict[str, Any],
        support: dict[str, Any],
        active_inference: dict[str, Any],
        control_status: dict[str, Any] | None,
        trusted_sha: str,
        variant: str,
        status_probe: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        contract = build_job_manifest_contract_snapshot()
        defaults = contract["defaults"]
        variant_access = self._live_board_access_for_variant(board_access, variant=variant)
        signed_summary = (
            self._signed_manifest_gate_details(variant_access, variant=variant)
            if admission.get("mode") == "signed_manifest_v1"
            else {}
        )
        variant_label = "PyTorch" if variant == "baseline" else "Current"
        active_variant = str(active_inference.get("variant") or "")
        active_job_running = bool(active_inference.get("running"))
        active_job_id = str(active_inference.get("job_id") or "")
        expected_sha = str(admission.get("artifact_sha256") or expected_sha_for_variant(variant_access, variant) or "")
        if variant == "current" and not expected_sha:
            expected_sha = trusted_sha

        expected_outputs = int(signed_summary.get("expected_outputs") or defaults["expected_outputs"])
        deadline_ms = int(signed_summary.get("deadline_ms") or defaults["deadline_ms"])
        job_flags = str(signed_summary.get("job_flags") or defaults["job_flags"])

        job_id = ""
        job_id_source = "launch_generated"
        guard_state = str((control_status or {}).get("guard_state") or "").upper()
        board_active_job_id = int((control_status or {}).get("active_job_id") or 0)
        if active_job_running and active_job_id:
            job_id = active_job_id
            job_id_source = "active_job"
        elif guard_state == "JOB_ACTIVE" and board_active_job_id > 0:
            job_id = str(board_active_job_id)
            job_id_source = "board_status"
        elif self._last_inference_result and self._last_inference_result.get("variant") == variant:
            last_job_id = str(self._last_inference_result.get("job_id") or "")
            if last_job_id:
                job_id = last_job_id
                job_id_source = "last_launch"

        preview_probe_failed = bool(status_probe) and str(status_probe.get("status") or "") != "success"
        ready_for_launch = bool(support.get("launch_allowed")) and admission.get("status") == "ready" and board_access.connection_ready
        verdict = "hold"
        verdict_label = "待补全"
        if active_job_running or guard_state == "JOB_ACTIVE":
            verdict = "deny"
            verdict_label = "暂不放行"
        elif preview_probe_failed:
            verdict = "hold"
            verdict_label = "待复核"
        elif ready_for_launch:
            verdict = "allow"
            verdict_label = "可放行"

        reasons: list[str] = []

        def append_reason(text: str) -> None:
            value = str(text or "").strip()
            if value and value not in reasons:
                reasons.append(value)

        if active_job_running and active_job_id:
            if active_variant == variant:
                append_reason(
                    f"{variant_label} live job {active_job_id} is already running in the demo process; a new ticket stays blocked."
                )
            else:
                append_reason(
                    f"Demo process already has active {active_variant or 'other'} live job {active_job_id}; "
                    "the gate conservatively blocks another ticket."
                )
        if guard_state == "JOB_ACTIVE":
            active_suffix = f" active_job_id={board_active_job_id}." if board_active_job_id else ""
            append_reason(f"STATUS_RESP reports guard_state=JOB_ACTIVE; the demo will not auto SAFE_STOP.{active_suffix}")
        if preview_probe_failed:
            probe_message = str(status_probe.get("message") or "").strip()
            if probe_message:
                append_reason(f"Preview STATUS_REQ did not return a usable STATUS_RESP: {probe_message}")
            else:
                append_reason("Preview STATUS_REQ did not return a usable STATUS_RESP; the gate remains conservative.")
        if not board_access.connection_ready:
            missing = ", ".join(board_access.missing_connection_fields()) or "host, user, password"
            append_reason(f"Board session is incomplete: missing {missing}.")
        support_note = str(support.get("note") or "")
        if not support.get("launch_allowed"):
            append_reason(support_note or f"{variant_label} live path is not launchable yet.")
        admission_note = str(admission.get("note") or "")
        if admission_note:
            append_reason(admission_note)
        if ready_for_launch and not status_probe:
            append_reason("This view reflects cached control/demo state; use the preview action to re-check admitability only.")

        if active_job_running and active_variant == variant:
            status = "running"
            label = "任务票已在推进"
            tone = "online"
            message = (
                f"{variant_label} 任务票已进入 live launch；若再提交新票，demo 会保守阻断，"
                "避免把预检和真实 live 路径混写。"
            )
        elif active_job_running:
            status = "blocked"
            label = "票据阻断"
            tone = "degraded"
            message = (
                f"当前 demo 进程已有 {active_variant or 'other'} live 作业占用；"
                f"{variant_label} 新票只做 gate 预检，不会越过现有控制面边界。"
            )
        elif guard_state == "JOB_ACTIVE":
            status = "blocked"
            label = "票据阻断"
            tone = "degraded"
            message = "板端当前 guard_state=JOB_ACTIVE；manifest gate 保守阻断新票，不自动 SAFE_STOP。"
        elif preview_probe_failed:
            status = "draft"
            label = "待复核"
            tone = "degraded"
            message = (
                f"{variant_label} 票据预检未拿到可用 STATUS_RESP；当前不会宣称可放行，"
                "也不会启动 board execution。"
            )
        elif support.get("launch_allowed") and admission.get("status") == "ready" and board_access.connection_ready:
            status = "ready"
            label = "可签发"
            tone = "online"
            message = (
                f"{variant_label} 票面参数已齐；launch 时继续沿用现有 "
                f"{admission.get('label') or 'admission'}，不改 JOB_REQ / signed-manifest 协议。"
            )
        else:
            status = "draft"
            label = "待补全"
            tone = "degraded"
            message = "当前仅展示任务票草案；会话、expected_sha 或 signed-manifest 条件未全部就绪，不宣称可放行。"

        field_map = {
            "job_id": job_id,
            "expected_sha256": expected_sha,
            "expected_outputs": expected_outputs,
            "deadline_ms": deadline_ms,
            "job_flags": job_flags,
            "input_shape": str(defaults["input_shape"]),
            "input_dtype": str(defaults["input_dtype"]),
            "output_shape": str(defaults["output_shape"]),
            "output_dtype": str(defaults["output_dtype"]),
            "shape_buckets": str(defaults["shape_buckets"]),
            "manifest_sha256": str(admission.get("manifest_sha256") or ""),
            "key_id": str(admission.get("key_id") or ""),
        }
        wire_fields = [
            {
                "key": "job_id",
                "label": "job_id",
                "value": job_id or "launch 时由 wrapper 分配 uint32",
                "source": job_id_source,
            },
            {
                "key": "expected_sha256",
                "label": "expected_sha256",
                "value": expected_sha or "未就绪",
                "source": "admission",
            },
            {
                "key": "expected_outputs",
                "label": "expected_outputs",
                "value": str(expected_outputs),
                "source": "signed_manifest" if signed_summary else "wrapper_default",
            },
            {
                "key": "deadline_ms",
                "label": "deadline_ms",
                "value": str(deadline_ms),
                "source": "signed_manifest" if signed_summary else "wrapper_default",
            },
            {
                "key": "job_flags",
                "label": "job_flags",
                "value": job_flags,
                "source": "signed_manifest" if signed_summary else "wrapper_default",
            },
            {
                "key": "manifest_sha256",
                "label": "manifest_sha256",
                "value": str(admission.get("manifest_sha256") or "legacy / none"),
                "source": "signed_manifest" if signed_summary else "legacy",
            },
            {
                "key": "key_id",
                "label": "key_id",
                "value": str(admission.get("key_id") or "legacy / none"),
                "source": "signed_manifest" if signed_summary else "legacy",
            },
        ]
        context_fields = [
            {
                "key": "input_shape",
                "label": "input_shape",
                "value": str(defaults["input_shape"]),
                "source": "archive_report",
            },
            {
                "key": "shape_buckets",
                "label": "shape_buckets",
                "value": str(defaults["shape_buckets"]),
                "source": "archive_report",
            },
            {
                "key": "output_shape",
                "label": "output_shape",
                "value": str(defaults["output_shape"]),
                "source": "archive_report",
            },
            {
                "key": "input_dtype",
                "label": "input_dtype",
                "value": str(defaults["input_dtype"]),
                "source": "archive_report",
            },
            {
                "key": "output_dtype",
                "label": "output_dtype",
                "value": str(defaults["output_dtype"]),
                "source": "archive_report",
            },
        ]
        return {
            "status": status,
            "label": label,
            "tone": tone,
            "verdict": verdict,
            "verdict_label": verdict_label,
            "variant": variant,
            "variant_label": variant_label,
            "admission_mode": str(admission.get("mode") or "legacy_sha"),
            "admission_label": str(admission.get("label") or ""),
            "admission_note": str(admission.get("note") or ""),
            "summary": contract["summary"],
            "protocol_boundary_note": contract["protocol_boundary_note"],
            "demo_only_note": (
                "Preview action is demo/operator-side only: it re-checks admitability and emits preview-only JOB_* events, "
                "but it does not send JOB_REQ or mutate board execution."
            ),
            "message": message,
            "reasons": reasons,
            "status_source": (
                "preview_status"
                if status_probe and str(status_probe.get("status") or "") == "success"
                else "preview_status_error"
                if preview_probe_failed
                else "cached_control_status"
                if control_status
                else "demo_snapshot"
            ),
            "field_map": field_map,
            "wire_fields": wire_fields,
            "context_fields": context_fields,
            "evidence": contract["evidence"],
        }

    def current_job_manifest_gate_status(
        self,
        *,
        variant: str = "current",
        status_probe: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
            control_status = dict(self._last_control_status or {}) if self._last_control_status else None
        active_inference = self._active_inference_summary()
        variant_access = self._live_board_access_for_variant(board_access, variant=variant)
        admission = describe_demo_admission(variant_access, variant=variant)
        support = describe_demo_variant_support(variant_access, variant=variant)
        effective_control_status = control_status
        if status_probe and str(status_probe.get("status") or "") == "success":
            effective_control_status = status_probe
        return self._job_manifest_gate_status(
            board_access=board_access,
            admission=admission,
            support=support,
            active_inference=active_inference,
            control_status=effective_control_status,
            trusted_sha=self._current_trusted_sha(variant_access),
            variant=variant,
            status_probe=status_probe,
        )

    def preview_job_manifest_gate(self, *, variant: str = "current") -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access

        variant_access = self._live_board_access_for_variant(board_access, variant=variant)
        status_probe: dict[str, Any] | None = None
        trusted_sha = expected_sha_for_variant(variant_access, variant) or self._trusted_current_sha
        if board_access.probe_ready:
            status_probe = query_live_status(board_access, trusted_sha=trusted_sha)
            if status_probe.get("status") == "success":
                with self._lock:
                    self._last_control_status = status_probe

        gate = self.current_job_manifest_gate_status(variant=variant, status_probe=status_probe)
        preview_job_id = self._next_manifest_preview_job_id(variant=variant)
        common_data = {
            "variant": variant,
            "preview_only": True,
            "preview_action": "job_manifest_gate_preview",
            "verdict": gate["verdict"],
            "status_category": gate["status"],
            "admission_mode": gate["admission_mode"],
            "status_source": gate["status_source"],
        }
        self._event_spine.publish(
            "JOB_SUBMITTED",
            job_id=preview_job_id,
            source="manifest_gate_preview",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"{gate['variant_label']} manifest gate preview requested by the operator.",
            data=common_data,
        )
        preview_event_type = "JOB_ADMITTED" if gate["verdict"] == "allow" else "JOB_REJECTED"
        preview_message = (
            f"{gate['variant_label']} 任务票 demo-only 预检判定为可放行；未发送 JOB_REQ，也未启动板端执行。"
            if gate["verdict"] == "allow"
            else f"{gate['variant_label']} 任务票 demo-only 预检未放行；未发送 JOB_REQ，也未启动板端执行。"
        )
        self._event_spine.publish(
            preview_event_type,
            job_id=preview_job_id,
            source="manifest_gate_preview",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=preview_message,
            data={
                **common_data,
                "reasons": list(gate["reasons"]),
            },
        )
        self._archive_event_snapshot(
            reason="job_manifest_gate_preview",
            job_id=preview_job_id,
            extra={
                "variant": variant,
                "preview_only": True,
                "verdict": gate["verdict"],
            },
        )
        return {
            "status": "ok",
            "action": "preview",
            "preview_only": True,
            "job_id": preview_job_id,
            "event_type": preview_event_type,
            "message": preview_message,
            "checked_at": now_iso(),
            "gate": gate,
        }

    def get_crypto_status(self) -> dict[str, Any]:
        """从板卡 tcp_server 的 HTTP /status 端点获取 ML-KEM 通道状态。

        逻辑:
        1. toggle OFF → disabled
        2. 板卡未配置密码 → 提示先输入密码
        3. 请求板卡 :8080/status → 成功则缓存并返回
        4. 请求失败 → 保留上次正常值，只更新 error 字段
        """
        result = self._get_crypto_status_core()
        result["service_mode"] = self._service_mode_snapshot()
        return result

    def _service_mode_snapshot(self) -> dict[str, Any]:
        """Compute service mode from the link director profile to drive the UI.
        Since local firmware 0x60-0x62 protocol has been integrated, we map
        the current link profile directly to the active service mode.
        """
        with self._lock:
            profile_id = self._link_director.get("selected_profile_id", "normal")

        if profile_id == "lossy":
            current_mode = "ROI_ONLY"
            allowed_mode = "ROI_ONLY"
            payload = "Frame skip (3:1)"
        elif profile_id == "flaky":
            current_mode = "ALERT_ONLY"
            allowed_mode = "ALERT_ONLY"
            payload = "Alerts / Coordinates Only"
        else:
            current_mode = "FULL_FRAME"
            allowed_mode = "FULL_FRAME"
            payload = "Full Frame tensor"

        return {
            "available": True,
            "source": "live_linked",
            "current_mode": current_mode,
            "allowed_mode": allowed_mode,
            "payload_strategy": payload,
            "mode_transitions": 1,
            "last_transition": "Link Director Event",
            "note": "上位机守护进程已通过 0x60/0x62 服务协议接管动态调度。",
        }

    @staticmethod
    def _auth_enabled_for_env(env_values: dict[str, str]) -> bool:
        raw_value = first_config_value(env_values, keys=MLKEM_AUTH_ENABLED_KEYS, default="")
        return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _coerce_payload_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _board_access_auth_overrides_from_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        overrides: dict[str, str] = {}
        auth_enabled_present = "auth_enabled" in payload
        auth_enabled = self._coerce_payload_bool(payload.get("auth_enabled")) if auth_enabled_present else False

        raw_policy = str(payload.get("auth_sig_policy") or "").strip().upper()
        if raw_policy:
            if raw_policy not in SUPPORTED_MLKEM_AUTH_SIG_POLICIES:
                supported = ", ".join(SUPPORTED_MLKEM_AUTH_SIG_POLICIES)
                raise ValueError(f"unsupported auth_sig_policy: {raw_policy}; expected one of {supported}")
            overrides["MLKEM_AUTH_SIG_POLICY"] = raw_policy

        raw_server_id = str(payload.get("auth_server_id") or "").strip()
        if raw_server_id:
            overrides["MLKEM_AUTH_SERVER_ID"] = raw_server_id

        if auth_enabled_present:
            overrides["MLKEM_AUTH_ENABLED"] = "1" if auth_enabled else "0"
            if auth_enabled:
                overrides.setdefault("MLKEM_AUTH_SIG_POLICY", DEFAULT_MLKEM_AUTH_SIG_POLICY)
                overrides.setdefault("MLKEM_AUTH_SERVER_ID", DEFAULT_MLKEM_AUTH_SERVER_ID)

        return overrides

    def _board_access_runtime_overrides_from_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        overrides: dict[str, str] = {}
        raw_transport_mode = payload.get("transport_mode")
        if raw_transport_mode in (None, ""):
            return overrides

        try:
            transport_mode = normalize_transport_mode(str(raw_transport_mode), default="")
        except ValueError as exc:
            raise ValueError("unsupported transport_mode; expected tcp or usrp") from exc

        overrides["MLKEM_TRANSPORT_MODE"] = transport_mode
        raw_jscc_link_mode = str(payload.get("jscc_link_mode") or "").strip()
        if raw_jscc_link_mode:
            try:
                overrides["JSCC_LINK_MODE"] = normalize_jscc_link_mode(raw_jscc_link_mode)
            except ValueError as exc:
                raise ValueError("unsupported jscc_link_mode; expected qpsk or iq-direct") from exc
        if transport_mode == "usrp":
            overrides.setdefault("JSCC_LINK_MODE", "iq-direct")
            overrides.setdefault("MLKEM_USRP_MODE", "ota")
            overrides.setdefault("OPENAMP_DEMO_INPUT_SOURCE_MODE", "usrp")
            for runner_key in (
                "OPENAMP_SSH_RUNNER",
                "OPENAMP_SSH_DOCKER_IMAGE",
                "OPENAMP_USRP_TX_RUNNER",
                "OPENAMP_USRP_TX_DOCKER_IMAGE",
                "OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET",
                "OPENAMP_TVM_BATCH_RUNNER",
                "OPENAMP_DEMO_TVM_BATCH_RUNNER",
                "OPENAMP_TVM_BATCH_EXIT_GRACE_SEC",
            ):
                runner_value = str(os.environ.get(runner_key) or "").strip()
                if runner_value:
                    overrides.setdefault(runner_key, runner_value)
            local_image_dir = self._discover_default_local_usrp_image_dir()
            if local_image_dir:
                overrides.setdefault("OPENAMP_DEMO_LOCAL_IMAGE_DIR", local_image_dir)
            if not str(payload.get("local_latent_dir") or "").strip():
                local_latent_dir = self._discover_default_local_usrp_latent_dir()
                if local_latent_dir:
                    overrides.setdefault("OPENAMP_DEMO_LOCAL_LATENT_DIR", local_latent_dir)
                    overrides.setdefault("OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED", "0")
            else:
                overrides["OPENAMP_DEMO_LOCAL_LATENT_DIR"] = str(payload.get("local_latent_dir") or "").strip()
                overrides.setdefault("OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED", "0")
            if str(payload.get("local_latent_pattern") or "").strip():
                overrides["OPENAMP_DEMO_LOCAL_LATENT_PATTERN"] = str(payload.get("local_latent_pattern") or "").strip()
            if str(payload.get("remote_usrp_rx_dir") or "").strip():
                overrides["REMOTE_USRP_RX_DIR"] = str(payload.get("remote_usrp_rx_dir") or "").strip()
        else:
            overrides.setdefault("OPENAMP_DEMO_INPUT_SOURCE_MODE", "prerecorded")
        return overrides

    @staticmethod
    def _discover_default_local_usrp_latent_dir() -> str:
        for candidate in DEFAULT_LOCAL_USRP_LATENT_DIR_CANDIDATES:
            try:
                if candidate.is_dir() and any(candidate.glob("*.npz")):
                    return str(candidate)
                if candidate.is_dir() and any(candidate.glob("*.pt")):
                    return str(candidate)
            except OSError:
                continue
        return ""

    @staticmethod
    def _discover_default_local_usrp_image_dir() -> str:
        for candidate in DEFAULT_LOCAL_USRP_IMAGE_DIR_CANDIDATES:
            try:
                if candidate.is_dir() and (any(candidate.glob("*.jpg")) or any(candidate.glob("*.png"))):
                    return str(candidate)
            except OSError:
                continue
        return ""

    @staticmethod
    def _auth_sig_policy_for_env(env_values: dict[str, str]) -> str:
        raw_value = first_config_value(
            env_values,
            keys=MLKEM_AUTH_SIG_POLICY_KEYS,
            default=DEFAULT_MLKEM_AUTH_SIG_POLICY,
        )
        return str(raw_value or DEFAULT_MLKEM_AUTH_SIG_POLICY).strip().upper() or DEFAULT_MLKEM_AUTH_SIG_POLICY

    def _auth_status_from_env(self, env_values: dict[str, str]) -> dict[str, Any]:
        if not self._auth_enabled_for_env(env_values):
            return {
                "auth_enabled": False,
                "sig_policy": "",
                "server_id": "",
            }
        server_id = first_config_value(
            env_values,
            keys=MLKEM_AUTH_SERVER_ID_KEYS,
            default=DEFAULT_MLKEM_AUTH_SERVER_ID,
        )
        return {
            "auth_enabled": True,
            "sig_policy": self._auth_sig_policy_for_env(env_values),
            "server_id": str(server_id or DEFAULT_MLKEM_AUTH_SERVER_ID).strip() or DEFAULT_MLKEM_AUTH_SERVER_ID,
        }

    @staticmethod
    def _normalize_cipher_suite_label(raw_value: Any) -> str:
        value = str(raw_value or "").strip()
        if not value:
            return "unknown"
        return value.lower().replace("_", "-")

    def _infer_local_kem_backend_label(
        self,
        env_values: dict[str, str],
        *,
        client_script: Path | None,
    ) -> str:
        explicit_tongsuo = first_config_value(env_values, keys=LOCAL_TONGSUO_BRIDGE_KEYS, default="")
        if explicit_tongsuo:
            return "tongsuo-ML-KEM-768"

        extra_roots: tuple[Path, ...] = ()
        if client_script is not None:
            extra_roots = (client_script.parent.parent,)

        runtime_root, _ = resolve_local_mlkem_runtime_root(env_values, extra_roots=extra_roots)
        if _detect_local_tongsuo_bridge(runtime_root) is not None:
            return "tongsuo-ML-KEM-768"

        explicit_oqs = first_config_value(env_values, keys=OQS_INSTALL_KEYS, default="")
        if explicit_oqs:
            return "liboqs-ML-KEM-768"

        oqs_root, _ = resolve_local_oqs_install(env_values, extra_roots=extra_roots)
        if oqs_root is not None:
            return "liboqs-ML-KEM-768"

        return "ML-KEM-768"

    @staticmethod
    def _status_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _status_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _record_successful_crypto_test(
        self,
        *,
        env_values: dict[str, str],
        client_script: Path,
        transport_mode: str,
        metrics: dict[str, Any],
        input_bytes: int,
    ) -> dict[str, Any]:
        suite = self._normalize_cipher_suite_label(
            metrics.get("suite") or first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE)
        )
        backend = str(metrics.get("backend") or "").strip() or self._infer_local_kem_backend_label(
            env_values,
            client_script=client_script,
        )
        last_sha256_match = metrics.get("sha256_match")
        if last_sha256_match is not None:
            last_sha256_match = bool(last_sha256_match)

        current_ts = now_iso()
        channel_state = "ready" if str(transport_mode).strip().lower() == "daemon" else "idle"
        encrypt_bytes = self._status_int(metrics.get("bytes_sent"))
        decrypt_bytes = self._status_int(metrics.get("bytes_received"))
        auth_snapshot = self._auth_status_from_env(env_values)
        if metrics.get("auth_enabled") is not None:
            auth_snapshot["auth_enabled"] = bool(metrics.get("auth_enabled"))
        if metrics.get("sig_policy"):
            auth_snapshot["sig_policy"] = str(metrics.get("sig_policy") or "").strip()
        if metrics.get("server_id"):
            auth_snapshot["server_id"] = str(metrics.get("server_id") or "").strip()

        with self._lock:
            prev_status = dict(self._crypto_status_cache or {})
            prev_test = dict(self._last_crypto_test_result or {})
            prev_session_count = max(
                int(prev_status.get("session_count") or 0),
                int(prev_test.get("session_count") or 0),
            )
            prev_bytes_sent = max(
                int(prev_status.get("bytes_sent") or 0),
                int(prev_test.get("bytes_sent") or 0),
            )
            prev_bytes_received = max(
                int(prev_status.get("bytes_received") or 0),
                int(prev_test.get("bytes_received") or 0),
            )

            snapshot = {
                "channel_state": channel_state,
                "kem_backend": backend,
                "cipher_suite": suite,
                "handshake_ms": self._status_float(metrics.get("handshake_ms")),
                "encrypt_ms": self._status_float(metrics.get("encrypt_ms")),
                "decrypt_ms": self._status_float(metrics.get("decrypt_ms")),
                "inference_ms": self._status_float(metrics.get("inference_ms")),
                "bytes_sent": prev_bytes_sent + max(encrypt_bytes if encrypt_bytes is not None else input_bytes, 0),
                "bytes_received": prev_bytes_received + max(decrypt_bytes or 0, 0),
                "last_sha256_match": last_sha256_match,
                "session_count": prev_session_count + 1,
                "last_session_at": current_ts,
                "error": None,
                "enabled": True,
                "board_configured": True,
                **auth_snapshot,
            }
            self._last_crypto_test_result = dict(snapshot)
            self._crypto_status_cache = dict(snapshot)
            self._crypto_status_cache_ts = time.monotonic()

        return snapshot

    @staticmethod
    def _format_board_status_error(exc: Exception) -> str:
        return f"board status endpoint unavailable: {exc}"

    def _get_crypto_status_core(self) -> dict[str, Any]:
        """Internal: crypto status without degradation overlay."""
        control_summary = self._control_plane_summary()
        auth_summary = self._auth_status_from_env(self._board_access.build_env())
        _disabled = {
            "channel_state": "disabled",
            "kem_backend": "-",
            "cipher_suite": "-",
            "handshake_ms": None,
            "encrypt_ms": None,
            "decrypt_ms": None,
            "inference_ms": None,
            "bytes_sent": 0,
            "bytes_received": 0,
            "last_sha256_match": None,
            "session_count": 0,
            "last_session_at": None,
            "error": None,
            "enabled": False,
            "board_configured": False,
            **auth_summary,
            **control_summary,
        }

        with self._lock:
            board_access = self._board_access
            if not self._crypto_enabled:
                bc = bool(board_access and board_access.connection_ready)
                return {
                    **_disabled,
                    "board_configured": bc,
                    "batch_benchmark": None,
                    "batch_transport_benchmark": None,
                    "batch_inference_benchmark": None,
                    "batch_iq_stage_benchmark": None,
                }
            cached = self._crypto_status_cache
            cache_ts = self._crypto_status_cache_ts
            last_test = self._last_crypto_test_result
            if cached is not None and (time.monotonic() - cache_ts) < 1.5:
                batch = self._batch_state
                bm = batch.get("benchmark") if batch else None
                transport_bm = batch.get("transport_benchmark") if batch else None
                inference_bm = batch.get("inference_benchmark") if batch else None
                iq_stage_bm = batch.get("iq_stage_benchmark") if batch else None
                bs = batch.get("status") if batch else None
                bc_completed = batch.get("completed", 0) if batch else 0
                bc_total = batch.get("total", 0) if batch else 0
                return {
                    **cached,
                    "enabled": True,
                    **control_summary,
                    "batch_benchmark": bm,
                    "batch_transport_benchmark": transport_bm,
                    "batch_inference_benchmark": inference_bm,
                    "batch_iq_stage_benchmark": iq_stage_bm,
                    "batch_status": bs,
                    "batch_completed": bc_completed,
                    "batch_total": bc_total,
                }

        board_configured = bool(board_access and board_access.connection_ready)

        if not board_configured:
            return {
                "channel_state": "disabled",
                "kem_backend": "-",
                "cipher_suite": "-",
                "handshake_ms": None,
                "encrypt_ms": None,
                "decrypt_ms": None,
                "inference_ms": None,
                "bytes_sent": 0,
                "bytes_received": 0,
                "last_sha256_match": None,
                "session_count": 0,
                "last_session_at": None,
                "error": "board_not_configured",
                "enabled": True,
                "board_configured": False,
                "batch_benchmark": None,
                "batch_transport_benchmark": None,
                "batch_inference_benchmark": None,
                "batch_iq_stage_benchmark": None,
                "batch_status": None,
                "batch_completed": 0,
                "batch_total": 0,
                **auth_summary,
                **control_summary,
            }

        host = board_access.host
        status_port = parse_int_config(
            first_config_value(board_access.env_values, keys=STATUS_PORT_KEYS),
            DEFAULT_STATUS_PORT,
        )
        url = f"http://{host}:{status_port}/status"

        try:
            data = fetch_json_direct(url, timeout=3)
            data["enabled"] = True
            data["board_configured"] = True
            data.update(control_summary)
            with self._lock:
                self._crypto_status_cache = data
                self._crypto_status_cache_ts = time.monotonic()
                batch = self._batch_state
            data["batch_benchmark"] = batch.get("benchmark") if batch else None
            data["batch_transport_benchmark"] = batch.get("transport_benchmark") if batch else None
            data["batch_inference_benchmark"] = batch.get("inference_benchmark") if batch else None
            data["batch_iq_stage_benchmark"] = batch.get("iq_stage_benchmark") if batch else None
            data["batch_status"] = batch.get("status") if batch else None
            data["batch_completed"] = batch.get("completed", 0) if batch else 0
            data["batch_total"] = batch.get("total", 0) if batch else 0
            data.setdefault("auth_enabled", auth_summary["auth_enabled"])
            data.setdefault("sig_policy", auth_summary["sig_policy"])
            data.setdefault("server_id", auth_summary["server_id"])
            return data
        except (URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
            error_text = self._format_board_status_error(exc)
            # 保留上次正常值，只更新 error
            with self._lock:
                prev = self._crypto_status_cache
                last_test = self._last_crypto_test_result
                batch = self._batch_state
            if prev is not None:
                fallback = {
                    **prev,
                    "enabled": True,
                    "board_configured": True,
                    "error": error_text,
                    "batch_benchmark": batch.get("benchmark") if batch else None,
                    "batch_transport_benchmark": batch.get("transport_benchmark") if batch else None,
                    "batch_inference_benchmark": batch.get("inference_benchmark") if batch else None,
                    "batch_iq_stage_benchmark": batch.get("iq_stage_benchmark") if batch else None,
                    "batch_status": batch.get("status") if batch else None,
                    "batch_completed": batch.get("completed", 0) if batch else 0,
                    "batch_total": batch.get("total", 0) if batch else 0,
                    **auth_summary,
                    **control_summary,
                }
                with self._lock:
                    self._crypto_status_cache = fallback
                    self._crypto_status_cache_ts = time.monotonic()
                return fallback
            if last_test is not None:
                fallback = {
                    **last_test,
                    "enabled": True,
                    "board_configured": True,
                    "error": error_text,
                    "batch_benchmark": batch.get("benchmark") if batch else None,
                    "batch_transport_benchmark": batch.get("transport_benchmark") if batch else None,
                    "batch_inference_benchmark": batch.get("inference_benchmark") if batch else None,
                    "batch_iq_stage_benchmark": batch.get("iq_stage_benchmark") if batch else None,
                    "batch_status": batch.get("status") if batch else None,
                    "batch_completed": batch.get("completed", 0) if batch else 0,
                    "batch_total": batch.get("total", 0) if batch else 0,
                    **auth_summary,
                    **control_summary,
                }
                with self._lock:
                    self._crypto_status_cache = fallback
                    self._crypto_status_cache_ts = time.monotonic()
                return fallback
            # 从未成功获取过 → 返回带 error 的 idle
            cold: dict[str, Any] = {
                "channel_state": "idle",
                "kem_backend": "unknown",
                "cipher_suite": "unknown",
                "handshake_ms": None,
                "encrypt_ms": None,
                "decrypt_ms": None,
                "inference_ms": None,
                "bytes_sent": 0,
                "bytes_received": 0,
                "last_sha256_match": None,
                "session_count": 0,
                "last_session_at": None,
                "error": error_text,
                "enabled": True,
                "board_configured": True,
                "batch_benchmark": None,
                "batch_transport_benchmark": None,
                "batch_inference_benchmark": None,
                "batch_iq_stage_benchmark": None,
                "batch_status": None,
                "batch_completed": 0,
                "batch_total": 0,
                **auth_summary,
                **control_summary,
            }
            with self._lock:
                self._crypto_status_cache = cold
                self._crypto_status_cache_ts = time.monotonic()
            return cold

    def _control_plane_summary(self) -> dict[str, Any]:
        with self._lock:
            control_status = dict(self._last_control_status or {})
            probe_error = dict(self._last_control_probe_error or {})
            soft_recover = dict(self._last_soft_recover_result or {})
            auto_probe_triggered = self._auto_control_probe_triggered
            auto_probe_inflight = self._auto_control_probe_inflight
        event_summary = self._event_spine.summary(limit=1)
        aggregate = event_summary.get("aggregate") if isinstance(event_summary, dict) else {}
        event_counters = aggregate.get("event_counters") if isinstance(aggregate, dict) else {}
        if not isinstance(event_counters, dict):
            event_counters = {}

        heartbeat_ok_events = self._safe_int(event_counters.get("HEARTBEAT_OK"), default=0)
        heartbeat_lost_events = self._safe_int(event_counters.get("HEARTBEAT_LOST"), default=0)
        safe_stop_triggered_events = self._safe_int(event_counters.get("SAFE_STOP_TRIGGERED"), default=0)
        safe_stop_cleared_events = self._safe_int(event_counters.get("SAFE_STOP_CLEARED"), default=0)
        if control_status.get("status") == "success":
            status_source = "live_control"
            status_note = "已缓存最近一次 RPMsg 控制面读数。"
            guard_state = str(control_status.get("guard_state") or "UNKNOWN")
            last_fault_code = str(control_status.get("last_fault_code") or "UNKNOWN")
        elif probe_error:
            status_source = str(probe_error.get("status_source") or "probe_error")
            status_note = str(probe_error.get("message") or "控制面探测失败。")
            guard_state = str(probe_error.get("guard_state") or "PROBE_ERROR")
            last_fault_code = str(probe_error.get("last_fault_code") or "PROBE_ERROR")
        elif auto_probe_inflight:
            status_source = "probe_running"
            status_note = "控制面探测正在后台执行。"
            guard_state = "PROBING"
            last_fault_code = "PROBING"
        elif auto_probe_triggered:
            status_source = "probe_pending"
            status_note = "控制面探测已触发，等待状态回填。"
            guard_state = "PROBING"
            last_fault_code = "PROBING"
        else:
            status_source = "not_probed"
            status_note = "控制面尚未探测。"
            guard_state = "NOT_PROBED"
            last_fault_code = "NOT_PROBED"
        return {
            "control_guard_state": guard_state,
            "control_last_fault_code": last_fault_code,
            "control_heartbeat_ok": self._safe_int(control_status.get("heartbeat_ok"), default=0),
            "control_total_fault_count": self._safe_int(control_status.get("total_fault_count"), default=0),
            "control_job_req_count": self._safe_int(event_counters.get("JOB_SUBMITTED"), default=0),
            "control_job_admit_count": self._safe_int(event_counters.get("JOB_ADMITTED"), default=0),
            "control_job_reject_count": self._safe_int(event_counters.get("JOB_REJECTED"), default=0),
            "control_heartbeat_event_count": heartbeat_ok_events + heartbeat_lost_events,
            "control_heartbeat_lost_count": heartbeat_lost_events,
            "control_safe_stop_triggered_count": safe_stop_triggered_events,
            "control_safe_stop_cleared_count": safe_stop_cleared_events,
            "control_recover_attempted": bool(soft_recover),
            "control_recover_note": str(soft_recover.get("note") or ""),
            "status_source": status_source,
            "status_note": status_note,
        }

    def _refresh_control_plane_status(
        self,
        board_access: BoardAccessConfig,
        *,
        variant: str = "current",
        source: str,
        job_id: str = "",
    ) -> dict[str, Any] | None:
        if not board_access.probe_ready:
            return None

        variant_access = self._live_board_access_for_variant(board_access, variant=variant)
        trusted_sha = expected_sha_for_variant(variant_access, variant) or self._current_trusted_sha(variant_access)
        try:
            status_probe = query_live_status(board_access, trusted_sha=trusted_sha)
        except Exception as exc:
            error_payload = {
                "status": "error",
                "message": str(exc),
                "status_source": "probe_error",
                "guard_state": "PROBE_ERROR",
                "last_fault_code": "PROBE_ERROR",
            }
            with self._lock:
                self._last_control_probe_error = error_payload
            return error_payload

        if status_probe.get("status") == "success":
            with self._lock:
                self._last_control_status = status_probe
                self._last_control_probe_error = None
            self._emit_status_observation_events(status_probe, source=source, job_id=job_id)
        else:
            error_payload = {
                "status": str(status_probe.get("status") or "error"),
                "message": str(status_probe.get("message") or "控制面探测失败。"),
                "status_source": "probe_error",
                "guard_state": str(status_probe.get("guard_state") or "PROBE_ERROR"),
                "last_fault_code": str(status_probe.get("last_fault_code") or "PROBE_ERROR"),
            }
            with self._lock:
                self._last_control_probe_error = error_payload
        return status_probe

    def _trigger_auto_control_probe(self, board_access: 'BoardAccessConfig') -> None:
        """后台自动触发一次控制面探测。"""
        if not board_access.connection_ready:
            return
        with self._lock:
            if self._last_control_status or self._auto_control_probe_inflight:
                return
            now = time.monotonic()
            if self._last_control_probe_error and now - self._auto_control_probe_last_attempt_ts < 10.0:
                return
            self._auto_control_probe_triggered = True
            self._auto_control_probe_inflight = True
            self._auto_control_probe_last_attempt_ts = now

        def _probe() -> None:
            try:
                self._refresh_control_plane_status(
                    board_access, variant="current", source="auto_probe",
                )
            except Exception as exc:
                with self._lock:
                    self._last_control_probe_error = {
                        "status": "error",
                        "message": str(exc),
                        "status_source": "probe_error",
                        "guard_state": "PROBE_ERROR",
                        "last_fault_code": "PROBE_ERROR",
                    }
            finally:
                with self._lock:
                    self._auto_control_probe_inflight = False

        threading.Thread(target=_probe, daemon=True, name="auto-control-probe").start()

    def _maybe_soft_recover_control_plane(
        self,
        board_access: BoardAccessConfig,
        *,
        trusted_sha: str,
        reason: str,
    ) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last_soft_recover_ts
            cooldown = self._soft_recover_cooldown_sec
        if elapsed < cooldown:
            note = f"soft recover skipped by cooldown ({cooldown - elapsed:.1f}s left)"
            return {"attempted": False, "note": note}

        recover_result = run_recover_action(board_access, trusted_sha=trusted_sha)
        status_probe = query_live_status(board_access, trusted_sha=trusted_sha)
        attempted = {
            "attempted": True,
            "reason": reason,
            "recover_status": str(recover_result.get("status") or ""),
            "probe_status": str(status_probe.get("status") or ""),
            "note": "soft recover attempted before deciding to block",
        }
        with self._lock:
            self._last_soft_recover_ts = time.monotonic()
            self._last_soft_recover_result = attempted
            if recover_result.get("status") == "success":
                self._last_control_status = recover_result
            if status_probe.get("status") == "success":
                self._last_control_status = status_probe
        if status_probe.get("status") == "success":
            self._emit_status_observation_events(status_probe, source="soft_recover_retry")
        return {**attempted, "recover_result": recover_result, "status_retry": status_probe}

    def set_crypto_toggle(self, enabled: bool) -> dict[str, Any]:
        """设置 ML-KEM 开关状态

        当 enabled=True 时，自动通过 SSH 检测板卡 tcp_server 是否在运行，
        如果没有则自动启动（后台 nohup），这样用户不需要手动 SSH。
        """
        with self._lock:
            self._crypto_enabled = enabled
            board_access = self._board_access

        if enabled and board_access and board_access.connection_ready:
            import threading
            threading.Thread(
                target=self._ensure_board_tcp_server,
                args=(board_access,),
                daemon=True,
                name="tcp-server-toggle-start",
            ).start()

        return {"enabled": enabled}

    def _write_remote_text_file(
        self,
        board_access: BoardAccessConfig,
        *,
        remote_path: str,
        content: str,
        mode: int,
        timeout: float,
    ) -> None:
        remote_target = PurePosixPath(remote_path)
        remote_temp_path = str(
            remote_target.parent
            / f".{remote_target.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        local_tmp_path: Path | None = None
        try:
            fd, raw_tmp_path = tempfile.mkstemp(prefix="openamp-remote-", suffix=".txt", text=True)
            local_tmp_path = Path(raw_tmp_path)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)

            prepare_proc = run_ssh_command(
                host=board_access.host,
                user=board_access.user,
                password=board_access.password,
                port=board_access.port or "22",
                remote_command=_build_remote_file_copy_prepare_command(remote_temp_path),
                timeout=timeout,
            )
            if prepare_proc.returncode != 0:
                error_output = prepare_proc.stderr.strip() or prepare_proc.stdout.strip() or "unknown error"
                raise RuntimeError(f"failed to prepare remote file {remote_path}: {error_output}")

            copy_proc = run_scp_file(
                host=board_access.host,
                user=board_access.user,
                password=board_access.password,
                port=board_access.port or "22",
                local_path=local_tmp_path,
                remote_path=remote_temp_path,
                timeout=timeout,
            )
            if copy_proc.returncode != 0:
                error_output = copy_proc.stderr.strip() or copy_proc.stdout.strip() or "unknown error"
                raise RuntimeError(f"failed to copy remote file {remote_path}: {error_output}")

            finalize_proc = run_ssh_command(
                host=board_access.host,
                user=board_access.user,
                password=board_access.password,
                port=board_access.port or "22",
                remote_command=_build_remote_file_copy_finalize_command(remote_temp_path, remote_path, mode),
                timeout=timeout,
            )
            if finalize_proc.returncode != 0:
                error_output = finalize_proc.stderr.strip() or finalize_proc.stdout.strip() or "unknown error"
                raise RuntimeError(f"failed to finalize remote file {remote_path}: {error_output}")
        finally:
            if local_tmp_path is not None:
                try:
                    local_tmp_path.unlink()
                except OSError:
                    pass

    def _aircraft_position_upstream_probe_snapshot(
        self,
        *,
        board_access: BoardAccessConfig,
        defer_refresh: bool = False,
    ) -> dict[str, Any]:
        runtime = _aircraft_position_bridge_runtime(
            board_access,
            bind_host=self._bind_host,
            bind_port=self._bind_port,
        )
        if runtime["upstream_url_source"] == "env":
            return {
                "status": "configured",
                "selected_url": runtime["upstream_url"],
                "selected_source": "env",
                "candidate_urls": list(runtime["candidate_urls"]),
                "results": [],
                "checked_at": now_iso(),
            }
        if not board_access.connection_ready:
            return {
                "status": "waiting_session",
                "selected_url": "",
                "selected_source": "",
                "candidate_urls": list(runtime["candidate_urls"]),
                "results": [],
                "checked_at": now_iso(),
            }
        with self._lock:
            cached_probe = (
                json.loads(json.dumps(self._aircraft_position_upstream_probe_cache, ensure_ascii=False))
                if self._aircraft_position_upstream_probe_cache is not None
                else None
            )
            cached_ts = self._aircraft_position_upstream_probe_cache_ts
            refreshing = self._aircraft_position_upstream_probe_refreshing
        if defer_refresh and cached_probe is not None:
            cached_probe["stale"] = True
            cached_probe["note"] = "TVM live 推理进行中，暂缓板端定位上游探测，继续展示最近一次缓存结果。"
            return cached_probe
        if defer_refresh:
            return _aircraft_position_upstream_pending_status(
                runtime,
                status="deferred",
                note="TVM live 推理进行中，暂缓板端定位上游首次探测。",
            )
        if cached_probe is not None and (time.monotonic() - cached_ts) <= AIRCRAFT_POSITION_UPSTREAM_DISCOVERY_TTL_SEC:
            return cached_probe
        self._start_aircraft_position_upstream_probe_refresh(board_access, runtime=runtime)
        if cached_probe is not None:
            cached_probe["stale"] = True
            cached_probe["note"] = (
                "板端定位上游后台探测中，继续展示最近一次缓存结果。"
                if not refreshing
                else "板端定位上游仍在后台探测，继续展示最近一次缓存结果。"
            )
            return cached_probe
        return _aircraft_position_upstream_pending_status(
            runtime,
            status="refreshing",
            note="板端定位上游后台探测中，等待首次探测结果。",
        )

    def _start_aircraft_position_upstream_probe_refresh(
        self,
        board_access: BoardAccessConfig,
        *,
        runtime: dict[str, Any],
    ) -> None:
        with self._lock:
            if self._aircraft_position_upstream_probe_refreshing:
                return
            self._aircraft_position_upstream_probe_refreshing = True
        candidate_urls = list(runtime["candidate_urls"])
        upstream_headers = _parse_json_dict_text(runtime["runtime_env"].get("AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON", ""))
        timeout_sec = min(max(self._probe_timeout_sec, 2.0), 8.0)

        def worker() -> None:
            try:
                probe = query_board_aircraft_position_upstream(
                    board_access,
                    candidate_urls=candidate_urls,
                    upstream_headers=upstream_headers,
                    timeout_sec=timeout_sec,
                )
            except Exception as exc:
                probe = {
                    "status": "error",
                    "selected_url": "",
                    "selected_source": "",
                    "candidate_urls": candidate_urls,
                    "results": [],
                    "checked_at": now_iso(),
                    "error": str(exc),
                }
            else:
                if probe.get("selected_url"):
                    probe["selected_source"] = "auto_discovered"
                else:
                    probe.setdefault("selected_source", "")
            with self._lock:
                self._aircraft_position_upstream_probe_cache = json.loads(json.dumps(probe, ensure_ascii=False))
                self._aircraft_position_upstream_probe_cache_ts = time.monotonic()
                self._aircraft_position_upstream_probe_refreshing = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="aircraft-position-upstream-refresh",
        ).start()

    def _ensure_board_position_api_service(self, board_access: BoardAccessConfig) -> None:
        runtime = _board_position_api_runtime(board_access)
        assets = _board_position_api_local_assets()
        remote_paths = _board_position_api_remote_paths(runtime["remote_root"])
        health_wait = _remote_http_wait_command(_board_position_api_health_url(runtime["runtime_env"]))
        stop_command = _remote_terminate_matching_processes_command(BOARD_POSITION_API_SCRIPT_NAME)
        ssh_timeout = 25.0
        try:
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["service_script"],
                content=read_text(assets["service_script"]),
                mode=0o755,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["runner_script"],
                content=read_text(assets["runner_script"]),
                mode=0o755,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["env_file"],
                content=_render_board_position_api_env_file(runtime["runtime_env"]),
                mode=0o600,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["user_service"],
                content=_render_board_position_api_user_service(runtime["remote_root"]),
                mode=0o644,
                timeout=ssh_timeout,
            )
        except Exception as exc:
            print(f"[board-position-api] remote asset sync failed: {exc}")
            return

        root_direct_proc: subprocess.CompletedProcess[str] | None = None
        if board_access.password:
            root_direct_inner = (
                f'USER_HOME="$(getent passwd {shlex.quote(board_access.user)} | cut -d: -f6)"; '
                f'[ -n "$USER_HOME" ] || USER_HOME={shlex.quote(f"/home/{board_access.user}")}; '
                'export HOME="$USER_HOME"; '
                f"{stop_command} && "
                "/usr/bin/env bash -lc "
                f"\"nohup /usr/bin/env bash -lc 'set -a; . {remote_paths['env_file']}; set +a; "
                f"exec {remote_paths['runner_script']}' >> {remote_paths['log_file']} 2>&1 < /dev/null &\" && "
                f"{health_wait}"
            )
            root_direct_proc = run_ssh_command(
                host=board_access.host,
                user=board_access.user,
                password=board_access.password,
                port=board_access.port or "22",
                remote_command=_remote_sudo_bash_command(root_direct_inner, board_access.password),
                timeout=20.0,
            )
            if root_direct_proc.returncode == 0:
                return

        direct_command = (
            f"{stop_command} && "
            "/usr/bin/env bash -lc "
            f"\"nohup /usr/bin/env bash -lc 'set -a; . {remote_paths['env_file']}; set +a; "
            f"exec {remote_paths['runner_script']}' >> {remote_paths['log_file']} 2>&1 < /dev/null &\" && "
            f"{health_wait}"
        )
        direct_proc = run_ssh_command(
            host=board_access.host,
            user=board_access.user,
            password=board_access.password,
            port=board_access.port or "22",
            remote_command=direct_command,
            timeout=20.0,
        )
        if direct_proc.returncode == 0:
            return

        fallback_command = (
            "mkdir -p ~/.config/systemd/user && "
            f"{stop_command} && "
            f"systemctl --user daemon-reload && systemctl --user enable --now {BOARD_POSITION_API_SERVICE_NAME} && "
            f"{health_wait}"
        )
        fallback_proc = run_ssh_command(
            host=board_access.host,
            user=board_access.user,
            password=board_access.password,
            port=board_access.port or "22",
            remote_command=fallback_command,
            timeout=20.0,
        )
        if fallback_proc.returncode != 0:
            root_error = (
                root_direct_proc.stderr.strip() or root_direct_proc.stdout.strip() or "root launch skipped"
            ) if root_direct_proc is not None else "root launch skipped"
            direct_error = direct_proc.stderr.strip() or direct_proc.stdout.strip() or "unknown direct error"
            fallback_error = fallback_proc.stderr.strip() or fallback_proc.stdout.strip() or "unknown fallback error"
            print(
                "[board-position-api] remote start failed: "
                f"root={root_error}; direct={direct_error}; fallback={fallback_error}"
            )

    def _autostart_board_aircraft_position_bridge(self, board_access: BoardAccessConfig) -> None:
        self._ensure_board_position_api_service(board_access)
        probe = self._aircraft_position_upstream_probe_snapshot(board_access=board_access)
        selected_url = str(probe.get("selected_url") or "").strip()
        runtime = _aircraft_position_bridge_runtime(
            board_access,
            bind_host=self._bind_host,
            bind_port=self._bind_port,
            discovered_upstream_url=selected_url,
        )
        if not runtime["configured"]:
            return
        effective_board_access = board_access
        if selected_url and runtime["upstream_url_source"] == "auto_discovered":
            effective_board_access = board_access.with_env_overrides({"AIRCRAFT_POSITION_UPSTREAM_URL": selected_url})
        self._ensure_board_aircraft_position_bridge(effective_board_access)

    def _ensure_board_aircraft_position_bridge(self, board_access: BoardAccessConfig) -> None:
        runtime = _aircraft_position_bridge_runtime(
            board_access,
            bind_host=self._bind_host,
            bind_port=self._bind_port,
        )
        if not runtime["configured"]:
            return

        assets = _aircraft_position_bridge_local_assets()
        remote_paths = _aircraft_position_bridge_remote_paths(runtime["remote_root"])
        stop_command = _remote_terminate_matching_processes_command(remote_paths["bridge_script"])
        ssh_timeout = 25.0
        try:
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["bridge_script"],
                content=read_text(assets["bridge_script"]),
                mode=0o755,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["runner_script"],
                content=read_text(assets["runner_script"]),
                mode=0o755,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["env_file"],
                content=_render_aircraft_position_bridge_env_file(runtime["runtime_env"]),
                mode=0o600,
                timeout=ssh_timeout,
            )
            self._write_remote_text_file(
                board_access,
                remote_path=remote_paths["user_service"],
                content=_render_aircraft_position_bridge_user_service(runtime["remote_root"]),
                mode=0o644,
                timeout=ssh_timeout,
            )
        except Exception as exc:
            print(f"[aircraft-position-bridge] remote asset sync failed: {exc}")
            return

        service_command = (
            "mkdir -p ~/.config/systemd/user && "
            f"{stop_command} && "
            f"systemctl --user daemon-reload && systemctl --user enable --now {AIRCRAFT_POSITION_SERVICE_NAME}"
        )
        service_proc = run_ssh_command(
            host=board_access.host,
            user=board_access.user,
            password=board_access.password,
            port=board_access.port or "22",
            remote_command=service_command,
            timeout=15.0,
        )
        if service_proc.returncode == 0:
            return

        fallback_command = (
            f"{stop_command} && "
            "/usr/bin/env bash -lc "
            f"\"nohup /usr/bin/env bash -lc 'set -a; . {remote_paths['env_file']}; set +a; "
            f"exec {remote_paths['runner_script']}' >> {remote_paths['log_file']} 2>&1 < /dev/null &\""
        )
        fallback_proc = run_ssh_command(
            host=board_access.host,
            user=board_access.user,
            password=board_access.password,
            port=board_access.port or "22",
            remote_command=fallback_command,
            timeout=15.0,
        )
        if fallback_proc.returncode != 0:
            service_error = service_proc.stderr.strip() or service_proc.stdout.strip() or "unknown service error"
            fallback_error = fallback_proc.stderr.strip() or fallback_proc.stdout.strip() or "unknown fallback error"
            print(
                "[aircraft-position-bridge] remote start failed: "
                f"systemd={service_error}; fallback={fallback_error}"
            )

    def _ensure_board_tcp_server(self, board_access: BoardAccessConfig) -> None:
        if not self._mlkem_board_start_lock.acquire(blocking=False):
            with self._mlkem_board_start_lock:
                return
        try:
            return self._ensure_board_tcp_server_impl(board_access)
        finally:
            self._mlkem_board_start_lock.release()

    def _ensure_board_tcp_server_impl(self, board_access: BoardAccessConfig) -> None:
        """通过 SSH 检测板卡 tcp_server 是否运行，如果没有则启动它。"""
        env_values_kill = board_access.build_env()
        if str(first_config_value(env_values_kill, keys=("OPENAMP_DEMO_DISABLE_TCP_AUTOSTART",), default="")).strip().lower() in {"1", "true", "yes", "on"}:
            return
        host = board_access.host
        user = board_access.user
        password = board_access.password
        ssh_port = board_access.port or "22"
        env_values = env_values_kill
        status_port = parse_int_config(
            first_config_value(env_values, keys=STATUS_PORT_KEYS),
            DEFAULT_STATUS_PORT,
        )
        status_startup_wait_sec = max(
            2,
            parse_int_config(
                first_config_value(
                    env_values,
                    keys=("MLKEM_STATUS_STARTUP_WAIT_SEC", "MLKEM_REMOTE_STATUS_STARTUP_WAIT_SEC"),
                ),
                60,
            ),
        )

        def wait_for_status_port(timeout_sec: int) -> bool:
            deadline = time.monotonic() + max(1, timeout_sec)
            while time.monotonic() < deadline:
                try:
                    fetch_json_direct(f"http://{host}:{status_port}/status", timeout=2)
                    return True
                except Exception:
                    time.sleep(1.0)
            return False

        def log_remote_tcp_server_diagnostics(reason: str) -> None:
            log_path = first_config_value(env_values, keys=("MLKEM_REMOTE_LOG_PATH",), default="/tmp/tcp_server.log")
            remote_command = (
                "printf '%s\\n' '--- pgrep tcp_server.py ---'; "
                "pgrep -af 'tcp_server.py' || true; "
                "printf '%s\\n' '--- listening ports ---'; "
                "(command -v ss >/dev/null 2>&1 && ss -ltnp || netstat -ltnp 2>/dev/null || true); "
                "printf '%s\\n' '--- tcp_server log tail ---'; "
                f"tail -n 120 {shlex.quote(log_path)} 2>&1 || true"
            )
            try:
                proc = run_ssh_command(
                    host=host,
                    user=user,
                    password=password,
                    port=ssh_port,
                    remote_command=remote_command,
                    timeout=12,
                )
            except Exception as exc:
                print(f"[ML-KEM auto-start] remote diagnostics failed after {reason}: {exc}")
                return
            output = (proc.stdout or proc.stderr or "").strip()
            if output:
                print(f"[ML-KEM auto-start] remote diagnostics after {reason}:\n{output[-4000:]}")

        runtime_env_values = dict(env_values)
        remote_home = ""
        explicit_remote_script = first_config_value(env_values, keys=REMOTE_SERVER_SCRIPT_KEYS)
        explicit_remote_root = first_config_value(env_values, keys=REMOTE_PROJECT_ROOT_KEYS)
        if not explicit_remote_script and not explicit_remote_root:
            try:
                home_proc = run_ssh_command(
                    host=host,
                    user=user,
                    password=password,
                    port=ssh_port,
                    remote_command='printf %s "$HOME"',
                    timeout=8,
                )
                remote_home = (home_proc.stdout or "").strip()
                if home_proc.returncode == 0 and remote_home:
                    runtime_env_values["MLKEM_REMOTE_SERVER_SCRIPT"] = (
                        f"{remote_home.rstrip('/')}/tcp_server.py"
                    )
            except Exception:
                pass
        if not first_config_value(
            runtime_env_values,
            keys=("MLKEM_REMOTE_RUN_LOGGER_DIR", "RUN_LOGGER_DIR"),
        ):
            remote_log_home = remote_home.rstrip("/") if remote_home else f"/home/{user}"
            runtime_env_values["MLKEM_REMOTE_RUN_LOGGER_DIR"] = (
                f"{remote_log_home}/artifacts/evidence/logs"
            )

        local_server_script, _ = resolve_local_crypto_server(runtime_env_values)
        remote_asset_sync = self._sync_remote_mlkem_server_assets(
            board_access,
            runtime_env_values=runtime_env_values,
            local_server_script=local_server_script,
        )

        # 1) 检测 status 端口是否响应，并验证密码套件是否匹配
        expected_suite = first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE).lower().replace("_", "-")
        expected_tvm_python_raw = first_config_value(env_values, keys=REMOTE_TVM_PYTHON_KEYS)
        expected_tvm_python = _normalize_remote_tvm_python(expected_tvm_python_raw)
        forced_restart = False
        if remote_asset_sync.get("updated"):
            forced_restart = True
            print(f"[ML-KEM auto-start] 已同步板端 helper 资产: {remote_asset_sync.get('note', 'remote assets refreshed')}")
        elif remote_asset_sync.get("error"):
            print(f"[ML-KEM auto-start] 板端 helper 同步失败，将继续尝试复用远端现有脚本: {remote_asset_sync.get('note', '')}")
        hotfix_result = self._apply_remote_mlkem_hotfixes(board_access)
        if hotfix_result.get("patched"):
            forced_restart = True
            print(f"[ML-KEM auto-start] 已应用板端热修: {hotfix_result.get('note', 'remote helper patched')}")
        # AES_256_GCM → aes-256-gcm, SM4_GCM → sm4-gcm
        try:
            status = fetch_json_direct(f"http://{host}:{status_port}/status", timeout=2)
            running_suite = str(status.get("cipher_suite") or "").lower()
            restart_reason = ""
            if running_suite and running_suite != expected_suite:
                restart_reason = (
                    f"套件不匹配 (running={running_suite}, expected={expected_suite})"
                )
            elif running_suite and expected_tvm_python_raw:
                try:
                    pgrep_proc = run_ssh_command(
                        host=host,
                        user=user,
                        password=password,
                        port=ssh_port,
                        remote_command="pgrep -af 'tcp_server.py' || true",
                        timeout=8,
                    )
                    running_cmdline = pgrep_proc.stdout or ""
                    raw_match = bool(running_cmdline and expected_tvm_python_raw in running_cmdline)
                    normalized_match = bool(
                        running_cmdline
                        and expected_tvm_python
                        and expected_tvm_python in running_cmdline
                    )
                    if running_cmdline and not raw_match and not normalized_match:
                        restart_reason = (
                            "检测到板端 tcp_server 的 --tvm-python 与当前期望运行时不一致"
                        )
                    elif raw_match and (
                        expected_tvm_python
                        and expected_tvm_python != expected_tvm_python_raw
                        and "--tvm-python env " in running_cmdline
                    ):
                        restart_reason = (
                            "检测到板端 tcp_server 仍使用 shell 包装的 --tvm-python 参数"
                        )
                except Exception:
                    pass

            if running_suite and not restart_reason and not forced_restart:
                return  # 已在运行且配置匹配
            if restart_reason or forced_restart:
                reason_text = restart_reason or "检测到板端 helper 资产已更新"
                print(f"[ML-KEM auto-start] {reason_text}，重启板端 tcp_server")
                forced_restart = True
                run_ssh_command(
                    host=host, user=user, password=password, port=ssh_port,
                    remote_command="pkill -f 'tcp_server.py' || true",
                    timeout=8,
                )
                import time as _time; _time.sleep(1)
        except Exception:
            pass  # 没运行，继续启动

        # 1b) 若进程已在运行但 status 不通，等一下再试
        if not forced_restart:
            try:
                pgrep_proc = run_ssh_command(
                    host=host,
                    user=user,
                    password=password,
                    port=ssh_port,
                    remote_command="pgrep -af 'tcp_server.py' || true",
                    timeout=8,
                )
                if pgrep_proc.returncode == 0 and (pgrep_proc.stdout or "").strip():
                    if wait_for_status_port(min(status_startup_wait_sec, 12)):
                        return
                    print("[ML-KEM auto-start] 检测到板端 tcp_server 进程存在但状态端口不通，重启板端 tcp_server")
                    forced_restart = True
                    run_ssh_command(
                        host=host,
                        user=user,
                        password=password,
                        port=ssh_port,
                        remote_command="pkill -f 'tcp_server.py' || true",
                        timeout=8,
                    )
                    time.sleep(1)
            except Exception:
                pass

        # 2) SSH 到板卡启动 tcp_server
        remote_command = build_remote_crypto_server_command(
            runtime_env_values,
            local_server_script=local_server_script,
        )

        try:
            proc = run_ssh_command(
                host=host,
                user=user,
                password=password,
                port=ssh_port,
                remote_command=remote_command,
                timeout=30,
            )
            if proc.returncode != 0:
                error_output = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
                print(f"[ML-KEM auto-start] SSH failed: {error_output}")
                return
            if wait_for_status_port(status_startup_wait_sec):
                return
            print(
                f"[ML-KEM auto-start] status port {host}:{status_port} "
                f"not ready after {status_startup_wait_sec}s"
            )
            log_remote_tcp_server_diagnostics("status wait timeout")
        except Exception as exc:
            print(f"[ML-KEM auto-start] error: {exc}")
            log_remote_tcp_server_diagnostics("startup exception")

    def _sync_remote_mlkem_server_assets(
        self,
        board_access: BoardAccessConfig,
        *,
        runtime_env_values: dict[str, str],
        local_server_script: Path | None,
    ) -> dict[str, Any]:
        if local_server_script is None:
            return {"updated": False, "note": "local tcp_server.py not found"}

        remote_server_script = _derive_remote_server_script(
            runtime_env_values,
            local_server_script=local_server_script,
        )
        assets: list[tuple[str, Path]] = [(remote_server_script, local_server_script)]
        for helper_name in (
            "tvm_inference_helper.py",
            "artifact_guard.py",
            "latent_transport.py",
            "replay_guard.py",
            "run_logger.py",
        ):
            local_helper_script = local_server_script.with_name(helper_name)
            if local_helper_script.exists():
                remote_helper_script = str(
                    PurePosixPath(remote_server_script).with_name(local_helper_script.name)
                )
                assets.append((remote_helper_script, local_helper_script))
        package_candidates = (
            local_server_script.parent / "mlkem_link",
            local_server_script.parent.parent / "mlkem_link",
        )
        local_package_dir = next((path for path in package_candidates if path.is_dir()), None)
        if local_package_dir is not None:
            remote_package_dir = PurePosixPath(remote_server_script).parent / local_package_dir.name
            for local_package_file in sorted(local_package_dir.rglob("*.py")):
                if "__pycache__" in local_package_file.parts or "tests" in local_package_file.parts:
                    continue
                remote_relative = local_package_file.relative_to(local_package_dir)
                remote_package_file = remote_package_dir.joinpath(*remote_relative.parts)
                assets.append((str(remote_package_file), local_package_file))

        hasher = hashlib.sha256()
        for remote_path, local_path in assets:
            hasher.update(remote_path.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(local_path.read_bytes())
        signature = hasher.hexdigest()
        signature_key = f"{board_access.host}:{remote_server_script}"

        with self._lock:
            if self._mlkem_remote_asset_signatures.get(signature_key) == signature:
                return {"updated": False, "note": "remote helper assets already synced"}

        try:
            for remote_path, local_path in assets:
                self._write_remote_text_file(
                    board_access,
                    remote_path=remote_path,
                    content=local_path.read_text(encoding="utf-8"),
                    mode=0o755,
                    timeout=25.0,
                )
        except Exception as exc:
            return {"updated": False, "error": True, "note": str(exc)}

        with self._lock:
            self._mlkem_remote_asset_signatures[signature_key] = signature
        return {"updated": True, "note": f"{len(assets)} file(s) uploaded to {remote_server_script}"}

    def _apply_remote_mlkem_hotfixes(self, board_access: BoardAccessConfig) -> dict[str, Any]:
        """修补板端已知的 helper bug，避免长批次中途断链。"""
        hotfix_script = "\n".join(
            [
                "from pathlib import Path",
                "import os",
                "",
                "path = Path(os.path.expanduser('~/replay_guard.py'))",
                "if not path.exists():",
                "    print('missing:replay_guard.py')",
                "    raise SystemExit(0)",
                "text = path.read_text(encoding='utf-8')",
                "old = \"                oldest_key, _ = next(iter(self._window))\\n                oldest_job, oldest_seq = oldest_key\\n\"",
                "new = \"                oldest_job, oldest_seq = next(iter(self._window))\\n\"",
                "if old in text:",
                "    path.write_text(text.replace(old, new, 1), encoding='utf-8')",
                "    print('patched:replay_guard_window_unpack')",
                "elif new in text:",
                "    print('ok:replay_guard_window_unpack')",
                "else:",
                "    print('unknown:replay_guard_window_unpack')",
            ]
        )
        remote_command = f"python3 -c {shlex.quote(hotfix_script)}"
        try:
            proc = run_ssh_command(
                host=board_access.host,
                user=board_access.user,
                password=board_access.password,
                port=board_access.port or "22",
                remote_command=remote_command,
                timeout=12,
            )
        except Exception as exc:
            return {"patched": False, "note": f"hotfix probe failed: {exc}"}

        output = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode != 0:
            return {"patched": False, "note": output or "hotfix probe failed"}
        if "patched:replay_guard_window_unpack" in output:
            return {"patched": True, "note": "replay_guard window unpack bug fixed"}
        if "ok:replay_guard_window_unpack" in output:
            return {"patched": False, "note": "replay_guard window unpack already fixed"}
        return {"patched": False, "note": output or "no remote hotfix applied"}

    def run_crypto_test(self) -> dict[str, Any]:
        """通过 tcp_client.py 向板卡发送测试 latent，验证 ML-KEM 加密通道"""
        with self._lock:
            board_access = self._board_access
            if not self._crypto_enabled:
                return {"status": "error", "message": "ML-KEM not enabled"}

        if not (board_access and board_access.connection_ready):
            return {"status": "error", "message": "board not configured, please enter board password first"}

        host = board_access.host
        env_values = board_access.build_env()
        transport_mode = local_crypto_transport_mode(env_values)
        if transport_mode == "tcp":
            self._ensure_board_tcp_server(board_access)
        tcp_client, searched_paths = resolve_local_crypto_client(env_values)
        if tcp_client is None:
            searched_text = ", ".join(str(path) for path in searched_paths[:5]) or "no candidate paths"
            return {
                "status": "error",
                "message": "tcp_client.py not found; set MLKEM_CLIENT_SCRIPT/MLKEM_LOCAL_REPO_ROOT. "
                f"searched: {searched_text}",
            }

        # 生成测试输入：兼容新版 batch client 与旧版单图 client。
        tmp_path = self._create_mlkem_input_file(tcp_client)
        test_job_id = f"crypto_test_{tmp_path.stem}"
        try:
            test_input_bytes = int(tmp_path.stat().st_size)
        except OSError:
            test_input_bytes = 0

        cmd, env = build_local_crypto_client_command(
            env_values,
            host=host,
            input_path=tmp_path,
            client_script=tcp_client,
        )

        # ── 尝试 daemon 模式（复用已有 session，省握手开销）──
        mgr = self._get_mlkem_session_manager(board_access, env_values)
        if mgr is not None:
            try:
                mgr.ensure_alive()
                t0 = time.monotonic()
                daemon_result = mgr.send_image(
                    str(tmp_path),
                    test_job_id,
                    run_tvm=False,
                    expect_result=False,
                )
                wall_ms = round((time.monotonic() - t0) * 1000, 1)
                tmp_path.unlink()
                result = {
                    "status": "ok" if daemon_result.get("status") == "ok" else "error",
                    "wall_ms": wall_ms,
                    "handshake_ms": round(mgr._handshake_ms, 1),
                    "sha256_match": daemon_result.get("sha256_match", False),
                    "transport_mode": "daemon",
                }
                if result["status"] == "ok":
                    daemon_metrics = {
                        "handshake_ms": result.get("handshake_ms"),
                        "encrypt_ms": daemon_result.get("encrypt_ms"),
                        "decrypt_ms": daemon_result.get("decrypt_ms"),
                        "inference_ms": daemon_result.get("inference_ms"),
                        "sha256_match": daemon_result.get("sha256_match"),
                        "suite": first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE),
                    }
                    self._record_successful_crypto_test(
                        env_values=env_values,
                        client_script=tcp_client,
                        transport_mode="daemon",
                        metrics=daemon_metrics,
                        input_bytes=test_input_bytes,
                    )
                    self._refresh_control_plane_status(
                        board_access,
                        source="crypto_test_probe",
                        job_id=test_job_id,
                    )
                return result
            except Exception:
                pass  # 回退到子进程模式

        # ── 子进程模式（原有逻辑）──
        try:
            t0 = time.monotonic()
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            wall_ms = round((time.monotonic() - t0) * 1000, 1)
            try:
                tmp_path.unlink()
            except OSError:
                pass

            if proc.returncode != 0:
                return {
                    "status": "error",
                    "message": proc.stderr[-500:] if proc.stderr else "unknown error",
                    "wall_ms": wall_ms,
                }

            # 解析 stdout 中关键指标
            stdout = proc.stdout
            metrics = self._parse_mlkem_client_metrics(stdout)
            result: dict[str, Any] = {
                "status": "ok",
                "wall_ms": wall_ms,
                "transport_mode": transport_mode,
            }
            if metrics.get("handshake_ms") is not None:
                result["handshake_ms"] = float(metrics["handshake_ms"])
            if metrics.get("sha256_match") is not None:
                result["sha256_match"] = bool(metrics["sha256_match"])

            self._record_successful_crypto_test(
                env_values=env_values,
                client_script=tcp_client,
                transport_mode=transport_mode,
                metrics=metrics,
                input_bytes=test_input_bytes,
            )
            self._refresh_control_plane_status(
                board_access,
                source="crypto_test_probe",
                job_id=test_job_id,
            )

            return result

        except subprocess.TimeoutExpired:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            return {"status": "error", "message": "timeout (30s)"}
        except Exception as exc:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            return {"status": "error", "message": str(exc)}

    def _board_telemetry_snapshot(
        self,
        *,
        board_access: BoardAccessConfig,
        board_online: bool,
        defer_refresh: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            cached = (
                json.loads(json.dumps(self._board_telemetry_cache, ensure_ascii=False))
                if self._board_telemetry_cache is not None
                else None
            )
            cached_ts = self._board_telemetry_cache_ts
            refreshing = self._board_telemetry_refreshing

        age_sec = time.monotonic() - cached_ts if cached_ts > 0 else None
        if defer_refresh and cached is not None:
            cached["status"] = "stale"
            cached["stale"] = True
            cached["note"] = "TVM live 推理进行中，暂缓板端资源占用刷新，继续展示最近一次缓存值。"
            return cached
        if defer_refresh:
            return _board_telemetry_pending_status(
                status="deferred",
                note="TVM live 推理进行中，暂缓板端资源占用首次采样。",
            )
        if cached is not None and age_sec is not None and age_sec <= BOARD_TELEMETRY_TTL_SEC:
            return cached

        if not board_access.connection_ready:
            if cached is not None:
                cached["status"] = "stale"
                cached["stale"] = True
                cached["note"] = "当前板卡会话不完整，继续展示上一次缓存的板端资源占用。"
                return cached
            return {
                "status": "unavailable",
                "stale": True,
                "source": "none",
                "collected_at": "",
                "compute_label": "CPU",
                "compute_pct": None,
                "memory_pct": None,
                "memory_used_mb": None,
                "memory_available_mb": None,
                "memory_total_mb": None,
                "loadavg_1m": None,
                "cpu_cores": None,
                "note": "板卡会话未配置，无法采集系统占用。",
            }

        if not board_online and cached is None:
            return {
                "status": "unavailable",
                "stale": True,
                "source": "none",
                "collected_at": "",
                "compute_label": "CPU",
                "compute_pct": None,
                "memory_pct": None,
                "memory_used_mb": None,
                "memory_available_mb": None,
                "memory_total_mb": None,
                "loadavg_1m": None,
                "cpu_cores": None,
                "note": "板卡当前未在线，尚无可展示的实时系统占用。",
            }

        if cached is not None:
            self._start_board_telemetry_refresh(
                board_access,
                timeout_sec=min(max(self._probe_timeout_sec, 3.0), 12.0),
            )
            cached["status"] = "stale"
            cached["stale"] = True
            cached["note"] = (
                "板端资源占用后台刷新中，继续展示最近一次缓存值。"
                if not refreshing
                else "板端资源占用仍在后台刷新，继续展示最近一次缓存值。"
            )
            return cached

        self._start_board_telemetry_refresh(
            board_access,
            timeout_sec=min(max(self._probe_timeout_sec, 2.0), 4.0),
        )
        return _board_telemetry_pending_status(
            status="refreshing",
            note="板端资源占用后台刷新中，等待首次采样结果。",
        )

    def _start_board_telemetry_refresh(self, board_access: BoardAccessConfig, *, timeout_sec: float) -> None:
        with self._lock:
            if self._board_telemetry_refreshing:
                return
            self._board_telemetry_refreshing = True

        def worker() -> None:
            try:
                telemetry = query_board_telemetry(board_access, timeout_sec=timeout_sec)
                with self._lock:
                    self._board_telemetry_cache = json.loads(json.dumps(telemetry, ensure_ascii=False))
                    self._board_telemetry_cache_ts = time.monotonic()
            except Exception:
                return
            finally:
                with self._lock:
                    self._board_telemetry_refreshing = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="board-telemetry-refresh",
        ).start()

    def _board_position_api_snapshot(
        self,
        board_access: BoardAccessConfig,
        *,
        defer_refresh: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            cached = (
                json.loads(json.dumps(self._board_position_api_cache, ensure_ascii=False))
                if self._board_position_api_cache is not None
                else None
            )
            cached_ts = self._board_position_api_cache_ts
            refreshing = self._board_position_api_refreshing

        age_sec = time.monotonic() - cached_ts if cached_ts > 0 else None
        if defer_refresh and cached is not None:
            cached["stale"] = True
            cached["note"] = "TVM live 推理进行中，暂缓板端定位 API 刷新，继续展示最近一次缓存值。"
            return cached
        if defer_refresh:
            return _board_position_api_pending_status(
                board_access,
                status="deferred",
                note="TVM live 推理进行中，暂缓板端定位 API 首次探测。",
            )
        if cached is not None and age_sec is not None and age_sec <= BOARD_POSITION_API_TTL_SEC:
            return cached

        if cached is not None and board_access.connection_ready:
            self._start_board_position_api_refresh(
                board_access,
                timeout_sec=min(max(self._probe_timeout_sec, 1.0), 4.0),
            )
            cached["stale"] = True
            cached["note"] = (
                "板端定位 API 状态后台刷新中，继续展示最近一次缓存值。"
                if not refreshing
                else "板端定位 API 状态仍在后台刷新，继续展示最近一次缓存值。"
            )
            return cached

        if board_access.connection_ready:
            self._start_board_position_api_refresh(
                board_access,
                timeout_sec=min(max(self._probe_timeout_sec, 1.0), 4.0),
            )
            return _board_position_api_pending_status(
                board_access,
                status="refreshing",
                note="板端定位 API 状态后台刷新中，等待首次健康探测结果。",
            )

        payload = _board_position_api_status(
            board_access,
            timeout_sec=min(max(self._probe_timeout_sec, 1.0), 2.0),
        )
        with self._lock:
            self._board_position_api_cache = json.loads(json.dumps(payload, ensure_ascii=False))
            self._board_position_api_cache_ts = time.monotonic()
        return payload

    def _start_board_position_api_refresh(self, board_access: BoardAccessConfig, *, timeout_sec: float) -> None:
        with self._lock:
            if self._board_position_api_refreshing:
                return
            self._board_position_api_refreshing = True

        def worker() -> None:
            try:
                payload = _board_position_api_status(board_access, timeout_sec=timeout_sec)
                with self._lock:
                    self._board_position_api_cache = json.loads(json.dumps(payload, ensure_ascii=False))
                    self._board_position_api_cache_ts = time.monotonic()
            except Exception:
                return
            finally:
                with self._lock:
                    self._board_position_api_refreshing = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="board-position-api-refresh",
        ).start()

    def current_system_status(self) -> dict[str, Any]:
        with self._lock:
            live_probe = self._last_live_probe
            board_access = self._board_access
            control_status = self._last_control_status
            last_inference = self._last_inference_result
            recent_inference_results = dict(self._recent_inference_results)
            last_fault = self._last_fault_result
            aircraft_position = self._aircraft_position
            local_aircraft_bridge_state = json.loads(json.dumps(self._local_aircraft_bridge_state, ensure_ascii=False))
            batch_state = dict(self._batch_state) if self._batch_state is not None else None

        snapshot = build_snapshot(live_probe=live_probe, aircraft_position=aircraft_position)
        aircraft_position_payload = snapshot["aircraft_position"]
        event_spine = self._event_spine.summary(limit=1)
        active_inference = self._active_inference_summary()
        batch_status = str((batch_state or {}).get("status") or "").strip().lower()
        defer_board_refresh = bool(active_inference.get("running")) or batch_status in {"launching", "running"}
        board_transport_mode = normalize_transport_mode(board_access.build_env().get("MLKEM_TRANSPORT_MODE", ""))
        defer_remote_refresh = defer_board_refresh or board_transport_mode == "usrp"
        aircraft_upstream_probe = self._aircraft_position_upstream_probe_snapshot(
            board_access=board_access,
            defer_refresh=defer_remote_refresh,
        )
        discovered_upstream_url = str(aircraft_upstream_probe.get("selected_url") or "").strip()
        board_position_api = self._board_position_api_snapshot(
            board_access,
            defer_refresh=defer_remote_refresh,
        )
        usrp_control_status = self._usrp_control_status_snapshot(
            board_access,
            defer_refresh=defer_remote_refresh,
        )
        aircraft_bridge = _aircraft_position_bridge_status(
            board_access,
            aircraft_position_payload=aircraft_position_payload,
            bind_host=self._bind_host,
            bind_port=self._bind_port,
            discovered_upstream_url=discovered_upstream_url,
            upstream_probe=aircraft_upstream_probe,
            local_runtime_state=local_aircraft_bridge_state,
        )
        aircraft_position_payload = {
            **aircraft_position_payload,
            "bridge_runtime": aircraft_bridge,
            "position_api_runtime": board_position_api,
        }
        current_board_access = self._live_board_access_for_variant(board_access, variant="current")
        baseline_board_access = self._live_board_access_for_variant(board_access, variant="baseline")
        admission = describe_demo_admission(current_board_access, variant="current")
        current_support = describe_demo_variant_support(current_board_access, variant="current")
        baseline_support = describe_demo_variant_support(baseline_board_access, variant="baseline")
        evidence_status = snapshot["board"]["evidence_status"]
        live_details = live_probe.get("details", {}) if live_probe else {}
        remoteproc_entries = live_details.get("remoteproc", [])
        remoteproc_state = (
            remoteproc_entries[0].get("state")
            if remoteproc_entries
            else evidence_status["transport"].get("remoteproc_state", "unknown")
        )
        rpmsg_devices = live_details.get("rpmsg_devices", [])
        rpmsg_device = rpmsg_devices[0] if rpmsg_devices else evidence_status["transport"].get("rpmsg_dev", "unknown")

        board_online = bool(live_probe and live_probe.get("reachable"))

        if control_status and control_status.get("status") == "success":
            guard_state = control_status.get("guard_state", "UNKNOWN")
            last_fault_code = control_status.get("last_fault_code", "UNKNOWN")
            active_job_id = control_status.get("active_job_id", 0)
            total_fault_count = control_status.get("total_fault_count", 0)
            status_source = "live_control"
            status_note = "已缓存最近一次 RPMsg 控制面读数。"
        else:
            fallback_timeout = evidence_status["timeout_ready_state"]
            guard_state = fallback_timeout.get("guard_state", "UNKNOWN")
            last_fault_code = fallback_timeout.get("last_fault", "UNKNOWN")
            active_job_id = fallback_timeout.get("active_job_id", 0)
            total_fault_count = fallback_timeout.get("total_fault_count", 0)
            status_source = "evidence"
            status_note = "当前 guard_state / fault_code 仍以正式证据包为准。"

        if str(guard_state or "").upper() == "JOB_ACTIVE":
            active_job_text = f" active_job_id={active_job_id}。" if active_job_id else ""
            status_note = (
                "板端当前 guard_state=JOB_ACTIVE；demo 会保守阻断新的 live launch，"
                f"不会自动 SAFE_STOP。{active_job_text}请等待现有作业完成，或由操作员手动 SAFE_STOP 后再重试。"
            )

        live_telemetry = self._board_telemetry_snapshot(
            board_access=board_access,
            board_online=board_online,
            defer_refresh=defer_remote_refresh,
        )
        safety_panel = build_safety_panel(
            guard_state=str(guard_state or "UNKNOWN"),
            last_fault_code=str(last_fault_code or "UNKNOWN"),
            total_fault_count=self._safe_int(total_fault_count, default=0),
            board_online=board_online,
            status_source=status_source,
            status_note=status_note,
            last_fault=last_fault or None,
        )
        if board_online:
            mode_label = "在线模式"
            mode_tone = "online"
            mode_summary = "当前处于 3-core Linux + RTOS demo mode；板卡 SSH 与 RPMsg 控制面可用，第二幕会展示语义回传数据面的真实在线推进。"
        elif board_access.connection_ready:
            mode_label = "降级模式"
            mode_tone = "degraded"
            mode_summary = "本场会话已就绪；若真机链路暂不可用，界面会明确切回归档证据，不把 demo mode 数字混写成 4-core 性能口径。"
        elif board_access.has_preloaded_defaults and board_access.missing_connection_fields() == ["password"]:
            mode_label = "待补全密码"
            mode_tone = "degraded"
            mode_summary = "SSH 与推理默认值已预载；补一次密码即可触发真机动作。headline 性能仍以 4-core Linux performance mode 报告为准。"
        elif board_access.configured:
            mode_label = "待补全会话"
            mode_tone = "degraded"
            mode_summary = "已接入部分会话信息；补齐缺失字段后即可尝试真机动作。OpenAMP live 仅用于控制与安全演示。"
        else:
            mode_label = "离线模式"
            mode_tone = "offline"
            mode_summary = "尚未配置板卡会话，当前只展示证据与预录结果；headline 性能仍引用 4-core Linux performance mode 报告。"

        board_access_public = board_access.to_public_dict()
        live_payload = {
            "board_online": board_online,
            "remoteproc_state": remoteproc_state,
            "rpmsg_device": rpmsg_device,
            "guard_state": guard_state,
            "last_fault_code": last_fault_code,
            "active_job_id": active_job_id,
            "total_fault_count": total_fault_count,
            "trusted_sha": self._current_trusted_sha(current_board_access),
            "target": self._target_label,
            "runtime": self._runtime_label,
            "admission": admission,
            "variant_support": {
                "current": current_support,
                "baseline": baseline_support,
            },
            "last_probe_at": live_probe.get("requested_at", "") if live_probe else "",
            "status_source": status_source,
            "status_note": status_note,
            "telemetry": live_telemetry,
            "aircraft_bridge": aircraft_bridge,
            "board_position_api": board_position_api,
            "usrp_control": usrp_control_status,
        }
        event_spine_payload = {
            "api_path": "/api/event-spine",
            "session_id": event_spine["session_id"],
            "event_count": event_spine["aggregate"]["event_count"],
            "last_event_at": event_spine["aggregate"]["last_event_at"],
            "archive_enabled": event_spine["aggregate"]["archive"]["enabled"],
        }
        link_director = self.current_link_director_status()
        job_manifest_gate = self._job_manifest_gate_status(
            board_access=current_board_access,
            admission=admission,
            support=current_support,
            active_inference=active_inference,
            control_status=control_status,
            trusted_sha=self._current_trusted_sha(current_board_access),
            variant="current",
        )
        operator_cue = build_operator_cue(
            snapshot=snapshot,
            board_access=board_access_public,
            live=live_payload,
            active_inference=active_inference,
            last_inference=last_inference or {},
            safety_panel=safety_panel,
            gate=job_manifest_gate,
            link_director=link_director,
            event_spine=event_spine_payload,
        )

        return {
            "generated_at": snapshot["generated_at"],
            "board_access": board_access_public,
            "execution_mode": {
                "label": mode_label,
                "tone": mode_tone,
                "summary": mode_summary,
            },
            "aircraft_position": aircraft_position_payload,
            "live": live_payload,
            "active_inference": active_inference,
            "last_inference": last_inference or {},
            "recent_results": recent_inference_results,
            "last_fault": last_fault or {},
            "safety_panel": safety_panel,
            "job_manifest_gate": job_manifest_gate,
            "link_director": link_director,
            "operator_cue": operator_cue,
            "event_spine": event_spine_payload,
        }

    def current_event_spine(self, *, limit: int = 25) -> dict[str, Any]:
        return self._event_spine.summary(limit=limit)

    def list_archive_sessions(self, *, limit: int = 25) -> dict[str, Any]:
        return list_archive_sessions(
            self._event_archive_root,
            current_session_id=self._event_spine.session_id,
            limit=limit,
        )

    def current_archive_session(self, *, session_id: str = "", recent_limit: int = 25) -> dict[str, Any]:
        selected_session_id = str(session_id or "").strip()
        if not selected_session_id:
            sessions_payload = self.list_archive_sessions(limit=max(1, recent_limit))
            sessions = sessions_payload.get("sessions") if isinstance(sessions_payload.get("sessions"), list) else []
            if not sessions:
                raise ArchiveSessionNotFoundError("no archived sessions found")
            current_session_id = self._event_spine.session_id
            matching_current = next(
                (item for item in sessions if str(item.get("session_id") or "") == current_session_id),
                None,
            )
            selected_session_id = str(
                (matching_current or sessions[0]).get("session_id") or ""
            ).strip()
        return load_archive_session(
            self._event_archive_root,
            session_id=selected_session_id,
            recent_limit=recent_limit,
        )

    def _archive_event_snapshot(self, *, reason: str, job_id: str = "", extra: dict[str, Any] | None = None) -> None:
        self._event_spine.write_snapshot(reason=reason, job_id=job_id, extra=extra)

    def _emit_status_observation_events(self, payload: dict[str, Any], *, source: str, job_id: str = "") -> None:
        if payload.get("status") != "success":
            return
        heartbeat_ok = self._safe_int(payload.get("heartbeat_ok"), default=0)
        last_fault_code = str(payload.get("last_fault_code") or "").upper()
        if heartbeat_ok > 0:
            self._event_spine.publish(
                "HEARTBEAT_OK",
                job_id=job_id,
                source=source,
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Heartbeat acknowledgement is healthy on the demo control path.",
                data={
                    "heartbeat_ok": heartbeat_ok,
                    "guard_state": str(payload.get("guard_state") or ""),
                    "last_fault_code": last_fault_code,
                },
            )
        if last_fault_code == "HEARTBEAT_TIMEOUT":
            self._event_spine.publish(
                "HEARTBEAT_LOST",
                job_id=job_id,
                source=source,
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Heartbeat watchdog reported HEARTBEAT_TIMEOUT on the demo control path.",
                data={
                    "guard_state": str(payload.get("guard_state") or ""),
                    "last_fault_code": last_fault_code,
                },
            )

    def _emit_inference_rejection_events(
        self,
        *,
        variant: str,
        image_index: int,
        status_category: str,
        message: str,
        diagnostics: dict[str, Any],
    ) -> None:
        self._event_spine.publish(
            "JOB_SUBMITTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"{variant} demo launch requested by the operator.",
            data={
                "variant": variant,
                "image_index": image_index,
                "status_category": status_category,
            },
        )
        self._event_spine.publish(
            "JOB_REJECTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=message,
            data={
                "variant": variant,
                "image_index": image_index,
                "status_category": status_category,
                "diagnostics": diagnostics,
            },
        )
        self._archive_event_snapshot(
            reason="job_rejected",
            extra={
                "variant": variant,
                "image_index": image_index,
                "status_category": status_category,
            },
        )

    def _emit_job_event_once(
        self,
        record: dict[str, Any],
        event_type: str,
        *,
        source: str,
        plane: str,
        mode_scope: str,
        message: str,
        data: dict[str, Any],
    ) -> bool:
        event_marks = record.setdefault("event_marks", set())
        if event_type in event_marks:
            return False
        self._event_spine.publish(
            event_type,
            job_id=str(record.get("job_id") or ""),
            source=source,
            plane=plane,
            mode_scope=mode_scope,
            message=message,
            data=data,
        )
        event_marks.add(event_type)
        return True

    def _emit_inference_record_events(self, record: dict[str, Any], payload: dict[str, Any]) -> None:
        variant = str(record.get("variant") or "")
        job_id = str(record.get("job_id") or "")
        image_index = self._safe_int(record.get("image_index"), default=0)
        live_attempt = payload.get("live_attempt") if isinstance(payload.get("live_attempt"), dict) else {}
        control_transport = str(live_attempt.get("control_transport") or "hook").strip().lower()
        data_transport = str(live_attempt.get("data_transport") or "").strip().lower()
        common_data = {
            "variant": variant,
            "image_index": image_index,
            "status": str(payload.get("status") or ""),
            "request_state": str(payload.get("request_state") or ""),
            "status_category": str(payload.get("status_category") or ""),
            "control_transport": control_transport or "hook",
            "data_transport": data_transport or "tcp",
        }
        self._emit_job_event_once(
            record,
            "JOB_SUBMITTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"Live job {job_id} entered the demo submission spine.",
            data=common_data,
        )
        if payload.get("execution_mode") == "live" and control_transport != "none":
            admit_message = f"OpenAMP admitted live job {job_id}."
            if data_transport == "usrp":
                admit_message = f"Mixed-link live job {job_id} admitted on the TCP/ML-KEM control plane."
            elif control_transport == "mlkem":
                admit_message = f"ML-KEM/TCP control plane admitted live job {job_id}."
            self._emit_job_event_once(
                record,
                "JOB_ADMITTED",
                source="inference",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message=admit_message,
                data=common_data,
            )
        if payload.get("execution_mode") == "live":
            self._emit_job_event_once(
                record,
                "JOB_STARTED",
                source="inference",
                plane="data",
                mode_scope=DATA_MODE_SCOPE,
                message=f"Reconstruction execution started for job {job_id}.",
                data=common_data,
            )
        if payload.get("request_state") != "completed":
            return
        if payload.get("status") == "success":
            self._emit_job_event_once(
                record,
                "FRAME_RECON_READY",
                source="inference",
                plane="data",
                mode_scope=DATA_MODE_SCOPE,
                message=f"Reconstruction output is ready for job {job_id}.",
                data={
                    **common_data,
                    "sample_label": str(payload.get("sample", {}).get("label") or ""),
                    "artifact_sha": str(payload.get("artifact_sha") or ""),
                },
            )
            done_emitted = self._emit_job_event_once(
                record,
                "JOB_DONE",
                source="inference",
                plane="data",
                mode_scope=DATA_MODE_SCOPE,
                message=f"Reconstruction job {job_id} completed.",
                data={
                    **common_data,
                    "artifact_sha": str(payload.get("artifact_sha") or ""),
                    "total_ms": payload.get("timings", {}).get("total_ms"),
                },
            )
            if done_emitted:
                self._archive_event_snapshot(
                    reason="job_done",
                    job_id=job_id,
                    extra={
                        "variant": variant,
                        "image_index": image_index,
                    },
                )
            return
        rejected_emitted = self._emit_job_event_once(
            record,
            "JOB_REJECTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=str(payload.get("message") or "Live job fallback captured in the demo spine."),
            data={
                **common_data,
                "execution_mode": str(payload.get("execution_mode") or ""),
            },
        )
        if rejected_emitted:
            self._archive_event_snapshot(
                reason="job_fallback",
                job_id=job_id,
                extra={
                    "variant": variant,
                    "image_index": image_index,
                    "status_category": str(payload.get("status_category") or ""),
                },
            )

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _empty_live_timings() -> dict[str, Any]:
        return {
            "payload_ms": None,
            "prepare_ms": None,
            "total_ms": None,
            "stages": [],
        }

    @staticmethod
    def _extract_board_runner_summary(summary: Any) -> dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        pipeline_summary = summary.get("pipeline")
        if isinstance(pipeline_summary, dict) and pipeline_summary:
            return pipeline_summary
        return summary

    def _build_live_payload_from_batch_summary(
        self,
        *,
        engine: str,
        job_id: str,
        count: int,
        summary: dict[str, Any],
        message: str = "",
        source_label: str = "",
    ) -> dict[str, Any]:
        payload = self._build_prerecorded_payload_safe(image_index=0, variant="current")
        engine_key = "mnn" if str(engine).lower() == "mnn" else "tvm"
        engine_label = "MNN" if engine_key == "mnn" else "TVM"
        processed = self._status_int(summary.get("processed_count")) or 0
        selected = self._status_int(
            summary.get("selected_input_count") or summary.get("input_count") or summary.get("max_inputs"),
        ) or count
        total = max(processed, selected, 1)
        benchmark = _compute_mnn_benchmark(summary) if engine_key == "mnn" else _compute_tvm_benchmark(summary)
        total_metric = benchmark.get("total_ms") if isinstance(benchmark, dict) else None
        inference_metric = benchmark.get("inference_ms") if isinstance(benchmark, dict) else None
        total_ms = _benchmark_metric_value(total_metric) or _benchmark_metric_value(inference_metric)
        run_ms = _benchmark_metric_value(inference_metric) or total_ms
        payload.update(
            {
                "status": "success",
                "execution_mode": "live",
                "request_state": "completed",
                "status_category": "success",
                "variant": "current",
                "job_id": job_id,
                "source_label": source_label or f"USRP 混合链路在线推进 + {engine_label} 板端推理 + 归档样例图",
                "message": message or f"USRP 模式已完成 {engine_label} 板端推理；图像质量指标沿用当前归档样例口径。",
                "timings": {
                    "payload_ms": run_ms,
                    "prepare_ms": None,
                    "total_ms": total_ms,
                    "stages": [
                        {
                            "label": f"{engine_label} 板端推理",
                            "value_ms": run_ms,
                            "emphasis": "total",
                        }
                    ] if run_ms is not None else [],
                },
                "runner_summary": summary,
                "wrapper_summary": {
                    "inference_engine": engine_key,
                    "inference_summary": summary,
                    "inference_benchmark": benchmark,
                    "per_image_ms": total_ms,
                },
                "live_progress": {
                    "state": "completed",
                    "label": f"USRP + {engine_label} 推理完成",
                    "tone": "online",
                    "percent": 100,
                    "phase_percent": 100,
                    "completed_count": processed or total,
                    "expected_count": total,
                    "remaining_count": 0,
                    "completion_ratio": 1.0,
                    "count_source": "usrp_batch",
                    "count_label": f"{processed or total} / {total}",
                    "current_stage": f"{engine_label} 板端推理完成",
                    "stages": [],
                    "event_log": [],
                },
            }
        )
        if local_crypto_transport_mode(self._board_access.build_env()) == "usrp":
            original_gallery = build_original_gallery_snapshot("usrp", count=total)
            payload["original_gallery"] = original_gallery
            preview_image_b64 = str(original_gallery.get("preview_image_b64") or "")
            preview_image_path = str(original_gallery.get("preview_image_path") or "")
            if preview_image_b64:
                payload["original_image_b64"] = preview_image_b64
            if preview_image_path:
                image_sources = payload.get("image_sources") if isinstance(payload.get("image_sources"), dict) else {}
                payload["image_sources"] = {**image_sources, "original_path": preview_image_path}
            gallery_range = original_gallery.get("range") if isinstance(original_gallery.get("range"), dict) else {}
            payload["sample"] = {
                **(payload.get("sample") if isinstance(payload.get("sample"), dict) else {}),
                "label": str(original_gallery.get("label") or "USRP 原始图像"),
                "title": f"USRP 原始图像 {gallery_range.get('label') or ''}".strip(),
                "note": f"本轮 USRP 批量使用原始图像范围 {gallery_range.get('label') or ''}。",
            }
        return payload

    def refresh_live_probe(self) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access

        if board_access.probe_ready:
            result = run_live_probe(timeout_sec=self._probe_timeout_sec, env_values=board_access.build_env())
        else:
            result = run_live_probe(env_file=self._probe_env, timeout_sec=self._probe_timeout_sec)

        if is_successful_probe(result):
            with self._lock:
                self._last_live_probe = result
                if self._probe_cache_path:
                    write_probe_output(result, self._probe_cache_path)
            if board_access.probe_ready:
                current_board_access = self._live_board_access_for_variant(board_access, variant="current")
                status_payload = query_live_status(
                    board_access,
                    trusted_sha=expected_sha_for_variant(current_board_access, "current") or self._trusted_current_sha,
                )
                if status_payload.get("status") == "success":
                    with self._lock:
                        self._last_control_status = status_payload
                    self._emit_status_observation_events(status_payload, source="probe_status")
                result["control_status"] = status_payload
            self._archive_event_snapshot(
                reason="probe_refresh",
                extra={"requested_at": str(result.get("requested_at") or "")},
            )
        return result

    def _can_launch_runner_only_fallback(
        self,
        *,
        board_access,
        status_payload: dict[str, Any],
    ) -> bool:
        if not board_access.connection_ready:
            return False
        status_category = str(status_payload.get("status_category") or "")
        return status_category in {"timeout", "permission_error", "error", "host_env_error"}

    def _build_inference_response(self, record: dict[str, Any], live_attempt: dict[str, Any]) -> dict[str, Any]:
        variant = str(record["variant"])
        image_index = int(record["image_index"])
        control_transport = str(live_attempt.get("control_transport") or "hook").strip().lower()
        data_transport = str(live_attempt.get("data_transport") or "").strip().lower()
        runner_summary = live_attempt.get("runner_summary") if isinstance(live_attempt.get("runner_summary"), dict) else {}
        diagnostics_payload = live_attempt.get("diagnostics") if isinstance(live_attempt.get("diagnostics"), dict) else {}
        input_source_label = str(
            runner_summary.get("input_source_label")
            or diagnostics_payload.get("input_source_label")
            or ""
        ).strip()

        def with_input_source(base_label: str) -> str:
            if not input_source_label or input_source_label in base_label:
                return base_label
            return f"{base_label} / {input_source_label}"

        runner_only_mode = control_transport == "none"
        usrp_mode = data_transport == "usrp"
        security_protocol = str(record.get("security_protocol") or "").strip().lower()
        security_handshake_ms = record.get("security_handshake_ms")
        security_summary = str(record.get("security_summary") or "").strip()
        security_armed = security_protocol == "mlkem_control"
        live_attempt_payload = dict(live_attempt)
        if security_armed:
            live_attempt_payload["security"] = {
                "protocol": security_protocol,
                "handshake_ms": security_handshake_ms,
                "summary": security_summary,
                "channel_state": str(record.get("security_channel_state") or ""),
            }
        payload = build_prerecorded_inference_result(image_index, variant)
        progress = live_attempt.get("progress", {})
        payload["job_id"] = record["job_id"]
        payload["request_state"] = live_attempt.get("request_state", "completed")
        payload["live_progress"] = progress

        if live_attempt.get("request_state") == "running":
            payload.update(
                {
                    "status": "running",
                    "execution_mode": "live",
                    "status_category": "running",
                    "source_label": with_input_source(
                        "ML-KEM 安全协议就绪 + USRP 混合链路在线推进"
                        if usrp_mode and security_armed
                        else (
                            "USRP 混合链路在线推进"
                            if usrp_mode
                            else (
                                "ML-KEM 安全协议就绪 + 真实在线执行（控制面降级）"
                                if security_armed and runner_only_mode
                                else (
                                    "ML-KEM 安全协议就绪 + 真实在线推进"
                                    if security_armed
                                    else ("真实在线执行（控制面降级）" if runner_only_mode else "真实在线推进")
                                )
                            )
                        )
                    ),
                    "message": (
                        live_attempt.get("message")
                        or (
                            (
                                f"{security_summary} 数据面已切到 USRP 射频链路，界面正在同步当前 2922 批处理进度。"
                                if usrp_mode and security_armed
                                else (
                                    "当前演示已切到 USRP 数据面，界面正在同步 2922 批处理进度；图像对比继续使用归档样例。"
                                    if usrp_mode
                                    else (
                                        (
                                            f"{security_summary} 控制面预检未通过后已切到 SSH 兼容模式，"
                                            "界面正在同步板端本地 latent 重建进度。"
                                        )
                                        if security_armed and runner_only_mode
                                        else (
                                            f"{security_summary} 界面正在同步板端本地 latent 重建进度。"
                                            if security_armed
                                            else (
                                                "控制面预检未通过后已切到 SSH 兼容模式，界面正在同步板端执行进度。"
                                                if runner_only_mode
                                                else "OpenAMP 控制面已接入本次演示，界面正在同步板端推进阶段。"
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    ),
                    "timings": self._empty_live_timings(),
                    "quality": payload["quality"],
                    "live_attempt": live_attempt_payload,
                }
            )
            return payload

        if live_attempt.get("status") == "success":
            summary = live_attempt["runner_summary"]
            wrapper_summary = live_attempt.get("wrapper_summary", {})
            board_summary = self._extract_board_runner_summary(summary)
            pipeline_summary_used = board_summary is not summary
            load_ms = round(float(board_summary.get("load_ms") or 0.0), 3)
            vm_init_ms = round(float(board_summary.get("vm_init_ms") or 0.0), 3)
            board_endpoint_ms_raw = board_summary.get("ms_per_image")
            board_payload_ms_raw = board_endpoint_ms_raw
            if board_payload_ms_raw is None:
                board_payload_ms_raw = board_summary.get("run_median_ms")
            if board_payload_ms_raw is None:
                board_payload_ms_raw = board_summary.get("run_mean_ms")
            live_stages = []
            board_payload_ms = (
                round(float(board_payload_ms_raw), 3)
                if board_payload_ms_raw is not None
                else None
            )
            inference_engine = str(wrapper_summary.get("inference_engine") or "").strip().lower()
            if not inference_engine and usrp_mode:
                inference_summary = wrapper_summary.get("inference_summary")
                if isinstance(inference_summary, dict):
                    if isinstance(inference_summary.get("sample_stats"), dict):
                        inference_engine = "mnn"
                    else:
                        inference_engine = "tvm"
            if inference_engine:
                payload["inference_engine"] = inference_engine
            if pipeline_summary_used and board_endpoint_ms_raw is not None:
                live_stages.append(
                    {
                        "label": "板端重建（流水线）",
                        "value_ms": board_payload_ms,
                        "emphasis": "total",
                    }
                )
            else:
                live_stages.extend(
                    [
                        {
                            "label": "板端装载",
                            "value_ms": load_ms,
                            "emphasis": "host",
                        },
                        {
                            "label": "板端初始化",
                            "value_ms": vm_init_ms,
                            "emphasis": "board",
                        },
                    ]
                )
                if board_payload_ms is not None:
                    live_stages.append(
                        {
                            "label": "板端推理",
                            "value_ms": board_payload_ms,
                            "emphasis": "total",
                        }
                    )
            live_total_ms = wrapper_summary.get("per_image_ms")
            if live_total_ms is None:
                live_total_ms = board_endpoint_ms_raw
            if pipeline_summary_used and live_total_ms is not None:
                live_total_ms = round(float(live_total_ms), 3)
            elif live_total_ms is not None:
                live_total_ms = round(load_ms + vm_init_ms + float(live_total_ms), 3)
            else:
                live_total_ms = round(sum(item["value_ms"] for item in live_stages), 3)
            payload.update(
                {
                    "status": "success",
                    "execution_mode": "live",
                    "status_category": "success",
                    "source_label": with_input_source(
                        "ML-KEM 安全协议就绪 + USRP 混合链路在线推进 + 归档样例图"
                        if usrp_mode and security_armed
                        else (
                            "USRP 混合链路在线推进 + 归档样例图"
                            if usrp_mode
                            else (
                                "ML-KEM 安全协议就绪 + 真实在线执行（控制面降级） + 归档样例图"
                                if security_armed and runner_only_mode
                                else (
                                    "ML-KEM 安全协议就绪 + 真实在线推进 + 归档样例图"
                                    if security_armed
                                    else (
                                        "真实在线执行（控制面降级） + 归档样例图"
                                        if runner_only_mode
                                        else "真实在线推进 + 归档样例图"
                                    )
                                )
                            )
                        )
                    ),
                    "message": live_attempt.get("message")
                    or (
                        (
                            f"{security_summary} 数据面已通过 USRP 射频链路完成传输；图像对比继续使用归档样例，"
                            "链路指标来自当前 2922 运行时。"
                            if usrp_mode and security_armed
                            else (
                                "本次演示已通过 USRP 射频链路完成数据面传输；图像对比继续使用归档样例，"
                                "链路指标来自当前 2922 运行时。"
                                if usrp_mode
                                else (
                                    (
                                        f"{security_summary} 本次重建未通过 TCP 批量搬运 latent；"
                                        "真实重建继续使用板端本地 latent / 既有 live 数据面，图像对比继续使用归档样例。"
                                    )
                                    if security_armed
                                    else (
                                        "本次演示已通过 OpenAMP 控制面完成作业下发、板端执行与结果回收；图像对比继续使用归档样例，"
                                        "现场呈现更稳定。"
                                        if not runner_only_mode
                                        else (
                                            "本次演示已在 SSH 兼容模式下完成真实板端执行；"
                                            "图像对比继续使用归档样例，当前不宣称控制面握手已成功。"
                                        )
                                    )
                                )
                            )
                        )
                    ),
                    "timings": {
                        "payload_ms": board_payload_ms,
                        "prepare_ms": round(load_ms + vm_init_ms, 3),
                        "total_ms": round(float(live_total_ms), 3),
                        "stages": live_stages,
                    },
                    "artifact_sha": board_summary.get("artifact_sha256") or summary.get("artifact_sha256") or payload["artifact_sha"],
                    "runner_summary": summary,
                    "wrapper_summary": wrapper_summary,
                    "quality": payload["quality"],
                    "live_attempt": live_attempt_payload,
                }
            )
            return payload

        payload.update(
            {
                "status": "fallback",
                "execution_mode": "prerecorded",
                "status_category": live_attempt.get("status_category", "fallback"),
                "source_label": with_input_source(
                    "握手未完成，回退展示（归档样例）"
                    if live_attempt.get("control_handshake_complete") is False
                    else "回退展示（归档样例）"
                ),
                "message": (
                    f"{live_attempt.get('message', '在线推进未完成')}"
                    + (
                        " 当前画面仅显示归档样例与正式报告，不宣称本次 live 已完成。"
                        if live_attempt.get("control_handshake_complete") is False
                        else " 当前画面已切回归档样例，上方阶段条保留本次真机推进停留点。"
                    )
                ),
                "timings": self._empty_live_timings(),
                "live_attempt": live_attempt_payload,
            }
        )
        return payload

    def _hydrate_recent_inference_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        cached_payload = _json_safe_copy(payload)
        live_attempt = (
            cached_payload.get("live_attempt")
            if isinstance(cached_payload.get("live_attempt"), dict)
            else {}
        )
        runner_summary = (
            cached_payload.get("runner_summary")
            if isinstance(cached_payload.get("runner_summary"), dict)
            else {}
        )
        wrapper_summary = (
            cached_payload.get("wrapper_summary")
            if isinstance(cached_payload.get("wrapper_summary"), dict)
            else {}
        )
        if not runner_summary and isinstance(live_attempt.get("runner_summary"), dict):
            runner_summary = live_attempt["runner_summary"]
            cached_payload["runner_summary"] = runner_summary
        if not wrapper_summary and isinstance(live_attempt.get("wrapper_summary"), dict):
            wrapper_summary = live_attempt["wrapper_summary"]
            cached_payload["wrapper_summary"] = wrapper_summary

        board_summary = self._extract_board_runner_summary(runner_summary)
        run_id = (
            str(cached_payload.get("run_id") or "").strip()
            or str(runner_summary.get("run_id") or "").strip()
            or str(wrapper_summary.get("run_id") or "").strip()
            or str(board_summary.get("run_id") or "").strip()
        )
        if run_id:
            cached_payload["run_id"] = run_id

        processed = (
            self._status_int(cached_payload.get("processed_count"))
            or self._status_int(board_summary.get("processed_count"))
            or self._status_int(board_summary.get("output_count"))
            or self._status_int(board_summary.get("run_count"))
            or self._status_int(runner_summary.get("processed_count"))
            or self._status_int(wrapper_summary.get("processed_count"))
        )
        if processed:
            cached_payload["processed_count"] = processed
            cached_payload.setdefault("completed_count", processed)

        selected = (
            self._status_int(cached_payload.get("selected_input_count"))
            or self._status_int(board_summary.get("selected_input_count"))
            or self._status_int(board_summary.get("input_count"))
            or self._status_int(board_summary.get("available_input_count"))
            or self._status_int(runner_summary.get("selected_input_count"))
            or self._status_int(wrapper_summary.get("selected_input_count"))
        )
        if selected:
            cached_payload["selected_input_count"] = selected

        benchmark = (
            cached_payload.get("inference_benchmark")
            if isinstance(cached_payload.get("inference_benchmark"), dict)
            else None
        )
        if benchmark is None:
            benchmark = (
                wrapper_summary.get("inference_benchmark")
                if isinstance(wrapper_summary.get("inference_benchmark"), dict)
                else None
            )
        if benchmark is None or not benchmark.get("inference_ms"):
            candidate = (
                _compute_mnn_benchmark(board_summary)
                if isinstance(board_summary.get("sample_stats"), dict)
                else _compute_tvm_benchmark(runner_summary or board_summary)
            )
            if isinstance(candidate.get("inference_ms"), dict):
                benchmark = candidate
        if isinstance(benchmark, dict) and benchmark.get("inference_ms"):
            cached_payload["inference_benchmark"] = benchmark
            cached_payload["benchmark"] = benchmark

        return cached_payload

    def _update_last_inference_summary(self, payload: dict[str, Any], variant: str) -> None:
        cached_payload = self._hydrate_recent_inference_payload(payload)
        timings = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}
        sample = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}
        self._last_inference_result = {
            "status": payload.get("status", ""),
            "execution_mode": payload.get("execution_mode", ""),
            "status_category": payload.get("status_category", "fallback"),
            "variant": variant,
            "total_ms": timings.get("total_ms"),
            "artifact_sha": payload.get("artifact_sha"),
            "message": payload.get("message", ""),
            "source_label": payload.get("source_label", ""),
            "sample_label": sample.get("label", ""),
            "request_state": payload.get("request_state", "completed"),
        }
        self._recent_inference_results[variant] = cached_payload

    def _running_inference_job_record(self) -> dict[str, Any] | None:
        with self._lock:
            records = list(self._inference_jobs.values())
        for record in records:
            try:
                snapshot = record["job"].snapshot()
            except Exception:
                snapshot = record.get("last_snapshot")
                if not isinstance(snapshot, dict):
                    continue
            else:
                with self._lock:
                    current_record = self._inference_jobs.get(str(record.get("job_id") or ""))
                    if current_record is not None:
                        current_record["last_snapshot"] = snapshot
            if snapshot.get("request_state") == "running":
                return {
                    "job_id": record["job_id"],
                    "variant": record["variant"],
                    "snapshot": snapshot,
                }
        return None

    def _blocked_live_progress(
        self,
        *,
        label: str,
        detail: str,
        expected_count: int = DEFAULT_MAX_INPUTS,
        event_log: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "state": "completed",
            "label": label,
            "tone": "degraded",
            "percent": 0,
            "phase_percent": 100,
            "completed_count": 0,
            "expected_count": expected_count,
            "remaining_count": expected_count,
            "completion_ratio": 0.0,
            "count_source": "demo_default",
            "count_label": f"0 / {expected_count}",
            "current_stage": "未发起 live launch",
            "stages": [
                {
                    "key": "launch_guard",
                    "label": "启动前检查",
                    "status": "error",
                    "detail": detail,
                }
            ],
            "event_log": list(event_log or []),
        }

    def _build_blocked_inference_payload(
        self,
        *,
        variant: str,
        image_index: int,
        status_category: str,
        source_label: str,
        message: str,
        detail: str,
        diagnostics: dict[str, Any],
        expected_count: int = DEFAULT_MAX_INPUTS,
        event_log: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = self._build_prerecorded_payload_safe(image_index=image_index, variant=variant)
        fallback_timings = (
            payload.get("timings")
            if str(variant or "").strip().lower() == "baseline" and isinstance(payload.get("timings"), dict)
            else self._empty_live_timings()
        )
        fallback_execution_mode = (
            payload.get("execution_mode")
            if str(variant or "").strip().lower() == "baseline"
            else "prerecorded"
        )
        payload.update(
            {
                "status": "fallback",
                "execution_mode": fallback_execution_mode,
                "request_state": "completed",
                "status_category": status_category,
                "source_label": source_label,
                "message": message,
                "timings": fallback_timings,
                "live_progress": self._blocked_live_progress(
                    label=source_label,
                    detail=detail,
                    expected_count=expected_count,
                    event_log=event_log,
                ),
                "live_attempt": {
                    "status": "blocked",
                    "request_state": "completed",
                    "status_category": status_category,
                    "message": message,
                    "diagnostics": _json_safe_copy(diagnostics),
                },
            }
        )
        return payload

    def _build_prerecorded_payload_safe(self, *, image_index: int, variant: str) -> dict[str, Any]:
        """Return a prerecorded payload template, tolerating out-of-range indices.

        Batch live runs can request many indices (e.g. 0..299), while prerecorded
        assets are a smaller fixed subset. For live path accounting, we keep the
        requested index and reuse a stable template when index is out of range.
        """
        try:
            payload = build_prerecorded_inference_result(image_index, variant)
        except IndexError:
            payload = build_prerecorded_inference_result(0, variant)
            payload["message"] = (
                f"image_index={image_index} 超出预录样例范围，已复用 index=0 模板承载本次 live 结果。"
            )
        payload["image_index"] = image_index
        return payload

    def _parse_mlkem_client_metrics(self, stdout: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "handshake_ms": None,
            "encrypt_ms": None,
            "decrypt_ms": None,
            "inference_ms": None,
            "result_recv_ms": None,
            "sha256_match": None,
            "result_received": None,
            "bytes_sent": None,
            "bytes_received": None,
            "suite": "",
            "backend": "",
            "auth_enabled": None,
            "sig_policy": "",
            "server_id": "",
        }
        for line in stdout.splitlines():
            text = str(line).strip()
            if not text:
                continue
            if text.startswith("密码套件:"):
                metrics["suite"] = text.split(":", 1)[1].strip()
            elif text.startswith("KEM 后端:"):
                metrics["backend"] = text.split(":", 1)[1].strip()
            elif "握手完成" in text:
                m = re.search(r"([\d.]+)\s*ms", text)
                if m:
                    metrics["handshake_ms"] = float(m.group(1))
            elif "加密发送" in text:
                m = re.search(r"(\d+)\s*B", text)
                if m:
                    metrics["bytes_sent"] = int(m.group(1))
                m = re.search(r"耗时\s*([\d.]+)\s*ms", text)
                if m:
                    metrics["encrypt_ms"] = float(m.group(1))
            elif "接收重建结果" in text:
                m = re.search(r"(\d+)\s*B", text)
                if m:
                    metrics["bytes_received"] = int(m.group(1))
                m = re.search(r"耗时\s*([\d.]+)\s*ms", text)
                if m:
                    metrics["result_recv_ms"] = float(m.group(1))
                    metrics["decrypt_ms"] = metrics["result_recv_ms"]
                metrics["result_received"] = True
            elif "TVM 推理耗时" in text:
                m = re.search(r"([\d.]+)\s*ms", text)
                if m:
                    metrics["inference_ms"] = float(m.group(1))
            elif text.startswith("身份认证:"):
                metrics["auth_enabled"] = "已启用" in text
                m = re.search(r"\(([^)]+)\)", text)
                if m:
                    metrics["sig_policy"] = m.group(1).strip()
            elif text.startswith("服务端标识:"):
                metrics["server_id"] = text.split(":", 1)[1].strip()
            elif "板端重建结果:" in text:
                if "已回传" in text:
                    metrics["result_received"] = True
                elif "未回传" in text:
                    metrics["result_received"] = False
            elif "对端 SHA256 匹配: 是" in text or "SHA256 匹配" in text:
                metrics["sha256_match"] = True
            elif "SHA256 不匹配" in text:
                metrics["sha256_match"] = False
        return metrics

    # ── 批量推理 ──────────────────────────────────────────────────────────────

    def get_batch_state(self) -> dict[str, Any]:
        with self._lock:
            state = self._batch_state
        if state is None:
            return {"status": "idle"}
        return dict(state)

    def _mnn_batch_access(self) -> BoardAccessConfig:
        with self._lock:
            board_access = self._board_access
        if DEFAULT_MNN_BATCH_ENV_FILE.is_file():
            _, mnn_env_values = load_env_file(str(DEFAULT_MNN_BATCH_ENV_FILE))
            runtime_env_values = board_access.build_env()
            for key in (
                "MLKEM_TRANSPORT_MODE",
                "OPENAMP_DEMO_INPUT_SOURCE_MODE",
                "REMOTE_INPUT_SOURCE_MODE",
                "REMOTE_USRP_RX_DIR",
            ):
                value = str(runtime_env_values.get(key, "") or "").strip()
                if value:
                    mnn_env_values[key] = value
            return board_access.with_env_overrides(mnn_env_values)
        return board_access

    def _run_mnn_batch(self, *, count: int = 300, progress_callback: Any = None) -> dict[str, Any]:
        access = self._mnn_batch_access()
        return self._run_mnn_batch_with_access(access, count=count, progress_callback=progress_callback)

    def _run_mnn_batch_with_access(
        self,
        access: BoardAccessConfig,
        *,
        count: int = 300,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        env_values = access.build_env()
        missing = access.missing_connection_fields()
        input_source_mode = current_input_source_mode(env_values)
        required_input_key = "REMOTE_USRP_RX_DIR" if input_source_mode == "usrp" else "REMOTE_INPUT_DIR"
        for key in ("REMOTE_MNN_PYTHON", required_input_key, "REMOTE_OUTPUT_BASE", "MNN_FP32_MODEL", "REMOTE_SNR_CURRENT"):
            if not str(env_values.get(key, "")).strip():
                missing.append(key)
        if missing:
            return {
                "status": "config_error",
                "message": f"MNN 推理配置不完整: {', '.join(missing)}",
                "errors": [f"missing_fields={', '.join(missing)}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        output_prefix = f"mnn_demo_batch_{int(time.time())}"
        command = [
            resolve_bash_executable(),
            str(REMOTE_MNN_RECONSTRUCTION_SCRIPT),
            "--variant",
            "current",
            "--model-path",
            str(env_values.get("MNN_FP32_MODEL") or ""),
            "--max-inputs",
            str(max(1, count)),
            "--warmup-inputs",
            "0",
            "--output-prefix",
            output_prefix,
        ]
        env = access.build_subprocess_env()
        if not str(env_values.get("MNN_EXTRA_PYTHONPATH", "")).strip():
            env.pop("REMOTE_TORCH_PYTHONPATH", None)
            env.pop("REMOTE_REAL_EXTRA_PYTHONPATH", None)
            env.pop("MNN_EXTRA_PYTHONPATH", None)
        env["REMOTE_MODE"] = "ssh"
        timeout_sec = max(900.0, float(max(1, count)) * 5.0)
        try:
            proc = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            return {
                "status": "launch_error",
                "message": f"MNN 推理启动失败: {exc}",
                "errors": [f"{type(exc).__name__}: {exc}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        stdout_lines: list[str] = []
        stderr_text = ""
        timeout_flag = {"value": False}
        completed_count = 0
        def _kill_proc_on_timeout() -> None:
            timeout_flag["value"] = True
            try:
                proc.kill()
            except OSError:
                pass

        timer = threading.Timer(timeout_sec, _kill_proc_on_timeout)
        timer.start()
        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                stdout_lines.append(raw_line)
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    line_payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                progress_payload = line_payload.get("openamp_demo_progress") if isinstance(line_payload, dict) else None
                if not isinstance(progress_payload, dict):
                    continue
                try:
                    delta = int(progress_payload.get("delta") or 0)
                except (TypeError, ValueError):
                    delta = 0
                if delta <= 0:
                    continue
                completed_count = min(max(1, count), completed_count + delta)
                if progress_callback is not None:
                    progress_callback(completed_count, max(1, count))
            proc.wait()
            if proc.stderr is not None:
                stderr_text = proc.stderr.read()
        finally:
            timer.cancel()

        if proc.returncode is None:
            proc.kill()
            proc.wait()

        if timeout_flag["value"]:
            return {
                "status": "timeout",
                "message": "MNN 300 张批量推理超时。",
                "errors": ["TimeoutExpired: MNN batch timed out"],
                "selected_input_count": count,
                "processed_count": completed_count,
            }

        stdout_text = "".join(stdout_lines)
        try:
            payload = _parse_json_stdout_payload(stdout_text)
        except (json.JSONDecodeError, ValueError) as exc:
            stderr = (stderr_text or "").strip()
            stdout = stdout_text.strip()
            detail = stderr or stdout or str(exc)
            return {
                "status": "parse_error",
                "message": f"MNN 推理结果解析失败: {detail}",
                "errors": [f"{type(exc).__name__}: {detail}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        if progress_callback is not None:
            processed = int(payload.get("processed_count") or completed_count or 0)
            if processed > completed_count:
                progress_callback(min(processed, max(1, count)), max(1, int(payload.get("selected_input_count") or count or 1)))

        if proc.returncode != 0 and str(payload.get("status") or "").lower() == "ok":
            payload["status"] = "error"
        if proc.returncode != 0 and not payload.get("errors"):
            payload["errors"] = [((stderr_text or "").strip() or stdout_text.strip() or f"returncode={proc.returncode}")]
        return payload

    def _run_tvm_batch_with_access(
        self,
        access: BoardAccessConfig,
        *,
        count: int = 300,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        env_values = access.build_env()
        missing = access.missing_inference_fields("current")
        if missing:
            return {
                "status": "config_error",
                "message": f"TVM 推理配置不完整: {', '.join(missing)}",
                "errors": [f"missing_fields={', '.join(missing)}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        runner_script = BIG_LITTLE_PIPELINE_SCRIPT if _current_tvm_batch_uses_big_little(env_values) else REMOTE_TVM_RECONSTRUCTION_SCRIPT
        command = [
            resolve_bash_executable(),
            str(runner_script),
            "--variant",
            "current",
            "--max-inputs",
            str(max(1, count)),
            "--seed",
            "0",
        ]
        env = access.build_subprocess_env()
        env["REMOTE_MODE"] = "ssh"
        env[DEMO_MODE_ENV] = "1"
        env[DEMO_MAX_INPUTS_ENV] = str(max(1, count))
        timeout_sec = max(900.0, float(max(1, count)) * 5.0)
        try:
            proc = subprocess.Popen(
                command,
                cwd=REPO_ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            return {
                "status": "launch_error",
                "message": f"TVM 推理启动失败: {exc}",
                "errors": [f"{type(exc).__name__}: {exc}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_queue: queue.Queue[Any] = queue.Queue()
        stdout_done = {"value": False}
        timeout_flag = {"value": False}
        stale_wrapper_after_complete = {"value": False}
        completed_count = 0
        all_progress_received = {"value": False}
        progress_done_deadline = {"value": 0.0}
        stdout_sentinel = object()

        def _kill_proc_on_timeout() -> None:
            timeout_flag["value"] = True
            try:
                if os.name == "nt" and getattr(proc, "pid", None):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    proc.kill()
            except OSError:
                try:
                    proc.kill()
                except OSError:
                    pass

        def _read_stdout() -> None:
            try:
                if proc.stdout is not None:
                    for raw_line in proc.stdout:
                        stdout_queue.put(raw_line)
            finally:
                stdout_queue.put(stdout_sentinel)

        def _read_stderr() -> None:
            if proc.stderr is None:
                return
            read_any = False
            try:
                for raw_line in proc.stderr:
                    stderr_lines.append(raw_line)
                    read_any = True
                if not read_any and hasattr(proc.stderr, "read"):
                    tail = proc.stderr.read()
                    if tail:
                        stderr_lines.append(tail)
            except TypeError:
                stderr_lines.append(proc.stderr.read())

        def _process_stdout_line(raw_line: str) -> None:
            nonlocal completed_count
            stdout_lines.append(raw_line)
            stripped = raw_line.strip()
            if not stripped:
                return
            try:
                line_payload = json.loads(stripped)
            except json.JSONDecodeError:
                return
            progress_payload = line_payload.get("openamp_demo_progress") if isinstance(line_payload, dict) else None
            if not isinstance(progress_payload, dict):
                return
            try:
                delta = int(progress_payload.get("delta") or 0)
            except (TypeError, ValueError):
                delta = 0
            if delta <= 0:
                return
            try:
                completed_from_payload = int(progress_payload.get("completed_count") or 0)
            except (TypeError, ValueError):
                completed_from_payload = 0
            completed_count = min(max(1, count), max(completed_from_payload, completed_count + delta))
            if progress_callback is not None:
                progress_callback(completed_count, max(1, count))
            if completed_count >= count and not all_progress_received["value"]:
                all_progress_received["value"] = True
                grace_raw = env.get("OPENAMP_TVM_BATCH_EXIT_GRACE_SEC") or os.environ.get("OPENAMP_TVM_BATCH_EXIT_GRACE_SEC", "5.0")
                try:
                    grace_sec = max(0.1, float(grace_raw))
                except (TypeError, ValueError):
                    grace_sec = 5.0
                progress_done_deadline["value"] = time.monotonic() + grace_sec

        def _drain_stdout_queue(*, block: bool = False) -> None:
            while True:
                try:
                    item = stdout_queue.get(timeout=0.05 if block else 0.0)
                except queue.Empty:
                    return
                if item is stdout_sentinel:
                    stdout_done["value"] = True
                    continue
                _process_stdout_line(str(item))
                block = False

        stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        deadline = time.monotonic() + timeout_sec
        while True:
            _drain_stdout_queue(block=True)
            poll = getattr(proc, "poll", None)
            returncode = poll() if callable(poll) else getattr(proc, "returncode", None)
            if returncode is not None:
                break
            now = time.monotonic()
            if all_progress_received["value"] and progress_done_deadline["value"] and now >= progress_done_deadline["value"]:
                stale_wrapper_after_complete["value"] = True
                _kill_proc_on_timeout()
                break
            if now >= deadline:
                _kill_proc_on_timeout()
                break

        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            _kill_proc_on_timeout()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass

        stdout_thread.join(timeout=2.0)
        stderr_thread.join(timeout=2.0)
        _drain_stdout_queue(block=False)
        stderr_text = "".join(stderr_lines)

        proc_returncode = getattr(proc, "returncode", None)

        stdout_text = "".join(stdout_lines)
        try:
            payload = _parse_json_stdout_payload(stdout_text)
            payload = _flatten_big_little_pipeline_payload(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            if timeout_flag["value"]:
                return {
                    "status": "timeout",
                    "message": "TVM 批量推理超时。",
                    "errors": ["TimeoutExpired: TVM batch timed out"],
                    "selected_input_count": count,
                    "processed_count": completed_count,
                }
            stderr = (stderr_text or "").strip()
            stdout = stdout_text.strip()
            detail = stderr or stdout or str(exc)
            return {
                "status": "parse_error",
                "message": f"TVM 推理结果解析失败: {detail}",
                "errors": [f"{type(exc).__name__}: {detail}"],
                "selected_input_count": count,
                "processed_count": 0,
            }

        try:
            parsed_processed = int(payload.get("processed_count") or completed_count or 0)
        except (TypeError, ValueError):
            parsed_processed = completed_count
        try:
            parsed_selected = int(payload.get("selected_input_count") or payload.get("input_count") or count or 1)
        except (TypeError, ValueError):
            parsed_selected = max(1, count)
        complete_payload = parsed_processed >= max(1, min(max(1, parsed_selected), max(1, count)))
        if complete_payload and not str(payload.get("status") or "").strip() and not payload.get("errors"):
            payload["status"] = "ok"

        if timeout_flag["value"] and not complete_payload:
            return {
                "status": "timeout",
                "message": "TVM 批量推理超时。",
                "errors": ["TimeoutExpired: TVM batch timed out"],
                "selected_input_count": count,
                "processed_count": completed_count,
            }

        if progress_callback is not None:
            processed = parsed_processed
            selected = parsed_selected
            if processed > completed_count:
                progress_callback(min(processed, max(1, selected)), max(1, selected))

        if timeout_flag["value"] and complete_payload:
            payload["wrapper_timeout_recovered"] = True
        if stale_wrapper_after_complete["value"] and complete_payload:
            payload["stale_wrapper_after_complete"] = True
        if proc_returncode != 0 and str(payload.get("status") or "ok").lower() in {"ok", "success"} and not complete_payload:
            payload["status"] = "error"
        if proc_returncode != 0 and not payload.get("errors") and not complete_payload:
            payload["errors"] = [((stderr_text or "").strip() or stdout_text.strip() or f"returncode={proc.returncode}")]
        return payload

    def _usrp_stage_access(
        self,
        base_access: BoardAccessConfig,
        remote_stage_manifest: dict[str, Any],
        *,
        engine: str = INFERENCE_ENGINE_TVM,
    ) -> BoardAccessConfig:
        base_env = base_access.build_env()
        remote_dir = str(remote_stage_manifest.get("remote_dir") or "").strip()
        if not remote_dir:
            remote_dir = str(base_env.get("REMOTE_USRP_RX_DIR") or "").strip()
        remote_run_name = Path(remote_dir.rstrip("/")).name or f"usrp-{int(time.time())}"
        run_token = remote_run_name.removeprefix("cockpit_usrp_").removesuffix("_rx").removeprefix("usrp-")
        safe_run_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_token).strip("_.-") or str(int(time.time()))
        usrp_output_prefix = f"openamp3_usrp_{safe_run_name}"
        output_root = first_config_value(
            base_env,
            keys=USRP_REMOTE_OUTPUT_ROOT_KEYS,
            default=DEFAULT_USRP_REMOTE_OUTPUT_ROOT,
        )
        output_engine = "mnn" if str(engine).lower() == INFERENCE_ENGINE_MNN else "tvm"
        usrp_output_base = f"{output_root.rstrip('/')}/{output_engine}"
        return base_access.with_env_overrides(
            {
                "OPENAMP_DEMO_INPUT_SOURCE_MODE": "usrp",
                "REMOTE_INPUT_SOURCE_MODE": "usrp",
                "REMOTE_USRP_RX_DIR": remote_dir,
                "REMOTE_INPUT_DIR": remote_dir,
                "REMOTE_OUTPUT_BASE": usrp_output_base,
                "INFERENCE_REAL_OUTPUT_PREFIX": usrp_output_prefix,
                "BIG_LITTLE_OUTPUT_PREFIX": usrp_output_prefix,
                "BIG_LITTLE_REPORT_PREFIX": usrp_output_prefix,
            }
        )

    def _run_tvm_after_usrp_stage(
        self,
        base_access: BoardAccessConfig,
        *,
        count: int,
        progress_callback: Any = None,
    ) -> Any:
        def _callback(remote_stage_manifest: dict[str, Any], progress: Any) -> dict[str, Any]:
            access = self._usrp_stage_access(base_access, remote_stage_manifest, engine=INFERENCE_ENGINE_TVM)
            env_values = access.build_env()
            if not str(env_values.get("BIG_LITTLE_INPUT_WAIT_TIMEOUT_SEC") or "").strip():
                access = access.with_env_overrides(
                    {
                        "BIG_LITTLE_INPUT_WAIT_TIMEOUT_SEC": str(max(60.0, float(max(1, count)))),
                        "BIG_LITTLE_INPUT_POLL_SEC": str(env_values.get("BIG_LITTLE_INPUT_POLL_SEC") or "0.05"),
                    }
                )
            progress_callback_to_use = progress_callback or progress
            progress_callback_to_use(0, max(1, count))
            result = self._run_tvm_batch_with_access(
                access,
                count=max(1, count),
                progress_callback=progress_callback_to_use,
            )
            status_text = str(result.get("status") or "").lower()
            if status_text in {"ok", "success"}:
                processed = int(result.get("processed_count") or 0)
                selected = int(result.get("selected_input_count") or result.get("input_count") or max(1, count))
                progress_callback_to_use(processed, max(1, selected))
                return {"status": "ok", **result}
            error_text = str(result.get("message") or "TVM 推理失败")
            return {
                "status": "error",
                "message": error_text,
                "errors": [error_text],
                "processed_count": 0,
                "selected_input_count": max(1, count),
                "runner_result": result,
            }

        return _callback

    def _run_mnn_after_usrp_stage(
        self,
        base_access: BoardAccessConfig,
        *,
        count: int,
        progress_callback: Any = None,
    ) -> Any:
        def _callback(remote_stage_manifest: dict[str, Any], progress: Any) -> dict[str, Any]:
            access = self._usrp_stage_access(base_access, remote_stage_manifest, engine=INFERENCE_ENGINE_MNN)
            return self._run_mnn_batch_with_access(
                access,
                count=max(1, count),
                progress_callback=progress_callback or progress,
            )

        return _callback

    def start_mnn_batch_inference(self, *, count: int = 300) -> dict[str, Any]:
        import threading

        with self._lock:
            existing = self._batch_state
            if existing and existing.get("status") == "running":
                return {"status": "already_running", "batch_job_id": existing.get("batch_job_id"), "engine": existing.get("engine")}

            board_access = self._board_access
            env_values = board_access.build_env()
            if local_crypto_transport_mode(env_values) == "usrp":
                batch_job_id = f"mnn-usrp-{int(time.time())}-{max(1, count)}"
                self._batch_state = {
                    "status": "launching",
                    "batch_job_id": batch_job_id,
                    "engine": "mnn",
                    "total": max(1, count),
                    "completed": 0,
                    "success": 0,
                    "fallback": 0,
                    "sha_match": 0,
                    "started_at": time.time(),
                    "finished_at": None,
                    "service_mode": None,
                    "benchmark": None,
                    "host_preprocess_progress": {"completed": 0, "total": max(1, count), "status": "pending"},
                    "transport_progress": {"completed": 0, "total": max(1, count), "status": "pending"},
                    "inference_progress": {"completed": 0, "total": max(1, count), "status": "pending"},
                }

                security_context, security_blocked = self._arm_mlkem_security_context(
                    board_access=board_access,
                    variant="current",
                    image_index=0,
                    expected_count=max(1, count),
                )
                if security_blocked is not None:
                    state = self._batch_state
                    if state is not None and state.get("batch_job_id") == batch_job_id:
                        state["status"] = "done"
                        state["finished_at"] = time.time()
                        state["fallback"] = max(1, count)
                        state["message"] = str(security_blocked.get("message") or "MNN USRP 推理未启动")
                        state["status_category"] = str(security_blocked.get("status_category") or "")
                    return {
                        "status": "blocked",
                        "batch_job_id": batch_job_id,
                        "total": max(1, count),
                        "engine": "mnn",
                        "message": str(security_blocked.get("message") or "MNN USRP 推理未启动"),
                    }

                def _mnn_usrp_progress(completed: int, total: int) -> None:
                    with self._lock:
                        state = self._batch_state
                        if state is None or state.get("batch_job_id") != batch_job_id:
                            return
                        state["inference_progress"] = {
                            "completed": max(0, min(int(completed), max(1, int(total)))),
                            "total": max(1, int(total)),
                            "status": "running",
                        }
                        state["completed"] = state["inference_progress"]["completed"]
                        state["total"] = state["inference_progress"]["total"]

                live_job = launch_local_usrp_reconstruction_job(
                    board_access,
                    variant="current",
                    max_inputs=max(1, count),
                    control_transport="mlkem" if security_context else "none",
                    inference_engine=INFERENCE_ENGINE_MNN,
                    inference_callback=self._run_mnn_after_usrp_stage(
                        board_access,
                        count=max(1, count),
                        progress_callback=_mnn_usrp_progress,
                    ),
                )
                record, _payload = self._register_live_job(
                    live_job=live_job,
                    variant="current",
                    image_index=0,
                    security_context=security_context,
                )
                live_job_id = str(record["job_id"])
                self._batch_state = {**self._batch_state, "status": "running", "live_job_id": live_job_id}

                def _usrp_mnn_worker() -> None:
                    worker_error = ""
                    last_result: dict[str, Any] | None = None
                    try:
                        deadline = time.monotonic() + max(1800.0, float(max(1, count)) * 10.0)
                        while True:
                            last_result = self._peek_inference_progress(live_job_id)
                            live_progress = last_result.get("live_progress") if isinstance(last_result.get("live_progress"), dict) else {}
                            live_attempt = last_result.get("live_attempt") if isinstance(last_result.get("live_attempt"), dict) else {}
                            stage_progress = live_attempt.get("stage_progress") if isinstance(live_attempt.get("stage_progress"), dict) else {}
                            host_stage = stage_progress.get("host_preprocess") if isinstance(stage_progress.get("host_preprocess"), dict) else {}
                            transport_stage = stage_progress.get("transport") if isinstance(stage_progress.get("transport"), dict) else {}
                            inference_stage = stage_progress.get("inference") if isinstance(stage_progress.get("inference"), dict) else {}
                            with self._lock:
                                state = self._batch_state
                                if state is None or state.get("batch_job_id") != batch_job_id or state.get("status") != "running":
                                    return
                                state["host_preprocess_progress"] = {
                                    "completed": int(host_stage.get("completed_count") or 0),
                                    "total": max(1, int(host_stage.get("expected_count") or count)),
                                    "status": str(host_stage.get("state") or "pending"),
                                }
                                state["transport_progress"] = {
                                    "completed": int(transport_stage.get("completed_count") or 0),
                                    "total": max(1, int(transport_stage.get("expected_count") or count)),
                                    "status": str(transport_stage.get("state") or "running"),
                                }
                                state["inference_progress"] = {
                                    "completed": int(inference_stage.get("completed_count") or 0),
                                    "total": max(1, int(inference_stage.get("expected_count") or count)),
                                    "status": str(inference_stage.get("state") or "pending"),
                                }
                                state["completed"] = int(live_progress.get("completed_count") or 0)
                                state["total"] = max(1, int(live_progress.get("expected_count") or count))
                            if last_result.get("request_state") != "running":
                                break
                            if time.monotonic() >= deadline:
                                worker_error = "MNN USRP 全链路等待完成超时"
                                break
                            time.sleep(0.2)
                    except Exception as exc:
                        worker_error = f"{type(exc).__name__}: {exc}"

                    last_result = last_result or {}
                    live_attempt = last_result.get("live_attempt") if isinstance(last_result.get("live_attempt"), dict) else {}
                    wrapper_summary = live_attempt.get("wrapper_summary") if isinstance(live_attempt.get("wrapper_summary"), dict) else {}
                    artifacts = live_attempt.get("artifacts") if isinstance(live_attempt.get("artifacts"), dict) else {}
                    stage_progress = live_attempt.get("stage_progress") if isinstance(live_attempt.get("stage_progress"), dict) else {}
                    host_stage = stage_progress.get("host_preprocess") if isinstance(stage_progress.get("host_preprocess"), dict) else {}
                    inference_summary = wrapper_summary.get("inference_summary") if isinstance(wrapper_summary.get("inference_summary"), dict) else {}
                    processed = max(0, int(inference_summary.get("processed_count") or 0))
                    total = max(processed, int(inference_summary.get("selected_input_count") or count or 1))
                    succeeded = last_result.get("execution_mode") == "live" and last_result.get("status") == "success"
                    with self._lock:
                        state = self._batch_state
                        if state is None or state.get("batch_job_id") != batch_job_id:
                            return
                        state["host_preprocess_progress"] = {
                            "completed": int(host_stage.get("completed_count") or (max(1, count) if succeeded else 0)),
                            "total": max(1, int(host_stage.get("expected_count") or count)),
                            "status": str(host_stage.get("state") or ("completed" if succeeded else "fallback")),
                        }
                        if str(artifacts.get("remote_rx_dir") or "").strip():
                            state["remote_usrp_rx_payload_dir"] = str(artifacts.get("remote_rx_dir") or "").strip()
                        state["status"] = "done"
                        state["finished_at"] = time.time()
                        state["completed"] = processed if processed > 0 else (total if succeeded else 0)
                        state["total"] = total
                        state["success"] = processed if succeeded else 0
                        state["fallback"] = 0 if succeeded else max(0, total - processed)
                        state["benchmark"] = _compute_mnn_benchmark(inference_summary)
                        state["inference_benchmark"] = state["benchmark"]
                        transport_benchmark = wrapper_summary.get("transport_benchmark") if isinstance(wrapper_summary.get("transport_benchmark"), dict) else None
                        state["transport_benchmark"] = transport_benchmark
                        state["engine"] = "mnn"
                        state["runner_summary"] = inference_summary
                        if succeeded:
                            state["quality"] = self._build_prerecorded_payload_safe(image_index=0, variant="current").get("quality")
                        state["message"] = str(last_result.get("message") or worker_error or "")
                        state["status_category"] = str(last_result.get("status_category") or ("success" if succeeded else "error"))
                        if succeeded:
                            current_payload = self._build_live_payload_from_batch_summary(
                                engine="mnn",
                                job_id=live_job_id,
                                count=max(1, count),
                                summary=inference_summary,
                                message=state["message"],
                            )
                            self._update_last_inference_summary(current_payload, "current")
                        if worker_error and not succeeded:
                            state["error"] = worker_error

                thread = threading.Thread(target=_usrp_mnn_worker, daemon=True)
                thread.start()
                return {"status": "started", "batch_job_id": batch_job_id, "total": max(1, count), "engine": "mnn"}

            batch_job_id = f"mnn-{int(time.time())}-{max(1, count)}"
            self._batch_state = {
                "status": "running",
                "batch_job_id": batch_job_id,
                "engine": "mnn",
                "total": max(1, count),
                "completed": 0,
                "success": 0,
                "fallback": 0,
                "sha_match": 0,
                "started_at": time.time(),
                "finished_at": None,
                "service_mode": None,
                "benchmark": None,
            }

        def _worker() -> None:
            def _progress_update(completed: int, total: int) -> None:
                with self._lock:
                    state = self._batch_state
                    if state is None or state.get("batch_job_id") != batch_job_id or state.get("status") != "running":
                        return
                    state["completed"] = max(0, min(completed, max(1, total)))
                    state["total"] = max(1, total)

            summary = self._run_mnn_batch(count=count, progress_callback=_progress_update)
            processed = max(0, int(summary.get("processed_count") or 0))
            total = max(processed, int(summary.get("selected_input_count") or count or 1))
            status_text = str(summary.get("status") or "").lower()
            succeeded = status_text == "ok"
            error_text = ""
            errors = summary.get("errors")
            if isinstance(errors, list) and errors:
                error_text = str(errors[0])
            elif not succeeded:
                error_text = str(summary.get("message") or "MNN 推理失败")

            with self._lock:
                state = self._batch_state
                if state is None or state.get("batch_job_id") != batch_job_id:
                    return
                state["status"] = "done"
                state["finished_at"] = time.time()
                state["completed"] = processed if processed > 0 else (total if succeeded else 0)
                state["total"] = total
                state["success"] = processed if succeeded else 0
                state["fallback"] = 0 if succeeded else max(0, total - processed)
                state["benchmark"] = _compute_mnn_benchmark(summary)
                state["engine"] = "mnn"
                state["runner_summary"] = summary
                if error_text:
                    state["error"] = error_text

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return {"status": "started", "batch_job_id": batch_job_id, "total": max(1, count), "engine": "mnn"}

    def _peek_inference_progress(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._inference_jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        job_snapshot = record["job"].snapshot()
        with self._lock:
            record["last_snapshot"] = job_snapshot
        return self._build_inference_response(record, job_snapshot)

    def _register_live_job(
        self,
        *,
        live_job: Any,
        variant: str,
        image_index: int,
        security_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        live_result = live_job.snapshot()
        record: dict[str, Any] = {
            "job": live_job,
            "job_id": live_job.job_id,
            "variant": variant,
            "image_index": image_index,
            "last_snapshot": live_result,
        }
        if security_context:
            record["security_protocol"] = str(security_context.get("protocol") or "")
            record["security_handshake_ms"] = security_context.get("handshake_ms")
            record["security_summary"] = str(security_context.get("summary") or "")
            record["security_channel_state"] = str(security_context.get("channel_state") or "")
        with self._lock:
            self._inference_jobs[live_job.job_id] = record
        return record, self._build_inference_response(record, live_result)

    def _arm_mlkem_security_context(
        self,
        *,
        board_access: BoardAccessConfig,
        variant: str,
        image_index: int,
        expected_count: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        with self._lock:
            crypto_enabled = self._crypto_enabled
        if not crypto_enabled or variant != "current":
            return None, None

        if not board_access.connection_ready:
            return None, self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                source_label="ML-KEM 会话未配置，回退展示（归档样例）",
                message="尚未录入完整板卡会话，无法建立 ML-KEM 安全协议。",
                detail="请先补齐 host/user/password/port 后再启用 Current live 重建。",
                diagnostics={"crypto_enabled": True},
                expected_count=expected_count,
            )

        env_values = board_access.build_env()
        self._ensure_board_tcp_server(board_access)
        mgr = self._get_mlkem_session_manager(board_access, env_values)
        if mgr is None:
            tcp_client, searched_paths = resolve_local_crypto_client(env_values)
            searched_text = ", ".join(str(path) for path in (searched_paths or [])[:5]) or "no candidate paths"
            detail = (
                f"searched: {searched_text}"
                if tcp_client is None
                else f"tcp_client={tcp_client} does not support persistent daemon mode"
            )
            return None, self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="client_missing",
                source_label="ML-KEM 客户端缺失，回退展示（归档样例）",
                message="本机未找到可用的 ML-KEM 客户端，无法建立安全协议。",
                detail=detail,
                diagnostics={"searched": (searched_paths or [])[:10]},
                expected_count=expected_count,
            )

        try:
            mgr.ensure_alive()
            ping = mgr.ping()
        except Exception as exc:
            return None, self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="crypto_unavailable",
                source_label="ML-KEM 安全协议未就绪，回退展示（归档样例）",
                message="ML-KEM 安全协议未建立，本次按安全策略不发起 Current live 重建。",
                detail=str(exc),
                diagnostics={"crypto_enabled": True},
                expected_count=expected_count,
            )

        handshake_ms = mgr._handshake_ms if mgr._handshake_ms > 0 else None
        return {
            "protocol": "mlkem_control",
            "handshake_ms": round(float(handshake_ms), 3) if handshake_ms is not None else None,
            "channel_state": str(ping.get("status") or "ok"),
            "summary": "ML-KEM 安全协议已建立；Current 继续走板端本地 latent / 既有 live 数据面。",
        }, None

    def start_batch_inference(self, *, count: int = 300, allow_preflight_degraded: bool = True) -> dict[str, Any]:
        """在后台线程启动 Current live 300 张推进，并镜像为 batch_state。

        服务模式联动：
        - FULL_FRAME：全量推理（默认）
        - ROI_ONLY：跳帧降采样，有效推理数量 = count // 3
        - ALERT_ONLY：不做推理，改为模拟北斗坐标持续下发
        """
        import threading

        # ── 读取当前服务模式 ──
        service_snapshot = self._service_mode_snapshot()
        current_mode = service_snapshot.get("current_mode", "FULL_FRAME")

        with self._lock:
            existing = self._batch_state
            if existing and existing.get("status") == "running":
                return {"status": "already_running", "batch_job_id": existing.get("batch_job_id")}
            board_access_for_mode = self._board_access
            is_usrp_batch = local_crypto_transport_mode(board_access_for_mode.build_env()) == "usrp"

            # ── ALERT_ONLY：不做推理，模拟坐标下发 ──
            if current_mode == "ALERT_ONLY":
                batch_job_id = f"alert-{int(time.time())}-coord"
                self._batch_state = {
                    "status": "running",
                    "batch_job_id": batch_job_id,
                    "engine": "tvm",
                    "total": count,
                    "completed": 0,
                    "success": 0,
                    "fallback": 0,
                    "sha_match": 0,
                    "started_at": time.time(),
                    "finished_at": None,
                    "service_mode": "ALERT_ONLY",
                    "_samples": {"handshake_ms": [], "encrypt_ms": [], "decrypt_ms": [], "inference_ms": [], "total_ms": []},
                    "benchmark": None,
                }

                def _coord_worker() -> None:
                    """模拟 ALERT_ONLY 下持续转发北斗坐标，不做推理。

                    批量任务启动后冻结本批次的 service_mode，避免 worker 在线程里
                    再次读取 link director 状态时与 get_batch_state()/UI 轮询发生锁重入，
                    也避免导演台临时切换 staged profile 让本批次被提前截断。
                    """
                    worker_error = ""
                    try:
                        for i in range(count):
                            with self._lock:
                                state = self._batch_state
                                if state is None or state.get("status") != "running":
                                    return
                                if state.get("batch_job_id") != batch_job_id:
                                    return
                                if str(state.get("service_mode") or current_mode) != "ALERT_ONLY":
                                    state["completed"] = i
                                    break
                                state["completed"] = i + 1
                            self._event_spine.publish(
                                "COORD_FORWARDED",
                                source="alert_mode",
                                plane="data",
                                mode_scope=CONTROL_MODE_SCOPE,
                                message=f"北斗坐标帧 #{i + 1} 已下发至下位机。",
                                data={"frame_index": i, "mode": "ALERT_ONLY"},
                            )
                            time.sleep(0.08)  # 模拟坐标帧间隔
                    except Exception as exc:
                        worker_error = f"{type(exc).__name__}: {exc}"
                    with self._lock:
                        state = self._batch_state
                        if state is not None and state.get("batch_job_id") == batch_job_id:
                            state["status"] = "done"
                            state["finished_at"] = time.time()
                            state["benchmark"] = None
                            if worker_error:
                                state["error"] = worker_error

                thread = threading.Thread(target=_coord_worker, daemon=True)
                thread.start()
                self._event_spine.publish(
                    "MODE_ALERT_ACTIVE",
                    source="batch",
                    plane="control",
                    mode_scope=CONTROL_MODE_SCOPE,
                    message="ALERT_ONLY 模式激活：推理任务已挂起，切换为北斗坐标持续下发。",
                    data={"service_mode": "ALERT_ONLY", "coord_frames": count},
                )
                return {
                    "status": "started",
                    "batch_job_id": batch_job_id,
                    "total": count,
                    "service_mode": "ALERT_ONLY",
                    "message": "ALERT_ONLY 模式：推理已挂起，正在持续下发北斗定位坐标。",
                }

            # ── ROI_ONLY：跳帧降采样 ──
            effective_count = count
            if current_mode == "ROI_ONLY":
                effective_count = max(1, count // 3)

            batch_job_id = f"batch-{int(time.time())}-{effective_count}"
            self._batch_state = {
                "status": "launching",
                "batch_job_id": batch_job_id,
                "engine": "tvm",
                "total": effective_count,
                "completed": 0,
                "success": 0,
                "fallback": 0,
                "sha_match": 0,
                "started_at": time.time(),
                "finished_at": None,
                "service_mode": current_mode,
                # 各阶段计时样本列表（仅 live success 时记录）
                "_samples": {
                    "handshake_ms": [],
                    "encrypt_ms": [],
                    "decrypt_ms": [],
                    "inference_ms": [],
                    "total_ms": [],
                },
                "benchmark": None,
            }
            if is_usrp_batch:
                self._batch_state["transport_progress"] = {
                    "completed": 0,
                    "total": effective_count,
                    "status": "pending",
                }
                self._batch_state["host_preprocess_progress"] = {
                    "completed": 0,
                    "total": effective_count,
                    "status": "pending",
                }
                self._batch_state["inference_progress"] = {
                    "completed": 0,
                    "total": effective_count,
                    "status": "pending",
                }

        if current_mode == "ROI_ONLY":
            self._event_spine.publish(
                "MODE_ROI_ACTIVE",
                source="batch",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message=f"ROI_ONLY 降采样模式：有效推理帧 {effective_count}/{count}（跳帧比 3:1）。",
                data={"service_mode": "ROI_ONLY", "effective_count": effective_count, "original_count": count},
            )

        try:
            # Batch TVM must stay on the standard live runner so INFERENCE_CURRENT_CMD
            # can select the handwritten big.LITTLE pipeline. ML-KEM is control/auth
            # context here, not the batch data path.
            initial_result = self.run_demo_inference(
                variant="current",
                image_index=0,
                allow_preflight_degraded=allow_preflight_degraded,
                max_inputs=effective_count,
            )
        except Exception as exc:
            with self._lock:
                state = self._batch_state
                if (
                    state is not None
                    and state.get("batch_job_id") == batch_job_id
                    and state.get("status") == "launching"
                ):
                    self._batch_state = None
            return {
                "status": "error",
                "batch_job_id": batch_job_id,
                "service_mode": current_mode,
                "engine": "tvm",
                "message": f"{type(exc).__name__}: {exc}",
            }

        if initial_result.get("request_state") != "running" or not initial_result.get("job_id"):
            with self._lock:
                state = self._batch_state
                if (
                    state is not None
                    and state.get("batch_job_id") == batch_job_id
                    and state.get("status") == "launching"
                ):
                    state["status"] = "done"
                    state["finished_at"] = time.time()
                    state["completed"] = 0
                    state["success"] = 0
                    state["fallback"] = int(state.get("total") or effective_count)
                    state["message"] = str(initial_result.get("message") or "TVM 推理未启动")
                    state["status_category"] = str(initial_result.get("status_category") or "")
                    state["execution_mode"] = str(initial_result.get("execution_mode") or "")
                    state["source_label"] = str(initial_result.get("source_label") or "")
                    live_attempt = initial_result.get("live_attempt")
                    if isinstance(live_attempt, dict):
                        state["diagnostics"] = live_attempt.get("diagnostics") or {}
                    state["benchmark"] = _compute_benchmark(state["_samples"])
            return {
                "status": "blocked",
                "batch_job_id": batch_job_id,
                "service_mode": current_mode,
                "engine": "tvm",
                "message": str(initial_result.get("message") or "TVM 推理未启动"),
                "status_category": str(initial_result.get("status_category") or ""),
                "execution_mode": str(initial_result.get("execution_mode") or ""),
                "source_label": str(initial_result.get("source_label") or ""),
            }

        live_job_id = str(initial_result["job_id"])
        with self._lock:
            state = self._batch_state
            if state is None or state.get("batch_job_id") != batch_job_id:
                return {"status": "already_running", "batch_job_id": batch_job_id}
            self._batch_state = {
                **state,
                "status": "running",
            }

        def _worker() -> None:
            worker_error = ""
            last_result: dict[str, Any] | None = initial_result
            try:
                deadline = time.monotonic() + max(1800.0 if is_usrp_batch else 120.0, effective_count * 10.0)
                while True:
                    progress = last_result.get("live_progress") if isinstance(last_result.get("live_progress"), dict) else {}
                    live_attempt = last_result.get("live_attempt") if isinstance(last_result.get("live_attempt"), dict) else {}
                    wrapper_summary = live_attempt.get("wrapper_summary") if isinstance(live_attempt.get("wrapper_summary"), dict) else {}
                    if not wrapper_summary and isinstance(last_result.get("wrapper_summary"), dict):
                        wrapper_summary = last_result["wrapper_summary"]
                    iq_manifest = (
                        wrapper_summary.get("iq_remote_decode_manifest")
                        if isinstance(wrapper_summary.get("iq_remote_decode_manifest"), dict)
                        else None
                    )
                    stage_progress = live_attempt.get("stage_progress") if isinstance(live_attempt.get("stage_progress"), dict) else {}
                    host_stage = stage_progress.get("host_preprocess") if isinstance(stage_progress.get("host_preprocess"), dict) else {}
                    transport_stage = stage_progress.get("transport") if isinstance(stage_progress.get("transport"), dict) else {}
                    inference_stage = stage_progress.get("inference") if isinstance(stage_progress.get("inference"), dict) else {}
                    with self._lock:
                        state = self._batch_state
                        if state is None or state.get("status") != "running":
                            return
                        if is_usrp_batch:
                            state["host_preprocess_progress"] = {
                                "completed": int(host_stage.get("completed_count") or 0),
                                "total": max(1, int(host_stage.get("expected_count") or effective_count)),
                                "status": str(host_stage.get("state") or "pending"),
                            }
                            state["transport_progress"] = {
                                "completed": int(transport_stage.get("completed_count") or 0),
                                "total": max(1, int(transport_stage.get("expected_count") or effective_count)),
                                "status": str(transport_stage.get("state") or "running"),
                            }
                            state["inference_progress"] = {
                                "completed": int(inference_stage.get("completed_count") or 0),
                                "total": max(1, int(inference_stage.get("expected_count") or effective_count)),
                                "status": str(inference_stage.get("state") or "pending"),
                            }
                            state["completed"] = int(state["inference_progress"]["completed"])
                            state["total"] = max(1, int(state["inference_progress"]["total"]))
                            iq_images = _iq_streaming_images_from_manifest(
                                iq_manifest,
                                total=state["total"],
                                inference_state=str(inference_stage.get("state") or "pending"),
                            )
                            if iq_images:
                                state["iq_streaming_images"] = iq_images
                                state["iq_decoded_count"] = sum(
                                    1
                                    for image in iq_images
                                    if image.get("status") in {"decoded", "tvm_running", "done"}
                                )
                        else:
                            state["completed"] = int(progress.get("completed_count") or 0)
                            state["total"] = max(1, int(progress.get("expected_count") or effective_count))
                        if last_result.get("request_state") != "running":
                            break
                    if time.monotonic() >= deadline:
                        last_result = {
                            "status": "fallback",
                            "execution_mode": "fallback",
                            "request_state": "completed",
                            "message": "Current 在线推进等待完成超时",
                            "live_progress": {
                                "completed_count": int(progress.get("completed_count") or 0),
                                "expected_count": max(1, int(progress.get("expected_count") or effective_count)),
                            },
                            "live_attempt": {
                                "diagnostics": {"reason": "batch_wait_timeout"},
                                "security": (
                                    (last_result.get("live_attempt") or {}).get("security")
                                    if isinstance(last_result.get("live_attempt"), dict)
                                    else {}
                                ),
                            },
                            "timings": {},
                        }
                        break
                    time.sleep(0.05)
                    last_result = self._peek_inference_progress(live_job_id)

                assert last_result is not None
                progress = last_result.get("live_progress") if isinstance(last_result.get("live_progress"), dict) else {}
                completed = int(progress.get("completed_count") or 0)
                total = max(1, int(progress.get("expected_count") or effective_count))
                is_live = last_result.get("execution_mode") == "live" and last_result.get("status") == "success"
                live_attempt = last_result.get("live_attempt") if isinstance(last_result.get("live_attempt"), dict) else {}
                security = live_attempt.get("security") if isinstance(live_attempt.get("security"), dict) else {}
                timings = last_result.get("timings") if isinstance(last_result.get("timings"), dict) else {}
                runner_summary = live_attempt.get("runner_summary") if isinstance(live_attempt.get("runner_summary"), dict) else {}
                wrapper_summary = live_attempt.get("wrapper_summary") if isinstance(live_attempt.get("wrapper_summary"), dict) else {}
                if not runner_summary and isinstance(last_result.get("runner_summary"), dict):
                    runner_summary = last_result["runner_summary"]
                if not wrapper_summary and isinstance(last_result.get("wrapper_summary"), dict):
                    wrapper_summary = last_result["wrapper_summary"]
                artifacts = live_attempt.get("artifacts") if isinstance(live_attempt.get("artifacts"), dict) else {}
                stage_progress = live_attempt.get("stage_progress") if isinstance(live_attempt.get("stage_progress"), dict) else {}
                host_stage = stage_progress.get("host_preprocess") if isinstance(stage_progress.get("host_preprocess"), dict) else {}
                transport_stage = stage_progress.get("transport") if isinstance(stage_progress.get("transport"), dict) else {}
                inference_stage = stage_progress.get("inference") if isinstance(stage_progress.get("inference"), dict) else {}
                inference_summary = wrapper_summary.get("inference_summary") if isinstance(wrapper_summary.get("inference_summary"), dict) else {}
                transport_benchmark = wrapper_summary.get("transport_benchmark") if isinstance(wrapper_summary.get("transport_benchmark"), dict) else None
                iq_stage_benchmark = wrapper_summary.get("iq_stage_benchmark") if isinstance(wrapper_summary.get("iq_stage_benchmark"), dict) else None
                inference_benchmark = wrapper_summary.get("inference_benchmark") if isinstance(wrapper_summary.get("inference_benchmark"), dict) else None
                iq_manifest = (
                    wrapper_summary.get("iq_remote_decode_manifest")
                    if isinstance(wrapper_summary.get("iq_remote_decode_manifest"), dict)
                    else None
                )
                tvm_summary = inference_summary or runner_summary or wrapper_summary

                with self._lock:
                    state = self._batch_state
                    if state is None:
                        return
                    if is_usrp_batch:
                        state["host_preprocess_progress"] = {
                            "completed": int(host_stage.get("completed_count") or effective_count),
                            "total": max(1, int(host_stage.get("expected_count") or effective_count)),
                            "status": str(host_stage.get("state") or ("completed" if is_live else "fallback")),
                        }
                        if str(artifacts.get("remote_rx_dir") or "").strip():
                            state["remote_usrp_rx_payload_dir"] = str(artifacts.get("remote_rx_dir") or "").strip()
                        state["transport_progress"] = {
                            "completed": int(transport_stage.get("completed_count") or completed),
                            "total": max(1, int(transport_stage.get("expected_count") or total)),
                            "status": str(transport_stage.get("state") or ("completed" if is_live else "fallback")),
                        }
                        state["inference_progress"] = {
                            "completed": int(inference_stage.get("completed_count") or completed),
                            "total": max(1, int(inference_stage.get("expected_count") or total)),
                            "status": str(inference_stage.get("state") or ("completed" if is_live else "fallback")),
                        }
                        state["completed"] = int(state["inference_progress"]["completed"])
                        state["total"] = max(1, int(state["inference_progress"]["total"]))
                        iq_images = _iq_streaming_images_from_manifest(
                            iq_manifest,
                            total=state["total"],
                            inference_state=str(inference_stage.get("state") or ("completed" if is_live else "fallback")),
                            final_success=is_live,
                        )
                        if iq_images:
                            state["iq_streaming_images"] = iq_images
                            state["iq_decoded_count"] = sum(
                                1
                                for image in iq_images
                                if image.get("status") in {"decoded", "tvm_running", "done"}
                            )
                    else:
                        state["completed"] = completed
                        state["total"] = total
                    state["success"] = completed if is_live else 0
                    state["fallback"] = 0 if is_live else max(0, total - completed)
                    state["sha_match"] = 0
                    samples = state["_samples"]
                    handshake_ms = security.get("handshake_ms")
                    if handshake_ms is not None:
                        samples["handshake_ms"] = [float(handshake_ms)]
                    board_payload_ms = timings.get("payload_ms")
                    if board_payload_ms is not None and is_live:
                        samples["inference_ms"] = [float(board_payload_ms)]
                    total_ms = timings.get("total_ms")
                    if total_ms is None:
                        total_ms = wrapper_summary.get("per_image_ms")
                    if total_ms is not None and is_live:
                        samples["total_ms"] = [float(total_ms)]
                    if not is_usrp_batch and is_live and inference_benchmark is None and tvm_summary:
                        inference_benchmark = _compute_tvm_benchmark(tvm_summary)
                    if (
                        not is_usrp_batch
                        and is_live
                        and inference_benchmark
                        and inference_benchmark.get("inference_ms")
                    ):
                        state["benchmark"] = inference_benchmark
                        state["inference_benchmark"] = inference_benchmark
                        state["runner_summary"] = tvm_summary
                    if is_usrp_batch:
                        if inference_benchmark is None and inference_summary:
                            inference_benchmark = _compute_tvm_benchmark(inference_summary)
                        state["benchmark"] = inference_benchmark
                        state["inference_benchmark"] = inference_benchmark
                        state["transport_benchmark"] = transport_benchmark
                        state["iq_stage_benchmark"] = iq_stage_benchmark
                        state["runner_summary"] = inference_summary or runner_summary
                        if is_live:
                            state["quality"] = self._build_prerecorded_payload_safe(image_index=0, variant="current").get("quality")
                    if (
                        last_result.get("request_state") == "completed"
                        and isinstance(last_result.get("sample"), dict)
                        and isinstance(timings, dict)
                        and "source_label" in last_result
                        and "message" in last_result
                        and "artifact_sha" in last_result
                    ):
                        self._update_last_inference_summary(last_result, "current")
                    elif is_live and is_usrp_batch and inference_summary:
                        current_payload = self._build_live_payload_from_batch_summary(
                            engine="tvm",
                            job_id=live_job_id,
                            count=effective_count,
                            summary=inference_summary,
                            message=str(last_result.get("message") or ""),
                            source_label=str(last_result.get("source_label") or ""),
                        )
                        self._update_last_inference_summary(current_payload, "current")
            except Exception as exc:
                worker_error = f"{type(exc).__name__}: {exc}"

            with self._lock:
                state = self._batch_state
                if state is None:
                    return
                state["status"] = "done"
                state["finished_at"] = time.time()
                if not state.get("benchmark"):
                    state["benchmark"] = _compute_benchmark(state["_samples"])
                if worker_error:
                    state["error"] = worker_error

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return {
            "status": "started",
            "batch_job_id": batch_job_id,
            "total": effective_count,
            "service_mode": current_mode,
            "engine": "tvm",
        }

    def run_mlkem_inference(
        self,
        *,
        variant: str,
        image_index: int,
        allow_preflight_degraded: bool = False,
        max_inputs: int = DEFAULT_MAX_INPUTS,
        skip_control_preflight: bool = False,
        defer_board_start: bool = False,
    ) -> dict[str, Any]:
        payload = self._build_prerecorded_payload_safe(image_index=image_index, variant=variant)
        with self._lock:
            board_access = self._board_access
            crypto_enabled = self._crypto_enabled

        if not crypto_enabled:
            return self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="crypto_disabled",
                source_label="ML-KEM 未启用，回退展示（归档样例）",
                message="当前 ML-KEM 开关为 OFF，本次不发起加密推理。",
                detail="启用安全信道后，Current 主路径才会走 ML-KEM 加密通道。",
                diagnostics={"crypto_enabled": False},
                expected_count=max_inputs,
            )

        if not (board_access and board_access.connection_ready):
            return self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                source_label="会话未配置，回退展示（归档样例）",
                message="尚未录入完整板卡会话，无法发起 ML-KEM 推理。",
                detail="请先补齐 host/user/password。",
                diagnostics={"board_configured": False},
                expected_count=max_inputs,
            )

        # ── Preflight：daemon 存活时跳过 SSH 查询（O-1 优化） ──
        env_values = board_access.build_env()
        mgr_early = self._get_mlkem_session_manager(board_access, env_values)
        daemon_alive = mgr_early is not None and mgr_early.is_alive

        if skip_control_preflight:
            with self._lock:
                preflight = self._last_control_status
            if not preflight or preflight.get("status") not in ("success", "degraded"):
                preflight = {
                    "status": "degraded",
                    "message": "standalone TVM batch skips OpenAMP STATUS_REQ preflight",
                    "logs": [],
                    "guard_state": "UNKNOWN",
                    "last_fault_code": "NONE",
                    "heartbeat_ok": 1,
                    "total_fault_count": 0,
                    "status_category": "standalone_tvm_skip_preflight",
                }
        elif daemon_alive:
            # daemon 已与板端建立 ML-KEM 会话，板卡 TCP 通道畅通，无需 SSH 预检
            with self._lock:
                preflight = self._last_control_status
            if not preflight or preflight.get("status") not in ("success", "degraded"):
                preflight = {
                    "status": "degraded",
                    "message": "daemon 存活，跳过 SSH preflight",
                    "logs": [],
                    "guard_state": "UNKNOWN",
                    "last_fault_code": "NONE",
                    "heartbeat_ok": 1,
                    "total_fault_count": 0,
                    "status_category": "daemon_skip_preflight",
                }
        else:
            # daemon 未启动，走完整 SSH + RPMsg 预检
            live_board_access = self._live_board_access_for_variant(board_access, variant=variant)
            variant_expected_sha = expected_sha_for_variant(live_board_access, variant) or self._trusted_current_sha
            preflight = query_live_status(board_access, trusted_sha=variant_expected_sha)
            if preflight.get("status") != "success":
                soft_recover = self._maybe_soft_recover_control_plane(
                    board_access,
                    trusted_sha=variant_expected_sha,
                    reason="mlkem_preflight_failed",
                )
                retry = soft_recover.get("status_retry") if isinstance(soft_recover.get("status_retry"), dict) else {}
                if retry.get("status") == "success":
                    preflight = retry
                else:
                    if allow_preflight_degraded:
                        preflight = {
                            "status": "degraded",
                            "message": str(preflight.get("message") or "control preflight timeout"),
                            "logs": list(preflight.get("logs") or []),
                            "guard_state": "UNKNOWN",
                            "last_fault_code": "UNKNOWN",
                            "heartbeat_ok": 0,
                            "total_fault_count": 0,
                            "status_category": "control_preflight_degraded",
                        }
                    else:
                        return self._build_blocked_inference_payload(
                            variant=variant,
                            image_index=image_index,
                            status_category="control_preflight_failed",
                            source_label="控制面预检失败，回退展示（归档样例）",
                            message="控制面 STATUS_REQ 预检失败，本次不继续 ML-KEM 推理。",
                            detail=str(preflight.get("message") or "未拿到有效 STATUS_RESP"),
                            diagnostics={"control_status": preflight, "soft_recover": soft_recover},
                            expected_count=max_inputs,
                            event_log=list(preflight.get("logs") or []),
                        )

        with self._lock:
            self._last_control_status = preflight
        self._emit_status_observation_events(preflight, source="mlkem_preflight")

        guard_state = str(preflight.get("guard_state") or "UNKNOWN").upper()
        if guard_state == "JOB_ACTIVE":
            active_job_id = int(preflight.get("active_job_id") or 0)
            active_suffix = f" active_job_id={active_job_id}。" if active_job_id else ""
            return self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="board_busy",
                source_label="保守阻断（板端已有活动作业）",
                message=(
                    "板端当前 guard_state=JOB_ACTIVE，本次 ML-KEM 推理已保守阻断；"
                    f"不会自动 SAFE_STOP。{active_suffix}"
                ),
                detail="STATUS_RESP 显示 guard_state=JOB_ACTIVE；未再发起新的加密推理。",
                diagnostics={"control_status": preflight},
                expected_count=max_inputs,
                event_log=list(preflight.get("logs") or []),
            )

        # env_values 已在上方 O-1 优化块中提前获取
        if not defer_board_start:
            self._ensure_board_tcp_server(board_access)
        # O-3: 复用 mgr_early 的 client_script，避免重复文件系统搜索
        if mgr_early is not None:
            tcp_client = mgr_early._client_script
            searched_paths = [tcp_client]
        else:
            tcp_client, searched_paths = resolve_local_crypto_client(env_values)
        if tcp_client is None:
            searched_text = ", ".join(str(path) for path in searched_paths[:5]) or "no candidate paths"
            return self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="client_missing",
                source_label="客户端缺失，回退展示（归档样例）",
                message="tcp_client.py 未找到，无法执行 ML-KEM 推理主路径。",
                detail=f"searched: {searched_text}",
                diagnostics={"searched": searched_paths[:10]},
                expected_count=max_inputs,
            )

        import tempfile
        from threading import Thread

        # ── 构建 ML-KEM 后台 job（和 SSH 路径一样：返回 running，后台推进） ──
        mlkem_job_id = generate_live_job_id()
        client_caps = inspect_local_crypto_client_capabilities(tcp_client)
        max_inputs = max(1, int(max_inputs))
        if client_caps.get("legacy_single_input_only") and max_inputs == DEFAULT_MAX_INPUTS:
            max_inputs = 1

        class _MlkemJob:
            """模拟 LiveRemoteReconstructionJob：后台线程逐张 ML-KEM 推理，前端轮询进度。"""
            def __init__(self_self, jid: str, max_n: int, board: Any, env_vals: dict,
                         client_script: str, variant_name: str, img_idx: int,
                         preflight_data: dict, app_state: Any,
                         session_mgr: "MlkemSessionManager | None" = None,
                         client_caps: dict[str, bool] | None = None,
                         ensure_board_before_run: bool = False):
                self_self.job_id = jid
                self_self._max = max_n
                self_self._board = board
                self_self._env_vals = env_vals
                self_self._client = client_script
                self_self._variant = variant_name
                self_self._img_idx = img_idx
                self_self._preflight = preflight_data
                self_self._app = app_state
                self_self._session_mgr = session_mgr
                self_self._client_caps = dict(client_caps or {})
                self_self._ensure_board_before_run = ensure_board_before_run
                self_self._lock = Lock()
                self_self._completed = 0
                self_self._final_snapshot: dict[str, Any] | None = None
                self_self._stages_summary: list[dict[str, Any]] = []
                self_self._total_ms = 0.0
                self_self._sha_match: bool | None = None
                self_self._error: str | None = None
                self_self._metrics_samples: dict[str, list[float]] = {
                    "encrypt_ms": [],
                    "decrypt_ms": [],
                    "inference_ms": [],
                    "total_ms": [],
                }

            def snapshot(self_self) -> dict:
                with self_self._lock:
                    if self_self._final_snapshot is not None:
                        return dict(self_self._final_snapshot)
                completed = self_self._completed
                pct = int(round(completed / self_self._max * 100)) if self_self._max > 0 else 0
                return {
                    "status": "running",
                    "request_state": "running",
                    "status_category": "running",
                    "execution_mode": "live",
                    "variant": self_self._variant,
                    "message": "ML-KEM 安全信道在线推进中…",
                    "control_transport": "mlkem",
                    "control_handshake_complete": True,
                    "runner_summary": {"processed_count": completed, "input_count": self_self._max, "max_inputs": self_self._max},
                    "wrapper_summary": {},
                    "diagnostics": {"control_preflight": self_self._preflight},
                    "progress": {
                        "state": "running",
                        "label": "ML-KEM 加密推理中",
                        "tone": "online",
                        "percent": pct,
                        "phase_percent": pct,
                        "completed_count": completed,
                        "expected_count": self_self._max,
                        "remaining_count": self_self._max - completed,
                        "completion_ratio": round(completed / self_self._max, 4) if self_self._max > 0 else 0.0,
                        "count_source": "mlkem_live",
                        "count_label": f"{completed} / {self_self._max}",
                        "current_stage": f"ML-KEM 加密推理 {completed}/{self_self._max}",
                        "stages": [{"key": "mlkem_live", "label": "ML-KEM 全链路", "status": "current",
                                     "detail": f"已完成 {completed}/{self_self._max}"}],
                        "event_log": [],
                    },
                    "artifacts": [],
                }

            def start(self_self) -> None:
                Thread(target=self_self._run_loop, daemon=True).start()

            def _average_metric(self_self, key: str) -> float | None:
                values = self_self._metrics_samples.get(key) or []
                if not values:
                    return None
                return round(sum(values) / len(values), 3)

            def _metric_payload(self_self, *, handshake_ms: float | None, per_image_ms: float | None = None) -> dict[str, Any]:
                total_ms = per_image_ms
                if total_ms is None:
                    total_ms = self_self._average_metric("total_ms")
                return {
                    "handshake_ms": round(float(handshake_ms), 3) if handshake_ms is not None else None,
                    "encrypt_ms": self_self._average_metric("encrypt_ms"),
                    "decrypt_ms": self_self._average_metric("decrypt_ms"),
                    "inference_ms": self_self._average_metric("inference_ms"),
                    "total_ms": round(float(total_ms), 3) if total_ms is not None else None,
                    "sha256_match": self_self._sha_match,
                }

            def _set_final_snapshot(
                self_self,
                *,
                transport_mode: str,
                total_wall: float,
                handshake_ms: float | None,
                per_image_ms: float | None = None,
                board_inference_ms: float | None = None,
                completed_override: int | None = None,
                error_message: str | None = None,
            ) -> None:
                if completed_override is not None:
                    self_self._completed = completed_override
                self_self._total_ms = total_wall
                self_self._error = error_message
                if self_self._sha_match is None:
                    self_self._sha_match = self_self._completed == self_self._max and error_message is None
                effective_per_image = per_image_ms
                if effective_per_image is None and self_self._completed > 0:
                    effective_per_image = total_wall / self_self._completed
                effective_board_inference_ms = board_inference_ms
                if effective_board_inference_ms is None:
                    effective_board_inference_ms = self_self._average_metric("inference_ms")
                is_ok = self_self._completed == self_self._max and self_self._error is None
                metrics = self_self._metric_payload(handshake_ms=handshake_ms, per_image_ms=effective_per_image)
                fallback_message = error_message or (
                    f"ML-KEM 推理中断（已完成 {self_self._completed}/{self_self._max}），已回退。"
                )
                self_self._final_snapshot = {
                    "status": "success" if is_ok else "fallback",
                    "request_state": "completed",
                    "status_category": "success" if is_ok else "fallback",
                    "execution_mode": "live" if is_ok else "fallback",
                    "variant": self_self._variant,
                    "message": (
                        "Current 已通过 ML-KEM 安全信道完成加密传输与板端执行。"
                        if is_ok
                        else fallback_message
                    ),
                    "control_transport": "mlkem",
                    "control_handshake_complete": True,
                    "runner_summary": {
                        "processed_count": self_self._completed,
                        "input_count": self_self._max,
                        "max_inputs": self_self._max,
                        "total_ms": round(total_wall, 3),
                        "load_ms": round(float(handshake_ms or 0.0), 3),
                        "vm_init_ms": 0.0,
                        "run_mean_ms": (
                            round(float(effective_board_inference_ms), 3)
                            if effective_board_inference_ms is not None
                            else None
                        ),
                        "run_median_ms": (
                            round(float(effective_board_inference_ms), 3)
                            if effective_board_inference_ms is not None
                            else None
                        ),
                    },
                    "wrapper_summary": {
                        "total_ms": round(total_wall, 3),
                        "sha_match": self_self._sha_match,
                        "handshake_ms": round(float(handshake_ms), 3) if handshake_ms is not None else None,
                        "per_image_ms": round(float(effective_per_image), 3) if effective_per_image is not None else None,
                        "transport_mode": transport_mode,
                    },
                    "metrics": metrics,
                    "diagnostics": {"control_preflight": self_self._preflight},
                    "progress": {
                        "state": "completed" if is_ok else "fallback",
                        "label": "ML-KEM 加密推理完成" if is_ok else "ML-KEM 推理中断",
                        "tone": "online" if is_ok else "degraded",
                        "percent": 100 if is_ok else int(round(self_self._completed / self_self._max * 100)),
                        "phase_percent": 100,
                        "completed_count": self_self._completed,
                        "expected_count": self_self._max,
                        "remaining_count": self_self._max - self_self._completed,
                        "completion_ratio": round(self_self._completed / self_self._max, 4) if self_self._max > 0 else 0.0,
                        "count_source": "mlkem_live",
                        "count_label": f"{self_self._completed} / {self_self._max}",
                        "current_stage": "加密推理完成" if is_ok else "推理中断",
                        "stages": [{
                            "key": "mlkem_live_done",
                            "label": "ML-KEM 全链路",
                            "status": "done" if is_ok else "error",
                            "detail": f"wall={round(total_wall, 1)}ms, sha_match={self_self._sha_match}",
                        }],
                        "event_log": [] if is_ok else [f"error: {self_self._error}"],
                    },
                    "artifacts": [],
                }

            def _finish_with_error(
                self_self,
                *,
                error_message: str,
                transport_mode: str,
                total_wall: float,
                handshake_ms: float | None,
                completed_override: int | None = None,
            ) -> None:
                self_self._set_final_snapshot(
                    transport_mode=transport_mode,
                    total_wall=total_wall,
                    handshake_ms=handshake_ms,
                    completed_override=completed_override,
                    error_message=error_message,
                )

            def _run_loop(self_self) -> None:
                input_path = self_self._app._create_mlkem_input_file(self_self._client)
                run_started = time.monotonic()
                try:
                    if self_self._ensure_board_before_run:
                        self_self._app._ensure_board_tcp_server(self_self._board)
                    if self_self._session_mgr is not None:
                        self_self._run_loop_daemon(input_path)
                    else:
                        self_self._run_loop_subprocess(input_path)
                except Exception as exc:
                    with self_self._lock:
                        self_self._sha_match = False
                        self_self._finish_with_error(
                            error_message=f"ML-KEM 后台任务异常: {type(exc).__name__}: {exc}",
                            transport_mode="startup",
                            total_wall=(time.monotonic() - run_started) * 1000,
                            handshake_ms=None,
                            completed_override=self_self._completed,
                        )
                finally:
                    try:
                        input_path.unlink()
                    except OSError:
                        pass

            def _run_loop_daemon(self_self, input_path: Path) -> None:
                """通过持久化 daemon 发送图片（一次握手 N 张复用）"""
                mgr = self_self._session_mgr
                assert mgr is not None

                try:
                    mgr.ensure_alive()
                except Exception as e:
                    print(f"[ML-KEM _run_loop] daemon 启动失败, 回退子进程: {e}")
                    self_self._run_loop_subprocess(input_path)
                    return

                t0 = time.monotonic()
                should_expect_result = (
                    self_self._max == 1
                    and bool(self_self._client_caps.get("supports_expect_result"))
                )
                for i in range(self_self._max):
                    job_id = f"{self_self.job_id}_{i:04d}"
                    try:
                        result = mgr.send_image(
                            str(input_path),
                            job_id,
                            run_tvm=True,
                            expect_result=should_expect_result,
                        )
                    except Exception as e:
                        print(f"[ML-KEM _run_loop] daemon 错误 (第 {i} 张): {e}")
                        # 回退：剩余图片用子进程
                        remaining = self_self._max - i
                        if remaining > 0:
                            self_self._run_loop_subprocess(
                                input_path,
                                remaining=remaining,
                                completed_prefix=self_self._completed,
                            )
                        return

                    if result.get("status") == "ok":
                        if should_expect_result and result.get("result_received") is not True:
                            print(f"[ML-KEM _run_loop] 第 {i} 张未回传板端结果: {result}")
                            total_wall = (time.monotonic() - t0) * 1000
                            with self_self._lock:
                                self_self._sha_match = False
                                self_self._finish_with_error(
                                    error_message=f"第 {i} 张未收到板端重建结果",
                                    transport_mode="daemon",
                                    total_wall=total_wall,
                                    handshake_ms=mgr._handshake_ms,
                                )
                            return
                        with self_self._lock:
                            self_self._completed += 1
                            self_self._total_ms = (time.monotonic() - t0) * 1000
                            for key in ("encrypt_ms", "decrypt_ms", "inference_ms", "total_ms"):
                                value = result.get(key)
                                if value is not None:
                                    self_self._metrics_samples[key].append(float(value))
                    else:
                        print(f"[ML-KEM _run_loop] 第 {i} 张失败: {result}")
                        total_wall = (time.monotonic() - t0) * 1000
                        with self_self._lock:
                            self_self._sha_match = False
                            self_self._finish_with_error(
                                error_message=f"第 {i} 张失败: {result.get('message', '')}",
                                transport_mode="daemon",
                                total_wall=total_wall,
                                handshake_ms=mgr._handshake_ms,
                            )
                        return

                total_wall = (time.monotonic() - t0) * 1000
                with self_self._lock:
                    self_self._sha_match = (self_self._completed == self_self._max)
                    per_image_ms = total_wall / max(self_self._max, 1)
                    self_self._set_final_snapshot(
                        transport_mode="daemon",
                        total_wall=total_wall,
                        handshake_ms=mgr._handshake_ms,
                        per_image_ms=per_image_ms,
                        board_inference_ms=self_self._average_metric("inference_ms"),
                    )
                    is_ok = self_self._completed == self_self._max and self_self._error is None
                    self_self._app._event_spine.publish("JOB_DONE", source="inference", plane="data",
                        mode_scope=DATA_MODE_SCOPE,
                        message=f"ML-KEM live job {self_self.job_id} completed (daemon).",
                        data={"variant": self_self._variant, "image_index": self_self._img_idx,
                              "total_ms": round(total_wall, 3), "sha256_match": self_self._sha_match,
                              "control_transport": "mlkem"})

            def _run_loop_subprocess(self_self, input_path: Path,
                                     remaining: int | None = None,
                                     completed_prefix: int = 0) -> None:
                """通过一次性子进程发送图片（原有逻辑，回退路径）"""
                count = remaining if remaining is not None else self_self._max
                if not self_self._client_caps.get("supports_batch_summary"):
                    self_self._run_loop_legacy_subprocess(
                        input_path,
                        count=count,
                        completed_prefix=completed_prefix,
                    )
                    return

                cmd, env = build_local_crypto_client_command(
                    self_self._env_vals, host=self_self._board.host,
                    input_path=input_path, client_script=self_self._client,
                )
                cmd.extend([
                    "--job-id", self_self.job_id,
                    "--count", str(count),
                    "--json-summary",
                    "--run-tvm",
                ])
                if self_self._max == 1 and self_self._client_caps.get("supports_expect_result"):
                    cmd.append("--expect-result")
                env["PYTHONUNBUFFERED"] = "1"
                timeout_s = count * 10
                t0 = time.monotonic()
                stdout_lines: list[str] = []
                print(f"[ML-KEM _run_loop_subprocess] cmd={' '.join(cmd[:8])}...")
                try:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, env=env, bufsize=1)
                    assert proc.stdout is not None
                    for raw_line in proc.stdout:
                        line = raw_line.rstrip('\n')
                        stdout_lines.append(line)
                        if "✓" in line:
                            with self_self._lock:
                                self_self._completed += 1
                                self_self._total_ms = (time.monotonic() - t0) * 1000
                    proc.wait(timeout=timeout_s - (time.monotonic() - t0))
                except subprocess.TimeoutExpired:
                    print(f"[ML-KEM _run_loop_subprocess] TIMEOUT after {timeout_s}s")
                    with self_self._lock:
                        self_self._sha_match = False
                        self_self._finish_with_error(
                            error_message="ML-KEM 批量传输超时",
                            transport_mode="subprocess",
                            total_wall=(time.monotonic() - t0) * 1000,
                            handshake_ms=None,
                            completed_override=self_self._completed,
                        )
                    return
                except Exception as e:
                    print(f"[ML-KEM _run_loop_subprocess] EXCEPTION: {e}")
                    with self_self._lock:
                        self_self._sha_match = False
                        self_self._finish_with_error(
                            error_message=f"ML-KEM 进程异常: {e}",
                            transport_mode="subprocess",
                            total_wall=(time.monotonic() - t0) * 1000,
                            handshake_ms=None,
                            completed_override=self_self._completed,
                        )
                    return
                total_wall = (time.monotonic() - t0) * 1000
                stdout_full = '\n'.join(stdout_lines)

                if proc.returncode != 0:
                    stderr = (proc.stderr.read() if proc.stderr else "")[-300:]
                    with self_self._lock:
                        self_self._sha_match = False
                        self_self._finish_with_error(
                            error_message=f"ML-KEM 批量失败 (rc={proc.returncode}): {stderr.strip()}",
                            transport_mode="subprocess",
                            total_wall=total_wall,
                            handshake_ms=None,
                            completed_override=self_self._completed,
                        )
                    print(f"[ML-KEM _run_loop_subprocess] FAIL rc={proc.returncode}: {stderr.strip()[:200]}")
                    return

                print(f"[ML-KEM _run_loop_subprocess] done rc=0, {len(stdout_lines)} lines, {total_wall:.0f}ms")

                summary = _MlkemJob._parse_json_summary(stdout_full)
                success = int(summary.get("success", max(self_self._completed - completed_prefix, 0)))
                total = summary.get("total", count)
                handshake_ms = summary.get("handshake_ms", 0)
                per_image_ms = summary.get("per_image_ms", 0)

                with self_self._lock:
                    self_self._completed = completed_prefix + success
                    self_self._total_ms = total_wall
                    self_self._stages_summary = [
                        {"label": "ML-KEM 握手 (1 次)", "value_ms": handshake_ms, "emphasis": "host"},
                        {"label": "AEAD 加密传输 (N 张)", "value_ms": round(per_image_ms * total, 1), "emphasis": "data"},
                    ]
                    self_self._sha_match = (completed_prefix + success) == self_self._max
                    self_self._metrics_samples["total_ms"].append(float(per_image_ms or total_wall))
                    self_self._set_final_snapshot(
                        transport_mode="subprocess",
                        total_wall=total_wall,
                        handshake_ms=handshake_ms,
                        per_image_ms=per_image_ms,
                    )
                    is_ok = self_self._completed == self_self._max and self_self._error is None
                    self_self._app._event_spine.publish("JOB_DONE", source="inference", plane="data",
                        mode_scope=DATA_MODE_SCOPE,
                        message=f"ML-KEM live job {self_self.job_id} completed.",
                        data={"variant": self_self._variant, "image_index": self_self._img_idx,
                              "total_ms": round(total_wall, 3), "sha256_match": self_self._sha_match,
                              "control_transport": "mlkem"})
                    self_self._app._archive_event_snapshot(
                        reason="mlkem_live_done", job_id=self_self.job_id,
                        extra={"variant": self_self._variant, "completed": self_self._completed,
                              "total_ms": round(total_wall, 3)})

            def _run_loop_legacy_subprocess(
                self_self,
                input_path: Path,
                *,
                count: int,
                completed_prefix: int = 0,
            ) -> None:
                """兼容仅支持单张 --input 的旧版 tcp_client.py。"""
                t0 = time.monotonic()
                handshake_samples: list[float] = []
                total_samples: list[float] = []
                board_inference_samples: list[float] = []

                for index in range(count):
                    cmd, env = build_local_crypto_client_command(
                        self_self._env_vals,
                        host=self_self._board.host,
                        input_path=input_path,
                        client_script=self_self._client,
                    )
                    job_id = (
                        self_self.job_id
                        if count == 1 and completed_prefix == 0
                        else f"{self_self.job_id}_{completed_prefix + index:04d}"
                    )
                    cmd.extend(["--job-id", job_id])
                    cmd.append("--run-tvm")
                    if self_self._max == 1 and self_self._client_caps.get("supports_expect_result"):
                        cmd.append("--expect-result")
                    env["PYTHONUNBUFFERED"] = "1"

                    iter_t0 = time.monotonic()
                    try:
                        proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=60,
                            env=env,
                        )
                    except subprocess.TimeoutExpired:
                        with self_self._lock:
                            self_self._sha_match = False
                            self_self._finish_with_error(
                                error_message=(
                                    f"ML-KEM 单张兼容模式超时 "
                                    f"({completed_prefix + index + 1}/{self_self._max})"
                                ),
                                transport_mode="subprocess_legacy",
                                total_wall=(time.monotonic() - t0) * 1000,
                                handshake_ms=None,
                                completed_override=self_self._completed,
                            )
                        return

                    stdout = proc.stdout or ""
                    stderr = proc.stderr or ""
                    metrics = self_self._app._parse_mlkem_client_metrics(stdout)
                    iter_total_ms = (time.monotonic() - iter_t0) * 1000

                    if proc.returncode != 0:
                        error_text = (stderr.strip() or stdout.strip() or "unknown error")[-300:]
                        with self_self._lock:
                            self_self._sha_match = False
                            self_self._finish_with_error(
                                error_message=(
                                    f"ML-KEM 单张兼容模式失败 "
                                    f"(rc={proc.returncode}, {completed_prefix + index + 1}/{self_self._max}): "
                                    f"{error_text}"
                                ),
                                transport_mode="subprocess_legacy",
                                total_wall=(time.monotonic() - t0) * 1000,
                                handshake_ms=None,
                                completed_override=self_self._completed,
                            )
                        return

                    if metrics.get("sha256_match") is False:
                        with self_self._lock:
                            self_self._sha_match = False
                            self_self._finish_with_error(
                                error_message=(
                                    f"ML-KEM 单张兼容模式 SHA256 校验失败 "
                                    f"({completed_prefix + index + 1}/{self_self._max})"
                                ),
                                transport_mode="subprocess_legacy",
                                total_wall=(time.monotonic() - t0) * 1000,
                                handshake_ms=None,
                                completed_override=self_self._completed,
                            )
                        return

                    if metrics.get("result_received") is False:
                        with self_self._lock:
                            self_self._sha_match = False
                            self_self._finish_with_error(
                                error_message=(
                                    f"ML-KEM 单张兼容模式未收到板端重建结果 "
                                    f"({completed_prefix + index + 1}/{self_self._max})"
                                ),
                                transport_mode="subprocess_legacy",
                                total_wall=(time.monotonic() - t0) * 1000,
                                handshake_ms=None,
                                completed_override=self_self._completed,
                            )
                        return

                    handshake_ms = metrics.get("handshake_ms")
                    if handshake_ms is not None:
                        handshake_samples.append(float(handshake_ms))

                    for key in ("encrypt_ms", "decrypt_ms", "inference_ms"):
                        value = metrics.get(key)
                        if value is not None:
                            self_self._metrics_samples[key].append(float(value))
                    if metrics.get("inference_ms") is not None:
                        board_inference_samples.append(float(metrics["inference_ms"]))

                    per_image_total = sum(
                        float(metrics.get(key) or 0.0)
                        for key in ("encrypt_ms", "decrypt_ms", "inference_ms")
                        if metrics.get(key) is not None
                    )
                    if per_image_total <= 0:
                        per_image_total = iter_total_ms
                    total_samples.append(float(per_image_total))
                    self_self._metrics_samples["total_ms"].append(float(per_image_total))

                    with self_self._lock:
                        self_self._completed = completed_prefix + index + 1
                        self_self._total_ms = (time.monotonic() - t0) * 1000

                total_wall = (time.monotonic() - t0) * 1000
                avg_handshake_ms = (
                    round(sum(handshake_samples) / len(handshake_samples), 3)
                    if handshake_samples
                    else None
                )
                per_image_ms = (
                    round(sum(total_samples) / len(total_samples), 3)
                    if total_samples
                    else round(total_wall / max(count, 1), 3)
                )
                board_inference_ms = (
                    round(sum(board_inference_samples) / len(board_inference_samples), 3)
                    if board_inference_samples
                    else None
                )

                with self_self._lock:
                    self_self._completed = completed_prefix + count
                    self_self._total_ms = total_wall
                    self_self._stages_summary = [
                        {
                            "label": "ML-KEM 握手 (兼容模式)",
                            "value_ms": round(float(avg_handshake_ms or 0.0), 3),
                            "emphasis": "host",
                        },
                        {
                            "label": "AEAD 加密传输 + 板端执行",
                            "value_ms": round(per_image_ms * count, 1),
                            "emphasis": "data",
                        },
                    ]
                    self_self._sha_match = self_self._completed == self_self._max
                    self_self._set_final_snapshot(
                        transport_mode="subprocess_legacy",
                        total_wall=total_wall,
                        handshake_ms=avg_handshake_ms,
                        per_image_ms=per_image_ms,
                        board_inference_ms=board_inference_ms,
                    )
                    self_self._app._event_spine.publish(
                        "JOB_DONE",
                        source="inference",
                        plane="data",
                        mode_scope=DATA_MODE_SCOPE,
                        message=f"ML-KEM live job {self_self.job_id} completed (legacy client compatibility).",
                        data={
                            "variant": self_self._variant,
                            "image_index": self_self._img_idx,
                            "total_ms": round(total_wall, 3),
                            "sha256_match": self_self._sha_match,
                            "control_transport": "mlkem",
                        },
                    )
                    self_self._app._archive_event_snapshot(
                        reason="mlkem_live_done",
                        job_id=self_self.job_id,
                        extra={
                            "variant": self_self._variant,
                            "completed": self_self._completed,
                            "total_ms": round(total_wall, 3),
                            "transport_mode": "subprocess_legacy",
                        },
                    )

            @staticmethod
            def _parse_json_summary(stdout: str) -> dict[str, Any]:
                """解析 tcp_client.py --json-summary 输出的 JSON"""
                # JSON 摘要在 stdout 末尾，找到最后一个 '{' 开始的行
                lines = stdout.splitlines()
                json_start = -1
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('{') or stripped.startswith('['):
                        json_start = i
                if json_start < 0:
                    return {}
                try:
                    return json.loads('\n'.join(lines[json_start:]))
                except (json.JSONDecodeError, ValueError):
                    return {}

            @staticmethod
            def _parse_stdout(stdout: str) -> dict[str, Any]:
                metrics: dict[str, Any] = {}
                for line in stdout.splitlines():
                    text = line.strip()
                    if "握手完成" in text:
                        m = re.search(r"([\d.]+)\s*ms", text)
                        if m:
                            metrics.setdefault("stages", []).append(
                                {"label": "ML-KEM 握手", "value_ms": round(float(m.group(1)), 3), "emphasis": "host"})
                    elif "加密发送" in text:
                        m = re.search(r"([\d.]+)\s*ms", text)
                        if m:
                            metrics.setdefault("stages", []).append(
                                {"label": "AEAD 加密发送", "value_ms": round(float(m.group(1)), 3), "emphasis": "data"})
                    elif "TVM 推理" in text or "解密结果" in text:
                        m = re.search(r"([\d.]+)\s*ms", text)
                        if m:
                            metrics.setdefault("stages", []).append(
                                {"label": "板端 TVM 推理", "value_ms": round(float(m.group(1)), 3), "emphasis": "board"})
                    elif "SHA256 匹配" in text or "sha256" in text.lower():
                        if "不匹配" not in text and "mismatch" not in text.lower():
                            metrics["sha_match"] = True
                return metrics

        mgr = self._get_mlkem_session_manager(board_access, env_values)
        mlkem_job = _MlkemJob(
            jid=mlkem_job_id, max_n=max_inputs, board=board_access,
            env_vals=env_values, client_script=tcp_client, variant_name=variant,
            img_idx=image_index, preflight_data=preflight, app_state=self,
            session_mgr=mgr,
            client_caps=client_caps,
            ensure_board_before_run=defer_board_start,
        )

        # 初始 "running" snapshot → 通过 _build_inference_response 生成 payload
        running_snapshot = mlkem_job.snapshot()
        record = {
            "job": mlkem_job,
            "job_id": mlkem_job_id,
            "variant": variant,
            "image_index": image_index,
            "last_snapshot": dict(running_snapshot),
        }
        with self._lock:
            self._inference_jobs[mlkem_job_id] = record

        payload = self._build_inference_response(record, running_snapshot)
        payload["source_label"] = "ML-KEM 全链路加密（控制+数据）"

        # 启动后台推理线程
        mlkem_job.start()

        self._event_spine.publish(
            "JOB_SUBMITTED", source="inference", plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"ML-KEM live job {mlkem_job_id} submitted ({max_inputs} images).",
            data={"variant": variant, "image_index": image_index, "control_transport": "mlkem"},
        )
        self._event_spine.publish(
            "JOB_ADMITTED", source="inference", plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"ML-KEM live job {mlkem_job_id} admitted.",
            data={"variant": variant, "image_index": image_index, "control_transport": "mlkem"},
        )

        return payload

    def run_demo_inference(
        self,
        *,
        variant: str,
        image_index: int,
        allow_preflight_degraded: bool = False,
        max_inputs: int = DEFAULT_MAX_INPUTS,
    ) -> dict[str, Any]:
        payload = self._build_prerecorded_payload_safe(image_index=image_index, variant=variant)
        event_record: dict[str, Any] | None = None
        security_context: dict[str, Any] | None = None
        with self._lock:
            board_access = self._board_access
            last_live_probe = self._last_live_probe
        env_values = board_access.build_env()
        if local_crypto_transport_mode(env_values) == "usrp":
            if board_access.configured:
                active_record = self._running_inference_job_record()
                if active_record is not None:
                    # Clear stale record and proceed
                    with self._lock:
                        stale_job_id = str(active_record.get("job_id", ""))
                        if stale_job_id and stale_job_id in self._inference_jobs:
                            del self._inference_jobs[stale_job_id]
                if True:  # always proceed for USRP mode (stale record cleared above)
                    security_context, security_blocked = self._arm_mlkem_security_context(
                        board_access=board_access,
                        variant=variant,
                        image_index=image_index,
                        expected_count=max_inputs,
                    )
                    if security_blocked is not None:
                        payload = security_blocked
                    else:
                        live_job = launch_local_usrp_reconstruction_job(
                            board_access,
                            variant=variant,
                            max_inputs=max_inputs,
                            control_transport="mlkem" if security_context else "none",
                            inference_engine=INFERENCE_ENGINE_TVM if variant == "current" else INFERENCE_ENGINE_NONE,
                            inference_callback=(
                                self._run_tvm_after_usrp_stage(board_access, count=max_inputs)
                                if variant == "current"
                                else None
                            ),
                        )
                        event_record, payload = self._register_live_job(
                            live_job=live_job,
                            variant=variant,
                            image_index=image_index,
                            security_context=security_context,
                        )
            else:
                payload.update(
                    {
                        "status": "fallback",
                        "request_state": "completed",
                        "status_category": "config_error",
                        "timings": self._empty_live_timings(),
                        "live_progress": {
                            "state": "completed",
                            "label": "回退展示",
                            "tone": "degraded",
                            "percent": 0,
                            "phase_percent": 100,
                            "completed_count": 0,
                            "expected_count": max_inputs,
                            "remaining_count": max_inputs,
                            "completion_ratio": 0.0,
                            "count_source": "demo_default",
                            "count_label": f"0 / {max_inputs}",
                            "current_stage": "回退展示",
                            "stages": [],
                            "event_log": [],
                        },
                        "message": "尚未录入本场板卡会话，当前无法建立混合链路控制面；已回退到归档样例。",
                        "live_attempt": {
                            "status": "config_error",
                            "request_state": "completed",
                            "status_category": "config_error",
                            "message": "混合链路模式未完成会话配置，当前已回退到预录结果。",
                            "diagnostics": {"data_transport": "usrp"},
                        },
                    }
                )
            with self._lock:
                if payload.get("request_state") == "completed":
                    self._update_last_inference_summary(payload, variant)
            if event_record is not None:
                self._emit_inference_record_events(event_record, payload)
            elif payload.get("request_state") == "completed":
                self._emit_inference_rejection_events(
                    variant=variant,
                    image_index=image_index,
                    status_category=str(payload.get("status_category") or "fallback"),
                    message=str(payload.get("message") or "Live job request rejected in demo spine."),
                    diagnostics=dict(payload.get("live_attempt", {}).get("diagnostics") or {}),
                )
            return payload
        live_board_access = self._live_board_access_for_variant(board_access, variant=variant)
        variant_expected_sha = expected_sha_for_variant(live_board_access, variant) or self._trusted_current_sha
        variant_support = describe_demo_variant_support(live_board_access, variant=variant)
        missing_inference_fields = live_board_access.missing_inference_fields(variant)

        if missing_inference_fields:
            payload = self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                source_label="配置不完整，回退展示（归档样例）",
                message="远端推理配置不完整或不可用，请检查连接信息和推理环境参数。 当前已回退到预录结果。",
                detail=f"missing_fields={', '.join(missing_inference_fields)}",
                diagnostics={"missing_fields": missing_inference_fields},
                expected_count=max_inputs,
            )
            payload["live_attempt"]["status"] = "config_error"
            with self._lock:
                self._update_last_inference_summary(payload, variant)
            self._emit_inference_rejection_events(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                message=str(payload.get("message") or "Live job request rejected in demo spine."),
                diagnostics={"missing_fields": missing_inference_fields},
            )
            return payload

        if self._nontrusted_current_requires_signed_admission(
            variant=variant,
            variant_expected_sha=variant_expected_sha,
            variant_support=variant_support,
        ):
            payload = self._build_blocked_inference_payload(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                source_label="Current live 需 signed-manifest admission",
                message=(
                    "当前 Current 工件 SHA 与 OpenAMP 固件内置 legacy SHA allowlist 不一致；"
                    "如需跑这条最新链路，请切到 signed-manifest admission。"
                ),
                detail=(
                    f"legacy SHA allowlist={self._trusted_current_sha[:12]}... "
                    f"current expected_sha={variant_expected_sha[:12]}..."
                ),
                diagnostics={
                    "trusted_current_sha": self._trusted_current_sha,
                    "current_expected_sha": variant_expected_sha,
                    "admission_mode": str(variant_support.get("mode") or ""),
                },
                expected_count=max_inputs,
            )
            payload["live_attempt"]["status"] = "config_error"
            with self._lock:
                self._update_last_inference_summary(payload, variant)
            self._emit_inference_rejection_events(
                variant=variant,
                image_index=image_index,
                status_category="config_error",
                message=str(payload.get("message") or "Current live requires signed-manifest admission."),
                diagnostics=dict(payload.get("diagnostics") or {}),
            )
            return payload

        if board_access.configured:
            active_record = self._running_inference_job_record()
            if active_record is not None:
                with self._lock:
                    stale = str(active_record.get("job_id", ""))
                    if stale and stale in self._inference_jobs:
                        del self._inference_jobs[stale]
            elif board_access.probe_ready:
                status_payload = query_live_status(board_access, trusted_sha=variant_expected_sha)
                if status_payload.get("status") == "success":
                    with self._lock:
                        self._last_control_status = status_payload
                    self._emit_status_observation_events(status_payload, source="status_preflight")
                    guard_state = str(status_payload.get("guard_state") or "UNKNOWN").upper()
                    if guard_state == "JOB_ACTIVE":
                        active_job_id = int(status_payload.get("active_job_id") or 0)
                        active_suffix = f" active_job_id={active_job_id}。" if active_job_id else ""
                        message_prefix = ""
                        if variant == "current" and variant_support.get("mode") == "signed_manifest_v1":
                            message_prefix = "Current signed-admission live path 已支持，但"
                        message = (
                            f"{message_prefix}板端当前 guard_state=JOB_ACTIVE，"
                            "本次 launch 已被保守阻断，demo 不会自动 SAFE_STOP。"
                            f"{active_suffix}请等待现有作业完成，或由操作员手动 SAFE_STOP 后再重试。"
                        )
                        payload = self._build_blocked_inference_payload(
                            variant=variant,
                            image_index=image_index,
                            status_category="board_busy",
                            source_label="保守阻断（板端已有活动作业）",
                            message=message,
                            detail="STATUS_RESP 显示 guard_state=JOB_ACTIVE；未再发起新的 live launch。",
                            diagnostics={"board_status": status_payload},
                            expected_count=max_inputs,
                            event_log=status_payload.get("logs", []),
                        )
                else:
                    status_category = str(status_payload.get("status_category") or "error")
                    preflight_message = str(status_payload.get("message") or "").strip()
                    firmware_sha = (
                        str(last_live_probe.get("details", {}).get("firmware", {}).get("sha256", ""))
                        if isinstance(last_live_probe, dict)
                        else ""
                    )
                    firmware_hint = f" 最近只读探板 firmware={firmware_sha[:12]}..." if firmware_sha else ""
                    detail = (
                        "启动前 STATUS_REQ 预检未返回可用 STATUS_RESP；"
                        "demo 判定当前 lower layer 与现有 live 控制面不兼容，"
                        "不会继续发起 live launch。"
                        f"{firmware_hint}"
                    )
                    message = (
                        f"{preflight_message} 启动前 STATUS_REQ 预检未通过，"
                        "本次不再继续发起 live launch，已回退到预录结果。"
                        if preflight_message
                        else (
                            "启动前 STATUS_REQ 预检未返回 STATUS_RESP，"
                            "当前 demo 判定下层行为与现有 live 控制面不兼容；"
                            "本次不再继续发起 live launch，已回退到预录结果。"
                        )
                    )
                    diagnostics = dict(status_payload.get("diagnostics") or {})
                    diagnostics["board_status_preflight"] = status_payload
                    if isinstance(last_live_probe, dict):
                        diagnostics["last_live_probe"] = last_live_probe
                    event_log = list(status_payload.get("logs") or [])
                    if self._can_launch_runner_only_fallback(board_access=board_access, status_payload=status_payload):
                        security_context = None
                        security_blocked = None
                        security_context, security_blocked = self._arm_mlkem_security_context(
                            board_access=board_access,
                            variant=variant,
                            image_index=image_index,
                            expected_count=max_inputs,
                        )
                        if security_blocked is not None and allow_preflight_degraded:
                            security_context = None
                            security_blocked = None
                        if security_blocked is not None:
                            payload = security_blocked
                        else:
                            live_job = launch_remote_reconstruction_job(
                                live_board_access,
                                variant=variant,
                                max_inputs=max_inputs,
                                control_transport="none",
                                control_preflight=status_payload,
                                link_health_profile=self._current_link_health_profile_id(),
                            )
                            event_record, payload = self._register_live_job(
                                live_job=live_job,
                                variant=variant,
                                image_index=image_index,
                                security_context=security_context,
                            )
                    else:
                        if detail not in event_log:
                            event_log.append(detail)
                        payload = self._build_blocked_inference_payload(
                            variant=variant,
                            image_index=image_index,
                            status_category=status_category,
                            source_label="启动前检查失败，回退展示（归档样例）",
                            message=message,
                            detail=detail,
                            diagnostics=diagnostics,
                            expected_count=max_inputs,
                            event_log=event_log,
                        )
                if payload.get("status") != "fallback" and not payload.get("job_id"):
                    security_context, security_blocked = self._arm_mlkem_security_context(
                        board_access=board_access,
                        variant=variant,
                        image_index=image_index,
                        expected_count=max_inputs,
                    )
                    if security_blocked is not None:
                        payload = security_blocked
                    else:
                        live_job = launch_remote_reconstruction_job(
                            live_board_access,
                            variant=variant,
                            max_inputs=max_inputs,
                            link_health_profile=self._current_link_health_profile_id(),
                        )
                        event_record, payload = self._register_live_job(
                            live_job=live_job,
                            variant=variant,
                            image_index=image_index,
                            security_context=security_context,
                        )
            else:
                security_context, security_blocked = self._arm_mlkem_security_context(
                    board_access=board_access,
                    variant=variant,
                    image_index=image_index,
                    expected_count=max_inputs,
                )
                if security_blocked is not None:
                    payload = security_blocked
                else:
                    live_job = launch_remote_reconstruction_job(
                        live_board_access,
                        variant=variant,
                        max_inputs=max_inputs,
                        link_health_profile=self._current_link_health_profile_id(),
                    )
                    event_record, payload = self._register_live_job(
                        live_job=live_job,
                        variant=variant,
                        image_index=image_index,
                        security_context=security_context,
                    )
        else:
            payload.update(
                {
                    "status": "fallback",
                    "request_state": "completed",
                    "status_category": "config_error",
                    "timings": self._empty_live_timings(),
                    "live_progress": {
                        "state": "completed",
                        "label": "回退展示",
                        "tone": "degraded",
                        "percent": 0,
                        "phase_percent": 100,
                        "completed_count": 0,
                        "expected_count": max_inputs,
                        "remaining_count": max_inputs,
                        "completion_ratio": 0.0,
                        "count_source": "demo_default",
                        "count_label": f"0 / {max_inputs}",
                        "current_stage": "回退展示",
                        "stages": [],
                        "event_log": [],
                    },
                    "message": "尚未录入本场板卡会话，当前展示归档样例与正式速度报告。",
                    "live_attempt": {
                        "status": "config_error",
                        "request_state": "completed",
                        "status_category": "config_error",
                        "message": "远端推理配置不完整或不可用。 当前已回退到预录结果。",
                        "diagnostics": {},
                    },
                }
            )

        with self._lock:
            if payload.get("request_state") == "completed":
                self._update_last_inference_summary(payload, variant)
        if event_record is not None:
            self._emit_inference_record_events(event_record, payload)
        elif payload.get("request_state") == "completed":
            self._emit_inference_rejection_events(
                variant=variant,
                image_index=image_index,
                status_category=str(payload.get("status_category") or "fallback"),
                message=str(payload.get("message") or "Live job request rejected in demo spine."),
                diagnostics=dict(payload.get("live_attempt", {}).get("diagnostics") or {}),
            )
        return payload

    def get_inference_progress(self, job_id: str) -> dict[str, Any]:
        payload = self._peek_inference_progress(job_id)
        with self._lock:
            record = self._inference_jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        with self._lock:
            if payload.get("request_state") == "completed":
                self._update_last_inference_summary(payload, record["variant"])
        self._emit_inference_record_events(record, payload)
        return payload

    def run_fault_demo(self, fault_type: str) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access

        if board_access.probe_ready:
            live_result = run_fault_action(
                board_access,
                fault_type=fault_type,
                trusted_sha=self._current_trusted_sha(board_access),
            )
            if live_result.get("status") == "success":
                response = {
                    "status": "injected",
                    "status_category": "success",
                    "execution_mode": "live",
                    "fault_type": fault_type,
                    "source_label": "真机注入",
                    "message": "已使用当前会话凭据执行 RPMsg 故障注入。",
                    "board_response": live_result.get("board_response", {}),
                    "guard_state": live_result.get("guard_state", "UNKNOWN"),
                    "last_fault_code": live_result.get("last_fault_code", "UNKNOWN"),
                    "status_lamp": "green" if live_result.get("last_fault_code") == "NONE" else "red",
                    "log_entries": live_result.get("logs", []),
                    "details": live_result,
                }
                with self._lock:
                    self._last_control_status = live_result
                    self._last_fault_result = {
                        "fault_type": fault_type,
                        "status": response["status"],
                        "status_category": response["status_category"],
                        "execution_mode": response["execution_mode"],
                        "message": response["message"],
                        "guard_state": response["guard_state"],
                        "last_fault_code": response["last_fault_code"],
                    }
                self._event_spine.publish(
                    "JOB_SUBMITTED",
                    source="fault",
                    plane="control",
                    mode_scope=CONTROL_MODE_SCOPE,
                    message=f"{fault_type} fault demo submitted a control-plane job request.",
                    data={"fault_type": fault_type},
                )
                if fault_type == "heartbeat_timeout":
                    self._event_spine.publish(
                        "JOB_ADMITTED",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message="Heartbeat timeout FIT received an ALLOW admission before watchdog expiry.",
                        data={"fault_type": fault_type},
                    )
                    self._event_spine.publish(
                        "HEARTBEAT_OK",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message="Heartbeat ACK observed before watchdog timeout during FIT-03.",
                        data={"fault_type": fault_type},
                    )
                    self._event_spine.publish(
                        "HEARTBEAT_LOST",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message="Heartbeat watchdog timeout observed during FIT-03.",
                        data={"fault_type": fault_type, "last_fault_code": response["last_fault_code"]},
                    )
                    self._event_spine.publish(
                        "SAFE_STOP_TRIGGERED",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message="SAFE_STOP cleanup triggered after heartbeat timeout FIT.",
                        data={"fault_type": fault_type, "reason": "heartbeat_timeout_cleanup"},
                    )
                    self._event_spine.publish(
                        "SAFE_STOP_CLEARED",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message="SAFE_STOP cleanup returned the board to READY after heartbeat timeout FIT.",
                        data={"fault_type": fault_type, "reason": "heartbeat_timeout_cleanup"},
                    )
                else:
                    self._event_spine.publish(
                        "JOB_REJECTED",
                        source="fault",
                        plane="control",
                        mode_scope=CONTROL_MODE_SCOPE,
                        message=f"{fault_type} fault demo ended in the expected rejection state.",
                        data={"fault_type": fault_type, "last_fault_code": response["last_fault_code"]},
                    )
                self._archive_event_snapshot(
                    reason=f"fault_{fault_type}",
                    extra={"fault_type": fault_type, "execution_mode": response["execution_mode"]},
                )
                return response
            replay = build_fault_replay(fault_type)
            replay["status_category"] = live_result.get("status_category", "fallback")
            replay["live_attempt"] = live_result
            replay["message"] = f"{live_result.get('message', '真机注入失败')} 已切换到 {replay['source_label']}。"
        else:
            replay = build_fault_replay(fault_type)
            replay["status_category"] = "fallback"
        with self._lock:
            self._last_fault_result = {
                "fault_type": fault_type,
                "status": replay["status"],
                "status_category": replay.get("status_category", "fallback"),
                "execution_mode": replay["execution_mode"],
                "message": replay["message"],
                "guard_state": replay["guard_state"],
                "last_fault_code": replay["last_fault_code"],
            }
            # ── Replay: also update control status so the dashboard panel reflects the change ──
            replay_control = dict(self._last_control_status or {})
            replay_control["guard_state"] = replay["guard_state"]
            replay_control["last_fault_code"] = replay["last_fault_code"]
            replay_control["total_fault_count"] = self._safe_int(replay_control.get("total_fault_count"), default=0) + 1
            if fault_type == "heartbeat_timeout":
                replay_control["heartbeat_ok"] = self._safe_int(replay_control.get("heartbeat_ok"), default=0) + 1
            self._last_control_status = replay_control
            self._crypto_status_cache = None  # force instant refresh on next poll
        # ── Replay: publish event_spine events so timeline and counters update ──
        self._event_spine.publish(
            "JOB_SUBMITTED",
            source="fault",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message=f"{fault_type} fault demo submitted (replay mode).",
            data={"fault_type": fault_type, "execution_mode": "replay"},
        )
        if fault_type == "heartbeat_timeout":
            self._event_spine.publish(
                "JOB_ADMITTED",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Heartbeat timeout FIT replay: job admitted before watchdog.",
                data={"fault_type": fault_type},
            )
            self._event_spine.publish(
                "HEARTBEAT_OK",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Heartbeat ACK observed (replay).",
                data={"fault_type": fault_type},
            )
            self._event_spine.publish(
                "HEARTBEAT_LOST",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Heartbeat watchdog timeout (replay).",
                data={"fault_type": fault_type, "last_fault_code": replay["last_fault_code"]},
            )
            self._event_spine.publish(
                "SAFE_STOP_TRIGGERED",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="SAFE_STOP triggered after heartbeat timeout (replay).",
                data={"fault_type": fault_type},
            )
            self._event_spine.publish(
                "SAFE_STOP_CLEARED",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="SAFE_STOP cleared, guard returned to READY (replay).",
                data={"fault_type": fault_type},
            )
        else:
            self._event_spine.publish(
                "JOB_REJECTED",
                source="fault",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message=f"{fault_type} fault demo rejected as expected (replay).",
                data={"fault_type": fault_type, "last_fault_code": replay["last_fault_code"]},
            )
        return replay

    def recover_fault(self) -> dict[str, Any]:
        with self._lock:
            board_access = self._board_access
            control_status = self._last_control_status
            last_fault = self._last_fault_result

        retained_fault_code = ""
        if last_fault and last_fault.get("last_fault_code"):
            retained_fault_code = str(last_fault.get("last_fault_code") or "")
        elif control_status and control_status.get("last_fault_code"):
            retained_fault_code = str(control_status.get("last_fault_code") or "")

        if board_access.probe_ready:
            live_result = run_recover_action(board_access, trusted_sha=self._current_trusted_sha(board_access))
            if live_result.get("status") == "success":
                guard_state = live_result.get("guard_state", "UNKNOWN")
                last_fault_code = live_result.get("last_fault_code", "UNKNOWN")
                response = {
                    "status": "recovered",
                    "status_category": "success",
                    "execution_mode": "live",
                    "source_label": "真机 SAFE_STOP 收口",
                    "message": recover_message(guard_state, last_fault_code),
                    "board_response": live_result.get("board_response", {}),
                    "guard_state": guard_state,
                    "last_fault_code": last_fault_code,
                    "status_lamp": recover_status_lamp(guard_state, last_fault_code),
                    "log_entries": live_result.get("logs", []),
                    "details": live_result,
                }
                with self._lock:
                    self._last_control_status = live_result
                    self._last_fault_result = {
                        "fault_type": "recover",
                        "status": response["status"],
                        "status_category": response["status_category"],
                        "execution_mode": response["execution_mode"],
                        "message": response["message"],
                        "guard_state": response["guard_state"],
                        "last_fault_code": response["last_fault_code"],
                    }
                self._event_spine.publish(
                    "SAFE_STOP_TRIGGERED",
                    source="recover",
                    plane="control",
                    mode_scope=CONTROL_MODE_SCOPE,
                    message="Operator-triggered SAFE_STOP entered the demo event spine.",
                    data={"reason": "manual_recover", "last_fault_code": last_fault_code},
                )
                self._event_spine.publish(
                    "SAFE_STOP_CLEARED",
                    source="recover",
                    plane="control",
                    mode_scope=CONTROL_MODE_SCOPE,
                    message="SAFE_STOP returned the board to READY.",
                    data={"reason": "manual_recover", "last_fault_code": last_fault_code},
                )
                self._archive_event_snapshot(
                    reason="recover_safe_stop",
                    extra={"guard_state": guard_state, "last_fault_code": last_fault_code},
                )
                return response
            replay = build_recover_replay(retained_fault_code)
            replay["status_category"] = live_result.get("status_category", "fallback")
            replay["live_attempt"] = live_result
            replay["message"] = f"{live_result.get('message', '真机恢复失败')} 已切换到安全恢复回放。"
        else:
            replay = build_recover_replay(retained_fault_code)
            replay["status_category"] = "fallback"
        with self._lock:
            self._last_fault_result = {
                "fault_type": "recover",
                "status": replay["status"],
                "status_category": replay.get("status_category", "fallback"),
                "execution_mode": replay["execution_mode"],
                "message": replay["message"],
                "guard_state": replay["guard_state"],
                "last_fault_code": replay["last_fault_code"],
            }
            # ── Replay: update control status to reflect recovery ──
            replay_control = dict(self._last_control_status or {})
            replay_control["guard_state"] = replay["guard_state"]
            replay_control["last_fault_code"] = replay["last_fault_code"]
            self._last_control_status = replay_control
            self._crypto_status_cache = None  # force instant refresh on next poll
        # ── Replay: publish event_spine events for recovery ──
        self._event_spine.publish(
            "SAFE_STOP_TRIGGERED",
            source="recover",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message="Operator-triggered SAFE_STOP (replay).",
            data={"reason": "manual_recover", "last_fault_code": replay["last_fault_code"]},
        )
        self._event_spine.publish(
            "SAFE_STOP_CLEARED",
            source="recover",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message="SAFE_STOP returned guard to READY (replay).",
            data={"reason": "manual_recover", "last_fault_code": replay["last_fault_code"]},
        )
        return replay


class DemoHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type["DemoRequestHandler"], app_state: DashboardState) -> None:
        super().__init__(server_address, handler)
        self.app_state = app_state


def demo_startup_env_overrides(args: argparse.Namespace) -> dict[str, str]:
    overrides: dict[str, str] = {}
    aircraft_position_env_path = str(getattr(args, "aircraft_position_env", "") or "").strip()
    if aircraft_position_env_path:
        _, env_values = load_env_file(aircraft_position_env_path)
        overrides.update({str(key): str(value) for key, value in env_values.items() if str(value).strip()})

    for env_name in AIRCRAFT_POSITION_RUNTIME_ENV_KEYS:
        env_value = str(os.environ.get(env_name, "") or "").strip()
        if env_value:
            overrides[env_name] = env_value

    for env_name, default_value in DEFAULT_DEMO_AIRCRAFT_POSITION_LOCAL_OVERRIDES.items():
        if env_name not in overrides:
            overrides[env_name] = default_value

    env_or_arg_pairs = (
        (DEMO_ADMISSION_MODE_ENV, str(getattr(args, "demo_admission_mode", "") or "").strip()),
        (DEMO_SIGNED_MANIFEST_FILE_ENV, str(getattr(args, "signed_manifest_file", "") or "").strip()),
        (DEMO_SIGNED_MANIFEST_PUBLIC_KEY_ENV, str(getattr(args, "signed_manifest_public_key", "") or "").strip()),
        (DEMO_BASELINE_ADMISSION_MODE_ENV, str(getattr(args, "baseline_admission_mode", "") or "").strip()),
        (
            DEMO_BASELINE_SIGNED_MANIFEST_FILE_ENV,
            str(getattr(args, "baseline_signed_manifest_file", "") or "").strip(),
        ),
        (
            DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY_ENV,
            str(getattr(args, "baseline_signed_manifest_public_key", "") or "").strip(),
        ),
        ("REMOTE_PASS", ""),
        ("PHYTIUM_PI_PASSWORD", ""),
        ("MLKEM_REMOTE_OQS_INSTALL_PATH", ""),
        ("MLKEM_REMOTE_LD_LIBRARY_PATH", ""),
        ("MLKEM_REMOTE_TONGSUO_KEM_BRIDGE", ""),
        ("MLKEM_REMOTE_TONGSUO_SIG_BRIDGE", ""),
        ("MLKEM_REMOTE_RUN_LOGGER_DIR", ""),
        ("RUN_LOGGER_DIR", ""),
        ("MLKEM_AUTH_SERVER_SM2_KEY", ""),
        ("MLKEM_AUTH_SERVER_SM2_PUB", ""),
        ("MLKEM_AUTH_SERVER_MLDSA_KEY", ""),
        ("MLKEM_AUTH_SERVER_MLDSA_PUB", ""),
        ("MLKEM_AUTH_PEER_SM2_PUB", ""),
        ("MLKEM_AUTH_PEER_MLDSA_PUB", ""),
        ("MLKEM_LOCAL_TONGSUO_KEM_BRIDGE", ""),
        ("MLKEM_LOCAL_LD_LIBRARY_PATH", ""),
        ("TONGSUO_KEM_BRIDGE", ""),
        ("TONGSUO_SIG_BRIDGE", ""),
        ("OQS_INSTALL_PATH", ""),
        ("REMOTE_USRP_RX_DIR", ""),
        ("MLKEM_TRANSPORT_MODE", ""),
        ("MLKEM_USRP_MODE", ""),
        ("OPENAMP_DEMO_INPUT_SOURCE_MODE", ""),
        ("OPENAMP_DEMO_LINK_MODE", ""),
        ("OPENAMP_DEMO_LOCAL_LATENT_DIR", ""),
        ("OPENAMP_DEMO_LOCAL_LATENT_PATTERN", ""),
        ("OPENAMP_DEMO_LOCAL_IMAGE_DIR", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_SCRIPT", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_OUTPUT_DIR", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_DEVICE", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_CONFIG", ""),
        ("OPENAMP_DEMO_IMAGE_TO_LATENT_SNR", ""),
        ("OPENAMP_DEMO_USRP_PAYLOAD_CODEC", ""),
        ("OPENAMP_DEMO_USRP_WIRE_PREPARE_WORKERS", ""),
        ("OPENAMP_DEMO_USRP_WIRE_CACHE_ENABLED", ""),
        ("OPENAMP_DEMO_USRP_WIRE_CACHE_DIR", ""),
        ("USRP_WIRE_PREPARE_WORKERS", ""),
        ("USRP_WIRE_CACHE_ENABLED", ""),
        ("USRP_WIRE_CACHE_DIR", ""),
        ("OPENAMP_DEMO_REMOTE_DECODE_PYTHON", ""),
        ("REMOTE_USRP_DECODE_PYTHON", ""),
        ("MLKEM_USRP_RUNNER_SCRIPT", ""),
        ("MLKEM_USRP_INPUT_DIR", ""),
        ("MLKEM_USRP_INPUT_FILE", ""),
        ("MLKEM_USRP_RUN_ROOT", ""),
        ("MLKEM_USRP_MAX_ARQ_ROUNDS", ""),
        ("USRP_FAST_ARQ_PROFILE", ""),
        ("USRP_STOP_ON_FAIL", ""),
        ("USRP_AUTO_START_CONTROL", ""),
        ("OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT", ""),
        ("USRP_SHUTDOWN_CONTROL_AFTER_TRANSPORT", ""),
        ("RX_CONTROL_HOST", ""),
        ("RX_CONTROL_PORT", ""),
        ("TX_CONTROL_HOST", ""),
        ("TX_CONTROL_PORT", ""),
        ("RX_CAPTURE_MODE", ""),
        ("REMOTE_RX_SSH_TARGET", ""),
        ("REMOTE_RX_RUN_ROOT", ""),
        ("REMOTE_USRP_PROJECT_ROOT", ""),
        ("REMOTE_DECODE_BIN", ""),
        ("OPENAMP_SSH_RUNNER", ""),
        ("OPENAMP_SSH_DOCKER_IMAGE", ""),
        ("SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER", ""),
        ("OPENAMP_USRP_TX_RUNNER", ""),
        ("OPENAMP_USRP_TX_DOCKER_IMAGE", ""),
        ("OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET", ""),
        ("OPENAMP_TVM_BATCH_RUNNER", ""),
        ("OPENAMP_DEMO_TVM_BATCH_RUNNER", ""),
        ("OPENAMP_TVM_BATCH_EXIT_GRACE_SEC", ""),
        ("TX_ARGS", ""),
        ("RX_ARGS", ""),
        ("RX_ARM_WAIT_MS", ""),
        ("RX_STOP_WAIT_MS", ""),
        ("RATE", ""),
        ("FREQ", ""),
        ("TX_GAIN", ""),
        ("RX_GAIN", ""),
        ("RX_ANT", ""),
        ("BIND_ADDR", ""),
        ("FRAME_CANDIDATES", ""),
        ("BATCH_RX_TIMEOUT_SEC", ""),
        ("BATCH_TX_TIMEOUT_SEC", ""),
        ("USRP_JOB_TIMEOUT_SEC", ""),
        ("BATCH_SIZE", ""),
        ("BATCH_DECODE_WORKERS", ""),
        ("CHUNK_BYTES", ""),
        ("QPSK_DECODE_BACKEND", ""),
        ("QPSK_CPP_SYNC_MODE", ""),
        # ── IQ 直传模式开关 + AnalogLatentLink 参数透传 ──
        ("JSCC_LINK_MODE", ""),
        ("ANALOG_SPS", ""),
        ("ANALOG_AMPLITUDE", ""),
        ("ANALOG_RRC_BETA", ""),
        ("ANALOG_RRC_SPAN", ""),
        ("AMPLITUDE", ""),
        ("ANALOG_RX_TAIL_SEC", ""),
        ("PERSISTENT_RX_TX_DELAY", ""),
        ("ANALOG_REMOTE_CLEANUP_MODE", ""),
        ("ANALOG_PRECONNECT_CONTROL", ""),
        ("ANALOG_PRECONNECT_RX_CAPTURE_CONTROL", ""),
        ("ANALOG_RX_SESSION_CONTROL", ""),
        ("ANALOG_ZERO_GUARD_SAMPLES", ""),
        ("ANALOG_TAIL_GUARD_SAMPLES", ""),
        ("ANALOG_CFO_PILOT_SYMBOLS", ""),
        ("ANALOG_SYNC_PILOT_SYMBOLS", ""),
        ("ANALOG_DATA_BLOCK_SYMBOLS", ""),
        ("ANALOG_MID_PILOT_SYMBOLS", ""),
        ("ANALOG_CAPTURE_MARGIN_SAMPLES", ""),
        ("ANALOG_RX_POST_QUANTIZE", ""),
        ("ANALOG_RX_ARM_STATUS_TIMEOUT_SEC", ""),
        ("ANALOG_RX_ARM_STATUS_POLL_SEC", ""),
        ("ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC", ""),
        ("ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC", ""),
        ("ANALOG_RX_STOP_DRAIN_POLL_SEC", ""),
        ("ANALOG_PIPELINE_DEPTH", ""),
        ("ANALOG_ROBUST_SYNC", ""),
        ("ANALOG_MIN_SYNC_METRIC", ""),
        ("ANALOG_ROBUST_CFO_MAX_HZ", ""),
        ("ANALOG_ROBUST_CFO_STEP_HZ", ""),
        ("ANALOG_SYNC_PROFILE", ""),
        ("ANALOG_SYNC_CANDIDATES", ""),
        ("ANALOG_FAST_SYNC_CANDIDATES", ""),
        ("ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS", ""),
        ("ANALOG_FALLBACK_SYNC_CANDIDATES", ""),
        ("ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS", ""),
        ("ANALOG_RETRY_ON_BURST_MISS", ""),
        ("ANALOG_RETRY_ON_LOW_SYNC", ""),
        ("ANALOG_LOW_SYNC_RETRY_THRESHOLD", ""),
        ("ANALOG_REMOTE_DECODE_RESULT_MODE", ""),
        ("ANALOG_REMOTE_DECODED_OUTPUT_DIR", ""),
        ("ANALOG_REMOTE_DECODE_RESPONSE_MODE", ""),
        ("ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY", ""),
        ("ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC", ""),
        ("ANALOG_REMOTE_DECODE_WORKER_PREFIX", ""),
        ("ANALOG_REMOTE_DECODE_REQUEST_TIMEOUT_SEC", ""),
        ("ANALOG_REMOTE_DECODE_RESTART_ON_TIMEOUT", ""),
        ("ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_SEC", ""),
        ("ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC", ""),
        ("ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS", ""),
        ("ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK", ""),
        ("ANALOG_SCRAMBLE_KEY", ""),
        ("ANALOG_SCRAMBLE_KEY_HEX", ""),
        ("ANALOG_SCRAMBLE_CONTEXT", ""),
        ("ANALOG_SIM_CFO_HZ", ""),
        ("ANALOG_SIM_SNR_DB", ""),
        ("ANALOG_SIM_GAIN", ""),
        ("ANALOG_SIM_PHASE_DEG", ""),
        ("ANALOG_SIM_PHASE_DRIFT_DEG", ""),
        ("ANALOG_SIM_DC_REAL", ""),
        ("ANALOG_SIM_DC_IMAG", ""),
        ("ANALOG_SIM_SEED", ""),
    )

    for env_name, cli_value in env_or_arg_pairs:
        value = cli_value or str(os.environ.get(env_name, "") or "").strip()
        if value:
            overrides[env_name] = value
    raw_transport_mode = str(overrides.get("MLKEM_TRANSPORT_MODE") or "").strip()
    try:
        usrp_startup = normalize_transport_mode(raw_transport_mode) == "usrp"
    except ValueError:
        usrp_startup = raw_transport_mode.lower() == "usrp"
    usrp_startup = usrp_startup or str(overrides.get("OPENAMP_DEMO_INPUT_SOURCE_MODE") or "").strip().lower() == "usrp"
    if usrp_startup:
        overrides.setdefault("OPENAMP_DEMO_INPUT_SOURCE_MODE", "usrp")
        if not str(overrides.get("OPENAMP_DEMO_LOCAL_LATENT_DIR") or "").strip():
            local_latent_dir = DashboardState._discover_default_local_usrp_latent_dir()
            if local_latent_dir:
                overrides["OPENAMP_DEMO_LOCAL_LATENT_DIR"] = local_latent_dir
                overrides.setdefault("OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED", "0")
    return overrides


class DemoRequestHandler(SimpleHTTPRequestHandler):
    server: DemoHTTPServer

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_cors_headers(self) -> None:
        """Allow local Electron/renderer to call JSON APIs across origins (dev + file:// builds)."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            self.respond_json(HTTPStatus.OK, self.server.app_state.current_snapshot())
            return
        if parsed.path == "/api/job-manifest-gate":
            params = parse_qs(parsed.query)
            try:
                variant = self.coerce_variant(params.get("variant", ["current"])[0])
            except ValueError as exc:
                self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
                return
            self.respond_json(
                HTTPStatus.OK,
                {"status": "ok", "gate": self.server.app_state.current_job_manifest_gate_status(variant=variant)},
            )
            return
        if parsed.path == "/api/link-director":
            self.respond_json(HTTPStatus.OK, self.server.app_state.current_link_director_status())
            return
        if parsed.path == "/api/aircraft-position":
            self.respond_json(HTTPStatus.OK, self.server.app_state.current_aircraft_position())
            return
        if parsed.path == "/api/event-spine":
            params = parse_qs(parsed.query)
            limit = max(1, min(100, self.coerce_int(params.get("limit", ["25"])[0], default=25)))
            self.respond_json(HTTPStatus.OK, self.server.app_state.current_event_spine(limit=limit))
            return
        if parsed.path == "/api/archive/sessions":
            params = parse_qs(parsed.query)
            limit = max(1, min(100, self.coerce_int(params.get("limit", ["25"])[0], default=25)))
            self.respond_json(HTTPStatus.OK, self.server.app_state.list_archive_sessions(limit=limit))
            return
        if parsed.path == "/api/archive/session":
            params = parse_qs(parsed.query)
            session_id = str(params.get("session_id", [""])[0]).strip()
            limit = max(1, min(100, self.coerce_int(params.get("limit", ["25"])[0], default=25)))
            try:
                payload = self.server.app_state.current_archive_session(session_id=session_id, recent_limit=limit)
            except ArchiveSessionNotFoundError as exc:
                self.respond_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": str(exc)})
                return
            self.respond_json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/system-status":
            self.respond_json(HTTPStatus.OK, self.server.app_state.current_system_status())
            return
        if parsed.path == "/api/crypto-status":
            self.respond_json(HTTPStatus.OK, self.server.app_state.get_crypto_status())
            return
        if parsed.path == "/api/health":
            self.respond_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/inference-progress":
            params = parse_qs(parsed.query)
            job_id = str(params.get("job_id", [""])[0]).strip()
            if not job_id:
                self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "missing job_id"})
                return
            try:
                payload = self.server.app_state.get_inference_progress(job_id)
            except KeyError:
                self.respond_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "job not found"})
                return
            self.respond_json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/usrp-control":
            self.respond_json(HTTPStatus.OK, self.server.app_state.get_usrp_control_status())
            return
        if parsed.path == "/docs":
            self.respond_doc_view(parsed.query)
            return
        if parsed.path == "/api/batch-state":
            self.respond_json(HTTPStatus.OK, self.server.app_state.get_batch_state())
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self.read_json_body()
        if body is None:
            return
        try:
            if parsed.path == "/api/crypto-toggle":
                enabled = bool(body.get("enabled", False))
                payload = self.server.app_state.set_crypto_toggle(enabled)
                self.respond_json(HTTPStatus.OK, {"status": "ok", **payload})
                return
            if parsed.path == "/api/crypto-test":
                payload = self.server.app_state.run_crypto_test()
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/crypto-reset":
                payload = self.server.app_state.reset_crypto_channel(
                    restart_remote_server=bool(body.get("restart_remote_server", True)),
                )
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/session/board-access":
                try:
                    payload = self.server.app_state.set_board_access(body)
                except ValueError as exc:
                    self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
                    return
                self.respond_json(HTTPStatus.OK, {"status": "ok", "board_access": payload})
                return
            if parsed.path == "/api/usrp-control/start":
                payload = self.server.app_state.start_usrp_control()
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/usrp-control/stop":
                payload = self.server.app_state.stop_usrp_control()
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/link-director/profile":
                try:
                    payload = self.server.app_state.set_link_director_profile(body)
                except ValueError as exc:
                    self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
                    return
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/aircraft-position":
                payload = self.server.app_state.set_aircraft_position(body)
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/probe-board":
                payload = self.server.app_state.refresh_live_probe()
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/job-manifest-gate/preview":
                try:
                    variant = self.coerce_variant(body.get("variant"), default="current")
                except ValueError as exc:
                    self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": str(exc)})
                    return
                payload = self.server.app_state.preview_job_manifest_gate(variant=variant)
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/run-inference":
                image_index = self.coerce_int(body.get("image_index"), default=0)
                variant = str(body.get("mode") or "current").strip().lower() or "current"
                allow_preflight_degraded = bool(body.get("allow_preflight_degraded", True))
                payload = self.server.app_state.run_demo_inference(
                    variant=variant,
                    image_index=image_index,
                    allow_preflight_degraded=allow_preflight_degraded,
                )
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/run-baseline":
                image_index = self.coerce_int(body.get("image_index"), default=0)
                max_inputs = self.coerce_int(body.get("max_inputs"), default=DEFAULT_MAX_INPUTS)
                max_inputs = max(1, min(max_inputs, 1000))
                payload = self.server.app_state.run_demo_inference(
                    variant="baseline",
                    image_index=image_index,
                    max_inputs=max_inputs,
                )
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/run-inference-batch":
                count = self.coerce_int(body.get("count"), default=300)
                count = max(1, min(count, 1000))
                allow_degraded = bool(body.get("allow_preflight_degraded", True))
                payload = self.server.app_state.start_batch_inference(
                    count=count,
                    allow_preflight_degraded=allow_degraded,
                )
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/run-mnn-batch":
                count = self.coerce_int(body.get("count"), default=300)
                count = max(1, min(count, 1000))
                payload = self.server.app_state.start_mnn_batch_inference(count=count)
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/inject-fault":
                fault_type = str(body.get("fault_type") or "").strip()
                if fault_type not in {"wrong_sha", "illegal_param", "heartbeat_timeout"}:
                    self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "unsupported fault_type"})
                    return
                payload = self.server.app_state.run_fault_demo(fault_type)
                self.respond_json(HTTPStatus.OK, payload)
                return
            if parsed.path == "/api/recover":
                payload = self.server.app_state.recover_fault()
                self.respond_json(HTTPStatus.OK, payload)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            try:
                self.respond_json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                })
            except Exception:
                pass

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def read_json_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "invalid json body"})
            return None
        if not isinstance(payload, dict):
            self.respond_json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": "json body must be an object"})
            return None
        return payload

    def coerce_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def coerce_variant(self, value: Any, default: str = "current") -> str:
        variant = str(value or default).strip().lower() or default
        if variant not in {"current", "baseline"}:
            raise ValueError("unsupported variant")
        return variant

    def respond_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def respond_doc_view(self, query: str) -> None:
        params = parse_qs(query)
        raw_path = params.get("path", [""])[0]
        if not raw_path:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
            return
        try:
            path = resolve_repo_path(raw_path)
        except (ValueError, OSError):
            self.send_error(HTTPStatus.BAD_REQUEST, "invalid path")
            return
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        if path.suffix == ".json":
            content = json.dumps(json.loads(read_text(path)), ensure_ascii=False, indent=2)
        else:
            content = read_text(path)

        body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(repo_relative(path))}</title>
  <style>
    body {{
      margin: 0;
      font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Helvetica Neue", sans-serif;
      background: linear-gradient(180deg, #f3efe6 0%, #fcfbf8 100%);
      color: #123041;
    }}
    header {{
      padding: 1.25rem 1.5rem 1rem;
      border-bottom: 1px solid rgba(18, 48, 65, 0.12);
      background: rgba(255, 255, 255, 0.9);
      position: sticky;
      top: 0;
    }}
    a {{
      color: #a04b14;
      text-decoration: none;
      font-weight: 700;
    }}
    main {{
      padding: 1.25rem 1.5rem 2rem;
    }}
    pre {{
      margin: 0;
      overflow: auto;
      padding: 1rem;
      border-radius: 16px;
      background: #102635;
      color: #f7f1e8;
      line-height: 1.55;
      font-size: 0.92rem;
    }}
    .path {{
      font-family: "Noto Serif SC", "Source Han Serif SC", "STSong", serif;
      font-size: 1.15rem;
      margin-bottom: 0.35rem;
    }}
  </style>
</head>
<body>
  <header>
    <div class="path">{html.escape(repo_relative(path))}</div>
    <a href="/">返回演示系统</a>
  </header>
  <main><pre>{html.escape(content)}</pre></main>
</body>
</html>
""".encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"


def main() -> int:
    args = parse_args()
    app_state = DashboardState(
        args.probe_env,
        args.probe_timeout_sec,
        demo_startup_env_overrides=demo_startup_env_overrides(args),
        event_archive_root=default_event_archive_root(),
        bind_host=args.host,
        bind_port=args.port,
    )
    if args.probe_startup:
        app_state.refresh_live_probe()
    server = DemoHTTPServer((args.host, args.port), DemoRequestHandler, app_state)
    print(f"Feiteng semantic visual return demo dashboard: http://{args.host}:{args.port}")
    print(f"Project root: {PROJECT_ROOT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
