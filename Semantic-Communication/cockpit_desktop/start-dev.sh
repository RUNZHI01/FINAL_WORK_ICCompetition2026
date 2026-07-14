#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PACKAGE_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
BACKEND_HOST="${COCKPIT_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
FRONTEND_PORT="${COCKPIT_FRONTEND_PORT:-5173}"
BACKEND_LOG="${TMPDIR:-/tmp}/openamp-server.log"
FRONTEND_LOG="${TMPDIR:-/tmp}/cockpit-vite.log"
DEFAULT_AIRCRAFT_POSITION_ENV="$REPO_ROOT/session_bootstrap/tmp/aircraft_position_baidu_ip.local.env"
AUTH_KEYS_DIR="$PACKAGE_ROOT/keys"
AUTH_PUBLIC_KEYS_ARCHIVE="$PACKAGE_ROOT/board_deps/crypto/public_keys/board-auth-public-keys.tar.gz"

to_windows_path() {
  local path="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path"
    return 0
  fi
  (cd "$path" && pwd -W) 2>/dev/null || printf '%s\n' "$path"
}

stop_windows_port_listeners() {
  local port="$1"
  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi
  COCKPIT_STOP_PORT="$port" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
    $ErrorActionPreference = "SilentlyContinue"
    $port = [int]$env:COCKPIT_STOP_PORT
    Get-NetTCPConnection -State Listen -LocalPort $port |
      Select-Object -ExpandProperty OwningProcess -Unique |
      Where-Object { $_ -and $_ -ne $PID } |
      ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  ' >/dev/null 2>&1 || true
}

stop_windows_cockpit_processes() {
  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi
  local repo_root_win script_dir_win
  repo_root_win="$(to_windows_path "$REPO_ROOT")"
  script_dir_win="$(to_windows_path "$SCRIPT_DIR")"
  COCKPIT_REPO_ROOT_WIN="$repo_root_win" \
  COCKPIT_SCRIPT_DIR_WIN="$script_dir_win" \
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
      $ErrorActionPreference = "SilentlyContinue"
      $roots = @($env:COCKPIT_REPO_ROOT_WIN, $env:COCKPIT_SCRIPT_DIR_WIN) |
        Where-Object { $_ } |
        ForEach-Object { [regex]::Escape($_) }
      $serverPattern = "Semantic-Communication[/\\]session_bootstrap[/\\]demo[/\\]openamp_control_plane_demo[/\\]server\.py"
      $targetPatterns = @(
        "server\.py.*--host.*--port",
        "electron-vite(\.js)?\s+dev",
        "npm-cli\.js.*run\s+dev",
        "electron\.exe.*cockpit_desktop",
        "esbuild\.exe.*--service="
      )
      Get-CimInstance Win32_Process | Where-Object {
        $cmd = $_.CommandLine
        if (-not $cmd) {
          $false
        } else {
          $inTree = (($roots | Where-Object { $cmd -match $_ }).Count -gt 0)
          $matchesTarget = (($targetPatterns | Where-Object { $cmd -match $_ }).Count -gt 0)
          ($inTree -and $matchesTarget) -or ($cmd -match $serverPattern)
        }
      } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      }
    ' >/dev/null 2>&1 || true
}

ensure_auth_public_keys() {
  if [[ -f "$AUTH_KEYS_DIR/server_sm2_identity.pub" && -f "$AUTH_KEYS_DIR/server_mldsa_identity.pub" ]]; then
    return 0
  fi
  if [[ ! -f "$AUTH_PUBLIC_KEYS_ARCHIVE" ]]; then
    return 0
  fi
  mkdir -p "$AUTH_KEYS_DIR"
  tar -xzf "$AUTH_PUBLIC_KEYS_ARCHIVE" -C "$AUTH_KEYS_DIR"
}

