#!/usr/bin/env bash
set -euo pipefail

# Run a command on the Phytium Pi under the importable safe TVM 0.24dev stack.
#
# This wrapper assumes:
# - safe conda env: /home/user/anaconda3/envs/tvm310_safe
# - safe rebuilt TVM libs: /home/user/tvm_samegen_safe_20260309/build
# - TVM python source: /home/user/tvm_samegen_20260307/python
# - safe tvm_ffi package installed in tvm310_safe site-packages
#
# Example:
#   bash ./session_bootstrap/scripts/run_remote_tvm310_safe.sh \
#     --host 100.121.87.73 --user user --pass user -- \
#     /home/user/anaconda3/envs/tvm310_safe/bin/python -c 'import tvm; print(tvm.__version__)'

HOST=""
USER_NAME=""
PASS=""
PORT=22
SAFE_ENV=/home/user/anaconda3/envs/tvm310_safe
SAFE_BUILD=/home/user/tvm_samegen_safe_20260309/build
TVM_PYTHON_SRC=/home/user/tvm_samegen_20260307/python

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --safe-env) SAFE_ENV="$2"; shift 2 ;;
    --safe-build) SAFE_BUILD="$2"; shift 2 ;;
    --tvm-python-src) TVM_PYTHON_SRC="$2"; shift 2 ;;
    --) shift; break ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$PASS" ]]; then
  echo "Missing --host/--user/--pass" >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  echo "Missing remote command after --" >&2
  exit 2
fi

SITE_PACKAGES="$SAFE_ENV/lib/python3.10/site-packages"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"

REMOTE_CMD=$(printf "%q " "$@")

bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- \
  bash -lc "TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH='$SITE_PACKAGES/tvm_ffi/lib:$SAFE_BUILD' TVM_LIBRARY_PATH='$SAFE_BUILD' PYTHONPATH='$TVM_PYTHON_SRC:$SITE_PACKAGES' $REMOTE_CMD"
