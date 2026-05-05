#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_remote_tvm_inference_payload.sh --variant <baseline|current>

Notes:
  - Runs a safe one-shot remote inference benchmark:
      load_module() once -> VM init once -> warmup -> repeated inference runs
  - Avoids same-process repeated load_module() loops.
  - Required env:
      REMOTE_TVM_PYTHON
      REMOTE_TVM_PRIMARY_DIR
      REMOTE_TVM_JSCC_BASE_DIR
      TUNE_INPUT_SHAPE
      TUNE_INPUT_DTYPE
  - Optional env:
      INFERENCE_BASELINE_ARCHIVE
      INFERENCE_CURRENT_ARCHIVE
      INFERENCE_BASELINE_EXPECTED_SHA256
      INFERENCE_CURRENT_EXPECTED_SHA256
      INFERENCE_EXPECTED_SHA256
      INFERENCE_ENTRY=main
      INFERENCE_WARMUP_RUNS=1
      INFERENCE_REPEAT=5
      INFERENCE_DEVICE=cpu
      REMOTE_MODE=ssh|local (default: ssh)
EOF
}

VARIANT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$VARIANT" != "baseline" && "$VARIANT" != "current" ]]; then
  echo "ERROR: --variant must be baseline or current." >&2
  exit 1
fi

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

build_remote_probe_command() {
  local remote_command="env"
  local arg=""
  for arg in "$@"; do
    remote_command+=" $(shell_quote "$arg")"
  done
  # REMOTE_TVM_PYTHON may be a shell snippet such as
  # "env PYTHONPATH=/tmp/tvm_only /usr/bin/python3".
  remote_command+=" ${REMOTE_TVM_PYTHON}"
  remote_command+=" $(shell_quote "-")"
  remote_command+=" $(shell_quote "$ARCHIVE_DIR")"
  remote_command+=" $(shell_quote "$VARIANT")"
  printf '%s' "$remote_command"
}

REMOTE_MODE_RAW="${REMOTE_MODE:-ssh}"
REMOTE_MODE="$(printf '%s' "$REMOTE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$REMOTE_MODE" != "ssh" && "$REMOTE_MODE" != "local" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh or local (got: $REMOTE_MODE_RAW)" >&2
  exit 1
fi

require_var REMOTE_TVM_PYTHON
require_var TUNE_INPUT_SHAPE
require_var TUNE_INPUT_DTYPE

