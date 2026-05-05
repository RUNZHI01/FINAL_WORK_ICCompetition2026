#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_rpc_tune.sh --env <path> [--skip-full] [--skip-services] [--runner rpc|local]

Full closed-loop:
  1) Start RPC services (tracker + remote runner)
  2) Readiness check
  3) MetaSchedule tune (search+compile on laptop, measure on device)
  4) Quick comparison (baseline .so vs tuned .so)
  5) Full comparison (optional)
  6) Daily summary

Notes:
  - The env file must define ONNX_MODEL_PATH, TUNE_*, RPC_*, REMOTE_* fields.
  - Use --skip-services if tracker/runner are already running.
  - Use --runner local for smoke testing without a real device.
EOF
}

ENV_FILE=""
SKIP_FULL=0
SKIP_SERVICES=0
RUNNER_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env requires a file path." >&2
        exit 1
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    --skip-full)
      SKIP_FULL=1
      shift
      ;;
    --skip-services)
      SKIP_SERVICES=1
      shift
      ;;
    --runner)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --runner requires rpc|local." >&2
        exit 1
      fi
      RUNNER_OVERRIDE="$2"
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

if [[ -z "$ENV_FILE" ]]; then
  echo "ERROR: --env is required." >&2
  usage >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a
source "$ENV_FILE"
set +a

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
}

require_var ONNX_MODEL_PATH
require_var TUNE_INPUT_SHAPE
require_var TUNE_TOTAL_TRIALS
require_var TUNE_OUTPUT_DIR
require_var TARGET
require_var DEVICE_KEY
require_var RPC_TRACKER_HOST
require_var RPC_TRACKER_PORT

LOCAL_TVM_PYTHON="${LOCAL_TVM_PYTHON:-${TVM_PYTHON:-python3}}"
TUNE_RUNNER="${RUNNER_OVERRIDE:-${TUNE_RUNNER:-rpc}}"
TUNE_INPUT_NAME="${TUNE_INPUT_NAME:-input}"
TUNE_INPUT_DTYPE="${TUNE_INPUT_DTYPE:-float32}"
TUNE_MAX_TRIALS_PER_TASK="${TUNE_MAX_TRIALS_PER_TASK:-}"
TUNE_NUM_TRIALS_PER_ITER="${TUNE_NUM_TRIALS_PER_ITER:-64}"
TUNE_SESSION_TIMEOUT="${TUNE_SESSION_TIMEOUT:-120}"
TUNE_TIMEOUT_SEC="${TUNE_TIMEOUT_SEC:-7200}"
TUNE_EXISTING_DB_VAL="${TUNE_EXISTING_DB:-}"
TUNE_OP_NAMES_VAL="${TUNE_OP_NAMES:-${FULL_HOTSPOT_TASKS:-}}"
TUNE_REQUIRE_REAL="${TUNE_REQUIRE_REAL:-0}"
TUNE_MODE_LABEL="${TUNE_MODE_LABEL:-}"
REMOTE_MODE_LOWER="$(printf '%s' "${REMOTE_MODE:-ssh}" | tr '[:upper:]' '[:lower:]')"

TUNE_MODE="real_rpc"
if [[ "$TUNE_RUNNER" != "rpc" ]]; then
  TUNE_MODE="local_smoke"
fi
if [[ "${TUNE_TOTAL_TRIALS:-0}" =~ ^[0-9]+$ ]] && [[ "${TUNE_TOTAL_TRIALS:-0}" -eq 0 ]]; then
  TUNE_MODE="rebuild_only"
fi

if [[ "$TUNE_REQUIRE_REAL" == "1" ]]; then
  if [[ "$TUNE_RUNNER" != "rpc" ]]; then
    echo "ERROR: TUNE_REQUIRE_REAL=1 but runner=$TUNE_RUNNER (expected rpc)." >&2
    exit 1
  fi
  if ! [[ "${TUNE_TOTAL_TRIALS:-}" =~ ^[0-9]+$ ]] || [[ "${TUNE_TOTAL_TRIALS:-0}" -lt 1 ]]; then
    echo "ERROR: TUNE_REQUIRE_REAL=1 but TUNE_TOTAL_TRIALS=${TUNE_TOTAL_TRIALS:-N/A} (expected >=1)." >&2
    exit 1
  fi
fi

ONNX_RESOLVED="$(resolve_path "$ONNX_MODEL_PATH")"
OUTPUT_DIR_RESOLVED="$(resolve_path "$TUNE_OUTPUT_DIR")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"

