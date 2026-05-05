#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_RUNNER_SOURCE="$SCRIPT_DIR/mnn_real_reconstruction.py"

usage() {
  cat <<'EOF'
Usage:
  run_remote_mnn_reconstruction.sh --variant <baseline|current> --model-path <path> [options]

Options:
  --model-path <path>           Required MNN model path on the execution target.
  --variant <baseline|current>  Logical variant label for logging/reporting.
  --output-prefix <prefix>      Output directory name under REMOTE_OUTPUT_BASE.
  --max-inputs <n>              Optional cap on the number of latent inputs.
  --seed <int>                  Optional deterministic AWGN seed.
  --interpreter-count <n>       Number of MNN interpreter/session workers.
  --session-threads <n>         CPU threads per session.
  --precision <normal|low|high> Session precision mode.
  --shape-mode <dynamic|bucketed>
                                Session reuse mode.
  --bucket-shapes <csv>         Exact latent shapes for prebuilt bucket sessions.
  --warmup-inputs <n>           Number of warmup inputs before timing.
  --auto-backend                Enable MNN auto-backend/tuning hints.
  --tune-num <n>                Hint count used with --auto-backend.
  --dry-run                     Skip real MNN execution and synthesize outputs.
  --mock-infer-ms <ms>          Mock per-item infer time when --dry-run is used.
  -h, --help                    Show this message.

Required env:
  REMOTE_MODE=ssh|local
  REMOTE_MNN_PYTHON
  REMOTE_OUTPUT_BASE
  REMOTE_SNR_BASELINE / REMOTE_SNR_CURRENT

Input source env:
  OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded|usrp
  REMOTE_INPUT_DIR      Required when input source is prerecorded.
  REMOTE_USRP_RX_DIR    Required when input source is usrp.

SSH env when REMOTE_MODE=ssh:
  REMOTE_HOST
  REMOTE_USER
  REMOTE_PASS
  REMOTE_SSH_PORT
EOF
}

VARIANT=""
MODEL_PATH=""
OUTPUT_PREFIX=""
MAX_INPUTS=""
SEED=""
INTERPRETER_COUNT=""
SESSION_THREADS=""
PRECISION=""
SHAPE_MODE=""
BUCKET_SHAPES=""
WARMUP_INPUTS=""
AUTO_BACKEND=0
TUNE_NUM=""
DRY_RUN=0
MOCK_INFER_MS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    --model-path)
      MODEL_PATH="${2:-}"
      shift 2
      ;;
    --output-prefix)
      OUTPUT_PREFIX="${2:-}"
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
    --interpreter-count)
      INTERPRETER_COUNT="${2:-}"
      shift 2
      ;;
    --session-threads)
      SESSION_THREADS="${2:-}"
      shift 2
      ;;
    --precision)
      PRECISION="${2:-}"
      shift 2
      ;;
    --shape-mode)
      SHAPE_MODE="${2:-}"
      shift 2
      ;;
    --bucket-shapes)
      BUCKET_SHAPES="${2:-}"
      shift 2
      ;;
    --warmup-inputs)
      WARMUP_INPUTS="${2:-}"
      shift 2
      ;;
    --auto-backend)
      AUTO_BACKEND=1
      shift
      ;;
    --tune-num)
      TUNE_NUM="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --mock-infer-ms)
      MOCK_INFER_MS="${2:-}"
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
if [[ -z "$MODEL_PATH" ]]; then
  echo "ERROR: --model-path is required." >&2
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

require_var REMOTE_MNN_PYTHON
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

if [[ "$VARIANT" == "baseline" ]]; then
  require_var REMOTE_SNR_BASELINE
  REAL_SNR="$REMOTE_SNR_BASELINE"
else
  require_var REMOTE_SNR_CURRENT
  REAL_SNR="$REMOTE_SNR_CURRENT"
fi

MNN_EXPECTED_SHA256="${MNN_EXPECTED_SHA256:-}"
MNN_EXTRA_PYTHONPATH="${MNN_EXTRA_PYTHONPATH:-${REMOTE_TORCH_PYTHONPATH:-${REMOTE_REAL_EXTRA_PYTHONPATH:-}}}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-mnn_reconstruction_${VARIANT}}"
REAL_OUTPUT_DIR="$REMOTE_OUTPUT_BASE/$OUTPUT_PREFIX"
INTERPRETER_COUNT="${INTERPRETER_COUNT:-${MNN_INTERPRETER_COUNT:-1}}"
SESSION_THREADS="${SESSION_THREADS:-${MNN_SESSION_THREADS:-1}}"
PRECISION="${PRECISION:-${MNN_PRECISION:-normal}}"
SHAPE_MODE="${SHAPE_MODE:-${MNN_SHAPE_MODE:-dynamic}}"
WARMUP_INPUTS="${WARMUP_INPUTS:-${MNN_WARMUP_INPUTS:-0}}"
TUNE_NUM="${TUNE_NUM:-${MNN_TUNE_NUM:-20}}"
MOCK_INFER_MS="${MOCK_INFER_MS:-${MNN_MOCK_INFER_MS:-15}}"

