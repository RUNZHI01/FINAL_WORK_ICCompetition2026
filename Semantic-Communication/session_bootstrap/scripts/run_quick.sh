#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/local.env"

usage() {
  cat <<'EOF'
Usage:
  run_quick.sh [--env <path>]

Notes:
  - The env file must define:
    MODEL_NAME, TARGET, SHAPE_BUCKETS, QUICK_BASELINE_CMD, QUICK_CURRENT_CMD
  - Optional:
    THREADS, QUICK_REPEAT, QUICK_TIMEOUT_SEC, TUNING_DB_DIR, LOG_DIR, REPORT_DIR, EXECUTION_ID,
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
require_var QUICK_BASELINE_CMD
require_var QUICK_CURRENT_CMD

THREADS="${THREADS:-unknown}"
QUICK_REPEAT="${QUICK_REPEAT:-5}"
QUICK_TIMEOUT_SEC="${QUICK_TIMEOUT_SEC:-0}"
TUNING_DB_DIR_RESOLVED="$(resolve_path "${TUNING_DB_DIR:-./db}")"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

if ! [[ "$QUICK_REPEAT" =~ ^[0-9]+$ ]] || [[ "$QUICK_REPEAT" -lt 1 ]]; then
  echo "ERROR: QUICK_REPEAT must be a positive integer." >&2
  exit 1
fi

if ! [[ "$QUICK_TIMEOUT_SEC" =~ ^[0-9]+$ ]]; then
  echo "ERROR: QUICK_TIMEOUT_SEC must be a non-negative integer." >&2
  exit 1
fi

if [[ "$QUICK_TIMEOUT_SEC" -gt 0 ]] && ! command -v timeout >/dev/null 2>&1; then
  echo "ERROR: timeout command not found but QUICK_TIMEOUT_SEC is set." >&2
  exit 1
fi

mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED" "$TUNING_DB_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${EXECUTION_ID:-quick_${STAMP}}"
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
    echo "Hint: set a new EXECUTION_ID or export ALLOW_REPORT_OVERWRITE=1 to overwrite intentionally." >&2
    exit 1
  fi
fi

cat >"$RAW_CSV_FILE" <<'EOF'
mode,iteration,elapsed_ms,exit_code
EOF

{
  echo "[$(date -Iseconds)] quick run started"
  echo "run_id=$RUN_ID"
  echo "model_name=$MODEL_NAME"
  echo "target=$TARGET"
  echo "shape_buckets=$SHAPE_BUCKETS"
  echo "threads=$THREADS"
  echo "quick_repeat=$QUICK_REPEAT"
  echo "quick_timeout_sec=$QUICK_TIMEOUT_SEC"
  echo "env_file=$ENV_FILE"
  echo "tuning_db_dir=$TUNING_DB_DIR_RESOLVED"
  echo "baseline_cmd=$QUICK_BASELINE_CMD"
  echo "current_cmd=$QUICK_CURRENT_CMD"
} >"$LOG_FILE"

run_and_measure() {
  local mode="$1"
  local cmd="$2"
  local iteration=1

  while [[ "$iteration" -le "$QUICK_REPEAT" ]]; do
    echo "[$(date -Iseconds)] mode=$mode iteration=$iteration/$QUICK_REPEAT cmd=$cmd" >>"$LOG_FILE"
    local start_ns end_ns elapsed_ms exit_code

    start_ns="$(date +%s%N)"
    set +e
    if [[ "$QUICK_TIMEOUT_SEC" -gt 0 ]]; then
      timeout "$QUICK_TIMEOUT_SEC" bash -lc "cd \"$PROJECT_DIR\" && $cmd" >>"$LOG_FILE" 2>&1
    else
      bash -lc "cd \"$PROJECT_DIR\" && $cmd" >>"$LOG_FILE" 2>&1
    fi
    exit_code=$?
    set -e
    end_ns="$(date +%s%N)"

    elapsed_ms="$(awk -v s="$start_ns" -v e="$end_ns" 'BEGIN { printf "%.3f", (e - s) / 1000000 }')"
    printf '%s,%s,%s,%s\n' "$mode" "$iteration" "$elapsed_ms" "$exit_code" >>"$RAW_CSV_FILE"

    if [[ "$exit_code" -ne 0 ]]; then
      echo "[$(date -Iseconds)] mode=$mode iteration=$iteration failed with exit_code=$exit_code" >>"$LOG_FILE"
      return "$exit_code"
    fi

    iteration="$((iteration + 1))"
  done
}

calc_stats() {
  local mode="$1"
  local count mean variance median

  count="$(awk -F, -v m="$mode" '$1 == m && $4 == 0 { n++ } END { print n + 0 }' "$RAW_CSV_FILE")"
  if [[ "$count" -eq 0 ]]; then
    return 1
  fi

  read -r mean variance < <(
    awk -F, -v m="$mode" '
      $1 == m && $4 == 0 { sum += $3; sq += ($3 * $3); n++ }
      END {
        if (n == 0) {
          exit 1
        }
        mean = sum / n
        variance = (sq / n) - (mean * mean)
        if (variance < 0) {
          variance = 0
        }
        printf "%.3f %.6f\n", mean, variance
      }
    ' "$RAW_CSV_FILE"
  )

  median="$(
    awk -F, -v m="$mode" '$1 == m && $4 == 0 { print $3 }' "$RAW_CSV_FILE" \
      | sort -n \
      | awk '
        { values[NR] = $1 }
        END {
          if (NR == 0) {
            exit 1
          }
          if (NR % 2 == 1) {
            printf "%.3f\n", values[(NR + 1) / 2]
          } else {
            printf "%.3f\n", (values[NR / 2] + values[(NR / 2) + 1]) / 2
          }
        }
      '
  )"

  printf '%s %s %s %s\n' "$count" "$median" "$mean" "$variance"
}

