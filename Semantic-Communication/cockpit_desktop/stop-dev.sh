#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
FRONTEND_PORT="${COCKPIT_FRONTEND_PORT:-5173}"

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

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

echo "停止 Cockpit Desktop 开发环境..."

stop_pid_file "${TMPDIR:-/tmp}/cockpit-dev.pid"
stop_pid_file "${TMPDIR:-/tmp}/cockpit-backend.pid"

BACKEND_PIDS="$(find_port_pids "$BACKEND_PORT")"
if [[ -n "$BACKEND_PIDS" ]]; then
  kill $BACKEND_PIDS 2>/dev/null || true
fi

FRONTEND_PIDS="$(find_port_pids "$FRONTEND_PORT")"
if [[ -n "$FRONTEND_PIDS" ]]; then
  kill $FRONTEND_PIDS 2>/dev/null || true
fi

pkill -f "electron-vite dev" 2>/dev/null || true
pkill -f "server.py --host" 2>/dev/null || true

echo "开发环境已停止"
