#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_RUNNER_SOURCE="$SCRIPT_DIR/current_real_reconstruction.py"

usage() {
  cat <<'EOF'
Usage:
  run_remote_current_real_reconstruction.sh --variant <baseline|current> [options]

Notes:
  - Runs a real reconstruction path analogous to the legacy JSCC tvm_002.py flow:
      read latent input -> add channel noise -> VM decode -> write outputs
  - Emits legacy per-sample latency lines plus a final JSON summary so
    run_inference_benchmark.sh can parse timings directly.
  - Supports `.pt` latent inputs for the real remote dataset and `.npz` / `.npy`
    fallbacks for lightweight local validation.
  - Task 5.1 can request a lightweight per-op profiling attempt on the same
    trusted current runtime path with --profile-ops.

Required env:
  REMOTE_MODE=ssh|local
  REMOTE_TVM_PYTHON
  REMOTE_INPUT_DIR
  REMOTE_OUTPUT_BASE
  REMOTE_SNR_BASELINE / REMOTE_SNR_CURRENT
  REMOTE_BATCH_BASELINE / REMOTE_BATCH_CURRENT

Artifact selection:
  baseline -> REMOTE_BASELINE_ARTIFACT or INFERENCE_BASELINE_ARCHIVE or REMOTE_TVM_PRIMARY_DIR
  current  -> REMOTE_CURRENT_ARTIFACT  or INFERENCE_CURRENT_ARCHIVE  or REMOTE_TVM_JSCC_BASE_DIR

Optional env:
  REMOTE_TORCH_PYTHONPATH
  REMOTE_REAL_EXTRA_PYTHONPATH
  OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded|usrp
  REMOTE_USRP_RX_DIR
  INFERENCE_OUTPUT_PREFIX
  INFERENCE_REAL_OUTPUT_PREFIX
  LOCAL_CURRENT_ARTIFACT_SOURCE
  REMOTE_CURRENT_ARTIFACT_STAGE_DIR
  INFERENCE_BASELINE_EXPECTED_SHA256
  INFERENCE_CURRENT_EXPECTED_SHA256
  INFERENCE_EXPECTED_SHA256

Options:
  --max-inputs <n>         Optional cap on latent inputs. 0 means all.
  --seed <int>             Optional numpy random seed for the remote runner.
  --profile-ops            Attempt vm.profile on the first profiled samples.
  --profile-samples <n>    How many samples attempt vm.profile. Default: 1.
EOF
}

VARIANT=""
MAX_INPUTS=""
SEED=""
PROFILE_OPS=0
PROFILE_SAMPLES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    --max-inputs)
      MAX_INPUTS="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --profile-ops)
      PROFILE_OPS=1
      shift
      ;;
    --profile-samples)
      PROFILE_SAMPLES="${2:-}"
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

demo_mode_flag="$(printf '%s' "${OPENAMP_DEMO_MODE:-}" | tr '[:upper:]' '[:lower:]')"
if [[ -z "$MAX_INPUTS" && ( "$demo_mode_flag" == "1" || "$demo_mode_flag" == "true" || "$demo_mode_flag" == "yes" || "$demo_mode_flag" == "on" ) ]]; then
  MAX_INPUTS="${OPENAMP_DEMO_MAX_INPUTS:-300}"
fi

if [[ "$VARIANT" != "baseline" && "$VARIANT" != "current" ]]; then
  echo "ERROR: --variant must be baseline or current." >&2
  exit 1
fi

if [[ ! -f "$PYTHON_RUNNER_SOURCE" ]]; then
  echo "ERROR: runner source not found: $PYTHON_RUNNER_SOURCE" >&2
  exit 1
fi

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
}

REMOTE_MODE_RAW="${REMOTE_MODE:-ssh}"
REMOTE_MODE="$(printf '%s' "$REMOTE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$REMOTE_MODE" != "ssh" && "$REMOTE_MODE" != "local" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh or local (got: $REMOTE_MODE_RAW)" >&2
  exit 1
fi

require_var REMOTE_TVM_PYTHON
require_var REMOTE_OUTPUT_BASE

