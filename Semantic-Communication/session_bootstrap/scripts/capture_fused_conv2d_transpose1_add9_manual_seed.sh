#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

OPERATOR_NAME="fused_conv2d_transpose1_add9"
DEFAULT_SCAFFOLD_DIR="$SESSION_DIR/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold"
DEFAULT_REBUILD_ENV="$DEFAULT_SCAFFOLD_DIR/manual_hook_overlay.env"
DEFAULT_OUTPUT_DIR="./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_seed_capture"

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/capture_fused_conv2d_transpose1_add9_manual_seed.sh [options]

Purpose:
  Run the existing local rebuild path just far enough to capture a manual seed for
  ${OPERATOR_NAME} via rpc_tune.py's handwritten hook, without any remote upload
  or inference work.

Options:
  --scaffold-dir <path>           Existing scaffold directory. Defaults to:
                                  $DEFAULT_SCAFFOLD_DIR
  --rebuild-env <path>            Hook overlay env to source. Defaults to:
                                  $DEFAULT_REBUILD_ENV
  --output-dir <path>             Local rpc_tune.py output dir. Defaults to:
                                  $DEFAULT_OUTPUT_DIR
  --allow-existing-output         Reuse an existing output dir.
  --help                          Show this message.

Notes:
  - This helper forces --runner local and --total-trials 0.
  - It always narrows --op-names to ${OPERATOR_NAME}.
  - It never uploads optimized_model.so and never starts a remote job.
EOF
}

SCAFFOLD_DIR="$DEFAULT_SCAFFOLD_DIR"
REBUILD_ENV="$DEFAULT_REBUILD_ENV"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
ALLOW_EXISTING_OUTPUT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scaffold-dir)
      SCAFFOLD_DIR="${2:-}"
      shift 2
      ;;
    --rebuild-env)
      REBUILD_ENV="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --allow-existing-output)
      ALLOW_EXISTING_OUTPUT=1
      shift
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

