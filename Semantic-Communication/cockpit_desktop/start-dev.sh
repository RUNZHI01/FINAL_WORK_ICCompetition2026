#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_HOST="${COCKPIT_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
FRONTEND_PORT="${COCKPIT_FRONTEND_PORT:-5173}"
BACKEND_LOG="${TMPDIR:-/tmp}/openamp-server.log"
DEFAULT_AIRCRAFT_POSITION_ENV="$REPO_ROOT/session_bootstrap/tmp/aircraft_position_baidu_ip.local.env"

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

PYTHON_CMD="$(resolve_python)" || {
  echo "ERROR: python3/python not found. Set COCKPIT_PYTHON if needed." >&2
  exit 1
}

echo "启动 Cockpit Desktop 开发环境..."
echo "仓库根目录: $REPO_ROOT"
echo "后端地址: http://$BACKEND_HOST:$BACKEND_PORT"

PORT_PIDS="$(find_port_pids "$BACKEND_PORT")"
if [[ -n "$PORT_PIDS" ]]; then
  echo "检测到端口 $BACKEND_PORT 已被占用，先停止旧进程: $PORT_PIDS"
  kill $PORT_PIDS 2>/dev/null || true
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

echo "启动 Electron/Vite 开发环境..."
(
  cd "$SCRIPT_DIR"
  COCKPIT_SKIP_PYTHON=1 \
  COCKPIT_BACKEND_HOST="$BACKEND_HOST" \
  COCKPIT_BACKEND_PORT="$BACKEND_PORT" \
  npm run dev &
  echo $! >"${TMPDIR:-/tmp}/cockpit-dev.pid"
)

echo
echo "开发环境已启动"
echo "后端日志: $BACKEND_LOG"
echo "Vite 页面: http://localhost:$FRONTEND_PORT/#/"
echo "停止命令: $SCRIPT_DIR/stop-dev.sh"
