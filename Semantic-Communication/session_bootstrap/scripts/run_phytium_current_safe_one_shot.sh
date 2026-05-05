#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

DEFAULT_REBUILD_ENV="$SESSION_DIR/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
DEFAULT_INFERENCE_ENV="$SESSION_DIR/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
RECOMMENDED_TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
DEFAULT_REPEAT=10
DEFAULT_WARMUP_RUNS=2
DEFAULT_ENTRY=main
DEFAULT_TUNE_RUNNER=local
DEFAULT_REPORT_PREFIX="phytium_current_safe_one_shot"
DEFAULT_REPORT_TITLE="Phytium Pi baseline-seeded current-safe one-shot summary"
DEFAULT_START_LABEL="Phytium baseline-seeded current-safe one-shot started"
DEFAULT_COMPLETE_LABEL="Phytium baseline-seeded current-safe one-shot complete."
DEFAULT_INFERENCE_SECTION_TITLE="Safe Runtime Inference"
DEFAULT_INFERENCE_RUNTIME_LABEL="TVM 0.24.dev0 safe path only"
DEFAULT_MODE_LOG_DESCRIPTION="baseline-seeded warm-start current + safe runtime"
DEFAULT_REBUILD_MODE_DESCRIPTION="baseline-seeded warm-start current rebuild-only + safe runtime"
DEFAULT_INCREMENTAL_MODE_DESCRIPTION="baseline-seeded warm-start current incremental tuning + safe runtime"

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh [options]

Purpose:
  Reproduce the validated baseline-seeded current + safe-runtime path for Phytium Pi:
    1) rebuild current artifact locally from the existing tuning DB
    2) upload optimized_model.so into the remote current archive
    3) run the real safe-runtime inference payload on the Pi
    4) save a concise summary with the important numbers

Defaults:
  rebuild env   : $DEFAULT_REBUILD_ENV
  inference env : $DEFAULT_INFERENCE_ENV
  target        : $RECOMMENDED_TARGET
  warmup/repeat : ${DEFAULT_WARMUP_RUNS}/${DEFAULT_REPEAT}

Options:
  --rebuild-env <path>        Override rebuild env file.
  --inference-env <path>      Override safe-runtime inference env file.
  --target <json>             Override the current-safe target JSON.
  --output-dir <path>         Override local output dir for rebuilt artifact.
  --remote-archive-dir <dir>  Override remote current archive dir.
  --report-id <id>            Override report/log prefix.
  --repeat <n>                Override inference repeat count.
  --warmup-runs <n>           Override inference warmup count.
  --entry <name>              Override Relax VM entry name (default: ${DEFAULT_ENTRY}).
  --total-trials <n>          Override MetaSchedule trial budget (default comes from env; one-shot env uses 0).
  --runner <local|rpc>        Override tuning runner (default comes from env; one-shot env uses ${DEFAULT_TUNE_RUNNER}).
  --upload-db                 Also upload the resulting tuning_logs DB into the remote current archive.
  --help                      Show this message.

Notes:
  - This script is explicit about the baseline-seeded current + safe runtime path only.
  - It does not touch baseline/compat execution paths.
  - It reuses the existing DB with --total-trials 0 via rpc_tune.py.
  - Treat it as a rebuild-only warm-start current baseline, not as an independent fresh search line.
  - For a real nonzero-budget warm-start round, use the dedicated baseline-seeded incremental wrapper.
EOF
}

REBUILD_ENV="$DEFAULT_REBUILD_ENV"
INFERENCE_ENV="$DEFAULT_INFERENCE_ENV"
OUTPUT_DIR_OVERRIDE=""
REMOTE_ARCHIVE_DIR_OVERRIDE=""
REPORT_ID_OVERRIDE=""
REPEAT_OVERRIDE=""
WARMUP_OVERRIDE=""
ENTRY_OVERRIDE=""
TARGET_OVERRIDE=""
TOTAL_TRIALS_OVERRIDE=""
RUNNER_OVERRIDE=""
UPLOAD_DB_FLAG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild-env)
      REBUILD_ENV="${2:-}"
      shift 2
      ;;
    --inference-env)
      INFERENCE_ENV="${2:-}"
      shift 2
      ;;
    --target)
      TARGET_OVERRIDE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --remote-archive-dir)
      REMOTE_ARCHIVE_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --report-id)
      REPORT_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --repeat)
      REPEAT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --warmup-runs)
      WARMUP_OVERRIDE="${2:-}"
      shift 2
      ;;
    --entry)
      ENTRY_OVERRIDE="${2:-}"
      shift 2
      ;;
    --total-trials)
      TOTAL_TRIALS_OVERRIDE="${2:-}"
      shift 2
      ;;
    --runner)
      RUNNER_OVERRIDE="${2:-}"
      shift 2
      ;;
    --upload-db)
      UPLOAD_DB_FLAG=1
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

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
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

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

assert_same_or_empty() {
  local left="$1"
  local right="$2"
  local label="$3"
  if [[ -n "$left" && -n "$right" && "$left" != "$right" ]]; then
    echo "ERROR: ${label} mismatch between rebuild/inference envs." >&2
    exit 1
  fi
}

extract_last_json_line() {
  python3 - "$1" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, 'r', encoding='utf-8', errors='replace') as infile:
    lines = [line.strip() for line in infile if line.strip()]