configure_runtime_defaults() {
  ensure_auth_public_keys
  local auth_keys_dir_win
  auth_keys_dir_win="$(to_windows_path "$AUTH_KEYS_DIR")"
  if command -v powershell.exe >/dev/null 2>&1; then
    export OPENAMP_SSH_RUNNER="${OPENAMP_SSH_RUNNER:-docker}"
    export OPENAMP_SSH_DOCKER_IMAGE="${OPENAMP_SSH_DOCKER_IMAGE:-iccomp-usrp-tx:latest}"
    export MLKEM_LOCAL_CLIENT_RUNNER="${MLKEM_LOCAL_CLIENT_RUNNER:-docker}"
    export MLKEM_LOCAL_CLIENT_DOCKER_IMAGE="${MLKEM_LOCAL_CLIENT_DOCKER_IMAGE:-$OPENAMP_SSH_DOCKER_IMAGE}"
    export OPENAMP_USRP_TX_RUNNER="${OPENAMP_USRP_TX_RUNNER:-docker}"
    export OPENAMP_USRP_TX_DOCKER_IMAGE="${OPENAMP_USRP_TX_DOCKER_IMAGE:-iccomp-usrp-tx:latest}"
  fi
  if command -v cygpath >/dev/null 2>&1 || [[ -n "${MSYSTEM:-}" ]]; then
    local msys_env_exclusions
    msys_env_exclusions="REMOTE_USRP_RX_DIR;REMOTE_RX_RUN_ROOT;REMOTE_DECODE_PYTHON;OPENAMP_DEMO_REMOTE_DECODE_PYTHON;REMOTE_USRP_DECODE_PYTHON;REMOTE_USRP_PROJECT_ROOT;OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET;USRP_TX_DOCKER_MOUNT_TARGET;MLKEM_REMOTE_OQS_INSTALL_PATH;MLKEM_REMOTE_LD_LIBRARY_PATH;MLKEM_REMOTE_TONGSUO_KEM_BRIDGE;MLKEM_REMOTE_TONGSUO_SIG_BRIDGE;MLKEM_REMOTE_RUN_LOGGER_DIR;MLKEM_AUTH_SERVER_SM2_KEY;MLKEM_AUTH_SERVER_SM2_PUB;MLKEM_AUTH_SERVER_MLDSA_KEY;MLKEM_AUTH_SERVER_MLDSA_PUB;MLKEM_AUTH_PEER_SM2_PUB;MLKEM_AUTH_PEER_MLDSA_PUB;MLKEM_LOCAL_CLIENT_DOCKER_SCRIPT"
    export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:-*}"
    if [[ -n "${MSYS2_ENV_CONV_EXCL:-}" ]]; then
      export MSYS2_ENV_CONV_EXCL="$MSYS2_ENV_CONV_EXCL;$msys_env_exclusions"
    else
      export MSYS2_ENV_CONV_EXCL="$msys_env_exclusions"
    fi
  fi
  export MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-usrp}"
  export MLKEM_USRP_MODE="${MLKEM_USRP_MODE:-ota}"
  export MLKEM_USRP_MAX_ARQ_ROUNDS="${MLKEM_USRP_MAX_ARQ_ROUNDS:-5}"
  export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-usrp}"
  export JSCC_LINK_MODE="${JSCC_LINK_MODE:-iq-direct}"
  export OPENAMP_DEMO_LINK_MODE="${OPENAMP_DEMO_LINK_MODE:-iq-direct}"
  export MLKEM_CIPHER_SUITE="${MLKEM_CIPHER_SUITE:-SM4_GCM}"
  if [[ "$JSCC_LINK_MODE" == "iq-direct" ]]; then
    export OPENAMP_IQ_STREAMING_TVM="${OPENAMP_IQ_STREAMING_TVM:-0}"
    export OPENAMP_IQ_STREAMING_MIN_READY="${OPENAMP_IQ_STREAMING_MIN_READY:-10}"
    export BIG_LITTLE_INPUT_CHUNK_SIZE="${BIG_LITTLE_INPUT_CHUNK_SIZE:-10}"
  fi
  export OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="${OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT:-0}"
  export COCKPIT_STARTUP_USRP_WARMUP="${COCKPIT_STARTUP_USRP_WARMUP:-1}"
  export COCKPIT_STARTUP_USRP_WARMUP_COUNT="${COCKPIT_STARTUP_USRP_WARMUP_COUNT:-5}"
  export COCKPIT_STARTUP_USRP_WARMUP_TIMEOUT_SEC="${COCKPIT_STARTUP_USRP_WARMUP_TIMEOUT_SEC:-360}"
  export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"
  export MLKEM_AUTH_SERVER_ID="${MLKEM_AUTH_SERVER_ID:-phytium-board}"
  export MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"
  export MLKEM_AUTH_SERVER_SM2_KEY="${MLKEM_AUTH_SERVER_SM2_KEY:-/home/user/keys/server_sm2_identity.key}"
  export MLKEM_AUTH_SERVER_SM2_PUB="${MLKEM_AUTH_SERVER_SM2_PUB:-/home/user/keys/server_sm2_identity.pub}"
  export MLKEM_AUTH_SERVER_MLDSA_KEY="${MLKEM_AUTH_SERVER_MLDSA_KEY:-/home/user/keys/server_mldsa_identity.key}"
  export MLKEM_AUTH_SERVER_MLDSA_PUB="${MLKEM_AUTH_SERVER_MLDSA_PUB:-/home/user/keys/server_mldsa_identity.pub}"
  export MLKEM_AUTH_PEER_SM2_PUB="${MLKEM_AUTH_PEER_SM2_PUB:-$auth_keys_dir_win/server_sm2_identity.pub}"
  export MLKEM_AUTH_PEER_MLDSA_PUB="${MLKEM_AUTH_PEER_MLDSA_PUB:-$auth_keys_dir_win/server_mldsa_identity.pub}"
  export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE="${MLKEM_REMOTE_TONGSUO_SIG_BRIDGE:-/home/user/libtongsuo_sig_bridge.so}"
  export MLKEM_REMOTE_OQS_INSTALL_PATH="${MLKEM_REMOTE_OQS_INSTALL_PATH:-/home/user/liboqs-dist}"
  export REMOTE_USRP_RX_DIR="${REMOTE_USRP_RX_DIR:-/home/user/cockpit_usrp_rx}"
  export REMOTE_RX_RUN_ROOT="${REMOTE_RX_RUN_ROOT:-/dev/shm/usrp292x_remote_runs}"
  export OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"
  export REMOTE_DECODE_PYTHON="${REMOTE_DECODE_PYTHON:-$OPENAMP_DEMO_REMOTE_DECODE_PYTHON}"
  export RX_ARM_WAIT_MS="${RX_ARM_WAIT_MS:-500}"
  export RX_STOP_WAIT_MS="${RX_STOP_WAIT_MS:-8000}"
  export ANALOG_RX_TAIL_SEC="${ANALOG_RX_TAIL_SEC:-0.040}"
  export ANALOG_REMOTE_CLEANUP_MODE="${ANALOG_REMOTE_CLEANUP_MODE:-skip}"
  export ANALOG_PRECONNECT_CONTROL="${ANALOG_PRECONNECT_CONTROL:-1}"
  export ANALOG_RX_SESSION_CONTROL="${ANALOG_RX_SESSION_CONTROL:-1}"
  export ANALOG_RX_BATCH_SESSION_CONTROL="${ANALOG_RX_BATCH_SESSION_CONTROL:-1}"
  export ANALOG_RX_HEALTH_RESET_ON_STALL="${ANALOG_RX_HEALTH_RESET_ON_STALL:-1}"
  export ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC="${ANALOG_RX_HEALTH_STALL_THRESHOLD_SEC:-0.25}"
  if [[ "$JSCC_LINK_MODE" == "iq-direct" ]]; then
    export ANALOG_RX_BATCH_SESSION_MAX_IMAGES="${ANALOG_RX_BATCH_SESSION_MAX_IMAGES:-16}"
  else
    export ANALOG_RX_BATCH_SESSION_MAX_IMAGES="${ANALOG_RX_BATCH_SESSION_MAX_IMAGES:-16}"
  fi
  export ANALOG_RETRY_ON_BURST_MISS="${ANALOG_RETRY_ON_BURST_MISS:-1}"
  export ANALOG_RETRY_ON_LOW_SYNC="${ANALOG_RETRY_ON_LOW_SYNC:-1}"
  export ANALOG_LOW_SYNC_RETRY_THRESHOLD="${ANALOG_LOW_SYNC_RETRY_THRESHOLD:-0.08}"
  export ANALOG_FALLBACK_SYNC_CANDIDATES="${ANALOG_FALLBACK_SYNC_CANDIDATES:-4}"
  export ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS="${ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS:-1024}"
  export ANALOG_REMOTE_DECODE_RESPONSE_MODE="${ANALOG_REMOTE_DECODE_RESPONSE_MODE:-minimal}"
  export ANALOG_REMOTE_DECODED_FORMAT="${ANALOG_REMOTE_DECODED_FORMAT:-npy}"
  export ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY="${ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY:-1}"
  export ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC="${ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC:-0.05}"
  export ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS="${ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS:-1}"
  export ANALOG_RX_SC16_MMAP="${ANALOG_RX_SC16_MMAP:-1}"
  export ANALOG_RX_CLIPPING_DECIMATION="${ANALOG_RX_CLIPPING_DECIMATION:-8}"
  export ANALOG_RX_POST_QUANTIZE="${ANALOG_RX_POST_QUANTIZE:-0}"
  export ANALOG_ROBUST_SYNC="${ANALOG_ROBUST_SYNC:-0}"
  export ANALOG_RX_ARM_STATUS_TIMEOUT_SEC="${ANALOG_RX_ARM_STATUS_TIMEOUT_SEC:-0.5}"
  export ANALOG_RX_ARM_STATUS_POLL_SEC="${ANALOG_RX_ARM_STATUS_POLL_SEC:-0.025}"
  export ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC="${ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC:-8.0}"
  export ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC="${ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC:-1.5}"
  export ANALOG_RX_STOP_DRAIN_POLL_SEC="${ANALOG_RX_STOP_DRAIN_POLL_SEC:-0.05}"
  if [[ "$JSCC_LINK_MODE" == "iq-direct" ]]; then
    export ANALOG_PIPELINE_DEPTH="${ANALOG_PIPELINE_DEPTH:-1}"
    export ANALOG_PIPELINE_RF_DECODE_OVERLAP="${ANALOG_PIPELINE_RF_DECODE_OVERLAP:-0}"
  else
    export ANALOG_PIPELINE_DEPTH="${ANALOG_PIPELINE_DEPTH:-1}"
  fi
}

