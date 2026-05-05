#!/usr/bin/env bash
set -euo pipefail

# Probe whether a given remote TVM Python/runtime combo can execute the
# current Phytium Pi artifact via relax.VirtualMachine.
#
# Usage:
#   bash ./session_bootstrap/scripts/remote_probe_current_vm_with_runtime.sh \
#     --host 100.121.87.73 --user user --pass user \
#     --python /home/user/venv/bin/python \
#     --pythonpath /home/user/tvm_samegen_safe_20260309/python:/home/user/tvm_samegen_safe_20260309/3rdparty/tvm-ffi/python \
#     --libpath /home/user/tvm_samegen_safe_20260309/build \
#     --ld-library-path /home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build

HOST=""
USER_NAME=""
PASS=""
PORT=22
REMOTE_PYTHON=""
REMOTE_PYTHONPATH=""
REMOTE_LIBPATH=""
REMOTE_LD_LIBRARY_PATH=""
REMOTE_ARTIFACT="/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --python) REMOTE_PYTHON="$2"; shift 2 ;;
    --pythonpath) REMOTE_PYTHONPATH="$2"; shift 2 ;;
    --libpath) REMOTE_LIBPATH="$2"; shift 2 ;;
    --ld-library-path) REMOTE_LD_LIBRARY_PATH="$2"; shift 2 ;;
    --artifact) REMOTE_ARTIFACT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$PASS" || -z "$REMOTE_PYTHON" ]]; then
  echo "Missing required args" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"

bash "$SSH_SCRIPT" \
  --host "$HOST" \
  --user "$USER_NAME" \
  --pass "$PASS" \
  --port "$PORT" \
  -- \
  bash -s -- \
  "$REMOTE_PYTHON" \
  "$REMOTE_PYTHONPATH" \
  "$REMOTE_LIBPATH" \
  "$REMOTE_ARTIFACT" \
  "$REMOTE_LD_LIBRARY_PATH" \
  <<'SH'
set -euo pipefail
REMOTE_PYTHON="$1"
REMOTE_PYTHONPATH="$2"
REMOTE_LIBPATH="$3"
REMOTE_ARTIFACT="$4"
REMOTE_LD_LIBRARY_PATH="$5"
export PYTHONPATH="$REMOTE_PYTHONPATH"
export TVM_LIBRARY_PATH="$REMOTE_LIBPATH"
if [[ -n "$REMOTE_LD_LIBRARY_PATH" ]]; then
  export LD_LIBRARY_PATH="$REMOTE_LD_LIBRARY_PATH"
fi
export REMOTE_ARTIFACT
"$REMOTE_PYTHON" - <<'PY'
import os
import numpy as np
import traceback
import tvm
from tvm import relax

artifact = os.environ['REMOTE_ARTIFACT']
try:
    mod = tvm.runtime.load_module(artifact)
    print('LOAD_OK', getattr(mod, 'type_key', 'NA'))
    vm = relax.VirtualMachine(mod, tvm.cpu(0))
    print('VM_OK')
    out = vm['main'](tvm.nd.array(np.zeros((1,32,32,32), dtype='float32'), tvm.cpu(0)))
    print('RUN_OK', getattr(out, 'shape', None), getattr(out, 'dtype', None))
except Exception:
    traceback.print_exc()
    raise
PY
SH