for line in reversed(lines):
    try:
        obj = json.loads(line)
    except Exception:
        continue
    print(json.dumps(obj, ensure_ascii=False))
    raise SystemExit(0)
raise SystemExit(1)
PY
}

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
field = sys.argv[2]
value = payload.get(field)
if isinstance(value, list):
    print(json.dumps(value, ensure_ascii=False))
elif value is None:
    print("NA")
else:
    print(value)
PY
}

normalize_target_json() {
  python3 - "$1" <<'PY'
import json
import sys

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception as err:
    print(f"ERROR: invalid target JSON: {err}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(payload, dict):
    print("ERROR: target must be a JSON object.", file=sys.stderr)
    raise SystemExit(1)

print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
PY
}

run_with_optional_timeout() {
  local timeout_sec="$1"
  shift

  if [[ "$timeout_sec" =~ ^[0-9]+$ ]] && [[ "$timeout_sec" -gt 0 ]] && command -v timeout >/dev/null 2>&1; then
    timeout "$timeout_sec" "$@"
  else
    "$@"
  fi
}

require_command python3
require_command sha256sum
require_command stat

require_file "$REBUILD_ENV" "rebuild env"
require_file "$INFERENCE_ENV" "inference env"

set -a
# shellcheck source=/dev/null
source "$REBUILD_ENV"
set +a

BUILD_MODEL_NAME="${MODEL_NAME:-jscc}"
BUILD_TARGET_FROM_ENV="${TARGET:-}"
BUILD_LOCAL_TVM_PYTHON="${LOCAL_TVM_PYTHON:-${TVM_PYTHON:-}}"
BUILD_ONNX_PATH="$(resolve_path "${ONNX_MODEL_PATH:-}")"
BUILD_EXISTING_DB="$(resolve_path "${TUNE_EXISTING_DB:-}")"
BUILD_INPUT_SHAPE="${TUNE_INPUT_SHAPE:-}"
BUILD_INPUT_NAME="${TUNE_INPUT_NAME:-input}"
BUILD_INPUT_DTYPE="${TUNE_INPUT_DTYPE:-float32}"
BUILD_TOTAL_TRIALS="${TOTAL_TRIALS_OVERRIDE:-${TUNE_TOTAL_TRIALS:-0}}"
BUILD_NUM_TRIALS_PER_ITER="${TUNE_NUM_TRIALS_PER_ITER:-64}"
BUILD_MAX_TRIALS_PER_TASK="${TUNE_MAX_TRIALS_PER_TASK:-}"
BUILD_OP_NAMES="${TUNE_OP_NAMES:-${FULL_HOTSPOT_TASKS:-}}"
BUILD_RUNNER="${RUNNER_OVERRIDE:-${TUNE_RUNNER:-$DEFAULT_TUNE_RUNNER}}"
BUILD_SESSION_TIMEOUT="${TUNE_SESSION_TIMEOUT:-120}"
BUILD_TIMEOUT_SEC="${TUNE_TIMEOUT_SEC:-7200}"
BUILD_TRACKER_HOST="${RPC_TRACKER_HOST:-127.0.0.1}"
BUILD_TRACKER_PORT="${RPC_TRACKER_PORT:-9190}"
BUILD_DEVICE_KEY="${DEVICE_KEY:-armv8}"
BUILD_REMOTE_HOST="${REMOTE_HOST:-}"
BUILD_REMOTE_USER="${REMOTE_USER:-}"
BUILD_REMOTE_PASS="${REMOTE_PASS:-}"
BUILD_REMOTE_PORT="${REMOTE_SSH_PORT:-22}"
BUILD_REMOTE_ARCHIVE_DIR="${REMOTE_TVM_JSCC_BASE_DIR:-}"
BUILD_LOG_DIR="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
BUILD_REPORT_DIR="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

set -a
# shellcheck source=/dev/null
source "$INFERENCE_ENV"
set +a

SAFE_REMOTE_MODE="${REMOTE_MODE:-ssh}"
SAFE_REMOTE_HOST="${REMOTE_HOST:-}"
SAFE_REMOTE_USER="${REMOTE_USER:-}"
SAFE_REMOTE_PASS="${REMOTE_PASS:-}"
SAFE_REMOTE_PORT="${REMOTE_SSH_PORT:-22}"
SAFE_REMOTE_TVM_PYTHON="${REMOTE_TVM_PYTHON:-}"
SAFE_REMOTE_ARCHIVE_DIR="${INFERENCE_CURRENT_ARCHIVE:-${REMOTE_TVM_JSCC_BASE_DIR:-}}"
SAFE_INPUT_SHAPE="${TUNE_INPUT_SHAPE:-}"
SAFE_INPUT_DTYPE="${TUNE_INPUT_DTYPE:-}"
SAFE_TIMEOUT_SEC="${INFERENCE_TIMEOUT_SEC:-3600}"
SAFE_ENTRY="${ENTRY_OVERRIDE:-$DEFAULT_ENTRY}"
SAFE_REPEAT="${REPEAT_OVERRIDE:-$DEFAULT_REPEAT}"
SAFE_WARMUP_RUNS="${WARMUP_OVERRIDE:-$DEFAULT_WARMUP_RUNS}"
SAFE_DEVICE="${INFERENCE_DEVICE:-cpu}"
BUILD_TARGET_NORMALIZED=""
REPORT_PREFIX="${PHYTIUM_ONE_SHOT_REPORT_PREFIX:-$DEFAULT_REPORT_PREFIX}"
REPORT_TITLE="${PHYTIUM_ONE_SHOT_REPORT_TITLE:-$DEFAULT_REPORT_TITLE}"
START_LABEL="${PHYTIUM_ONE_SHOT_START_LABEL:-$DEFAULT_START_LABEL}"
COMPLETE_LABEL="${PHYTIUM_ONE_SHOT_COMPLETE_LABEL:-$DEFAULT_COMPLETE_LABEL}"
INFERENCE_SECTION_TITLE="${PHYTIUM_ONE_SHOT_INFERENCE_SECTION_TITLE:-$DEFAULT_INFERENCE_SECTION_TITLE}"
INFERENCE_RUNTIME_LABEL="${PHYTIUM_ONE_SHOT_INFERENCE_RUNTIME_LABEL:-$DEFAULT_INFERENCE_RUNTIME_LABEL}"
MODE_LOG_DESCRIPTION="${PHYTIUM_ONE_SHOT_MODE_LOG_DESCRIPTION:-$DEFAULT_MODE_LOG_DESCRIPTION}"
REBUILD_MODE_DESCRIPTION="${PHYTIUM_ONE_SHOT_MODE_REBUILD_DESCRIPTION:-$DEFAULT_REBUILD_MODE_DESCRIPTION}"
INCREMENTAL_MODE_DESCRIPTION="${PHYTIUM_ONE_SHOT_MODE_INCREMENTAL_DESCRIPTION:-$DEFAULT_INCREMENTAL_MODE_DESCRIPTION}"

if [[ -n "$BUILD_TARGET_FROM_ENV" ]]; then
  BUILD_TARGET_NORMALIZED="$(normalize_target_json "$BUILD_TARGET_FROM_ENV")"
fi

CURRENT_SAFE_TARGET="${TARGET_OVERRIDE:-$RECOMMENDED_TARGET}"
CURRENT_SAFE_TARGET="$(normalize_target_json "$CURRENT_SAFE_TARGET")"

require_non_empty "$BUILD_LOCAL_TVM_PYTHON" "LOCAL_TVM_PYTHON/TVM_PYTHON"
require_non_empty "$BUILD_ONNX_PATH" "ONNX_MODEL_PATH"
require_non_empty "$BUILD_EXISTING_DB" "TUNE_EXISTING_DB"
require_non_empty "$BUILD_INPUT_SHAPE" "TUNE_INPUT_SHAPE"
require_non_empty "$BUILD_INPUT_DTYPE" "TUNE_INPUT_DTYPE"
require_non_empty "$SAFE_REMOTE_TVM_PYTHON" "REMOTE_TVM_PYTHON in inference env"

if [[ ! -x "$BUILD_LOCAL_TVM_PYTHON" ]]; then
  echo "ERROR: local builder python is not executable: $BUILD_LOCAL_TVM_PYTHON" >&2
  exit 1
fi

if [[ ! -f "$BUILD_ONNX_PATH" ]]; then
  echo "ERROR: ONNX model not found: $BUILD_ONNX_PATH" >&2
  exit 1
fi

if [[ ! -d "$BUILD_EXISTING_DB" ]]; then
  echo "ERROR: existing DB dir not found: $BUILD_EXISTING_DB" >&2
  exit 1
fi

for db_file in database_workload.json database_tuning_record.json; do
  if [[ ! -f "$BUILD_EXISTING_DB/$db_file" ]]; then
    echo "ERROR: existing DB missing: $BUILD_EXISTING_DB/$db_file" >&2
    exit 1
  fi
done

if [[ "$SAFE_REMOTE_MODE" != "ssh" ]]; then
  echo "ERROR: This one-shot path is for the Phytium Pi over SSH only (REMOTE_MODE=ssh expected)." >&2
  exit 1
fi

assert_same_or_empty "$BUILD_REMOTE_HOST" "$SAFE_REMOTE_HOST" "REMOTE_HOST"
assert_same_or_empty "$BUILD_REMOTE_USER" "$SAFE_REMOTE_USER" "REMOTE_USER"
assert_same_or_empty "$BUILD_REMOTE_PASS" "$SAFE_REMOTE_PASS" "REMOTE_PASS"
assert_same_or_empty "$BUILD_REMOTE_PORT" "$SAFE_REMOTE_PORT" "REMOTE_SSH_PORT"
assert_same_or_empty "$BUILD_REMOTE_ARCHIVE_DIR" "$SAFE_REMOTE_ARCHIVE_DIR" "remote current archive dir"
assert_same_or_empty "$BUILD_INPUT_SHAPE" "$SAFE_INPUT_SHAPE" "TUNE_INPUT_SHAPE"
assert_same_or_empty "$BUILD_INPUT_DTYPE" "$SAFE_INPUT_DTYPE" "TUNE_INPUT_DTYPE"

REMOTE_HOST_VAL="${SAFE_REMOTE_HOST:-$BUILD_REMOTE_HOST}"
REMOTE_USER_VAL="${SAFE_REMOTE_USER:-$BUILD_REMOTE_USER}"
REMOTE_PASS_VAL="${SAFE_REMOTE_PASS:-$BUILD_REMOTE_PASS}"
REMOTE_PORT_VAL="${SAFE_REMOTE_PORT:-$BUILD_REMOTE_PORT}"
REMOTE_ARCHIVE_DIR_VAL="${REMOTE_ARCHIVE_DIR_OVERRIDE:-${SAFE_REMOTE_ARCHIVE_DIR:-$BUILD_REMOTE_ARCHIVE_DIR}}"

require_non_empty "$REMOTE_HOST_VAL" "REMOTE_HOST"
require_non_empty "$REMOTE_USER_VAL" "REMOTE_USER"
require_non_empty "$REMOTE_PASS_VAL" "REMOTE_PASS"
require_non_empty "$REMOTE_ARCHIVE_DIR_VAL" "remote current archive dir"

if ! [[ "$SAFE_REPEAT" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --repeat must be a non-negative integer." >&2
  exit 1
fi
if ! [[ "$SAFE_WARMUP_RUNS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --warmup-runs must be a non-negative integer." >&2
  exit 1
fi
if ! [[ "$BUILD_TOTAL_TRIALS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --total-trials must be a non-negative integer." >&2
  exit 1
fi
if [[ "$BUILD_RUNNER" != "local" && "$BUILD_RUNNER" != "rpc" ]]; then
  echo "ERROR: --runner must be one of: local, rpc." >&2
  exit 1
fi

if [[ -n "$TARGET_OVERRIDE" ]]; then
  echo "INFO: using explicit current-safe target override: $CURRENT_SAFE_TARGET" >&2
elif [[ -n "$BUILD_TARGET_NORMALIZED" && "$BUILD_TARGET_NORMALIZED" != "$RECOMMENDED_TARGET" ]]; then
  echo "INFO: rebuild env target differs from the validated stable current-safe target; the one-shot script will use the stable default. Pass --target for other current-safe comparisons." >&2
fi

mkdir -p "$BUILD_LOG_DIR" "$BUILD_REPORT_DIR" "$SESSION_DIR/tmp"

STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_ID="${REPORT_ID_OVERRIDE:-${REPORT_PREFIX}_${STAMP}}"
OUTPUT_DIR_VAL="$(resolve_path "${OUTPUT_DIR_OVERRIDE:-./session_bootstrap/tmp/${REPORT_ID}}")"
LOG_FILE="$BUILD_LOG_DIR/${REPORT_ID}.log"
REMOTE_PAYLOAD_LOG="$BUILD_LOG_DIR/${REPORT_ID}_remote_payload.log"
SUMMARY_JSON="$BUILD_REPORT_DIR/${REPORT_ID}.json"
SUMMARY_MD="$BUILD_REPORT_DIR/${REPORT_ID}.md"
LOCAL_SO_PATH="$OUTPUT_DIR_VAL/optimized_model.so"
TUNE_REPORT_PATH="$OUTPUT_DIR_VAL/tune_report.json"
LOCAL_DB_DIR="$OUTPUT_DIR_VAL/tuning_logs"
REMOTE_SO_PATH="$REMOTE_ARCHIVE_DIR_VAL/tvm_tune_logs/optimized_model.so"
REMOTE_DB_DIR="$REMOTE_ARCHIVE_DIR_VAL/tuning_logs"
REMOTE_DB_WORKLOAD_PATH="$REMOTE_DB_DIR/database_workload.json"
REMOTE_DB_TUNING_RECORD_PATH="$REMOTE_DB_DIR/database_tuning_record.json"
SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"

mkdir -p "$OUTPUT_DIR_VAL"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$1" | tee -a "$LOG_FILE"
}

upload_remote_file() {
  local src_path="$1"
  local dst_path="$2"
  local step_label="$3"

  if ! bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST_VAL" \
    --user "$REMOTE_USER_VAL" \
    --pass "$REMOTE_PASS_VAL" \
    --port "$REMOTE_PORT_VAL" \
    -- \
    "mkdir -p $(shell_quote "$(dirname "$dst_path")") && cat > $(shell_quote "$dst_path")" \
    <"$src_path" >>"$LOG_FILE" 2>&1; then
    log "step=${step_label} failed"
    exit 1
  fi
}

log "$START_LABEL"
log "mode=$MODE_LOG_DESCRIPTION"
log "rebuild_env=$REBUILD_ENV"
log "inference_env=$INFERENCE_ENV"
log "target=$CURRENT_SAFE_TARGET"
log "report_id=$REPORT_ID"
log "output_dir=$OUTPUT_DIR_VAL"
log "remote_archive_dir=$REMOTE_ARCHIVE_DIR_VAL"
log "requested_total_trials=$BUILD_TOTAL_TRIALS"
log "requested_runner=$BUILD_RUNNER"

LOCAL_TVM_VERSION="$($BUILD_LOCAL_TVM_PYTHON - <<'PY'
import tvm
print(tvm.__version__)
PY
)"
log "local_tvm_version=$LOCAL_TVM_VERSION"

TUNE_CMD=(
  "$BUILD_LOCAL_TVM_PYTHON" "$SCRIPT_DIR/rpc_tune.py"
  --onnx-path "$BUILD_ONNX_PATH"
  --output-dir "$OUTPUT_DIR_VAL"
  --target "$CURRENT_SAFE_TARGET"
  --tracker-host "$BUILD_TRACKER_HOST"
  --tracker-port "$BUILD_TRACKER_PORT"
  --device-key "$BUILD_DEVICE_KEY"
  --total-trials "$BUILD_TOTAL_TRIALS"
  --input-shape "$BUILD_INPUT_SHAPE"
  --input-name "$BUILD_INPUT_NAME"
  --input-dtype "$BUILD_INPUT_DTYPE"
  --runner "$BUILD_RUNNER"
  --session-timeout "$BUILD_SESSION_TIMEOUT"
  --num-trials-per-iter "$BUILD_NUM_TRIALS_PER_ITER"
  --existing-db "$BUILD_EXISTING_DB"
)

if [[ -n "$BUILD_MAX_TRIALS_PER_TASK" ]]; then
  TUNE_CMD+=(--max-trials-per-task "$BUILD_MAX_TRIALS_PER_TASK")
fi

if [[ -n "$BUILD_OP_NAMES" ]]; then
  TUNE_CMD+=(--op-names "$BUILD_OP_NAMES")
fi

log "step=rebuild_current_safe start"
set +e
run_with_optional_timeout "$BUILD_TIMEOUT_SEC" "${TUNE_CMD[@]}" 2>&1 | tee -a "$LOG_FILE"
REBUILD_RC=${PIPESTATUS[0]}
set -e
if [[ "$REBUILD_RC" -ne 0 ]]; then
  log "step=rebuild_current_safe failed rc=$REBUILD_RC"
  exit "$REBUILD_RC"
fi
log "step=rebuild_current_safe success"

if [[ ! -f "$LOCAL_SO_PATH" ]]; then
  echo "ERROR: rebuilt artifact not found: $LOCAL_SO_PATH" >&2
  exit 1
fi
if [[ ! -f "$TUNE_REPORT_PATH" ]]; then
  echo "ERROR: tune report not found: $TUNE_REPORT_PATH" >&2
  exit 1
fi

BUILD_ELAPSED_SEC="$(python3 - "$TUNE_REPORT_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], 'r', encoding='utf-8') as infile:
    report = json.load(infile)
print(report.get('elapsed_sec', 'NA'))
PY
)"
readarray -t TUNE_REPORT_META < <(python3 - "$TUNE_REPORT_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as infile:
    report = json.load(infile)

for key in ("total_trials", "runner", "tuning_logs_dir", "task_summary_json"):
    value = report.get(key, "NA")
    if value in (None, ""):
        value = "NA"
    print(value)
PY
)
TUNE_TOTAL_TRIALS="${TUNE_REPORT_META[0]:-NA}"
TUNE_RUNNER="${TUNE_REPORT_META[1]:-NA}"
TUNE_LOGS_DIR="${TUNE_REPORT_META[2]:-NA}"
TASK_SUMMARY_PATH="${TUNE_REPORT_META[3]:-NA}"
BUILD_SEARCH_MODE="baseline_seeded_rebuild_only"
if [[ "$TUNE_TOTAL_TRIALS" =~ ^[0-9]+$ ]] && [[ "$TUNE_TOTAL_TRIALS" -gt 0 ]]; then
  BUILD_SEARCH_MODE="baseline_seeded_warm_start_incremental"
fi
BUILD_MODE_DESCRIPTION="$REBUILD_MODE_DESCRIPTION"
if [[ "$BUILD_SEARCH_MODE" == "baseline_seeded_warm_start_incremental" ]]; then
  BUILD_MODE_DESCRIPTION="$INCREMENTAL_MODE_DESCRIPTION"
fi
LOCAL_SO_SHA256="$(sha256sum "$LOCAL_SO_PATH" | awk '{print $1}')"
LOCAL_SO_SIZE_BYTES="$(stat -c '%s' "$LOCAL_SO_PATH")"
log "local_so=$LOCAL_SO_PATH"
log "local_so_sha256=$LOCAL_SO_SHA256"
log "local_so_size_bytes=$LOCAL_SO_SIZE_BYTES"
log "tune_total_trials=$TUNE_TOTAL_TRIALS"
log "tune_runner=$TUNE_RUNNER"
log "build_search_mode=$BUILD_SEARCH_MODE"

log "step=upload_current_safe_so start"
upload_remote_file "$LOCAL_SO_PATH" "$REMOTE_SO_PATH" "upload_current_safe_so"
log "step=upload_current_safe_so success"

REMOTE_DB_UPLOAD_ENABLED=0
if [[ "$UPLOAD_DB_FLAG" -eq 1 ]]; then
  for db_file in database_workload.json database_tuning_record.json; do
    if [[ ! -f "$LOCAL_DB_DIR/$db_file" ]]; then
      echo "ERROR: local tuning DB missing: $LOCAL_DB_DIR/$db_file" >&2
      exit 1
    fi
  done
  log "step=upload_current_safe_db start"
  upload_remote_file "$LOCAL_DB_DIR/database_workload.json" "$REMOTE_DB_WORKLOAD_PATH" "upload_current_safe_db_workload"
  upload_remote_file "$LOCAL_DB_DIR/database_tuning_record.json" "$REMOTE_DB_TUNING_RECORD_PATH" "upload_current_safe_db_tuning_record"
  REMOTE_DB_UPLOAD_ENABLED=1
  log "step=upload_current_safe_db success"
fi

REMOTE_META="$({
  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST_VAL" \
    --user "$REMOTE_USER_VAL" \
    --pass "$REMOTE_PASS_VAL" \
    --port "$REMOTE_PORT_VAL" \
    -- \
    bash -s -- "$REMOTE_SO_PATH" <<'SH'
set -euo pipefail
remote_so="$1"
if [[ ! -f "$remote_so" ]]; then
  echo "ERROR: missing remote artifact: $remote_so" >&2
  exit 1
fi
printf 'sha256=%s\n' "$(sha256sum "$remote_so" | cut -d' ' -f1)"
printf 'size_bytes=%s\n' "$(stat -c '%s' "$remote_so")"
SH
} 2>>"$LOG_FILE")"