resolve_path() {
  local maybe_relative="$1"
  if [[ -z "$maybe_relative" ]]; then
    printf '%s\n' ""
  elif [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

require_dir() {
  local path="$1"
  local label="$2"
  if [[ ! -d "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

require_non_empty() {
  local value="$1"
  local label="$2"
  if [[ -z "$value" ]]; then
    echo "ERROR: Missing required value: $label" >&2
    exit 1
  fi
}

cd "$PROJECT_DIR"

SCAFFOLD_DIR="$(resolve_path "$SCAFFOLD_DIR")"
REBUILD_ENV="$(resolve_path "$REBUILD_ENV")"
OUTPUT_DIR="$(resolve_path "$OUTPUT_DIR")"

require_dir "$SCAFFOLD_DIR" "scaffold dir"
require_file "$REBUILD_ENV" "rebuild env"

if [[ "$ALLOW_EXISTING_OUTPUT" -ne 1 ]] && [[ -e "$OUTPUT_DIR/tune_report.json" ]]; then
  echo "ERROR: output dir already contains a tune report: $OUTPUT_DIR" >&2
  echo "       Re-run with --allow-existing-output or choose a new --output-dir." >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$REBUILD_ENV"
set +a

LOCAL_TVM_PYTHON="${LOCAL_TVM_PYTHON:-${TVM_PYTHON:-}}"
ONNX_PATH="$(resolve_path "${ONNX_MODEL_PATH:-}")"
EXISTING_DB="$(resolve_path "${TUNE_EXISTING_DB:-}")"
INPUT_SHAPE="${TUNE_INPUT_SHAPE:-}"
INPUT_NAME="${TUNE_INPUT_NAME:-input}"
INPUT_DTYPE="${TUNE_INPUT_DTYPE:-float32}"
TARGET_JSON="${TARGET:-}"
TRACKER_HOST="${RPC_TRACKER_HOST:-127.0.0.1}"
TRACKER_PORT="${RPC_TRACKER_PORT:-9190}"
DEVICE_KEY="${DEVICE_KEY:-armv8}"
SESSION_TIMEOUT="${TUNE_SESSION_TIMEOUT:-120}"
NUM_TRIALS_PER_ITER="${TUNE_NUM_TRIALS_PER_ITER:-64}"
MAX_TRIALS_PER_TASK="${TUNE_MAX_TRIALS_PER_TASK:-}"
HANDWRITTEN_IMPL_PATH="$(resolve_path "${TVM_HANDWRITTEN_IMPL_PATH:-}")"

require_non_empty "$LOCAL_TVM_PYTHON" "LOCAL_TVM_PYTHON/TVM_PYTHON"
require_non_empty "$ONNX_PATH" "ONNX_MODEL_PATH"
require_non_empty "$EXISTING_DB" "TUNE_EXISTING_DB"
require_non_empty "$INPUT_SHAPE" "TUNE_INPUT_SHAPE"
require_non_empty "$TARGET_JSON" "TARGET"
require_non_empty "$HANDWRITTEN_IMPL_PATH" "TVM_HANDWRITTEN_IMPL_PATH"

if [[ ! -x "$LOCAL_TVM_PYTHON" ]]; then
  echo "ERROR: local builder python is not executable: $LOCAL_TVM_PYTHON" >&2
  exit 1
fi

require_file "$ONNX_PATH" "ONNX model"
require_dir "$EXISTING_DB" "existing tuning DB"
require_file "$HANDWRITTEN_IMPL_PATH" "manual implementation seed module"

mkdir -p "$OUTPUT_DIR"

TUNE_CMD=(
  "$LOCAL_TVM_PYTHON" "$SCRIPT_DIR/rpc_tune.py"
  --onnx-path "$ONNX_PATH"
  --output-dir "$OUTPUT_DIR"
  --target "$TARGET_JSON"
  --tracker-host "$TRACKER_HOST"
  --tracker-port "$TRACKER_PORT"
  --device-key "$DEVICE_KEY"
  --total-trials 0
  --input-shape "$INPUT_SHAPE"
  --input-name "$INPUT_NAME"
  --input-dtype "$INPUT_DTYPE"
  --runner local
  --session-timeout "$SESSION_TIMEOUT"
  --num-trials-per-iter "$NUM_TRIALS_PER_ITER"
  --existing-db "$EXISTING_DB"
  --op-names "$OPERATOR_NAME"
)

if [[ -n "$MAX_TRIALS_PER_TASK" ]]; then
  TUNE_CMD+=(--max-trials-per-task "$MAX_TRIALS_PER_TASK")
fi

printf '[manual-seed] scaffold_dir=%s\n' "$SCAFFOLD_DIR"
printf '[manual-seed] rebuild_env=%s\n' "$REBUILD_ENV"
printf '[manual-seed] output_dir=%s\n' "$OUTPUT_DIR"
printf '[manual-seed] impl_path=%s\n' "$HANDWRITTEN_IMPL_PATH"
printf '[manual-seed] operator=%s\n' "$OPERATOR_NAME"
printf '[manual-seed] mode=local_rebuild_only\n'

"${TUNE_CMD[@]}"

TUNE_REPORT_PATH="$OUTPUT_DIR/tune_report.json"
require_file "$TUNE_REPORT_PATH" "tune report"

python3 - "$TUNE_REPORT_PATH" <<'PY'
import json
import sys

report_path = sys.argv[1]
with open(report_path, "r", encoding="utf-8") as infile:
    report = json.load(infile)

hook = report.get("handwritten_hook") or {}
metadata = hook.get("metadata") or {}
print(f"[manual-seed] handwritten_hook_status={hook.get('status', 'NA')}")
print(f"[manual-seed] manual_impl={hook.get('impl_path', 'NA')}")
print(f"[manual-seed] seed_json={metadata.get('seed_json', 'NA')}")
print(f"[manual-seed] seed_tir={metadata.get('seed_tir', 'NA')}")
print(f"[manual-seed] local_artifact={report.get('output_so', 'NA')}")
print(f"[manual-seed] task_summary={report.get('task_summary_json', 'NA')}")
PY