get_stats_or_na() {
  local mode="$1"
  local stats
  if stats="$(calc_stats "$mode" 2>/dev/null)"; then
    printf '%s\n' "$stats"
  else
    printf '0 NA NA NA\n'
  fi
}

write_report() {
  local status="$1"
  local baseline_count="$2"
  local baseline_median="$3"
  local baseline_mean="$4"
  local baseline_var="$5"
  local baseline_exit_code="$6"
  local current_count="$7"
  local current_median="$8"
  local current_mean="$9"
  local current_var="${10}"
  local current_exit_code="${11}"
  local delta_ms="${12}"
  local improvement_pct="${13}"

  cat >"$REPORT_FILE" <<EOF
# Quick Report

- execution_id: $RUN_ID
- mode: quick
- status: $status
- timestamp: $(date -Iseconds)
- env_file: $ENV_FILE
- model_name: $MODEL_NAME
- target: $TARGET
- shape_buckets: $SHAPE_BUCKETS
- threads: $THREADS
- quick_repeat: $QUICK_REPEAT
- tuning_db_dir: $TUNING_DB_DIR_RESOLVED
- baseline_cmd: \`$QUICK_BASELINE_CMD\`
- current_cmd: \`$QUICK_CURRENT_CMD\`
- baseline_count: $baseline_count
- baseline_median_ms: $baseline_median
- baseline_mean_ms: $baseline_mean
- baseline_variance_ms2: $baseline_var
- baseline_exit_code: $baseline_exit_code
- current_count: $current_count
- current_median_ms: $current_median
- current_mean_ms: $current_mean
- current_variance_ms2: $current_var
- current_exit_code: $current_exit_code
- delta_ms_current_minus_baseline: $delta_ms
- improvement_pct: $improvement_pct

## Artifacts

- log_file: $LOG_FILE
- raw_csv_file: $RAW_CSV_FILE
EOF
}

status="success"
baseline_exit_code="NA"
current_exit_code="NA"
failure_exit_code=0

if run_and_measure baseline "$QUICK_BASELINE_CMD"; then
  baseline_exit_code=0
else
  baseline_exit_code=$?
  status="failed_baseline"
  failure_exit_code="$baseline_exit_code"
fi

if [[ "$status" == "success" ]]; then
  if run_and_measure current "$QUICK_CURRENT_CMD"; then
    current_exit_code=0
  else
    current_exit_code=$?
    status="failed_current"
    failure_exit_code="$current_exit_code"
  fi
fi

read -r baseline_count baseline_median baseline_mean baseline_var < <(get_stats_or_na baseline)
read -r current_count current_median current_mean current_var < <(get_stats_or_na current)

delta_ms="NA"
improvement_pct="NA"
if [[ "$status" == "success" && "$baseline_median" != "NA" && "$current_median" != "NA" ]]; then
  delta_ms="$(awk -v b="$baseline_median" -v c="$current_median" 'BEGIN { printf "%.3f", c - b }')"
  improvement_pct="$(
    awk -v b="$baseline_median" -v c="$current_median" '
      BEGIN {
        if (b == 0) {
          printf "0.00"
        } else {
          printf "%.2f", ((b - c) / b) * 100
        }
      }
    '
  )"
fi

write_report \
  "$status" \
  "$baseline_count" "$baseline_median" "$baseline_mean" "$baseline_var" "$baseline_exit_code" \
  "$current_count" "$current_median" "$current_mean" "$current_var" "$current_exit_code" \
  "$delta_ms" "$improvement_pct"

if [[ "$status" == "success" ]]; then
  echo "Quick run completed"
else
  echo "Quick run failed ($status)"
fi
echo "  report: $REPORT_FILE"
echo "  log:    $LOG_FILE"
echo "  raw:    $RAW_CSV_FILE"

if [[ "$status" != "success" ]]; then
  exit "$failure_exit_code"
fi
