#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
VENV_PYTHON="$COCKPIT_ROOT/.venv/bin/python"
RUNTIME_CACHE_ROOT="$COCKPIT_ROOT/runtime/xdg_cache"
OPERATOR_LAUNCH_SCRIPT="$PROJECT_ROOT/session_bootstrap/scripts/run_openamp_demo.sh"
OPERATOR_LOG_PATH="${COCKPIT_NATIVE_OPERATOR_LOG_PATH:-$COCKPIT_ROOT/runtime/openamp_demo_server.log}"
OPERATOR_API_BASE="${COCKPIT_NATIVE_OPERATOR_API_BASE:-http://127.0.0.1:8079}"
OPERATOR_AUTOSTART_WAIT_STEPS="${COCKPIT_NATIVE_OPERATOR_AUTOSTART_WAIT_STEPS:-20}"
OPERATOR_AUTOSTART_WAIT_SEC="${COCKPIT_NATIVE_OPERATOR_AUTOSTART_WAIT_SEC:-0.5}"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Missing native cockpit venv interpreter: $VENV_PYTHON" >&2
    echo "Expected repo-local capture launcher path: $PROJECT_ROOT/session_bootstrap/scripts/run_cockpit_native_capture.sh" >&2
    exit 1
fi

mkdir -p "$RUNTIME_CACHE_ROOT"
mkdir -p "$(dirname "$OPERATOR_LOG_PATH")"

export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$RUNTIME_CACHE_ROOT}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
export QSG_RHI_BACKEND="${QSG_RHI_BACKEND:-software}"
export QT_OPENGL="${QT_OPENGL:-software}"
export QT_ENABLE_HIGHDPI_SCALING="${QT_ENABLE_HIGHDPI_SCALING:-1}"
export QT_SCALE_FACTOR_ROUNDING_POLICY="${QT_SCALE_FACTOR_ROUNDING_POLICY:-PassThrough}"

operator_health_check() {
    "$VENV_PYTHON" - <<'PY' "$OPERATOR_API_BASE"
from __future__ import annotations

import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
request = urllib.request.Request(base + "/api/health", headers={"Accept": "application/json"})
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(request, timeout=1.5) as response:
    payload = json.loads(response.read().decode("utf-8"))
status = str(payload.get("status") or "").strip().lower()
raise SystemExit(0 if status == "ok" else 1)
PY
}

if [[ "${COCKPIT_NATIVE_SKIP_OPERATOR_AUTOSTART:-0}" != "1" && -x "$OPERATOR_LAUNCH_SCRIPT" ]]; then
    if ! operator_health_check >/dev/null 2>&1; then
        nohup "$OPERATOR_LAUNCH_SCRIPT" >"$OPERATOR_LOG_PATH" 2>&1 &
        for ((step=0; step<OPERATOR_AUTOSTART_WAIT_STEPS; step+=1)); do
            if operator_health_check >/dev/null 2>&1; then
                break
            fi
            sleep "$OPERATOR_AUTOSTART_WAIT_SEC"
        done
    fi
fi

cd "$PROJECT_ROOT"
exec "$VENV_PYTHON" -m cockpit_native.capture "$@"