INPUT_SOURCE_MODE_RAW="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-${REMOTE_INPUT_SOURCE_MODE:-prerecorded}}"
INPUT_SOURCE_MODE="$(printf '%s' "$INPUT_SOURCE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
case "$INPUT_SOURCE_MODE" in
  prerecorded|preset|archive)
    INPUT_SOURCE_MODE="prerecorded"
    require_var REMOTE_INPUT_DIR
    REAL_INPUT_DIR="$REMOTE_INPUT_DIR"
    INPUT_SOURCE_LABEL="预录模式"
    ;;
  usrp|radio|wireless)
    INPUT_SOURCE_MODE="usrp"
    require_var REMOTE_USRP_RX_DIR
    REAL_INPUT_DIR="$REMOTE_USRP_RX_DIR"
    INPUT_SOURCE_LABEL="USRP 传输模式"
    ;;
  *)
    echo "ERROR: unsupported OPENAMP_DEMO_INPUT_SOURCE_MODE/REMOTE_INPUT_SOURCE_MODE: $INPUT_SOURCE_MODE_RAW" >&2
    exit 1
    ;;
esac

if [[ "$REMOTE_MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

resolve_artifact_path() {
  local explicit_path="$1"
  local archive_dir="$2"
  if [[ -n "$explicit_path" ]]; then
    printf '%s\n' "$explicit_path"
    return 0
  fi
  if [[ -n "$archive_dir" ]]; then
    printf '%s/tvm_tune_logs/optimized_model.so\n' "$archive_dir"
    return 0
  fi
  return 1
}

sha256_file() {
  local file_path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file_path" | awk '{print $1}'
    return 0
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file_path" | awk '{print $1}'
    return 0
  fi
  python3 -c 'import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
with path.open("rb") as infile:
    for chunk in iter(lambda: infile.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())' "$file_path"
}

remote_sha256_file() {
  local remote_path="$1"
  bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "${REMOTE_SSH_PORT:-22}" \
    -- \
    python3 -c 'import hashlib, pathlib, sys; path = pathlib.Path(sys.argv[1]); digest = hashlib.sha256(); infile = path.open("rb"); [digest.update(chunk) for chunk in iter(lambda: infile.read(1024 * 1024), b"")]; infile.close(); print(digest.hexdigest())' \
    "$remote_path"
}

stage_current_artifact_from_local_source() {
  local local_source="$1"
  local expected_sha256_lower local_sha256 remote_stage_root remote_stage_dir remote_stage_path remote_sha256

  if [[ "$VARIANT" != "current" || "$REMOTE_MODE" != "ssh" || -z "$local_source" ]]; then
    return 0
  fi
  if [[ ! -f "$local_source" ]]; then
    echo "ERROR: trusted local current artifact source not found: $local_source" >&2
    exit 1
  fi

  local_sha256="$(sha256_file "$local_source")"
  expected_sha256_lower="$(printf '%s' "$REAL_EXPECTED_SHA256" | tr '[:upper:]' '[:lower:]')"
  if [[ -n "$expected_sha256_lower" && "$local_sha256" != "$expected_sha256_lower" ]]; then
    echo "ERROR: trusted local current artifact source sha256 mismatch path=$local_source expected=$expected_sha256_lower actual=$local_sha256" >&2
    exit 1
  fi

  remote_stage_root="${REMOTE_CURRENT_ARTIFACT_STAGE_DIR:-${REMOTE_TVM_JSCC_BASE_DIR:-${REMOTE_OUTPUT_BASE:-/tmp/openamp_demo_current_artifacts}}}"
  remote_stage_dir="${remote_stage_root%/}/.openamp_demo_current/${local_sha256}"
  remote_stage_path="${remote_stage_dir}/optimized_model.so"

  echo "[current-real] staging trusted current artifact source=$local_source remote_artifact=$remote_stage_path"
  base64 "$local_source" | bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "${REMOTE_SSH_PORT:-22}" \
    -- \
    python3 -c 'import base64, pathlib, sys; payload = base64.b64decode(sys.stdin.buffer.read()); path = pathlib.Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)' \
    "$remote_stage_path"

  remote_sha256="$(remote_sha256_file "$remote_stage_path" | tr -d '\r\n')"
  if [[ "$remote_sha256" != "$local_sha256" ]]; then
    echo "ERROR: remote staged current artifact sha256 mismatch path=$remote_stage_path expected=$local_sha256 actual=$remote_sha256" >&2
    exit 1
  fi

  REAL_ARTIFACT_PATH="$remote_stage_path"
  echo "[current-real] staged trusted current artifact source=$local_source remote_artifact=$REAL_ARTIFACT_PATH sha256=$local_sha256"
}

if [[ "$VARIANT" == "baseline" ]]; then
  require_var REMOTE_SNR_BASELINE
  require_var REMOTE_BATCH_BASELINE
  REAL_SNR="$REMOTE_SNR_BASELINE"
  REAL_BATCH="$REMOTE_BATCH_BASELINE"
  REAL_ARTIFACT_PATH="$(resolve_artifact_path "${REMOTE_BASELINE_ARTIFACT:-}" "${INFERENCE_BASELINE_ARCHIVE:-${REMOTE_TVM_PRIMARY_DIR:-}}")" || {
    echo "ERROR: Missing baseline artifact path. Set REMOTE_BASELINE_ARTIFACT or INFERENCE_BASELINE_ARCHIVE/REMOTE_TVM_PRIMARY_DIR." >&2
    exit 1
  }
  REAL_EXPECTED_SHA256="${INFERENCE_BASELINE_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
else
  require_var REMOTE_SNR_CURRENT
  require_var REMOTE_BATCH_CURRENT
  REAL_SNR="$REMOTE_SNR_CURRENT"
  REAL_BATCH="$REMOTE_BATCH_CURRENT"
  REAL_ARTIFACT_PATH="$(resolve_artifact_path "${REMOTE_CURRENT_ARTIFACT:-}" "${INFERENCE_CURRENT_ARCHIVE:-${REMOTE_TVM_JSCC_BASE_DIR:-}}")" || {
    echo "ERROR: Missing current artifact path. Set REMOTE_CURRENT_ARTIFACT or INFERENCE_CURRENT_ARCHIVE/REMOTE_TVM_JSCC_BASE_DIR." >&2
    exit 1
  }
  REAL_EXPECTED_SHA256="${INFERENCE_CURRENT_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
fi

if ! [[ "$REAL_BATCH" =~ ^[0-9]+$ ]]; then
  echo "ERROR: batch_size must be a non-negative integer (got: $REAL_BATCH)." >&2
  exit 1
fi
if [[ -n "$MAX_INPUTS" ]] && ! [[ "$MAX_INPUTS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-inputs must be a non-negative integer (got: $MAX_INPUTS)." >&2
  exit 1
fi

if [[ -n "$REAL_EXPECTED_SHA256" ]] && ! [[ "$REAL_EXPECTED_SHA256" =~ ^[0-9A-Fa-f]{64}$ ]]; then
  echo "ERROR: expected artifact sha256 must be 64 hex characters (got: $REAL_EXPECTED_SHA256)." >&2
  exit 1
fi

stage_current_artifact_from_local_source "${LOCAL_CURRENT_ARTIFACT_SOURCE:-}"

: "${TVM_RUNTIME_PRELOAD_PY:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_SO:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_FUNC:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_REG:=}"

OUTPUT_PREFIX="${INFERENCE_REAL_OUTPUT_PREFIX:-${INFERENCE_OUTPUT_PREFIX:-inference_real_reconstruction}}"
REAL_OUTPUT_DIR="$REMOTE_OUTPUT_BASE/${OUTPUT_PREFIX}_${VARIANT}"
REAL_EXTRA_PYTHONPATH="${REMOTE_REAL_EXTRA_PYTHONPATH:-${REMOTE_TORCH_PYTHONPATH:-}}"

run_real_reconstruction() {
  local runner_script
  local rc=0
  runner_script="$(mktemp)"
  {
    cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
    declare -p REMOTE_TVM_PYTHON REAL_INPUT_DIR REAL_OUTPUT_DIR REAL_SNR REAL_BATCH VARIANT REAL_ARTIFACT_PATH REAL_EXPECTED_SHA256 REAL_EXTRA_PYTHONPATH MAX_INPUTS SEED PROFILE_OPS PROFILE_SAMPLES TVM_RUNTIME_PRELOAD_PY TVM_TRANSPOSE_ADD6_PROXY_SO TVM_TRANSPOSE_ADD6_PROXY_FUNC TVM_TRANSPOSE_ADD6_PROXY_REG INPUT_SOURCE_MODE INPUT_SOURCE_LABEL
    cat <<'SH'

remote_python="$REMOTE_TVM_PYTHON"
input_dir="$REAL_INPUT_DIR"
output_dir="$REAL_OUTPUT_DIR"
snr="$REAL_SNR"
batch_size="$REAL_BATCH"
variant="$VARIANT"
artifact_path="$REAL_ARTIFACT_PATH"
expected_sha256="$REAL_EXPECTED_SHA256"
extra_pythonpath="$REAL_EXTRA_PYTHONPATH"
max_inputs="$MAX_INPUTS"
seed="$SEED"
profile_ops="$PROFILE_OPS"
profile_samples="$PROFILE_SAMPLES"
preload_py="${TVM_RUNTIME_PRELOAD_PY:-}"
proxy_so="${TVM_TRANSPOSE_ADD6_PROXY_SO:-}"
proxy_func="${TVM_TRANSPOSE_ADD6_PROXY_FUNC:-}"
proxy_reg="${TVM_TRANSPOSE_ADD6_PROXY_REG:-}"
input_source_mode="$INPUT_SOURCE_MODE"
input_source_label="$INPUT_SOURCE_LABEL"

mkdir -p "$output_dir"
rm -rf "$output_dir/reconstructions"

if [[ -n "$extra_pythonpath" ]]; then
  export PYTHONPATH="$extra_pythonpath${PYTHONPATH:+:$PYTHONPATH}"
  # Preserve the torch sidecar path inside the remote Python environment even
  # when REMOTE_TVM_PYTHON injects its own inline PYTHONPATH and overrides the
  # shell-level export above.
  export REMOTE_REAL_EXTRA_PYTHONPATH="$extra_pythonpath"
  export DEMO_EXTRA_PYTHONPATH="$extra_pythonpath"
  export REMOTE_TORCH_PYTHONPATH="${REMOTE_TORCH_PYTHONPATH:-$extra_pythonpath}"
fi
export PYTHONNOUSERSITE=1
if [[ -n "$preload_py" ]]; then
  export TVM_RUNTIME_PRELOAD_PY="$preload_py"
fi
if [[ -n "$proxy_so" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_SO="$proxy_so"
fi
if [[ -n "$proxy_func" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_FUNC="$proxy_func"
fi
if [[ -n "$proxy_reg" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_REG="$proxy_reg"
fi

run_remote_python() {
  local stdin_payload cmd arg rc=0
  stdin_payload="$(mktemp)"
  cat >"$stdin_payload"
  cmd="$remote_python"
  for arg in "$@"; do
    cmd+=" $(printf '%q' "$arg")"
  done
  set +e
  bash -c "$cmd" <"$stdin_payload"
  rc=$?
  set -e
  rm -f "$stdin_payload"
  return "$rc"
}

echo "[current-real] variant=$variant input_source_mode=$input_source_mode input_source_label=$input_source_label input_dir=$input_dir artifact=$artifact_path output_dir=$output_dir snr=$snr batch_size=$batch_size python=$remote_python"

extra_args=()
if [[ -n "$max_inputs" ]]; then
  extra_args+=(--max-inputs "$max_inputs")
fi
if [[ -n "$seed" ]]; then
  extra_args+=(--seed "$seed")
fi
if [[ "$profile_ops" == "1" ]]; then
  extra_args+=(--profile-ops)
fi
if [[ -n "$profile_samples" ]]; then
  extra_args+=(--profile-samples "$profile_samples")
fi

run_remote_python - \
  --artifact-path "$artifact_path" \
  --input-dir "$input_dir" \
  --output-dir "$output_dir" \
  --snr "$snr" \
  --batch-size "$batch_size" \
  --variant "$variant" \
  --input-source-mode "$input_source_mode" \
  --input-source-label "$input_source_label" \
  --expected-sha256 "$expected_sha256" \
  "${extra_args[@]}" <<'PY'
SH
    cat "$PYTHON_RUNNER_SOURCE"
    cat <<'SH'
PY
SH
  } >"$runner_script"
  chmod 700 "$runner_script"

  if [[ "$REMOTE_MODE" == "ssh" ]]; then
    set +e
    SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1 \
    bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$REMOTE_HOST" \
      --user "$REMOTE_USER" \
      --pass "$REMOTE_PASS" \
      --port "${REMOTE_SSH_PORT:-22}" \
      -- \
      bash -s \
      <"$runner_script"
    rc=$?
    set -e
    rm -f "$runner_script"
    return "$rc"
  fi

  set +e
  bash "$runner_script"
  rc=$?
  set -e
  rm -f "$runner_script"
  return "$rc"
}

run_real_reconstruction