if [[ "$REMOTE_MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

if [[ "$VARIANT" == "baseline" ]]; then
  ARCHIVE_DIR="${INFERENCE_BASELINE_ARCHIVE:-${REMOTE_TVM_PRIMARY_DIR:-}}"
else
  ARCHIVE_DIR="${INFERENCE_CURRENT_ARCHIVE:-${REMOTE_TVM_JSCC_BASE_DIR:-}}"
fi

if [[ -z "$ARCHIVE_DIR" ]]; then
  echo "ERROR: Missing archive dir for variant=$VARIANT. Set INFERENCE_BASELINE_ARCHIVE/INFERENCE_CURRENT_ARCHIVE or REMOTE_TVM_PRIMARY_DIR/REMOTE_TVM_JSCC_BASE_DIR." >&2
  exit 1
fi

INFERENCE_ENTRY_VALUE="${INFERENCE_ENTRY:-main}"
INFERENCE_WARMUP_RUNS_VALUE="${INFERENCE_WARMUP_RUNS:-1}"
INFERENCE_REPEAT_VALUE="${INFERENCE_REPEAT:-5}"
INFERENCE_DEVICE_VALUE="${INFERENCE_DEVICE:-cpu}"
if [[ "$VARIANT" == "baseline" ]]; then
  INFERENCE_EXPECTED_SHA256_VALUE="${INFERENCE_BASELINE_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
else
  INFERENCE_EXPECTED_SHA256_VALUE="${INFERENCE_CURRENT_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
fi

for value_name in INFERENCE_WARMUP_RUNS_VALUE INFERENCE_REPEAT_VALUE; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "ERROR: ${value_name} must be a non-negative integer (got: $value)." >&2
    exit 1
  fi
done

if [[ -n "$INFERENCE_EXPECTED_SHA256_VALUE" ]] && ! [[ "$INFERENCE_EXPECTED_SHA256_VALUE" =~ ^[0-9A-Fa-f]{64}$ ]]; then
  echo "ERROR: expected artifact sha256 must be 64 hex characters (got: $INFERENCE_EXPECTED_SHA256_VALUE)." >&2
  exit 1
fi

run_probe_python() {
  local py_script
  local rc=0
  py_script="$(mktemp)"
  cat >"$py_script" <<'PY'
import hashlib
import json
import os
import runpy
import statistics
import sys
import time

archive_dir, variant = sys.argv[1:3]
entry_name = os.environ.get("INFERENCE_ENTRY", "main")
warmup_runs = int(os.environ.get("INFERENCE_WARMUP_RUNS", "1"))
repeat = int(os.environ.get("INFERENCE_REPEAT", "5"))
shape = [int(x.strip()) for x in os.environ["TUNE_INPUT_SHAPE"].split(",") if x.strip()]
dtype = os.environ.get("TUNE_INPUT_DTYPE", "float32")
device_name = os.environ.get("INFERENCE_DEVICE", "cpu")
so_path = os.path.join(archive_dir, "tvm_tune_logs", "optimized_model.so")
expected_sha256 = os.environ.get("INFERENCE_EXPECTED_SHA256", "").strip().lower()

if not os.path.exists(so_path):
    raise SystemExit(f"ERROR: missing optimized_model.so: {so_path}")

sha256 = hashlib.sha256()
with open(so_path, "rb") as infile:
    for chunk in iter(lambda: infile.read(1024 * 1024), b""):
        sha256.update(chunk)
artifact_sha256 = sha256.hexdigest()
artifact_size_bytes = os.path.getsize(so_path)

if expected_sha256 and artifact_sha256 != expected_sha256:
    raise SystemExit(
        "ERROR: artifact sha256 mismatch "
        f"variant={variant} path={so_path} expected={expected_sha256} actual={artifact_sha256}"
    )

import numpy as np  # pylint: disable=import-error
import tvm  # pylint: disable=import-error
from tvm import relax  # pylint: disable=import-error

if device_name == "cpu":
    dev = tvm.cpu(0)
else:
    dev = tvm.device(device_name, 0)

runtime = getattr(tvm, "runtime", None)
runtime_tensor = getattr(runtime, "tensor", None) if runtime is not None else None
if runtime_tensor is None and runtime is not None:
    runtime_ndarray = getattr(runtime, "ndarray", None)
    if runtime_ndarray is not None:
        runtime_tensor = lambda arr, dev: runtime_ndarray.array(arr, dev)
if runtime_tensor is None:
    raise AttributeError("module tvm.runtime has neither tensor nor ndarray.array")

inp = runtime_tensor(np.zeros(shape, dtype=dtype), dev)

report = {
    "variant": variant,
    "archive": archive_dir,
    "entry": entry_name,
    "shape": shape,
    "dtype": dtype,
    "warmup_runs": warmup_runs,
    "repeat": repeat,
    "tvm_version": tvm.__version__,
    "device": str(dev),
    "artifact_path": so_path,
    "artifact_sha256": artifact_sha256,
    "artifact_size_bytes": artifact_size_bytes,
    "artifact_sha256_expected": expected_sha256 or None,
    "artifact_sha256_match": None if not expected_sha256 else artifact_sha256 == expected_sha256,
}

preload_py = os.environ.get("TVM_RUNTIME_PRELOAD_PY", "").strip()
if preload_py:
    runpy.run_path(preload_py, run_name="__main__")

load_t0 = time.perf_counter()
lib = tvm.runtime.load_module(so_path)
load_t1 = time.perf_counter()
vm = relax.VirtualMachine(lib, dev)
load_t2 = time.perf_counter()
fn = vm[entry_name]

for _ in range(warmup_runs):
    _ = fn(inp)

elapsed = []
last_res = None
for _ in range(repeat):
    t0 = time.perf_counter()
    last_res = fn(inp)
    t1 = time.perf_counter()
    elapsed.append((t1 - t0) * 1000.0)

shape_out = None
dtype_out = None
if last_res is not None:
    if hasattr(last_res, "shape"):
        shape_out = list(last_res.shape)
    if hasattr(last_res, "dtype"):
        dtype_out = str(last_res.dtype)

report.update(
    {
        "load_ms": round((load_t1 - load_t0) * 1000.0, 3),
        "vm_init_ms": round((load_t2 - load_t1) * 1000.0, 3),
        "run_count": len(elapsed),
        "run_samples_ms": [round(x, 3) for x in elapsed],
        "run_median_ms": round(statistics.median(elapsed), 3) if elapsed else None,
        "run_mean_ms": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
        "run_min_ms": round(min(elapsed), 3) if elapsed else None,
        "run_max_ms": round(max(elapsed), 3) if elapsed else None,
        "run_variance_ms2": round(statistics.pvariance(elapsed), 6) if len(elapsed) > 1 else 0.0,
        "output_shape": shape_out,
        "output_dtype": dtype_out,
    }
)

print(json.dumps(report, ensure_ascii=False))
PY

  if [[ "$REMOTE_MODE" == "ssh" ]]; then
    local remote_command
    remote_env_args=(
      "INFERENCE_ENTRY=$INFERENCE_ENTRY_VALUE"
      "INFERENCE_WARMUP_RUNS=$INFERENCE_WARMUP_RUNS_VALUE"
      "INFERENCE_REPEAT=$INFERENCE_REPEAT_VALUE"
      "INFERENCE_DEVICE=$INFERENCE_DEVICE_VALUE"
      "INFERENCE_EXPECTED_SHA256=$INFERENCE_EXPECTED_SHA256_VALUE"
      "TUNE_INPUT_SHAPE=$TUNE_INPUT_SHAPE"
      "TUNE_INPUT_DTYPE=$TUNE_INPUT_DTYPE"
    )
    if [[ -n "${TVM_RUNTIME_PRELOAD_PY:-}" ]]; then
      remote_env_args+=("TVM_RUNTIME_PRELOAD_PY=$TVM_RUNTIME_PRELOAD_PY")
    fi
    if [[ -n "${TVM_TRANSPOSE_ADD6_PROXY_SO:-}" ]]; then
      remote_env_args+=("TVM_TRANSPOSE_ADD6_PROXY_SO=$TVM_TRANSPOSE_ADD6_PROXY_SO")
    fi
    if [[ -n "${TVM_TRANSPOSE_ADD6_PROXY_FUNC:-}" ]]; then
      remote_env_args+=("TVM_TRANSPOSE_ADD6_PROXY_FUNC=$TVM_TRANSPOSE_ADD6_PROXY_FUNC")
    fi
    if [[ -n "${TVM_TRANSPOSE_ADD6_PROXY_REG:-}" ]]; then
      remote_env_args+=("TVM_TRANSPOSE_ADD6_PROXY_REG=$TVM_TRANSPOSE_ADD6_PROXY_REG")
    fi
    remote_command="$(build_remote_probe_command "${remote_env_args[@]}")"
    set +e
    bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$REMOTE_HOST" \
      --user "$REMOTE_USER" \
      --pass "$REMOTE_PASS" \
      --port "${REMOTE_SSH_PORT:-22}" \
      -- \
      "$remote_command" \
      <"$py_script"
    rc=$?
    set -e
    rm -f "$py_script"
    return "$rc"
  fi

  set +e
  env \
    "INFERENCE_ENTRY=$INFERENCE_ENTRY_VALUE" \
    "INFERENCE_WARMUP_RUNS=$INFERENCE_WARMUP_RUNS_VALUE" \
    "INFERENCE_REPEAT=$INFERENCE_REPEAT_VALUE" \
    "INFERENCE_DEVICE=$INFERENCE_DEVICE_VALUE" \
    "INFERENCE_EXPECTED_SHA256=$INFERENCE_EXPECTED_SHA256_VALUE" \
    "TUNE_INPUT_SHAPE=$TUNE_INPUT_SHAPE" \
    "TUNE_INPUT_DTYPE=$TUNE_INPUT_DTYPE" \
    "$REMOTE_TVM_PYTHON" - "$ARCHIVE_DIR" "$VARIANT" <"$py_script"
  rc=$?
  set -e
  rm -f "$py_script"
  return "$rc"
}

run_probe_python