REMOTE_SO_SHA256="$(printf '%s\n' "$REMOTE_META" | awk -F= '/^sha256=/{print $2}')"
REMOTE_SO_SIZE_BYTES="$(printf '%s\n' "$REMOTE_META" | awk -F= '/^size_bytes=/{print $2}')"
require_non_empty "$REMOTE_SO_SHA256" "remote optimized_model.so sha256"
require_non_empty "$REMOTE_SO_SIZE_BYTES" "remote optimized_model.so size"

if [[ "$LOCAL_SO_SHA256" != "$REMOTE_SO_SHA256" ]]; then
  echo "ERROR: uploaded artifact hash mismatch: local=$LOCAL_SO_SHA256 remote=$REMOTE_SO_SHA256" >&2
  exit 1
fi

SAFE_EXPECTED_CURRENT_SHA256="$REMOTE_SO_SHA256"
log "remote_so=$REMOTE_SO_PATH"
log "remote_so_sha256=$REMOTE_SO_SHA256"
log "remote_so_size_bytes=$REMOTE_SO_SIZE_BYTES"
log "inference_current_expected_sha256=$SAFE_EXPECTED_CURRENT_SHA256"
log "inference_current_expected_sha256_source=uploaded_remote_artifact"

log "step=run_safe_runtime_inference start"
set +e
(
  export REMOTE_MODE=ssh
  export REMOTE_HOST="$REMOTE_HOST_VAL"
  export REMOTE_USER="$REMOTE_USER_VAL"
  export REMOTE_PASS="$REMOTE_PASS_VAL"
  export REMOTE_SSH_PORT="$REMOTE_PORT_VAL"
  export REMOTE_TVM_PYTHON="$SAFE_REMOTE_TVM_PYTHON"
  export REMOTE_TVM_JSCC_BASE_DIR="$REMOTE_ARCHIVE_DIR_VAL"
  export INFERENCE_CURRENT_ARCHIVE="$REMOTE_ARCHIVE_DIR_VAL"
  export TUNE_INPUT_SHAPE="$BUILD_INPUT_SHAPE"
  export TUNE_INPUT_DTYPE="$BUILD_INPUT_DTYPE"
  export INFERENCE_REPEAT="$SAFE_REPEAT"
  export INFERENCE_WARMUP_RUNS="$SAFE_WARMUP_RUNS"
  export INFERENCE_ENTRY="$SAFE_ENTRY"
  export INFERENCE_DEVICE="$SAFE_DEVICE"
  export INFERENCE_CURRENT_EXPECTED_SHA256="$SAFE_EXPECTED_CURRENT_SHA256"
  run_with_optional_timeout "$SAFE_TIMEOUT_SEC" bash "$SCRIPT_DIR/run_remote_tvm_inference_payload.sh" --variant current
) >"$REMOTE_PAYLOAD_LOG" 2>&1
INFERENCE_RC=$?
set -e
cat "$REMOTE_PAYLOAD_LOG" >>"$LOG_FILE"
if [[ "$INFERENCE_RC" -ne 0 ]]; then
  log "step=run_safe_runtime_inference failed rc=$INFERENCE_RC"
  exit "$INFERENCE_RC"
