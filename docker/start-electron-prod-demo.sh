#!/usr/bin/env bash
set -euo pipefail

export COCKPIT_REPO_ROOT="${COCKPIT_REPO_ROOT:-/workspace/Semantic-Communication}"
export COCKPIT_BACKEND_HOST="${COCKPIT_BACKEND_HOST:-localhost}"
export COCKPIT_BACKEND_PORT="${COCKPIT_BACKEND_PORT:-8079}"
export COCKPIT_PYTHON="${COCKPIT_PYTHON:-/workspace/.venv/bin/python}"
export COCKPIT_SKIP_PYTHON="${COCKPIT_SKIP_PYTHON:-1}"
export ICCOMP_COCKPIT_PROFILE="${ICCOMP_COCKPIT_PROFILE:-default}"
if [ "$ICCOMP_COCKPIT_PROFILE" = "tvm250-prerecorded" ]; then
    export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"
    export MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-tcp}"
    export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-0}"
else
    export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"
    export MLKEM_TRANSPORT_MODE="${MLKEM_TRANSPORT_MODE:-tcp}"
    export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"
fi
export MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"
export JSCC_LINK_MODE="${JSCC_LINK_MODE:-qpsk}"
export ANALOG_IN_PROCESS_LOCAL_CODEC="${ANALOG_IN_PROCESS_LOCAL_CODEC:-1}"
export ANALOG_WARMUP_LOCAL_CODEC="${ANALOG_WARMUP_LOCAL_CODEC:-1}"
export REMOTE_USRP_DECODE_PYTHON="${REMOTE_USRP_DECODE_PYTHON:-/home/user/venv/bin/python}"
export OPENAMP_DEMO_REMOTE_DECODE_PYTHON="${OPENAMP_DEMO_REMOTE_DECODE_PYTHON:-/home/user/venv/bin/python}"
export MLKEM_STATUS_STARTUP_WAIT_SEC="${MLKEM_STATUS_STARTUP_WAIT_SEC:-60}"
export MLKEM_REMOTE_RUN_LOGGER_DIR="${MLKEM_REMOTE_RUN_LOGGER_DIR:-/home/user/artifacts/evidence/logs}"
export REMOTE_PASS="${REMOTE_PASS:-}"
export PHYTIUM_PI_PASSWORD="${PHYTIUM_PI_PASSWORD:-}"
export AIRCRAFT_POSITION_TIMEOUT_SEC="${AIRCRAFT_POSITION_TIMEOUT_SEC:-1.0}"
export ELECTRON_DISABLE_SECURITY_WARNINGS="${ELECTRON_DISABLE_SECURITY_WARNINGS:-true}"
export ELECTRON_DISABLE_SANDBOX="${ELECTRON_DISABLE_SANDBOX:-1}"
export OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-/opt/liboqs}"
export LD_LIBRARY_PATH="/opt/liboqs/lib:/opt/liboqs/lib64:${LD_LIBRARY_PATH:-}"
export PATH="/workspace/.venv/bin:${PATH}"

unset ELECTRON_RENDERER_URL

if [ "${ENABLE_TAILSCALE:-0}" = "1" ]; then
    bash /workspace/docker/start-tailscale.sh
fi

mkdir -p /workspace/artifacts/logs
cd /workspace
find /workspace/Semantic-Communication -type f -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null || true

python /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py \
    > /workspace/artifacts/logs/server-prod.log 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 40); do
    if python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8079/api/health", timeout=1).read()
PY
    then
        break
    fi
    sleep 0.5
done

cd /workspace/Semantic-Communication/cockpit_desktop
ELECTRON_CONTAINER_ARGS=(
    --no-sandbox
    --disable-setuid-sandbox
    --disable-gpu
    --disable-dev-shm-usage
)
exec ./node_modules/.bin/electron "${ELECTRON_CONTAINER_ARGS[@]}" . "$@"
