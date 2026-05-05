#!/usr/bin/env bash
set -euo pipefail

# Wait for Phytium Pi SSH recovery, then probe the newly built safe runtime
# against the current round1 artifact.

HOST="${1:-100.121.87.73}"
USER_NAME="${2:-user}"
PASS="${3:-user}"
PORT="${4:-22}"
WAIT_SEC="${WAIT_SEC:-900}"
INTERVAL_SEC="${INTERVAL_SEC:-15}"
REMOTE_BUILD_ROOT="${REMOTE_BUILD_ROOT:-/home/user/tvm_samegen_safe_20260309}"
REMOTE_ARTIFACT="${REMOTE_ARTIFACT:-/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"
PROBE_SCRIPT="$SCRIPT_DIR/remote_probe_current_vm_with_runtime.sh"

start_ts=$(date +%s)

echo "[resume-safe-runtime] waiting for SSH ${HOST}:${PORT} (timeout=${WAIT_SEC}s, interval=${INTERVAL_SEC}s)"
while true; do
  now_ts=$(date +%s)
  if (( now_ts - start_ts > WAIT_SEC )); then
    echo "[resume-safe-runtime] timeout waiting for SSH recovery" >&2
    exit 1
  fi

  if bash "$SSH_SCRIPT" --host "$HOST" --user "$USER_NAME" --pass "$PASS" --port "$PORT" -- "echo SSH_OK" >/tmp/resume_safe_runtime_ssh.log 2>&1; then
    echo "[resume-safe-runtime] SSH recovered"
    break
  fi

  sleep "$INTERVAL_SEC"
done

echo "[resume-safe-runtime] checking built libraries"
bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- "bash -lc 'ls -lh ${REMOTE_BUILD_ROOT}/build/libtvm.so ${REMOTE_BUILD_ROOT}/build/libtvm_runtime.so'"

echo "[resume-safe-runtime] probing current artifact with rebuilt runtime"
bash "$PROBE_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  --python /home/user/venv/bin/python \
  --pythonpath "${REMOTE_BUILD_ROOT}/python:${REMOTE_BUILD_ROOT}/3rdparty/tvm-ffi/python" \
  --libpath "${REMOTE_BUILD_ROOT}/build" \
  --artifact "$REMOTE_ARTIFACT"