fi
log "step=run_safe_runtime_inference success"

PAYLOAD_JSON="$(extract_last_json_line "$REMOTE_PAYLOAD_LOG")"

REMOTE_TVM_VERSION="$(json_field "$PAYLOAD_JSON" tvm_version)"
LOAD_MS="$(json_field "$PAYLOAD_JSON" load_ms)"
VM_INIT_MS="$(json_field "$PAYLOAD_JSON" vm_init_ms)"
RUN_COUNT="$(json_field "$PAYLOAD_JSON" run_count)"
RUN_MEDIAN_MS="$(json_field "$PAYLOAD_JSON" run_median_ms)"
RUN_MEAN_MS="$(json_field "$PAYLOAD_JSON" run_mean_ms)"
RUN_MIN_MS="$(json_field "$PAYLOAD_JSON" run_min_ms)"
RUN_MAX_MS="$(json_field "$PAYLOAD_JSON" run_max_ms)"
RUN_VARIANCE_MS2="$(json_field "$PAYLOAD_JSON" run_variance_ms2)"
OUTPUT_SHAPE="$(json_field "$PAYLOAD_JSON" output_shape)"
OUTPUT_DTYPE="$(json_field "$PAYLOAD_JSON" output_dtype)"

export PAYLOAD_JSON
export REPORT_ID
export REBUILD_ENV
export INFERENCE_ENV
export CURRENT_SAFE_TARGET
export BUILD_MODEL_NAME
export BUILD_LOCAL_TVM_PYTHON
export LOCAL_TVM_VERSION
export BUILD_ONNX_PATH
export BUILD_EXISTING_DB
export OUTPUT_DIR_VAL
export TUNE_REPORT_PATH
export TUNE_TOTAL_TRIALS
export TUNE_RUNNER
export TUNE_LOGS_DIR
export TASK_SUMMARY_PATH
export BUILD_SEARCH_MODE
export BUILD_MODE_DESCRIPTION
export LOCAL_SO_PATH
export LOCAL_SO_SHA256
export LOCAL_SO_SIZE_BYTES
export BUILD_ELAPSED_SEC
export REMOTE_HOST_VAL
export REMOTE_ARCHIVE_DIR_VAL
export REMOTE_SO_PATH
export REMOTE_SO_SHA256
export REMOTE_SO_SIZE_BYTES
export REMOTE_DB_UPLOAD_ENABLED
export REMOTE_DB_DIR
export REMOTE_DB_WORKLOAD_PATH
export REMOTE_DB_TUNING_RECORD_PATH
export SAFE_REMOTE_TVM_PYTHON
export REMOTE_TVM_VERSION
export BUILD_INPUT_SHAPE
export BUILD_INPUT_DTYPE
export SAFE_ENTRY
export SAFE_WARMUP_RUNS
export SAFE_REPEAT
export SAFE_DEVICE
export LOG_FILE
export REMOTE_PAYLOAD_LOG
export INFERENCE_RUNTIME_LABEL

