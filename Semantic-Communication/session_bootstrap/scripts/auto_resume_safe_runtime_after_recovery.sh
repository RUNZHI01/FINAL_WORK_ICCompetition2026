#!/usr/bin/env bash
set -euo pipefail

# Wait for Phytium Pi recovery, then either:
# 1) if the safe runtime libs already exist, probe current artifact immediately;
# 2) otherwise rebuild the safe runtime and then probe current artifact.

HOST="${1:-100.121.87.73}"
USER_NAME="${2:-user}"
PASS="${3:-user}"
PORT="${4:-22}"
WAIT_SEC="${WAIT_SEC:-1800}"
INTERVAL_SEC="${INTERVAL_SEC:-20}"
REMOTE_BUILD_ROOT="${REMOTE_BUILD_ROOT:-/home/user/tvm_samegen_safe_20260309}"
REMOTE_ARTIFACT="${REMOTE_ARTIFACT:-/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so}"
JOBS="${JOBS:-2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"
BUILD_SCRIPT="$SCRIPT_DIR/remote_build_safe_runtime_smoke.sh"
PROBE_SCRIPT="$SCRIPT_DIR/remote_probe_current_vm_with_runtime.sh"

start_ts=$(date +%s)

echo "[auto-resume-safe-runtime] waiting for SSH ${HOST}:${PORT} (timeout=${WAIT_SEC}s, interval=${INTERVAL_SEC}s)"
while true; do
  now_ts=$(date +%s)
  if (( now_ts - start_ts > WAIT_SEC )); then
    echo "[auto-resume-safe-runtime] timeout waiting for SSH recovery" >&2
    exit 1
  fi

  if bash "$SSH_SCRIPT" --host "$HOST" --user "$USER_NAME" --pass "$PASS" --port "$PORT" -- "echo SSH_OK" >/tmp/auto_resume_safe_runtime_ssh.log 2>&1; then
    echo "[auto-resume-safe-runtime] SSH recovered"
    break
  fi

  sleep "$INTERVAL_SEC"
done

echo "[auto-resume-safe-runtime] checking safe runtime outputs"
if bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- "bash -lc 'test -f ${REMOTE_BUILD_ROOT}/build/libtvm.so && test -f ${REMOTE_BUILD_ROOT}/build/libtvm_runtime.so'"; then
  echo "[auto-resume-safe-runtime] existing libs found; skip rebuild"
else
  echo "[auto-resume-safe-runtime] libs missing; rebuild safe runtime"
  bash "$BUILD_SCRIPT" \
    --host "$HOST" \
    --user "$USER_NAME" \
    --pass "$PASS" \
    --port "$PORT" \
    --remote-build "${REMOTE_BUILD_ROOT}/build" \
    --remote-prefix "${REMOTE_BUILD_ROOT}/install" \
    --jobs "$JOBS"
fi

echo "[auto-resume-safe-runtime] listing runtime outputs"
bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- "bash -lc 'ls -lh ${REMOTE_BUILD_ROOT}/build/libtvm.so ${REMOTE_BUILD_ROOT}/build/libtvm_runtime.so'"

echo "[auto-resume-safe-runtime] probing current artifact"
bash "$PROBE_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  --python /home/user/venv/bin/python \
  --pythonpath "${REMOTE_BUILD_ROOT}/python:${REMOTE_BUILD_ROOT}/3rdparty/tvm-ffi/python" \
  --libpath "${REMOTE_BUILD_ROOT}/build" \
  --artifact "$REMOTE_ARTIFACT"