resolve_aircraft_position_env() {
  if [[ -n "${COCKPIT_AIRCRAFT_POSITION_ENV:-}" ]]; then
    printf '%s\n' "$COCKPIT_AIRCRAFT_POSITION_ENV"
    return 0
  fi
  if [[ -f "$DEFAULT_AIRCRAFT_POSITION_ENV" ]]; then
    printf '%s\n' "$DEFAULT_AIRCRAFT_POSITION_ENV"
    return 0
  fi
  return 1
}

resolve_python() {
  if [[ -n "${COCKPIT_PYTHON:-}" ]]; then
    printf '%s\n' "$COCKPIT_PYTHON"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return 0
  fi
  return 1
}

find_port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti TCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "$port/tcp" 2>/dev/null || true
    return 0
  fi
  return 0
}

backend_healthy() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://$BACKEND_HOST:$BACKEND_PORT/api/health" >/dev/null 2>&1
    return $?
  fi
  "$PYTHON_CMD" - "$BACKEND_HOST" "$BACKEND_PORT" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

host = sys.argv[1]
port = sys.argv[2]
with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=1.5) as response:
    payload = json.load(response)
if payload.get("status") != "ok":
    raise SystemExit(1)
PY
}

frontend_healthy() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://127.0.0.1:$FRONTEND_PORT/#/" >/dev/null 2>&1
    return $?
  fi
  "$PYTHON_CMD" - "$FRONTEND_PORT" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

port = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:{port}/#/", timeout=1.5) as response:
    if response.status >= 400:
        raise SystemExit(1)
PY
}

truthy_env() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_board_password() {
  local candidate
  for candidate in "${REMOTE_PASS:-}" "${REMOTE_PASSWORD:-}" "${PHYTIUM_PI_PASS:-}" "${PHYTIUM_PI_PASSWORD:-}" "${BOARD_PASS:-}"; do
    if [[ -n "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

run_startup_usrp_warmup() {
  if ! truthy_env "${COCKPIT_STARTUP_USRP_WARMUP:-0}"; then
    return 0
  fi
  if [[ "${MLKEM_TRANSPORT_MODE:-}" != "usrp" || "${OPENAMP_DEMO_INPUT_SOURCE_MODE:-}" != "usrp" || "${JSCC_LINK_MODE:-}" != "iq-direct" ]]; then
    echo "启动预热跳过：当前不是 USRP IQ 直传路径"
    return 0
  fi

  local host="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-}}"
  local user="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"
  local port="${REMOTE_SSH_PORT:-${PHYTIUM_PI_PORT:-22}}"
  local password=""
  local count="${COCKPIT_STARTUP_USRP_WARMUP_COUNT:-5}"
  local timeout_sec="${COCKPIT_STARTUP_USRP_WARMUP_TIMEOUT_SEC:-360}"

  if [[ -z "$host" ]]; then
    echo "ERROR: 启动预热需要 REMOTE_HOST；如需跳过，设置 COCKPIT_STARTUP_USRP_WARMUP=0。" >&2
    return 1
  fi

  password="$(resolve_board_password || true)"
  if [[ -z "$password" && -t 0 ]]; then
    read -r -s -p "板卡 SSH 密码（启动预热需要，输入不会显示）: " password
    echo
  fi
  if [[ -z "$password" ]]; then
    echo "ERROR: 启动预热需要板卡密码。请临时设置 REMOTE_PASS，或设置 COCKPIT_STARTUP_USRP_WARMUP=0 跳过。" >&2
    return 1
  fi

  echo "启动前静默预热 USRP IQ + TVM：${count} 张..."
  COCKPIT_STARTUP_USRP_WARMUP_PASS="$password" \
    "$PYTHON_CMD" - \
      "http://$BACKEND_HOST:$BACKEND_PORT" \
      "$host" \
      "$user" \
      "$port" \
      "$count" \
      "$timeout_sec" \
      "${REMOTE_USRP_RX_DIR:-/home/user/cockpit_usrp_rx}" \
      "${JSCC_LINK_MODE:-iq-direct}" <<'PY'
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request


base_url = sys.argv[1].rstrip("/")
host = sys.argv[2]
user = sys.argv[3]
port = int(sys.argv[4])
count = max(1, int(sys.argv[5]))
timeout_sec = max(30.0, float(sys.argv[6]))
remote_usrp_rx_dir = sys.argv[7]
jscc_link_mode = sys.argv[8]
password = os.environ.get("COCKPIT_STARTUP_USRP_WARMUP_PASS", "")


def request_json(method: str, path: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body) if body.strip() else {}


session = request_json(
    "POST",
    "/api/session/board-access",
    {
        "host": host,
        "user": user,
        "password": password,
        "port": port,
        "transport_mode": "usrp",
        "remote_usrp_rx_dir": remote_usrp_rx_dir,
        "jscc_link_mode": jscc_link_mode,
        "auth_enabled": True,
        "auth_sig_policy": "DUAL_REQUIRED",
    },
)
if session.get("status") != "ok":
    raise SystemExit(f"board session setup failed: {session}")

usrp = request_json("POST", "/api/usrp-control/start", {}, timeout=90.0)
if usrp.get("status") != "ready":
    raise SystemExit(f"USRP control did not become ready: {usrp}")

started = request_json(
    "POST",
    "/api/run-inference-batch",
    {"count": count, "allow_preflight_degraded": True, "warmup": True},
    timeout=30.0,
)
if started.get("status") not in {"started", "done"}:
    raise SystemExit(f"warm-up batch did not start: {started}")
job_id = str(started.get("batch_job_id") or "")

deadline = time.monotonic() + timeout_sec
last_state: dict = {}
while time.monotonic() < deadline:
    last_state = request_json("GET", "/api/batch-state", timeout=10.0)
    status = str(last_state.get("status") or "")
    completed = int(last_state.get("completed") or 0)
    total = int(last_state.get("total") or count)
    print(f"启动预热进度: {completed}/{total} ({status})", flush=True)
    if status in {"done", "completed"}:
        break
    if status in {"failed", "error", "cancelled"}:
        raise SystemExit(f"warm-up failed: {last_state}")
    time.sleep(3.0)
else:
    raise SystemExit(f"warm-up timeout after {timeout_sec:.0f}s: {last_state}")

completed = int(last_state.get("completed") or 0)
success = int(last_state.get("success") or 0)
if completed < count or success < count:
    raise SystemExit(f"warm-up incomplete: completed={completed}, success={success}, expected={count}")

cleared = request_json(
    "POST",
    "/api/batch-state/clear",
    {"warmup_only": True, "batch_job_id": job_id},
    timeout=10.0,
)
if cleared.get("status") != "ok" or not cleared.get("cleared"):
    raise SystemExit(f"warm-up batch-state clear failed: {cleared}")

print(f"启动预热完成：{success}/{count}，Cockpit Desktop 即将显示。", flush=True)
PY
}

PYTHON_CMD="$(resolve_python)" || {
  echo "ERROR: python3/python not found. Set COCKPIT_PYTHON if needed." >&2
  exit 1
}

configure_runtime_defaults

echo "启动 Cockpit Desktop 开发环境..."
echo "仓库根目录: $REPO_ROOT"
echo "后端地址: http://$BACKEND_HOST:$BACKEND_PORT"
echo "USRP 运行默认: TRANSPORT=$MLKEM_TRANSPORT_MODE, LINK=$JSCC_LINK_MODE, SSH=${OPENAMP_SSH_RUNNER:-system}, TX=${OPENAMP_USRP_TX_RUNNER:-system}, REMOTE_PYTHON=$REMOTE_DECODE_PYTHON"
echo "USRP IQ 微批默认: STREAMING_TVM=${OPENAMP_IQ_STREAMING_TVM:-0}, MIN_READY=${OPENAMP_IQ_STREAMING_MIN_READY:-1}, CHUNK=${BIG_LITTLE_INPUT_CHUNK_SIZE:-1}, PIPELINE_DEPTH=${ANALOG_PIPELINE_DEPTH:-1}, RF_DECODE_OVERLAP=${ANALOG_PIPELINE_RF_DECODE_OVERLAP:-0}, DECODE_WORKER='${ANALOG_REMOTE_DECODE_WORKER_PREFIX:-}'"
if [[ -n "${REMOTE_HOST:-${PHYTIUM_PI_HOST:-}}" ]]; then
  echo "板卡地址覆盖: ${REMOTE_HOST:-${PHYTIUM_PI_HOST:-}}"
fi

if command -v powershell.exe >/dev/null 2>&1; then
  echo "清理旧 Cockpit/后端 Windows 进程..."
  stop_windows_cockpit_processes
  stop_windows_port_listeners "$BACKEND_PORT"
  stop_windows_port_listeners "$FRONTEND_PORT"
  sleep 1
fi

PORT_PIDS="$(find_port_pids "$BACKEND_PORT")"
if [[ -n "$PORT_PIDS" ]]; then
  echo "检测到端口 $BACKEND_PORT 已被占用，先停止旧进程: $PORT_PIDS"
  kill $PORT_PIDS 2>/dev/null || true
  sleep 1
fi

FRONTEND_PIDS="$(find_port_pids "$FRONTEND_PORT")"
if [[ -n "$FRONTEND_PIDS" ]]; then
  echo "检测到端口 $FRONTEND_PORT 已被占用，先停止旧进程: $FRONTEND_PIDS"
  kill $FRONTEND_PIDS 2>/dev/null || true
  sleep 1
fi

echo "启动 Python 后端..."
SERVER_ARGS=(
  session_bootstrap/demo/openamp_control_plane_demo/server.py
  --host "$BACKEND_HOST"
  --port "$BACKEND_PORT"
)
if AIRCRAFT_POSITION_ENV="$(resolve_aircraft_position_env)"; then
  echo "检测到本机定位配置: $AIRCRAFT_POSITION_ENV"
  SERVER_ARGS+=(--aircraft-position-env "$AIRCRAFT_POSITION_ENV")
fi
(
  cd "$REPO_ROOT"
  nohup "$PYTHON_CMD" "${SERVER_ARGS[@]}" >"$BACKEND_LOG" 2>&1 &
  echo $! >"${TMPDIR:-/tmp}/cockpit-backend.pid"
)

echo "等待后端就绪..."
for i in $(seq 1 15); do
  if backend_healthy; then
    echo "后端已就绪"
    break
  fi
  if [[ "$i" -eq 15 ]]; then
    echo "ERROR: 后端启动失败。日志: $BACKEND_LOG" >&2
    exit 1
  fi
  sleep 1
done

run_startup_usrp_warmup

echo "启动 Electron/Vite 开发环境..."
(
  cd "$SCRIPT_DIR"
  nohup env \
    COCKPIT_SKIP_PYTHON=1 \
    COCKPIT_BACKEND_HOST="$BACKEND_HOST" \
    COCKPIT_BACKEND_PORT="$BACKEND_PORT" \
    npm run dev >"$FRONTEND_LOG" 2>&1 &
  echo $! >"${TMPDIR:-/tmp}/cockpit-dev.pid"
)

echo "等待前端就绪..."
for i in $(seq 1 30); do
  if frontend_healthy; then
    echo "前端已就绪"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: 前端启动失败。日志: $FRONTEND_LOG" >&2
    exit 1
  fi
  sleep 1
done

echo
echo "开发环境已启动"
echo "后端日志: $BACKEND_LOG"
echo "前端日志: $FRONTEND_LOG"
echo "Vite 页面: http://localhost:$FRONTEND_PORT/#/"
echo "停止命令: $SCRIPT_DIR/stop-dev.sh"
