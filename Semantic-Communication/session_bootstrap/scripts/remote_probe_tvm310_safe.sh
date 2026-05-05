#!/usr/bin/env bash
set -euo pipefail

# Quick probe for the working Phytium Pi TVM 0.24dev safe env.
# This does not require the broken original tvm310 env.

HOST=""
USER_NAME=""
PASS=""
PORT=22
SAFE_ENV=/home/user/anaconda3/envs/tvm310_safe
SAFE_TVM_BUILD=/home/user/tvm_samegen_safe_20260309/build
SAFE_TVM_PY=/home/user/tvm_samegen_20260307/python

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --safe-env) SAFE_ENV="$2"; shift 2 ;;
    --safe-build) SAFE_TVM_BUILD="$2"; shift 2 ;;
    --safe-python) SAFE_TVM_PY="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"

bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- \
  bash -lc "TVM_FFI_DISABLE_TORCH_C_DLPACK=1 \
LD_LIBRARY_PATH=$SAFE_ENV/lib/python3.10/site-packages/tvm_ffi/lib:$SAFE_TVM_BUILD \
TVM_LIBRARY_PATH=$SAFE_TVM_BUILD \
PYTHONPATH=$SAFE_TVM_PY:$SAFE_ENV/lib/python3.10/site-packages \
$SAFE_ENV/bin/python -c 'import tvm; import sys; print(sys.executable); print(tvm.__version__); print(\"TVM310_SAFE_OK\")'"
