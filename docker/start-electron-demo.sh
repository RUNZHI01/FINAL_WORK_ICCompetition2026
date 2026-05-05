#!/usr/bin/env bash
set -euo pipefail

export COCKPIT_REPO_ROOT="${COCKPIT_REPO_ROOT:-/workspace/Semantic-Communication}"
export COCKPIT_BACKEND_HOST="${COCKPIT_BACKEND_HOST:-127.0.0.1}"
export COCKPIT_BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
export COCKPIT_PYTHON="${COCKPIT_PYTHON:-$(command -v python)}"
export COCKPIT_SKIP_PYTHON="${COCKPIT_SKIP_PYTHON:-1}"
export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"
export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-0}"
export MLKEM_STATUS_STARTUP_WAIT_SEC="${MLKEM_STATUS_STARTUP_WAIT_SEC:-60}"
export REMOTE_PASS="${REMOTE_PASS:-}"
export PHYTIUM_PI_PASSWORD="${PHYTIUM_PI_PASSWORD:-}"
export AIRCRAFT_POSITION_TIMEOUT_SEC="${AIRCRAFT_POSITION_TIMEOUT_SEC:-1.0}"
export ELECTRON_DISABLE_SECURITY_WARNINGS="${ELECTRON_DISABLE_SECURITY_WARNINGS:-true}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/iccomp-runtime}"

mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}"

if [ "${ENABLE_TAILSCALE:-0}" = "1" ]; then
    bash /workspace/docker/start-tailscale.sh
fi

cd /workspace

test -f /workspace/.venv/bin/activate
test -f /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py
test -f /workspace/Semantic-Communication/cockpit_desktop/package.json

printf '\n' >/tmp/iccomp-empty-board-password
exec bash ./start.sh </tmp/iccomp-empty-board-password