python3 - "$SUMMARY_JSON" <<'PY'
import json
import os
import sys

summary_path = sys.argv[1]
payload = json.loads(os.environ["PAYLOAD_JSON"])
summary = {
    "mode": os.environ["BUILD_MODE_DESCRIPTION"],
    "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
    "report_id": os.environ["REPORT_ID"],
    "rebuild_env": os.environ["REBUILD_ENV"],
    "inference_env": os.environ["INFERENCE_ENV"],
    "target": os.environ["CURRENT_SAFE_TARGET"],
    "local_build": {
        "model_name": os.environ["BUILD_MODEL_NAME"],
        "builder_python": os.environ["BUILD_LOCAL_TVM_PYTHON"],
        "tvm_version": os.environ["LOCAL_TVM_VERSION"],
        "onnx_model": os.environ["BUILD_ONNX_PATH"],
        "existing_db": os.environ["BUILD_EXISTING_DB"],
        "output_dir": os.environ["OUTPUT_DIR_VAL"],
        "tune_report": os.environ["TUNE_REPORT_PATH"],
        "tuning_logs_dir": os.environ["TUNE_LOGS_DIR"],
        "task_summary_json": None if os.environ["TASK_SUMMARY_PATH"] == "NA" else os.environ["TASK_SUMMARY_PATH"],
        "total_trials": int(os.environ["TUNE_TOTAL_TRIALS"]) if os.environ["TUNE_TOTAL_TRIALS"].isdigit() else os.environ["TUNE_TOTAL_TRIALS"],
        "runner": os.environ["TUNE_RUNNER"],
        "search_mode": os.environ["BUILD_SEARCH_MODE"],
        "optimized_model_so": os.environ["LOCAL_SO_PATH"],
        "optimized_model_sha256": os.environ["LOCAL_SO_SHA256"],
        "optimized_model_size_bytes": int(os.environ["LOCAL_SO_SIZE_BYTES"]),
        "rebuild_elapsed_sec": os.environ["BUILD_ELAPSED_SEC"],
    },
    "remote_artifact": {
        "host": os.environ["REMOTE_HOST_VAL"],
        "archive_dir": os.environ["REMOTE_ARCHIVE_DIR_VAL"],
        "optimized_model_so": os.environ["REMOTE_SO_PATH"],
        "optimized_model_sha256": os.environ["REMOTE_SO_SHA256"],
        "optimized_model_size_bytes": int(os.environ["REMOTE_SO_SIZE_BYTES"]),
        "hash_match": os.environ["LOCAL_SO_SHA256"] == os.environ["REMOTE_SO_SHA256"],
        "tuning_logs_uploaded": os.environ["REMOTE_DB_UPLOAD_ENABLED"] == "1",
        "tuning_logs_dir": os.environ["REMOTE_DB_DIR"] if os.environ["REMOTE_DB_UPLOAD_ENABLED"] == "1" else None,
        "database_workload_json": os.environ["REMOTE_DB_WORKLOAD_PATH"] if os.environ["REMOTE_DB_UPLOAD_ENABLED"] == "1" else None,
        "database_tuning_record_json": os.environ["REMOTE_DB_TUNING_RECORD_PATH"] if os.environ["REMOTE_DB_UPLOAD_ENABLED"] == "1" else None,
    },
    "safe_runtime_inference": {
        "runtime": os.environ["INFERENCE_RUNTIME_LABEL"],
        "remote_tvm_python": os.environ["SAFE_REMOTE_TVM_PYTHON"],
        "input_shape": os.environ["BUILD_INPUT_SHAPE"],
        "input_dtype": os.environ["BUILD_INPUT_DTYPE"],
        "entry": os.environ["SAFE_ENTRY"],
        "warmup_runs": int(os.environ["SAFE_WARMUP_RUNS"]),
        "repeat": int(os.environ["SAFE_REPEAT"]),
        "device": os.environ["SAFE_DEVICE"],
        "remote_tvm_version": os.environ["REMOTE_TVM_VERSION"],
        "payload": payload,
    },
    "logs": {
        "orchestrator_log": os.environ["LOG_FILE"],
        "remote_payload_log": os.environ["REMOTE_PAYLOAD_LOG"],
    },
}
with open(summary_path, "w", encoding="utf-8") as outfile:
    json.dump(summary, outfile, indent=2, ensure_ascii=False)
