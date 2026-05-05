#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COCKPIT_ROOT="$PROJECT_ROOT/cockpit_native"
VENV_PYTHON="$COCKPIT_ROOT/.venv/bin/python"
RUNTIME_CACHE_ROOT="$COCKPIT_ROOT/runtime/xdg_cache"
XCB_RUNTIME_ROOT="$COCKPIT_ROOT/runtime/xcb_runtime/root"
XCB_RUNTIME_LIB="$XCB_RUNTIME_ROOT/usr/lib/aarch64-linux-gnu"
OPERATOR_LAUNCH_SCRIPT="$PROJECT_ROOT/session_bootstrap/scripts/run_openamp_demo.sh"
OPERATOR_LOG_PATH="${COCKPIT_NATIVE_OPERATOR_LOG_PATH:-$COCKPIT_ROOT/runtime/openamp_demo_server.log}"
OPERATOR_API_BASE="${COCKPIT_NATIVE_OPERATOR_API_BASE:-http://127.0.0.1:8079}"
OPERATOR_AUTOSTART_WAIT_STEPS="${COCKPIT_NATIVE_OPERATOR_AUTOSTART_WAIT_STEPS:-20}"
OPERATOR_AUTOSTART_WAIT_SEC="${COCKPIT_NATIVE_OPERATOR_AUTOSTART_WAIT_SEC:-0.5}"
RENDER_MODE="${COCKPIT_NATIVE_RENDER_MODE:-auto}"
RENDER_BOOT_WAIT_STEPS="${COCKPIT_NATIVE_RENDER_BOOT_WAIT_STEPS:-8}"
RENDER_BOOT_WAIT_SEC="${COCKPIT_NATIVE_RENDER_BOOT_WAIT_SEC:-0.5}"
SINGLE_INSTANCE="${COCKPIT_NATIVE_SINGLE_INSTANCE:-1}"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Missing native cockpit venv interpreter: $VENV_PYTHON" >&2
    echo "Expected repo-local launcher path: $PROJECT_ROOT/session_bootstrap/scripts/run_cockpit_native.sh" >&2
    exit 1
fi

mkdir -p "$RUNTIME_CACHE_ROOT"
mkdir -p "$(dirname "$OPERATOR_LOG_PATH")"

export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$RUNTIME_CACHE_ROOT}"
export QT_ENABLE_HIGHDPI_SCALING="${QT_ENABLE_HIGHDPI_SCALING:-1}"
export QT_SCALE_FACTOR_ROUNDING_POLICY="${QT_SCALE_FACTOR_ROUNDING_POLICY:-PassThrough}"

if [[ -d "$XCB_RUNTIME_LIB" ]]; then
    export LD_LIBRARY_PATH="${XCB_RUNTIME_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
fi

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

if [[ "$SINGLE_INSTANCE" == "1" ]]; then
    pkill -f "$VENV_PYTHON -m cockpit_native" >/dev/null 2>&1 || true
    sleep 0.2
fi

apply_software_render_env() {
    export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
    export QSG_RHI_BACKEND="${QSG_RHI_BACKEND:-software}"
    export QT_OPENGL="${QT_OPENGL:-software}"
}

apply_hardware_render_env() {
    unset QT_QUICK_BACKEND || true
    unset QSG_RHI_BACKEND || true
    unset QT_OPENGL || true
}

render_boot_failed() {
    local log_path="$1"
    if grep -Eqi 'failed to create dri2 screen|failed to retrieve device information|failed to get driver name|MESA: error: ZINK' "$log_path"; then
        return 0
    fi
    return 1
}

launch_mode() {
    local mode="$1"
    shift
    local boot_log
    boot_log="$(mktemp "${COCKPIT_ROOT}/runtime/cockpit_native_${mode}_boot_XXXX.log")"
    local -a cmd=("$VENV_PYTHON" -m cockpit_native)

    if [[ "$mode" == "software" ]]; then
        apply_software_render_env
        cmd+=(--software-render)
    else
        apply_hardware_render_env
    fi

    cd "$PROJECT_ROOT"
    "${cmd[@]}" "$@" >"$boot_log" 2>&1 &
    local child_pid=$!

    for ((step=0; step<RENDER_BOOT_WAIT_STEPS; step+=1)); do
        if ! kill -0 "$child_pid" >/dev/null 2>&1; then
            wait "$child_pid" || true
            return 1
        fi
        sleep "$RENDER_BOOT_WAIT_SEC"
    done

    if render_boot_failed "$boot_log"; then
        kill "$child_pid" >/dev/null 2>&1 || true
        wait "$child_pid" >/dev/null 2>&1 || true
        return 1
    fi

    trap 'if [[ -n "${child_pid:-}" ]]; then kill "$child_pid" >/dev/null 2>&1 || true; fi' INT TERM
    wait "$child_pid"
    trap - INT TERM
}

cd "$PROJECT_ROOT"

case "$RENDER_MODE" in
    hardware)
        launch_mode hardware "$@"
        ;;
    software)
        launch_mode software "$@"
        ;;
    auto)
        if ! launch_mode hardware "$@"; then
            launch_mode software "$@"
        fi
        ;;
    *)
        echo "Unsupported COCKPIT_NATIVE_RENDER_MODE: $RENDER_MODE" >&2
        exit 2
        ;;
esac
