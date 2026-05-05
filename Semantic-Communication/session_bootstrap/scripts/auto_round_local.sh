#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_BASE_ENV="$SESSION_DIR/config/rpc_armv8.phytium_pi.2026-03-01.env"

usage() {
  cat <<'EOF'
Usage:
  auto_round_local.sh [--base-env <path>] [--run-tag <tag>] [--skip-full] [--lock-file <path>]

Flow:
  1) 生成唯一轮次 env（prepare_round_env.sh）
  2) readiness
  3) quick
  4) full（可选，默认开启）
  5) daily summary

Notes:
  - 使用 flock 防并发重复执行。
  - quick/full 任一步失败都会保留产物并返回非零状态。
EOF
}

BASE_ENV="$DEFAULT_BASE_ENV"
RUN_TAG=""
SKIP_FULL=0
LOCK_FILE="/tmp/tvm_metaschedule_auto_round.lock"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --base-env requires a file path." >&2
        exit 1
      fi
      BASE_ENV="$2"
      shift 2
      ;;
    --run-tag)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --run-tag requires a value." >&2
        exit 1
      fi
      RUN_TAG="$2"
      shift 2
      ;;
    --skip-full)
      SKIP_FULL=1
      shift
      ;;
    --lock-file)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --lock-file requires a file path." >&2
        exit 1
      fi
      LOCK_FILE="$2"
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

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

if ! command -v flock >/dev/null 2>&1; then
  echo "ERROR: flock command not found. Install util-linux first." >&2
  exit 1
fi

BASE_ENV_RESOLVED="$(resolve_path "$BASE_ENV")"
if [[ ! -f "$BASE_ENV_RESOLVED" ]]; then
  echo "ERROR: base env not found: $BASE_ENV_RESOLVED" >&2
  exit 1
fi

LOCK_FILE_RESOLVED="$(resolve_path "$LOCK_FILE")"
mkdir -p "$(dirname "$LOCK_FILE_RESOLVED")"
exec 9>"$LOCK_FILE_RESOLVED"
if ! flock -n 9; then
  echo "ERROR: another auto round is running (lock: $LOCK_FILE_RESOLVED)" >&2
  exit 3
fi

PREPARE_CMD=(bash "$SCRIPT_DIR/prepare_round_env.sh" --base-env "$BASE_ENV_RESOLVED")
if [[ -n "$RUN_TAG" ]]; then
  PREPARE_CMD+=(--run-tag "$RUN_TAG")
fi
RUN_ENV="$("${PREPARE_CMD[@]}")"

# shellcheck source=/dev/null
set -a
source "$RUN_ENV"
set +a

REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
mkdir -p "$REPORT_DIR_RESOLVED" "$LOG_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
ORCH_LOG="$LOG_DIR_RESOLVED/auto_round_${STAMP}.log"
ROUND_SUMMARY="$REPORT_DIR_RESOLVED/auto_round_summary_${STAMP}.md"
RUN_DATE="${DAILY_REPORT_DATE:-$(date +%F)}"
DAILY_OUTPUT="${DAILY_REPORT_FILE:-./session_bootstrap/reports/daily_${RUN_DATE}.md}"
DAILY_OUTPUT_RESOLVED="$(resolve_path "$DAILY_OUTPUT")"

log() {
  local msg="$1"
  printf '[%s] %s\n' "$(date -Iseconds)" "$msg" | tee -a "$ORCH_LOG"
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

readiness_rc=0
quick_rc=0
full_rc=0
summary_rc=0
full_state="skipped"

if run_step "readiness" bash "$SCRIPT_DIR/check_rpc_readiness.sh" --env "$RUN_ENV"; then
  readiness_rc=0
else
  readiness_rc=$?
fi
if [[ "$readiness_rc" -ne 0 ]]; then
  log "abort: readiness failed"
fi

if [[ "$readiness_rc" -eq 0 ]]; then
  if run_step "quick" bash "$SCRIPT_DIR/run_quick.sh" --env "$RUN_ENV"; then
    quick_rc=0
  else
    quick_rc=$?
  fi
fi

if [[ "$readiness_rc" -eq 0 && "$quick_rc" -eq 0 && "$SKIP_FULL" -eq 0 ]]; then
  if run_step "full" bash "$SCRIPT_DIR/run_full_placeholder.sh" --env "$RUN_ENV"; then
    full_rc=0
  else
    full_rc=$?
  fi
  if [[ "$full_rc" -eq 0 ]]; then
    full_state="success"
  else
    full_state="failed"
  fi
elif [[ "$SKIP_FULL" -eq 1 ]]; then
  full_state="skipped_by_flag"
elif [[ "$quick_rc" -ne 0 ]]; then
  full_state="skipped_due_to_quick_failure"
elif [[ "$readiness_rc" -ne 0 ]]; then
  full_state="skipped_due_to_readiness_failure"
fi

if run_step "daily" bash "$SCRIPT_DIR/summarize_to_daily.sh" --env "$RUN_ENV" --date "$RUN_DATE" --output "$DAILY_OUTPUT_RESOLVED"; then
  summary_rc=0
else
  summary_rc=$?
fi

{
  cat <<EOF
# Auto Round Summary

- generated_at: $(date -Iseconds)
- base_env: $BASE_ENV_RESOLVED
- run_env: $RUN_ENV
- execution_id: ${EXECUTION_ID:-N/A}
- full_execution_id: ${FULL_EXECUTION_ID:-N/A}
- daily_report: $DAILY_OUTPUT_RESOLVED
- orchestrator_log: $ORCH_LOG
- readiness_rc: $readiness_rc
- quick_rc: $quick_rc
- full_rc: $full_rc
- full_state: $full_state
- summary_rc: $summary_rc

## Artifacts

- quick_report: $REPORT_DIR_RESOLVED/${EXECUTION_ID:-N/A}.md
- full_report: $REPORT_DIR_RESOLVED/${FULL_EXECUTION_ID:-N/A}.md
- daily_report: $DAILY_OUTPUT_RESOLVED
EOF
} >"$ROUND_SUMMARY"

log "summary_file=$ROUND_SUMMARY"
log "run_env=$RUN_ENV"
log "daily_report=$DAILY_OUTPUT_RESOLVED"

final_rc=0
if [[ "$readiness_rc" -ne 0 ]]; then
  final_rc="$readiness_rc"
elif [[ "$quick_rc" -ne 0 ]]; then
  final_rc="$quick_rc"
elif [[ "$full_rc" -ne 0 ]]; then
  final_rc="$full_rc"
elif [[ "$summary_rc" -ne 0 ]]; then
  final_rc="$summary_rc"
fi

if [[ "$final_rc" -eq 0 ]]; then
  log "auto round completed successfully"
else
  log "auto round completed with failure rc=$final_rc"
fi

exit "$final_rc"