PY

cat >"$SUMMARY_MD" <<EOF
# $REPORT_TITLE

- mode: $BUILD_MODE_DESCRIPTION
- generated_at: $(date -Iseconds)
- report_id: $REPORT_ID
- rebuild_env: $REBUILD_ENV
- inference_env: $INFERENCE_ENV

## Build

- target: $CURRENT_SAFE_TARGET
- local_builder_python: $BUILD_LOCAL_TVM_PYTHON
- local_tvm_version: $LOCAL_TVM_VERSION
- onnx_model: $BUILD_ONNX_PATH
- existing_db: $BUILD_EXISTING_DB
- output_dir: $OUTPUT_DIR_VAL
- tune_report: $TUNE_REPORT_PATH
- tuning_logs_dir: $TUNE_LOGS_DIR
- task_summary_json: $TASK_SUMMARY_PATH
- total_trials: $TUNE_TOTAL_TRIALS
- runner: $TUNE_RUNNER
- search_mode: $BUILD_SEARCH_MODE
- optimized_model_so: $LOCAL_SO_PATH
- optimized_model_sha256: $LOCAL_SO_SHA256
- optimized_model_size_bytes: $LOCAL_SO_SIZE_BYTES
- rebuild_elapsed_sec: $BUILD_ELAPSED_SEC

