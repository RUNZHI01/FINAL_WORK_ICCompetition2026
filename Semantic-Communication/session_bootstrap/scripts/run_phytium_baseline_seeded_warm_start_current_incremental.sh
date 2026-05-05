#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

ONE_SHOT_SCRIPT="$SCRIPT_DIR/run_phytium_current_safe_one_shot.sh"
MANAGE_RPC_SERVICES_SCRIPT="$SCRIPT_DIR/manage_rpc_services.sh"
READINESS_SCRIPT="$SCRIPT_DIR/check_rpc_readiness.sh"

DEFAULT_REBUILD_ENV="$SESSION_DIR/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
DEFAULT_INFERENCE_ENV="$SESSION_DIR/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
DEFAULT_ENTRY=main

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh [options]

Purpose:
  Run a real baseline-seeded warm-start current incremental round for Phytium Pi:
    1) optionally start RPC tracker/server with the safe TVM runtime env
    2) run readiness against the warm-start current tuning env
    3) perform nonzero-budget MetaSchedule tuning from the existing DB
    4) upload the tuned current artifact + updated DB into the remote current archive
    5) validate the result through the same safe-runtime inference path

Defaults:
  rebuild env   : $DEFAULT_REBUILD_ENV
  inference env : $DEFAULT_INFERENCE_ENV

Options:
  --rebuild-env <path>        Override warm-start rebuild env file.
  --inference-env <path>      Override safe-runtime inference env file.
  --target <json>             Override the current target JSON.
  --output-dir <path>         Override local output dir for tuned artifact.
  --remote-archive-dir <dir>  Override remote current archive dir.
  --report-id <id>            Override report/log prefix.
  --total-trials <n>          Override nonzero tuning budget.
  --repeat <n>                Override inference repeat count.
  --warmup-runs <n>           Override inference warmup count.
  --entry <name>              Override Relax VM entry name (default: ${DEFAULT_ENTRY}).
  --skip-services             Do not try to start RPC tracker/server before tuning.
  --skip-readiness            Do not run readiness before tuning.
  --help                      Show this message.

Notes:
  - This entrypoint is for real baseline-seeded warm-start current tuning, not rebuild-only replay.
  - It requires TUNE_RUNNER=rpc and a positive TUNE_TOTAL_TRIALS (or --total-trials override).
  - It does not fabricate Pi measurements; without reachable RPC + SSH, the real run will fail.
EOF
}

REBUILD_ENV="$DEFAULT_REBUILD_ENV"
INFERENCE_ENV="$DEFAULT_INFERENCE_ENV"
TARGET_OVERRIDE=""
OUTPUT_DIR_OVERRIDE=""
REMOTE_ARCHIVE_DIR_OVERRIDE=""
REPORT_ID_OVERRIDE=""
TOTAL_TRIALS_OVERRIDE=""
REPEAT_OVERRIDE=""
WARMUP_OVERRIDE=""
ENTRY_OVERRIDE=""
SKIP_SERVICES=0
SKIP_READINESS=0

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
    --total-trials)
      TOTAL_TRIALS_OVERRIDE="${2:-}"
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
    --skip-services)
      SKIP_SERVICES=1
      shift
      ;;
    --skip-readiness)
      SKIP_READINESS=1
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

append_optional_arg() {
  local option="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    RUN_CMD+=("$option" "$value")
  fi
}

require_command bash
require_file "$ONE_SHOT_SCRIPT" "current-safe execution script"
require_file "$MANAGE_RPC_SERVICES_SCRIPT" "RPC service manager"
require_file "$READINESS_SCRIPT" "RPC readiness script"
require_file "$REBUILD_ENV" "warm-start rebuild env"
require_file "$INFERENCE_ENV" "safe-runtime inference env"

# shellcheck source=/dev/null
source "$REBUILD_ENV"

TOTAL_TRIALS="${TOTAL_TRIALS_OVERRIDE:-${TUNE_TOTAL_TRIALS:-}}"
RUNNER="${TUNE_RUNNER:-rpc}"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"