mkdir -p "$OUTPUT_DIR_RESOLVED" "$REPORT_DIR_RESOLVED" "$LOG_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
ORCH_LOG="$LOG_DIR_RESOLVED/rpc_tune_${STAMP}.log"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$1" | tee -a "$ORCH_LOG"
}

run_step() {
  local step="$1"
  shift
  log "step=${step} start"
  set +e
  "$@" >>"$ORCH_LOG" 2>&1
  local rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    log "step=${step} success"
  else
    log "step=${step} failed rc=${rc}"
  fi
  return "$rc"
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

get_md_field() {
  local file="$1"
  local key="$2"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  grep -E "^- ${key}:" "$file" | head -n 1 | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

derive_report_status() {
  local file="$1"
  local rc="$2"
  local status

  status="$(get_md_field "$file" "status")"
  if [[ -n "$status" ]]; then
    printf '%s\n' "$status"
    return 0
  fi

  if [[ -f "$file" ]]; then
    if [[ "$rc" -eq 0 ]]; then
      printf 'success_missing_status\n'
    else
      printf 'failed_missing_status_rc_%s\n' "$rc"
    fi
    return 0
  fi

  if [[ "$rc" -eq 0 ]]; then
    printf 'success_missing_report\n'
  else
    printf 'failed_missing_report_rc_%s\n' "$rc"
  fi
}

copy_file_to_current_archive() {
  local src="$1"
  local dst="$2"
  if [[ ! -f "$src" ]]; then
    log "ERROR: missing local artifact for deploy: $src"
    return 1
  fi

  if [[ "$REMOTE_MODE_LOWER" == "local" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    return 0
  fi

  if ! bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    -- "mkdir -p $(shell_quote "$(dirname "$dst")")" >>"$ORCH_LOG" 2>&1; then
    log "ERROR: remote mkdir failed for $dst"
    return 1
  fi

  if ! bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    -- "cat > $(shell_quote "$dst")" <"$src" >>"$ORCH_LOG" 2>&1; then
    log "ERROR: remote copy failed for $dst"
    return 1
  fi

  return 0
}

deploy_tune_artifacts() {
  require_var REMOTE_TVM_JSCC_BASE_DIR

  local so_src="$1"
  local db_dir="$2"
  local archive_base="$REMOTE_TVM_JSCC_BASE_DIR"

  log "step=deploy_tune_artifacts start"
  log "deploy current archive base=$archive_base"
  copy_file_to_current_archive "$so_src" "$archive_base/tvm_tune_logs/optimized_model.so" || return 1
  copy_file_to_current_archive "$db_dir/database_workload.json" "$archive_base/tuning_logs/database_workload.json" || return 1
  copy_file_to_current_archive "$db_dir/database_tuning_record.json" "$archive_base/tuning_logs/database_tuning_record.json" || return 1
  log "step=deploy_tune_artifacts success"
}

log "=== RPC Tune Closed Loop ==="
log "env=$ENV_FILE"
log "onnx=$ONNX_RESOLVED"
log "target=$TARGET"
log "runner=$TUNE_RUNNER"
log "total_trials=$TUNE_TOTAL_TRIALS"
log "tune_mode=$TUNE_MODE"
if [[ -n "$TUNE_MODE_LABEL" ]]; then
  log "tune_mode_label=$TUNE_MODE_LABEL"
fi
log "output_dir=$OUTPUT_DIR_RESOLVED"

if [[ "$TUNE_MODE" == "rebuild_only" ]]; then
  log "WARN: total_trials=0 => rebuild-only compile with warm-start DB; this is not a real MetaSchedule search round"
elif [[ "$TUNE_MODE" == "local_smoke" ]]; then
  log "WARN: runner=local => local smoke mode; this is not real device-guided tuning"
fi

# Step 1: Start RPC services
if [[ "$SKIP_SERVICES" -eq 0 && "$TUNE_RUNNER" == "rpc" ]]; then
  log "step=services start"
  set +e
  bash "$SCRIPT_DIR/manage_rpc_services.sh" --env "$ENV_FILE" start-all >>"$ORCH_LOG" 2>&1
  svc_rc=$?
  set -e
  if [[ "$svc_rc" -ne 0 ]]; then
    log "step=services failed rc=${svc_rc} (continuing, services may already be running)"
  else
    log "step=services success"
  fi
  sleep 2
fi

# Step 2: Readiness check
readiness_rc=0
if run_step "readiness" bash "$SCRIPT_DIR/check_rpc_readiness.sh" --env "$ENV_FILE"; then
  readiness_rc=0
else
  readiness_rc=$?
  log "WARN: readiness check returned rc=$readiness_rc (non-fatal for tune, continuing)"
fi

# Step 3: MetaSchedule tune
tune_rc=0
TUNE_CMD=("$LOCAL_TVM_PYTHON" "$SCRIPT_DIR/rpc_tune.py"
  --onnx-path "$ONNX_RESOLVED"
  --output-dir "$OUTPUT_DIR_RESOLVED"
  --target "$TARGET"
  --tracker-host "$RPC_TRACKER_HOST"
  --tracker-port "$RPC_TRACKER_PORT"
  --device-key "$DEVICE_KEY"
  --total-trials "$TUNE_TOTAL_TRIALS"
  --input-shape "$TUNE_INPUT_SHAPE"
  --input-name "$TUNE_INPUT_NAME"
  --input-dtype "$TUNE_INPUT_DTYPE"
  --runner "$TUNE_RUNNER"
  --session-timeout "$TUNE_SESSION_TIMEOUT"
  --num-trials-per-iter "$TUNE_NUM_TRIALS_PER_ITER"
)

if [[ -n "$TUNE_MAX_TRIALS_PER_TASK" ]]; then
  TUNE_CMD+=(--max-trials-per-task "$TUNE_MAX_TRIALS_PER_TASK")
fi

if [[ -n "$TUNE_OP_NAMES_VAL" ]]; then
  TUNE_CMD+=(--op-names "$TUNE_OP_NAMES_VAL")
fi

if [[ -n "$TUNE_EXISTING_DB_VAL" ]]; then
  TUNE_CMD+=(--existing-db "$(resolve_path "$TUNE_EXISTING_DB_VAL")")
fi

log "step=tune start (timeout=${TUNE_TIMEOUT_SEC}s)"
set +e
if [[ "$TUNE_TIMEOUT_SEC" -gt 0 ]] && command -v timeout >/dev/null 2>&1; then
  timeout "$TUNE_TIMEOUT_SEC" "${TUNE_CMD[@]}" 2>&1 | tee -a "$ORCH_LOG"
else
  "${TUNE_CMD[@]}" 2>&1 | tee -a "$ORCH_LOG"
fi
tune_rc=$?
set -e

TUNE_SO="$OUTPUT_DIR_RESOLVED/optimized_model.so"
TUNE_DB="$OUTPUT_DIR_RESOLVED/tuning_logs"

if [[ "$tune_rc" -ne 0 ]]; then
  log "step=tune failed rc=${tune_rc}"
  log "abort: tune failed, skipping quick/full/daily"
  exit "$tune_rc"
fi
log "step=tune success"

if [[ ! -f "$TUNE_SO" ]]; then
  log "ERROR: expected tune output not found: $TUNE_SO"
  exit 1
fi

# Step 4: Generate a run env that points quick/full commands at the tuned .so
RUN_ENV="$OUTPUT_DIR_RESOLVED/rpc_tune_run_${STAMP}.env"
cp "$ENV_FILE" "$RUN_ENV"
{
  echo
  echo "# --- Auto-generated by run_rpc_tune.sh (${STAMP}) ---"
  echo "EXECUTION_ID=quick_rpc_tune_${STAMP}"
  echo "FULL_EXECUTION_ID=full_rpc_tune_${STAMP}"
  echo "DAILY_REPORT_FILE=${REPORT_DIR_RESOLVED}/daily_rpc_tune_${STAMP}.md"
  echo "DAILY_REPORT_DATE=$(date +%F)"
  echo "TUNE_MODE=${TUNE_MODE}"
  echo "TUNE_MODE_LABEL=${TUNE_MODE_LABEL}"
  echo "TUNE_SO_PATH=${TUNE_SO}"
  echo "TUNE_DB_PATH=${TUNE_DB}"
} >>"$RUN_ENV"

# Re-source to pick up the new fields
# shellcheck source=/dev/null
set -a
source "$RUN_ENV"
set +a

# Step 4b: Deploy rebuilt current artifacts into the archive probed by quick/full.
deploy_tune_rc=0
if deploy_tune_artifacts "$TUNE_SO" "$TUNE_DB"; then
  deploy_tune_rc=0
else
  deploy_tune_rc=$?
  log "step=deploy_tune_artifacts failed rc=${deploy_tune_rc}"
  log "abort: deploy failed, skipping quick/full/daily"
  exit "$deploy_tune_rc"
fi

# Step 5: Quick comparison
QUICK_REPORT_PATH="$REPORT_DIR_RESOLVED/${EXECUTION_ID:-N/A}.md"
FULL_REPORT_PATH="$REPORT_DIR_RESOLVED/${FULL_EXECUTION_ID:-N/A}.md"
quick_rc=0
quick_status="not_run"
if run_step "quick" bash "$SCRIPT_DIR/run_quick.sh" --env "$RUN_ENV"; then
  quick_rc=0
else
  quick_rc=$?
fi
quick_status="$(derive_report_status "$QUICK_REPORT_PATH" "$quick_rc")"
log "step=quick result rc=${quick_rc} status=${quick_status} report=${QUICK_REPORT_PATH}"

# Step 6: Full comparison (optional)
full_rc=0
full_state="skipped"
full_status="not_run"
if [[ "$quick_rc" -eq 0 && "$SKIP_FULL" -eq 0 ]]; then
  if run_step "full" bash "$SCRIPT_DIR/run_full_placeholder.sh" --env "$RUN_ENV"; then
    full_rc=0
    full_state="success"
  else
    full_rc=$?
    full_state="failed"
  fi
  full_status="$(derive_report_status "$FULL_REPORT_PATH" "$full_rc")"
  log "step=full result rc=${full_rc} status=${full_status} report=${FULL_REPORT_PATH}"
elif [[ "$SKIP_FULL" -eq 1 ]]; then
  full_state="skipped_by_flag"
  full_status="skipped_by_flag"
else
  full_state="skipped_due_to_quick_failure"
  full_status="skipped_due_to_quick_failure"
fi

# Step 7: Daily summary
summary_rc=0
if run_step "daily" bash "$SCRIPT_DIR/summarize_to_daily.sh" \
    --env "$RUN_ENV" \
    --date "$(date +%F)" \
    --output "${DAILY_REPORT_FILE:-${REPORT_DIR_RESOLVED}/daily_rpc_tune_${STAMP}.md}"; then
  summary_rc=0
else
  summary_rc=$?
fi

# Write orchestrator summary
TUNE_SUMMARY="$REPORT_DIR_RESOLVED/rpc_tune_summary_${STAMP}.md"
cat >"$TUNE_SUMMARY" <<EOF
# RPC Tune Summary

- generated_at: $(date -Iseconds)
- env_file: $ENV_FILE
- run_env: $RUN_ENV
- onnx_model: $ONNX_RESOLVED
- target: $TARGET
- runner: $TUNE_RUNNER
- tune_mode: $TUNE_MODE
- tune_mode_label: ${TUNE_MODE_LABEL:-N/A}
- total_trials: $TUNE_TOTAL_TRIALS
- tune_rc: $tune_rc
- tune_so: $TUNE_SO
- tune_db: $TUNE_DB
- readiness_rc: $readiness_rc
- quick_rc: $quick_rc
- quick_status: $quick_status
- full_rc: $full_rc
- full_status: $full_status
- full_state: $full_state
- summary_rc: $summary_rc
- orchestrator_log: $ORCH_LOG

## Artifacts

- tune_report: $OUTPUT_DIR_RESOLVED/tune_report.json
- quick_report: $QUICK_REPORT_PATH
- full_report: $FULL_REPORT_PATH
- daily_report: ${DAILY_REPORT_FILE:-N/A}
EOF

log "summary_file=$TUNE_SUMMARY"
log "tune_so=$TUNE_SO"

final_rc=0
if [[ "$tune_rc" -ne 0 ]]; then
  final_rc="$tune_rc"
elif [[ "$quick_rc" -ne 0 ]]; then
  final_rc="$quick_rc"
elif [[ "$full_rc" -ne 0 ]]; then
  final_rc="$full_rc"
fi

if [[ "$final_rc" -eq 0 ]]; then
  log "RPC tune closed loop completed successfully"
else
  log "RPC tune closed loop completed with failure rc=$final_rc"
fi

echo "  tune summary: $TUNE_SUMMARY"
echo "  tune .so:     $TUNE_SO"
echo "  orch log:     $ORCH_LOG"

exit "$final_rc"