## Remote

- remote_host: $REMOTE_HOST_VAL
- remote_archive_dir: $REMOTE_ARCHIVE_DIR_VAL
- remote_so: $REMOTE_SO_PATH
- remote_so_sha256: $REMOTE_SO_SHA256
- remote_so_size_bytes: $REMOTE_SO_SIZE_BYTES
- artifact_hash_match: yes
- tuning_logs_uploaded: $(if [[ "$REMOTE_DB_UPLOAD_ENABLED" -eq 1 ]]; then printf 'yes'; else printf 'no'; fi)
- remote_tuning_logs_dir: $(if [[ "$REMOTE_DB_UPLOAD_ENABLED" -eq 1 ]]; then printf '%s' "$REMOTE_DB_DIR"; else printf 'NA'; fi)
- remote_database_workload_json: $(if [[ "$REMOTE_DB_UPLOAD_ENABLED" -eq 1 ]]; then printf '%s' "$REMOTE_DB_WORKLOAD_PATH"; else printf 'NA'; fi)
- remote_database_tuning_record_json: $(if [[ "$REMOTE_DB_UPLOAD_ENABLED" -eq 1 ]]; then printf '%s' "$REMOTE_DB_TUNING_RECORD_PATH"; else printf 'NA'; fi)

## $INFERENCE_SECTION_TITLE

