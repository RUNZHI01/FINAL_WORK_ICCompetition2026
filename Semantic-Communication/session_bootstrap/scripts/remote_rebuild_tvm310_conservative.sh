#!/usr/bin/env bash
set -euo pipefail

# Rebuild the TVM 0.24dev tree used by the remote tvm310 conda env on Phytium Pi.
# Goal: produce a conservative AArch64 build that avoids Illegal instruction on import.
#
# Usage:
#   bash ./session_bootstrap/scripts/remote_rebuild_tvm310_conservative.sh \
#     --host 100.121.87.73 --user user --pass user
#
# Notes:
#   - Always builds with -j1.
#   - Uses LLVM only if a supported (>=15) llvm-config is available on the Pi.
#   - Falls back to USE_LLVM=OFF when the Pi only has older LLVM, which is still
#     useful for runtime/import compatibility checks.
#   - Avoids native/aggressive CPU tuning.
#   - Builds in a fresh out-of-tree directory by default.

HOST=""
USER_NAME=""
PASS=""
PORT=22
REMOTE_SRC=/home/user/tvm_samegen_20260307
REMOTE_ROOT=/home/user/tvm_samegen_safe_20260309
REMOTE_BUILD=""
REMOTE_PREFIX=""
LLVM_CONFIG=auto
JOBS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --remote-src) REMOTE_SRC="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --remote-build) REMOTE_BUILD="$2"; shift 2 ;;
    --remote-prefix) REMOTE_PREFIX="$2"; shift 2 ;;
    --llvm-config) LLVM_CONFIG="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,28p' "$0"
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

if [[ -z "$REMOTE_BUILD" ]]; then
  REMOTE_BUILD="$REMOTE_ROOT/build"
fi
if [[ -z "$REMOTE_PREFIX" ]]; then
  REMOTE_PREFIX="$REMOTE_ROOT/install"
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
  "$REMOTE_BUILD" \
  "$REMOTE_PREFIX" \
  "$LLVM_CONFIG" \
  "$JOBS" <<'SH'
set -euo pipefail

REMOTE_SRC="$1"
REMOTE_ROOT="$2"
REMOTE_BUILD="$3"
REMOTE_PREFIX="$4"
LLVM_CONFIG="$5"
JOBS="$6"

mkdir -p "$REMOTE_ROOT" "$REMOTE_BUILD" "$REMOTE_PREFIX"
rm -f "$REMOTE_BUILD/config.cmake"

USE_LLVM_VALUE="OFF"
if [[ "$LLVM_CONFIG" != "off" ]]; then
  CANDIDATES=()
  if [[ "$LLVM_CONFIG" == "auto" ]]; then
    CANDIDATES=(
      /usr/lib/llvm-18/bin/llvm-config
      /usr/lib/llvm-17/bin/llvm-config
      /usr/lib/llvm-16/bin/llvm-config
      /usr/lib/llvm-15/bin/llvm-config
      /usr/bin/llvm-config-18
      /usr/bin/llvm-config-17
      /usr/bin/llvm-config-16
      /usr/bin/llvm-config-15
      /usr/bin/llvm-config
    )
  else
    CANDIDATES=("$LLVM_CONFIG")
  fi

  for candidate in "${CANDIDATES[@]}"; do
    if [[ -x "$candidate" ]]; then
      version="$($candidate --version 2>/dev/null || true)"
      major="${version%%.*}"
      if [[ "$major" =~ ^[0-9]+$ ]] && (( major >= 15 )); then
        USE_LLVM_VALUE="$candidate"
        break
      fi
    fi
  done
fi

echo "[remote-build] USE_LLVM=$USE_LLVM_VALUE"

cat > "$REMOTE_BUILD/config.cmake" <<EOF
set(USE_LLVM ${USE_LLVM_VALUE})
set(USE_RPC ON)
set(USE_CPP_RPC OFF)
set(USE_CPP_RTVM OFF)
set(USE_THREADS ON)
set(USE_OPENMP OFF)
set(USE_SORT ON)
set(USE_RANDOM ON)
set(USE_LIBBACKTRACE OFF)
set(USE_CCACHE OFF)
set(USE_LIBTORCH OFF)
set(USE_CUDA OFF)
set(USE_METAL OFF)
set(USE_VULKAN OFF)
EOF

cd "$REMOTE_BUILD"
cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$REMOTE_PREFIX" \
  -DCMAKE_C_FLAGS='-O2' \
  -DCMAKE_CXX_FLAGS='-O2' \
  "$REMOTE_SRC"

ninja -j"$JOBS"
printf '\n== build done ==\n'
ls -lh libtvm.so libtvm_runtime.so || true
if [[ -d lib ]]; then
  ls -lh lib || true
fi
SH
