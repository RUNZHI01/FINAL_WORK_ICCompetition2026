#!/usr/bin/env bash
set -euo pipefail

# Build a conservative AArch64 TVM runtime on the remote Phytium Pi.
# Goal: produce a newer runtime that can load current VMExecutable artifacts
# without triggering Illegal instruction.
#
# Usage:
#   bash ./session_bootstrap/scripts/remote_build_safe_runtime_smoke.sh \
#     --host 100.121.87.73 --user user --pass user

HOST=""
USER_NAME=""
PASS=""
PORT=22
REMOTE_SRC=/home/user/tvm_samegen_20260307
REMOTE_BUILD=/home/user/tvm_samegen_safe_20260309/build
REMOTE_PREFIX=/home/user/tvm_samegen_safe_20260309/install
JOBS=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --remote-src) REMOTE_SRC="$2"; shift 2 ;;
    --remote-build) REMOTE_BUILD="$2"; shift 2 ;;
    --remote-prefix) REMOTE_PREFIX="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$PASS" ]]; then
  echo "Missing --host/--user/--pass" >&2
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
  "$REMOTE_BUILD" \
  "$REMOTE_PREFIX" \
  "$JOBS" \
  <<'SH'
set -euo pipefail

REMOTE_SRC="$1"
REMOTE_BUILD="$2"
REMOTE_PREFIX="$3"
JOBS="$4"

mkdir -p "$REMOTE_BUILD" "$REMOTE_PREFIX"
cat > "$REMOTE_BUILD/config.cmake" <<'EOF'
set(USE_RPC ON)
set(USE_CPP_RPC OFF)
set(USE_CPP_RTVM OFF)
set(USE_LLVM OFF)
set(USE_OPENMP none)
set(USE_SORT ON)
set(USE_RANDOM ON)
set(USE_LIBBACKTRACE OFF)
set(USE_CCACHE OFF)
set(USE_THREADS ON)
EOF

cd "$REMOTE_BUILD"
cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_FLAGS=-O2\ -march=armv8-a+simd\ -mtune=generic \
  -DCMAKE_CXX_FLAGS=-O2\ -march=armv8-a+simd\ -mtune=generic \
  "$REMOTE_SRC"

ninja -j"$JOBS" tvm tvm_runtime
printf '\n== build done ==\n'
ls -lh libtvm.so libtvm_runtime.so
SH