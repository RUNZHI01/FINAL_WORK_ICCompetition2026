#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/local.env"

usage() {
  cat <<'EOF'
Usage:
  run_full_placeholder.sh [--env <path>]

Notes:
  - Required vars:
    MODEL_NAME, TARGET, SHAPE_BUCKETS
  - Full command vars:
    FULL_BASELINE_CMD, FULL_CURRENT_CMD
    (if omitted, fallback to QUICK_BASELINE_CMD/QUICK_CURRENT_CMD)
  - Optional vars:
    THREADS, FULL_TIMEOUT_SEC, TUNING_DB_DIR, LOG_DIR, REPORT_DIR,
    EXECUTION_ID, FULL_EXECUTION_ID, FULL_NOTES,
    ALLOW_REPORT_OVERWRITE=1 (reuse an existing RUN_ID and overwrite prior artifacts)
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  echo "Hint: copy $SESSION_DIR/config/local.example to $SESSION_DIR/config/local.env" >&2
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

require_var MODEL_NAME
require_var TARGET
require_var SHAPE_BUCKETS

THREADS="${THREADS:-unknown}"
FULL_TIMEOUT_SEC="${FULL_TIMEOUT_SEC:-0}"
FULL_BASELINE_CMD="${FULL_BASELINE_CMD:-${QUICK_BASELINE_CMD:-}}"
FULL_CURRENT_CMD="${FULL_CURRENT_CMD:-${QUICK_CURRENT_CMD:-}}"
FULL_NOTES="${FULL_NOTES:-}"
TUNING_DB_DIR_RESOLVED="$(resolve_path "${TUNING_DB_DIR:-./db}")"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

if [[ -z "$FULL_BASELINE_CMD" ]] || [[ -z "$FULL_CURRENT_CMD" ]]; then
  echo "ERROR: Missing FULL_BASELINE_CMD/FULL_CURRENT_CMD and QUICK fallback is unavailable." >&2
  exit 1
fi

if ! [[ "$FULL_TIMEOUT_SEC" =~ ^[0-9]+$ ]]; then
  echo "ERROR: FULL_TIMEOUT_SEC must be a non-negative integer." >&2
  exit 1
fi

if [[ "$FULL_TIMEOUT_SEC" -gt 0 ]] && ! command -v timeout >/dev/null 2>&1; then
  echo "ERROR: timeout command not found but FULL_TIMEOUT_SEC is set." >&2
  exit 1
fi

mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED" "$TUNING_DB_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${FULL_EXECUTION_ID:-${EXECUTION_ID:-full_${STAMP}}}"
ALLOW_REPORT_OVERWRITE="${ALLOW_REPORT_OVERWRITE:-0}"
LOG_FILE="$LOG_DIR_RESOLVED/${RUN_ID}.log"
RAW_CSV_FILE="$REPORT_DIR_RESOLVED/${RUN_ID}_raw.csv"
REPORT_FILE="$REPORT_DIR_RESOLVED/${RUN_ID}.md"

if [[ "$ALLOW_REPORT_OVERWRITE" != "1" ]]; then
  existing_outputs=()
  [[ -e "$LOG_FILE" ]] && existing_outputs+=("$LOG_FILE")
  [[ -e "$RAW_CSV_FILE" ]] && existing_outputs+=("$RAW_CSV_FILE")
  [[ -e "$REPORT_FILE" ]] && existing_outputs+=("$REPORT_FILE")
  if [[ "${#existing_outputs[@]}" -gt 0 ]]; then
    printf 'ERROR: run artifacts already exist for RUN_ID=%s\n' "$RUN_ID" >&2
    printf 'Refusing to overwrite:%s\n' "" >&2
    printf '  %s\n' "${existing_outputs[@]}" >&2
    echo "Hint: set a new FULL_EXECUTION_ID/EXECUTION_ID or export ALLOW_REPORT_OVERWRITE=1 to overwrite intentionally." >&2
    exit 1
  fi
fi

cat >"$RAW_CSV_FILE" <<'EOF'
mode,elapsed_ms,exit_code,start_at,end_at
EOF

{
  echo "[$(date -Iseconds)] full run started"
  echo "run_id=$RUN_ID"
  echo "model_name=$MODEL_NAME"
  echo "target=$TARGET"
  echo "shape_buckets=$SHAPE_BUCKETS"
  echo "threads=$THREADS"
  echo "full_timeout_sec=$FULL_TIMEOUT_SEC"
  echo "env_file=$ENV_FILE"
  echo "tuning_db_dir=$TUNING_DB_DIR_RESOLVED"
  echo "baseline_cmd=$FULL_BASELINE_CMD"
  echo "current_cmd=$FULL_CURRENT_CMD"
} >"$LOG_FILE"

LAST_ELAPSED_MS="NA"
LAST_EXIT_CODE="NA"

run_once() {
  local mode="$1"
  local cmd="$2"
  local start_ns end_ns start_at end_at elapsed_ms exit_code

  start_at="$(date -Iseconds)"
  start_ns="$(date +%s%N)"
  echo "[$start_at] mode=$mode cmd=$cmd" >>"$LOG_FILE"

  set +e
  if [[ "$FULL_TIMEOUT_SEC" -gt 0 ]]; then
    timeout "$FULL_TIMEOUT_SEC" bash -lc "cd \"$PROJECT_DIR\" && $cmd" >>"$LOG_FILE" 2>&1
  else
    bash -lc "cd \"$PROJECT_DIR\" && $cmd" >>"$LOG_FILE" 2>&1
  fi
  exit_code=$?
  set -e

  end_at="$(date -Iseconds)"
  end_ns="$(date +%s%N)"
  elapsed_ms="$(awk -v s="$start_ns" -v e="$end_ns" 'BEGIN { printf "%.3f", (e - s) / 1000000 }')"

  printf '%s,%s,%s,%s,%s\n' "$mode" "$elapsed_ms" "$exit_code" "$start_at" "$end_at" >>"$RAW_CSV_FILE"
  echo "[$end_at] mode=$mode exit_code=$exit_code elapsed_ms=$elapsed_ms" >>"$LOG_FILE"

  LAST_ELAPSED_MS="$elapsed_ms"
  LAST_EXIT_CODE="$exit_code"
  return "$exit_code"
}

write_report() {
  local status="$1"
  local baseline_elapsed="$2"
  local baseline_exit="$3"
  local current_elapsed="$4"
  local current_exit="$5"
  local delta_ms="$6"
  local improvement_pct="$7"
  local baseline_count="$8"
  local current_count="$9"

  cat >"$REPORT_FILE" <<EOF
# Full Report

- execution_id: $RUN_ID
- mode: full
- status: $status
- timestamp: $(date -Iseconds)
- env_file: $ENV_FILE
- model_name: $MODEL_NAME
- target: $TARGET
- shape_buckets: $SHAPE_BUCKETS
- threads: $THREADS
- full_timeout_sec: $FULL_TIMEOUT_SEC
- tuning_db_dir: $TUNING_DB_DIR_RESOLVED
- baseline_cmd: \`$FULL_BASELINE_CMD\`
- current_cmd: \`$FULL_CURRENT_CMD\`
- baseline_elapsed_ms: $baseline_elapsed
- baseline_exit_code: $baseline_exit
- baseline_count: $baseline_count
- current_elapsed_ms: $current_elapsed
- current_exit_code: $current_exit
- current_count: $current_count
- delta_ms_current_minus_baseline: $delta_ms
- improvement_pct: $improvement_pct
- full_notes: $FULL_NOTES

## Artifacts

- log_file: $LOG_FILE
- raw_csv_file: $RAW_CSV_FILE

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
EOF
}

baseline_elapsed_ms="NA"
baseline_exit_code="NA"
current_elapsed_ms="NA"
current_exit_code="NA"
delta_ms="NA"
improvement_pct="NA"
baseline_count=0
current_count=0

if run_once baseline "$FULL_BASELINE_CMD"; then
  baseline_elapsed_ms="$LAST_ELAPSED_MS"
  baseline_exit_code="$LAST_EXIT_CODE"
  baseline_count=1
else
  baseline_elapsed_ms="$LAST_ELAPSED_MS"
  baseline_exit_code="$LAST_EXIT_CODE"
  baseline_count=0
  write_report "failed_baseline" "$baseline_elapsed_ms" "$baseline_exit_code" "$current_elapsed_ms" "$current_exit_code" "$delta_ms" "$improvement_pct" "$baseline_count" "$current_count"
  echo "Full run failed in baseline stage"
  echo "  report: $REPORT_FILE"
  echo "  log:    $LOG_FILE"
  exit "$baseline_exit_code"
fi

if run_once current "$FULL_CURRENT_CMD"; then
  current_elapsed_ms="$LAST_ELAPSED_MS"
  current_exit_code="$LAST_EXIT_CODE"
  current_count=1
else
  current_elapsed_ms="$LAST_ELAPSED_MS"
  current_exit_code="$LAST_EXIT_CODE"
  current_count=0
  write_report "failed_current" "$baseline_elapsed_ms" "$baseline_exit_code" "$current_elapsed_ms" "$current_exit_code" "$delta_ms" "$improvement_pct" "$baseline_count" "$current_count"
  echo "Full run failed in current stage"
  echo "  report: $REPORT_FILE"
  echo "  log:    $LOG_FILE"
  exit "$current_exit_code"
fi

delta_ms="$(awk -v b="$baseline_elapsed_ms" -v c="$current_elapsed_ms" 'BEGIN { printf "%.3f", c - b }')"
improvement_pct="$(
  awk -v b="$baseline_elapsed_ms" -v c="$current_elapsed_ms" '
    BEGIN {
      if (b == 0) {
        printf "0.00"
      } else {
        printf "%.2f", ((b - c) / b) * 100
      }
    }
  '
)"

write_report "success" "$baseline_elapsed_ms" "$baseline_exit_code" "$current_elapsed_ms" "$current_exit_code" "$delta_ms" "$improvement_pct" "$baseline_count" "$current_count"

echo "Full run completed"
echo "  report: $REPORT_FILE"
echo "  log:    $LOG_FILE"
