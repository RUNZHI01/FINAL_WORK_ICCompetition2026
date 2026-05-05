#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_hotspot_micro_benchmark.sh \
    --label <baseline|current> \
    --hotspots <task_a,task_b,...> \
    --trials-per-task <int> \
    --work-units <int> \
    --db-dir <path>

Notes:
  - This is a low-cost executable payload for full-flow wiring validation.
  - Each "work unit" runs: dd if=/dev/zero of=/dev/null bs=1M count=<work-units>.
  - Results are appended to a csv snapshot under --db-dir.
EOF
}

LABEL=""
HOTSPOTS=""
TRIALS_PER_TASK=1
WORK_UNITS=8
DB_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --label requires a value." >&2
        usage
        exit 1
      fi
      LABEL="$2"
      shift 2
      ;;
    --hotspots)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --hotspots requires a value." >&2
        usage
        exit 1
      fi
      HOTSPOTS="$2"
      shift 2
      ;;
    --trials-per-task)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --trials-per-task requires a value." >&2
        usage
        exit 1
      fi
      TRIALS_PER_TASK="$2"
      shift 2
      ;;
    --work-units)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --work-units requires a value." >&2
        usage
        exit 1
      fi
      WORK_UNITS="$2"
      shift 2
      ;;
    --db-dir)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --db-dir requires a value." >&2
        usage
        exit 1
      fi
      DB_DIR="$2"
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

if [[ -z "$LABEL" || -z "$HOTSPOTS" || -z "$DB_DIR" ]]; then
  echo "ERROR: --label, --hotspots and --db-dir are required." >&2
  usage
  exit 1
fi

if [[ "$LABEL" != "baseline" && "$LABEL" != "current" ]]; then
  echo "ERROR: --label must be baseline or current." >&2
  exit 1
fi

if ! [[ "$TRIALS_PER_TASK" =~ ^[0-9]+$ ]] || [[ "$TRIALS_PER_TASK" -lt 1 ]]; then
  echo "ERROR: --trials-per-task must be a positive integer." >&2
  exit 1
fi

if ! [[ "$WORK_UNITS" =~ ^[0-9]+$ ]] || [[ "$WORK_UNITS" -lt 1 ]]; then
  echo "ERROR: --work-units must be a positive integer." >&2
  exit 1
fi

if ! command -v dd >/dev/null 2>&1; then
  echo "ERROR: dd command not found." >&2
  exit 1
fi

mkdir -p "$DB_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_CSV="$DB_DIR/full_payload_${LABEL}_${STAMP}.csv"

cat >"$OUTPUT_CSV" <<'EOF'
label,task,trial,work_units,elapsed_ms
EOF

IFS=',' read -r -a task_list <<< "$HOTSPOTS"
total_runs=0

for raw_task in "${task_list[@]}"; do
  task="$(printf '%s' "$raw_task" | xargs)"
  if [[ -z "$task" ]]; then
    continue
  fi

  trial=1
  while [[ "$trial" -le "$TRIALS_PER_TASK" ]]; do
    start_ns="$(date +%s%N)"
    dd if=/dev/zero of=/dev/null bs=1M count="$WORK_UNITS" status=none
    end_ns="$(date +%s%N)"
    elapsed_ms="$(awk -v s="$start_ns" -v e="$end_ns" 'BEGIN { printf "%.3f", (e - s) / 1000000 }')"

    printf '%s,%s,%s,%s,%s\n' "$LABEL" "$task" "$trial" "$WORK_UNITS" "$elapsed_ms" >>"$OUTPUT_CSV"
    echo "label=$LABEL task=$task trial=$trial work_units=$WORK_UNITS elapsed_ms=$elapsed_ms"

    total_runs="$((total_runs + 1))"
    trial="$((trial + 1))"
  done
done

if [[ "$total_runs" -eq 0 ]]; then
  echo "ERROR: no tasks were executed, check --hotspots." >&2
  exit 1
fi

echo "payload_csv=$OUTPUT_CSV total_runs=$total_runs"
