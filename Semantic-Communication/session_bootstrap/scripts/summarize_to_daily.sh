#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/local.env"

usage() {
  cat <<'EOF'
Usage:
  summarize_to_daily.sh [--env <path>] [--date <YYYY-MM-DD>] [--output <path>]

Notes:
  - Aggregates quick/full reports in reports/ and log snapshots in logs/.
  - If --env is omitted and config/local.env exists, it will be loaded.
  - Output defaults to: <REPORT_DIR>/daily_<YYYY-MM-DD>.md
EOF
}

ENV_FILE=""
TARGET_DATE="$(date +%F)"
OUTPUT_FILE=""

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
    --date)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --date requires YYYY-MM-DD." >&2
        exit 1
      fi
      TARGET_DATE="$2"
      shift 2
      ;;
    --output)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --output requires a file path." >&2
        exit 1
      fi
      OUTPUT_FILE="$2"
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

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: env file not found: $ENV_FILE" >&2
    exit 1
  fi
  # shellcheck source=/dev/null
  set -a
  source "$ENV_FILE"
  set +a
elif [[ -f "$DEFAULT_ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a
  source "$DEFAULT_ENV_FILE"
  set +a
fi

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

get_field() {
  local file="$1"
  local key="$2"
  grep -E "^- ${key}:" "$file" | head -n 1 | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

value_or_na() {
  local value="$1"
  if [[ -z "$value" ]]; then
    printf 'N/A\n'
  else
    printf '%s\n' "$value"
  fi
}

is_number() {
  local value="$1"
  [[ "$value" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

join_unique() {
  local out=""
  local item
  declare -A seen=()
  for item in "$@"; do
    [[ -z "$item" ]] && continue
    if [[ -z "${seen[$item]+x}" ]]; then
      seen["$item"]=1
      if [[ -n "$out" ]]; then
        out="${out}; ${item}"
      else
        out="$item"
      fi
    fi
  done

  if [[ -z "$out" ]]; then
    printf 'N/A\n'
  else
    printf '%s\n' "$out"
  fi
}

join_unique_limited() {
  local limit="$1"
  shift

  local out=""
  local item
  local count=0
  declare -A seen=()
  for item in "$@"; do
    [[ -z "$item" ]] && continue
    if [[ -n "${seen[$item]+x}" ]]; then
      continue
    fi
    seen["$item"]=1
    count="$((count + 1))"
    if [[ "$count" -gt "$limit" ]]; then
      break
    fi
    if [[ -n "$out" ]]; then
      out="${out}; ${item}"
    else
      out="$item"
    fi
  done

  if [[ -z "$out" ]]; then
    printf 'N/A\n'
  else
    printf '%s\n' "$out"
  fi
}

resolve_report_epoch() {
  local file="$1"
  local timestamp="$2"
  local report_epoch=""

  if [[ -n "$timestamp" ]]; then
    report_epoch="$(date -d "$timestamp" +%s 2>/dev/null || true)"
  fi

  if [[ -n "$report_epoch" ]]; then
    printf '%s\n' "$report_epoch"
  else
    date -r "$file" +%s
  fi
}

if ! [[ "$TARGET_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "ERROR: --date must be in YYYY-MM-DD format." >&2
  exit 1
fi

LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

if [[ -n "$OUTPUT_FILE" ]]; then
  OUTPUT_FILE_RESOLVED="$(resolve_path "$OUTPUT_FILE")"
else
  OUTPUT_FILE_RESOLVED="$REPORT_DIR_RESOLVED/daily_${TARGET_DATE}.md"
fi

mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED" "$(dirname "$OUTPUT_FILE_RESOLVED")"

report_count=0
quick_count=0
full_count=0
failed_report_count=0
candidate_report_count=0
deduped_report_count=0

declare -a run_rows=()
declare -a model_shape_pairs=()
declare -a target_thread_pairs=()
declare -a latency_lines=()
declare -a sample_lines=()
declare -a stability_lines=()
declare -a report_paths=()
declare -a artifact_paths=()
declare -a selected_report_keys=()
declare -A selected_report_by_key=()
declare -A selected_report_epoch=()

shopt -s nullglob
for report_file in "$REPORT_DIR_RESOLVED"/*.md; do
  if [[ "$report_file" == "$OUTPUT_FILE_RESOLVED" ]]; then
    continue
  fi

  mode="$(get_field "$report_file" "mode")"
  if [[ "$mode" != "quick" && "$mode" != "full" ]]; then
    continue
  fi

  timestamp="$(get_field "$report_file" "timestamp")"
  if [[ -n "$timestamp" ]]; then
    report_date="${timestamp%%T*}"
    report_date="${report_date%% *}"
  else
    report_date="$(date -r "$report_file" +%F)"
  fi

  if [[ "$report_date" != "$TARGET_DATE" ]]; then
    continue
  fi

  execution_id_raw="$(get_field "$report_file" "execution_id")"
  dedupe_key="${mode}|${execution_id_raw:-$(basename "$report_file")}"
  report_epoch="$(resolve_report_epoch "$report_file" "$timestamp")"
  candidate_report_count="$((candidate_report_count + 1))"

  if [[ -z "${selected_report_by_key[$dedupe_key]+x}" ]]; then
    selected_report_keys+=("$dedupe_key")
    selected_report_by_key["$dedupe_key"]="$report_file"
    selected_report_epoch["$dedupe_key"]="$report_epoch"
  elif [[ "$report_epoch" -ge "${selected_report_epoch[$dedupe_key]}" ]]; then
    selected_report_by_key["$dedupe_key"]="$report_file"
    selected_report_epoch["$dedupe_key"]="$report_epoch"
  fi
done
shopt -u nullglob

for dedupe_key in "${selected_report_keys[@]}"; do
  report_file="${selected_report_by_key[$dedupe_key]}"
  [[ -z "$report_file" ]] && continue

  report_count="$((report_count + 1))"
  report_paths+=("$report_file")

  mode="$(get_field "$report_file" "mode")"
  execution_id="$(value_or_na "$(get_field "$report_file" "execution_id")")"
  model_name="$(value_or_na "$(get_field "$report_file" "model_name")")"
  target="$(value_or_na "$(get_field "$report_file" "target")")"
  shape_buckets="$(value_or_na "$(get_field "$report_file" "shape_buckets")")"
  threads="$(value_or_na "$(get_field "$report_file" "threads")")"
  status="$(get_field "$report_file" "status")"
  if [[ -z "$status" ]]; then
    status="success"
  fi
  improvement_pct="$(value_or_na "$(get_field "$report_file" "improvement_pct")")"
  delta_ms="$(value_or_na "$(get_field "$report_file" "delta_ms_current_minus_baseline")")"

  run_rows+=("| $execution_id | $mode | $model_name | $target | $shape_buckets | $status | $improvement_pct | $report_file |")
  model_shape_pairs+=("${model_name}:${shape_buckets}")
  target_thread_pairs+=("${target}/threads=${threads}")

  if [[ "$mode" == "quick" ]]; then
    quick_count="$((quick_count + 1))"
    baseline_median="$(get_field "$report_file" "baseline_median_ms")"
    current_median="$(get_field "$report_file" "current_median_ms")"
    baseline_count="$(get_field "$report_file" "baseline_count")"
    current_count="$(get_field "$report_file" "current_count")"
    baseline_var="$(get_field "$report_file" "baseline_variance_ms2")"
    current_var="$(get_field "$report_file" "current_variance_ms2")"
    if [[ -n "$baseline_count" || -n "$current_count" ]]; then
      sample_lines+=("${execution_id}(quick): baseline=${baseline_count:-N/A}, current=${current_count:-N/A}")
    fi
    if is_number "$baseline_median" && is_number "$current_median" && is_number "$delta_ms" && is_number "$improvement_pct"; then
      latency_lines+=("${execution_id}(quick): ${baseline_median}ms -> ${current_median}ms (delta ${delta_ms}ms, ${improvement_pct}%)")
    elif [[ -n "$baseline_median" || -n "$current_median" ]]; then
      latency_lines+=("${execution_id}(quick): status=${status}, baseline=${baseline_median:-N/A}, current=${current_median:-N/A}")
    fi
    if is_number "$baseline_var" && is_number "$current_var"; then
      stability_lines+=("${execution_id}(quick): var ${baseline_var:-N/A} -> ${current_var:-N/A}")
    elif [[ -n "$baseline_var" || -n "$current_var" ]]; then
      stability_lines+=("${execution_id}(quick): status=${status}, var ${baseline_var:-N/A} -> ${current_var:-N/A}")
    fi
  else
    full_count="$((full_count + 1))"
    baseline_elapsed="$(get_field "$report_file" "baseline_elapsed_ms")"
    current_elapsed="$(get_field "$report_file" "current_elapsed_ms")"
    baseline_count="$(get_field "$report_file" "baseline_count")"
    current_count="$(get_field "$report_file" "current_count")"
    if [[ -n "$baseline_count" || -n "$current_count" ]]; then
      sample_lines+=("${execution_id}(full): baseline=${baseline_count:-N/A}, current=${current_count:-N/A}")
    fi
    if is_number "$baseline_elapsed" && is_number "$current_elapsed" && is_number "$delta_ms" && is_number "$improvement_pct"; then
      latency_lines+=("${execution_id}(full): ${baseline_elapsed}ms -> ${current_elapsed}ms (delta ${delta_ms}ms, ${improvement_pct}%)")
    elif [[ -n "$baseline_elapsed" || -n "$current_elapsed" ]]; then
      latency_lines+=("${execution_id}(full): status=${status}, baseline=${baseline_elapsed:-N/A}, current=${current_elapsed:-N/A}")
    fi
  fi

  if [[ "$status" != "success" ]]; then
    failed_report_count="$((failed_report_count + 1))"
  fi

  log_file="$(get_field "$report_file" "log_file")"
  raw_csv_file="$(get_field "$report_file" "raw_csv_file")"
  artifact_paths+=("$report_file" "$log_file" "$raw_csv_file")
done

deduped_report_count="$((candidate_report_count - report_count))"

log_count=0
error_like_log_count=0
declare -a today_logs=()

shopt -s nullglob
for log_file in "$LOG_DIR_RESOLVED"/*.log; do
  if [[ "$(date -r "$log_file" +%F)" != "$TARGET_DATE" ]]; then
    continue
  fi

  log_count="$((log_count + 1))"
  today_logs+=("$log_file")
  if grep -Eiq "failed with exit_code|full run failed|ERROR:|timed out|status=failed" "$log_file"; then
    error_like_log_count="$((error_like_log_count + 1))"
  fi
done
shopt -u nullglob

if [[ "$quick_count" -gt 0 && "$full_count" -gt 0 ]]; then
  mode_text="quick + full"
elif [[ "$quick_count" -gt 0 ]]; then
  mode_text="quick"
elif [[ "$full_count" -gt 0 ]]; then
  mode_text="full"
else
  mode_text="N/A"
fi

model_shape_text="$(join_unique "${model_shape_pairs[@]}")"
target_thread_text="$(join_unique "${target_thread_pairs[@]}")"
latency_text="$(join_unique "${latency_lines[@]}")"
sample_text="$(join_unique "${sample_lines[@]}")"
stability_text="$(join_unique "${stability_lines[@]}")"
report_samples="$(join_unique_limited 3 "${report_paths[@]}")"
log_samples="$(join_unique_limited 3 "${today_logs[@]}")"
artifact_samples="$(join_unique_limited 5 "${artifact_paths[@]}")"

if [[ "$failed_report_count" -gt 0 || "$error_like_log_count" -gt 0 || "$deduped_report_count" -gt 0 ]]; then
  issue_text="failed_reports=${failed_report_count}; logs_with_error_keywords=${error_like_log_count}; deduped_reports=${deduped_report_count}"
else
  issue_text="未发现失败关键词。"
fi

if [[ "$report_count" -eq 0 ]]; then
  conclusion_text="当日未找到 quick/full 报告，请先运行执行脚本。"
else
  conclusion_text="已聚合 ${report_count} 份去重后报告（候选=${candidate_report_count}; quick=${quick_count}, full=${full_count}）。"
fi

{
  cat <<EOF
# Daily Report

- 日期：$TARGET_DATE
- 执行人：${DAILY_OWNER:-${USER:-unknown}}
- 今日唯一改动变量：${DAILY_SINGLE_CHANGE:-TODO}
- 实验模式：$mode_text
- 目标模型与shape桶：$model_shape_text
- target与线程配置：$target_thread_text
- 延迟对比（baseline -> current）：$latency_text
- 有效样本（baseline/current）：$sample_text
- 稳定性（复测中位数/方差）：$stability_text
- 产物路径（DB/日志/报告）：reports_dir=$REPORT_DIR_RESOLVED; logs_dir=$LOG_DIR_RESOLVED; artifacts=$artifact_samples
- 异常与处理：$issue_text
- 结论：$conclusion_text
- 明日单一改动计划：${DAILY_NEXT_CHANGE:-TODO}

## Runs

| execution_id | mode | model | target | shape_buckets | status | improvement_pct | report_path |
|---|---|---|---|---|---|---|---|
EOF

  if [[ "${#run_rows[@]}" -eq 0 ]]; then
    echo "| N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
  else
    printf '%s\n' "${run_rows[@]}"
  fi

  cat <<EOF

## Log Snapshot

- 当日日志文件数：$log_count
- 命中失败关键词日志数：$error_like_log_count
- 日志路径样例：$log_samples
- 报告路径样例：$report_samples

## Metadata

- generated_at: $(date -Iseconds)
- generated_by: summarize_to_daily.sh
EOF
} >"$OUTPUT_FILE_RESOLVED"

echo "Daily summary generated"
echo "  report: $OUTPUT_FILE_RESOLVED"