- runtime: $INFERENCE_RUNTIME_LABEL
- remote_tvm_python: $SAFE_REMOTE_TVM_PYTHON
- remote_tvm_version: $REMOTE_TVM_VERSION
- input_shape: $BUILD_INPUT_SHAPE
- input_dtype: $BUILD_INPUT_DTYPE
- entry: $SAFE_ENTRY
- warmup_runs: $SAFE_WARMUP_RUNS
- repeat: $SAFE_REPEAT
- device: $SAFE_DEVICE
- load_ms: $LOAD_MS
- vm_init_ms: $VM_INIT_MS
- run_count: $RUN_COUNT
- run_median_ms: $RUN_MEDIAN_MS
- run_mean_ms: $RUN_MEAN_MS
- run_min_ms: $RUN_MIN_MS
- run_max_ms: $RUN_MAX_MS
- run_variance_ms2: $RUN_VARIANCE_MS2
- output_shape: $OUTPUT_SHAPE
- output_dtype: $OUTPUT_DTYPE

## Logs

- orchestrator_log: $LOG_FILE
- remote_payload_log: $REMOTE_PAYLOAD_LOG
- summary_json: $SUMMARY_JSON
EOF

cat <<EOF
$COMPLETE_LABEL
  target:         $CURRENT_SAFE_TARGET
  total_trials:   $TUNE_TOTAL_TRIALS
  runner:         $TUNE_RUNNER
  search_mode:    $BUILD_SEARCH_MODE
  local_so:       $LOCAL_SO_PATH
  remote_so:      $REMOTE_SO_PATH
  load_ms:        $LOAD_MS
  vm_init_ms:     $VM_INIT_MS
  run_median_ms:  $RUN_MEDIAN_MS
  run_mean_ms:    $RUN_MEAN_MS
  summary_md:     $SUMMARY_MD
  summary_json:   $SUMMARY_JSON
EOF