if [[ -z "$TOTAL_TRIALS" ]]; then
  echo "ERROR: Missing TUNE_TOTAL_TRIALS in rebuild env and no --total-trials override was provided." >&2
  exit 1
fi
if ! [[ "$TOTAL_TRIALS" =~ ^[0-9]+$ ]] || [[ "$TOTAL_TRIALS" -le 0 ]]; then
  echo "ERROR: baseline-seeded warm-start current incremental tuning requires --total-trials > 0." >&2
  exit 1
fi
if [[ "$RUNNER" != "rpc" ]]; then
  echo "ERROR: baseline-seeded warm-start current incremental tuning requires TUNE_RUNNER=rpc." >&2
  exit 1
fi

mkdir -p "$LOG_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_ID="${REPORT_ID_OVERRIDE:-phytium_baseline_seeded_warm_start_current_incremental_${STAMP}}"
WRAPPER_LOG="$LOG_DIR_RESOLVED/${REPORT_ID}_wrapper.log"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$1" | tee -a "$WRAPPER_LOG"
}

log "Phytium baseline-seeded warm-start current incremental tuning started"
log "rebuild_env=$REBUILD_ENV"
log "inference_env=$INFERENCE_ENV"
log "report_id=$REPORT_ID"
log "runner=$RUNNER"
log "total_trials=$TOTAL_TRIALS"

if [[ "$SKIP_SERVICES" -eq 0 ]]; then
  log "step=services start"
  set +e
  bash "$MANAGE_RPC_SERVICES_SCRIPT" --env "$REBUILD_ENV" start-all 2>&1 | tee -a "$WRAPPER_LOG"
  SERVICES_RC=${PIPESTATUS[0]}
  set -e
  if [[ "$SERVICES_RC" -ne 0 ]]; then
    log "step=services warn rc=$SERVICES_RC (continuing; services may already be running)"
  else
    log "step=services success"
  fi
fi

if [[ "$SKIP_READINESS" -eq 0 ]]; then
  log "step=readiness start"
  set +e
  bash "$READINESS_SCRIPT" --env "$REBUILD_ENV" 2>&1 | tee -a "$WRAPPER_LOG"
  READINESS_RC=${PIPESTATUS[0]}
  set -e
  if [[ "$READINESS_RC" -ne 0 ]]; then
    log "step=readiness failed rc=$READINESS_RC"
    exit "$READINESS_RC"
  fi
  log "step=readiness success"
fi

RUN_CMD=(
  bash "$ONE_SHOT_SCRIPT"
  --rebuild-env "$REBUILD_ENV"
  --inference-env "$INFERENCE_ENV"
  --report-id "$REPORT_ID"
  --total-trials "$TOTAL_TRIALS"
  --runner "$RUNNER"
  --upload-db
)
append_optional_arg --target "$TARGET_OVERRIDE"
append_optional_arg --output-dir "$OUTPUT_DIR_OVERRIDE"
append_optional_arg --remote-archive-dir "$REMOTE_ARCHIVE_DIR_OVERRIDE"
append_optional_arg --repeat "$REPEAT_OVERRIDE"
append_optional_arg --warmup-runs "$WARMUP_OVERRIDE"
append_optional_arg --entry "$ENTRY_OVERRIDE"

log "step=baseline_seeded_warm_start_current_incremental start"
set +e
("${RUN_CMD[@]}") 2>&1 | tee -a "$WRAPPER_LOG"
RUN_RC=${PIPESTATUS[0]}
set -e
if [[ "$RUN_RC" -ne 0 ]]; then
  log "step=baseline_seeded_warm_start_current_incremental failed rc=$RUN_RC"
  exit "$RUN_RC"
fi
log "step=baseline_seeded_warm_start_current_incremental success"

cat <<EOF
Phytium baseline-seeded warm-start current incremental tuning complete.
  report_id:    $REPORT_ID
  wrapper_log:  $WRAPPER_LOG
  total_trials: $TOTAL_TRIALS
  runner:       $RUNNER
EOF