if [[ -n "$MAX_INPUTS" ]] && ! [[ "$MAX_INPUTS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-inputs must be a non-negative integer (got: $MAX_INPUTS)." >&2
  exit 1
fi

run_remote_reconstruction() {
  local runner_script
  local rc=0
  runner_script="$(mktemp)"
  {
    cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
    declare -p REMOTE_MNN_PYTHON REAL_INPUT_DIR REAL_OUTPUT_DIR REAL_SNR VARIANT MODEL_PATH MNN_EXPECTED_SHA256 MNN_EXTRA_PYTHONPATH MAX_INPUTS SEED INTERPRETER_COUNT SESSION_THREADS PRECISION SHAPE_MODE BUCKET_SHAPES WARMUP_INPUTS AUTO_BACKEND TUNE_NUM DRY_RUN MOCK_INFER_MS INPUT_SOURCE_MODE INPUT_SOURCE_LABEL
    cat <<'SH'

remote_python="$REMOTE_MNN_PYTHON"
input_dir="$REAL_INPUT_DIR"
output_dir="$REAL_OUTPUT_DIR"
snr="$REAL_SNR"
variant="$VARIANT"
model_path="$MODEL_PATH"
expected_sha256="$MNN_EXPECTED_SHA256"
extra_pythonpath="$MNN_EXTRA_PYTHONPATH"
max_inputs="$MAX_INPUTS"
seed="$SEED"
interpreter_count="$INTERPRETER_COUNT"
session_threads="$SESSION_THREADS"
precision="$PRECISION"
shape_mode="$SHAPE_MODE"
bucket_shapes="$BUCKET_SHAPES"
warmup_inputs="$WARMUP_INPUTS"
auto_backend="$AUTO_BACKEND"
tune_num="$TUNE_NUM"
dry_run="$DRY_RUN"
mock_infer_ms="$MOCK_INFER_MS"
input_source_mode="$INPUT_SOURCE_MODE"
input_source_label="$INPUT_SOURCE_LABEL"

mkdir -p "$output_dir"
rm -rf "$output_dir/reconstructions"

if [[ -n "$extra_pythonpath" ]]; then
  export PYTHONPATH="$extra_pythonpath${PYTHONPATH:+:$PYTHONPATH}"
  export MNN_EXTRA_PYTHONPATH="$extra_pythonpath"
  export REMOTE_REAL_EXTRA_PYTHONPATH="$extra_pythonpath"
  export REMOTE_TORCH_PYTHONPATH="$extra_pythonpath"
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

extra_args=()
if [[ -n "$max_inputs" ]]; then
  extra_args+=(--max-inputs "$max_inputs")
fi
if [[ -n "$seed" ]]; then
  extra_args+=(--seed "$seed")
fi
if [[ -n "$bucket_shapes" ]]; then
  extra_args+=(--bucket-shapes "$bucket_shapes")
fi
if [[ -n "$warmup_inputs" ]]; then
  extra_args+=(--warmup-inputs "$warmup_inputs")
fi
if [[ "$auto_backend" == "1" ]]; then
  extra_args+=(--auto-backend --tune-num "$tune_num")
fi
if [[ "$dry_run" == "1" ]]; then
  extra_args+=(--dry-run --mock-infer-ms "$mock_infer_ms")
fi

echo "[mnn-remote] variant=$variant model=$model_path output_dir=$output_dir snr=$snr python=$remote_python interpreters=$interpreter_count threads=$session_threads precision=$precision shape_mode=$shape_mode input_source=$input_source_mode input_dir=$input_dir"

run_remote_python - \
  --model-path "$model_path" \
  --input-dir "$input_dir" \
  --output-dir "$output_dir" \
  --snr "$snr" \
  --variant "$variant" \
  --expected-sha256 "$expected_sha256" \
  --interpreter-count "$interpreter_count" \
  --session-threads "$session_threads" \
  --precision "$precision" \
  --shape-mode "$shape_mode" \
  --input-source-mode "$input_source_mode" \
  --input-source-label "$input_source_label" \
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

run_remote_reconstruction
