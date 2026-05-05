#!/usr/bin/env bash
set -euo pipefail

# Build and install the tvm_ffi Python extension into a separate safe conda env
# on the Phytium Pi. This is used after the conservative TVM C++ rebuild, when
# the remaining blocker is the env's broken tvm_ffi.core binary.

HOST=""
USER_NAME=""
PASS=""
PORT=22
REMOTE_SRC=/home/user/tvm_samegen_20260307/3rdparty/tvm-ffi
REMOTE_ROOT=/home/user/tvm_ffi_py_safe_20260310
REMOTE_ENV=/home/user/anaconda3/envs/tvm310_safe
JOBS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --remote-src) REMOTE_SRC="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --remote-env) REMOTE_ENV="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,24p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$PASS" ]]; then
  echo "Missing --host/--user/--pass" >&2
  exit 2
fi

if [[ "$JOBS" != "1" ]]; then
  echo "Refusing non-j1 build: --jobs must be 1 for this machine." >&2
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
  "$REMOTE_SRC" \
  "$REMOTE_ROOT" \
  "$REMOTE_ENV" \
  "$JOBS" <<'SH'
set -euo pipefail

REMOTE_SRC="$1"
REMOTE_ROOT="$2"
REMOTE_ENV="$3"
JOBS="$4"
REMOTE_BUILD="$REMOTE_ROOT/build"
REMOTE_PREFIX="$REMOTE_ENV/lib/python3.10/site-packages/tvm_ffi"
PYTHON_EXECUTABLE="$REMOTE_ENV/bin/python"
PIP_EXECUTABLE="$REMOTE_ENV/bin/pip"

mkdir -p "$REMOTE_BUILD" "$REMOTE_PREFIX"

"$PYTHON_EXECUTABLE" -m pip install cython

cd "$REMOTE_BUILD"
cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$REMOTE_PREFIX" \
  -DCMAKE_C_FLAGS='-O2' \
  -DCMAKE_CXX_FLAGS='-O2' \
  -DTVM_FFI_BUILD_PYTHON_MODULE=ON \
  -DPython_EXECUTABLE="$PYTHON_EXECUTABLE" \
  "$REMOTE_SRC"

ninja -j"$JOBS"
cmake --install .

printf '\n== tvm_ffi python build done ==\n'
find "$REMOTE_PREFIX" -maxdepth 3 \( -name 'core*.so' -o -name 'libtvm_ffi*.so' -o -name 'libtvm_ffi*.a' \) | sort | xargs -r ls -lh
SH
