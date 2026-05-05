#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/rpc_armv8.example.env"

usage() {
  cat <<'EOF'
Usage:
  run_rpc_first_round.sh [--env <path>] [--simulate] [--skip-full]

Notes:
  - 首轮闭环默认顺序：readiness -> quick -> full -> daily summary -> experiment record
  - --simulate: 跳过 tracker 连通性检查，适合离线脚手架验证
  - --skip-full: 仅执行 quick + summary（调试时使用）
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
SIMULATE=0
SKIP_FULL=0

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
    --simulate)
      SIMULATE=1
      shift
      ;;
    --skip-full)
      SKIP_FULL=1
      shift
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

extract_md_field() {
  local file="$1"
  local key="$2"
  grep -E "^- ${key}:" "$file" | head -n 1 | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

require_var MODEL_NAME
require_var TARGET
require_var SHAPE_BUCKETS
require_var DEVICE_KEY
require_var RPC_TRACKER_HOST
require_var RPC_TRACKER_PORT
require_var TUNING_DB_DIR
require_var QUICK_BASELINE_CMD
require_var QUICK_CURRENT_CMD

if [[ "$SKIP_FULL" -eq 0 ]]; then
  require_var FULL_BASELINE_CMD
  require_var FULL_CURRENT_CMD
fi

REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
mkdir -p "$REPORT_DIR_RESOLVED" "$LOG_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DATE="$(date +%F)"
QUICK_RUN_ID="${EXECUTION_ID:-quick_rpc_${STAMP}}"
FULL_RUN_ID="${FULL_EXECUTION_ID:-full_rpc_${STAMP}}"
COMMAND_TEMPLATE_FILE="$REPORT_DIR_RESOLVED/rpc_commands_${STAMP}.md"
READINESS_FILE="$REPORT_DIR_RESOLVED/readiness_rpc_${RUN_DATE}.md"
DAILY_REPORT_FILE_RESOLVED="$(resolve_path "${DAILY_REPORT_FILE:-./session_bootstrap/reports/daily_rpc_${RUN_DATE}.md}")"
EXPERIMENT_RECORD_FILE="$REPORT_DIR_RESOLVED/experiment_record_${FULL_RUN_ID}.md"
RUN_ENV_FILE="$REPORT_DIR_RESOLVED/rpc_run_env_${STAMP}.env"

cat "$ENV_FILE" >"$RUN_ENV_FILE"
{
  echo
  echo "EXECUTION_ID=$QUICK_RUN_ID"
  echo "FULL_EXECUTION_ID=$FULL_RUN_ID"
} >>"$RUN_ENV_FILE"

bash "$SCRIPT_DIR/check_rpc_readiness.sh" --env "$RUN_ENV_FILE" --output "$READINESS_FILE"
bash "$SCRIPT_DIR/rpc_print_cmd_templates.sh" --env "$RUN_ENV_FILE" --output "$COMMAND_TEMPLATE_FILE"

if [[ "$SIMULATE" -eq 0 ]]; then
  if command -v timeout >/dev/null 2>&1; then
    if ! timeout 3 bash -lc "cat < /dev/null > /dev/tcp/${RPC_TRACKER_HOST}/${RPC_TRACKER_PORT}" 2>/dev/null; then
      echo "ERROR: tracker is unreachable at ${RPC_TRACKER_HOST}:${RPC_TRACKER_PORT}" >&2
      echo "Hint: use --simulate for offline validation." >&2
      exit 1
    fi
  else
    echo "WARN: timeout command not found, skip tracker connectivity probe."
  fi
else
  echo "SIMULATE=1, skip tracker connectivity probe."
fi

bash "$SCRIPT_DIR/run_quick.sh" --env "$RUN_ENV_FILE"
if [[ "$SKIP_FULL" -eq 0 ]]; then
  bash "$SCRIPT_DIR/run_full_placeholder.sh" --env "$RUN_ENV_FILE"
fi
bash "$SCRIPT_DIR/summarize_to_daily.sh" --env "$RUN_ENV_FILE" --date "$RUN_DATE" --output "$DAILY_REPORT_FILE_RESOLVED"

QUICK_REPORT="$REPORT_DIR_RESOLVED/${QUICK_RUN_ID}.md"
FULL_REPORT="$REPORT_DIR_RESOLVED/${FULL_RUN_ID}.md"

quick_status="N/A"
quick_baseline="N/A"
quick_current="N/A"
quick_samples="N/A"
if [[ -f "$QUICK_REPORT" ]]; then
  quick_status="$(extract_md_field "$QUICK_REPORT" "status")"
  quick_baseline="$(extract_md_field "$QUICK_REPORT" "baseline_median_ms")"
  quick_current="$(extract_md_field "$QUICK_REPORT" "current_median_ms")"
  quick_samples="baseline=$(extract_md_field "$QUICK_REPORT" "baseline_count"), current=$(extract_md_field "$QUICK_REPORT" "current_count")"
fi

full_status="N/A"
full_baseline="N/A"
full_current="N/A"
if [[ "$SKIP_FULL" -eq 0 && -f "$FULL_REPORT" ]]; then
  full_status="$(extract_md_field "$FULL_REPORT" "status")"
  full_baseline="$(extract_md_field "$FULL_REPORT" "baseline_elapsed_ms")"
  full_current="$(extract_md_field "$FULL_REPORT" "current_elapsed_ms")"
fi

cat >"$EXPERIMENT_RECORD_FILE" <<EOF
# 实验记录

- 实验ID：EXP-RPC-FIRST-ROUND-${STAMP}
- 日期时间：$(date -Iseconds)
- 负责人：${DAILY_OWNER:-${USER:-unknown}}
- 模式：$(if [[ "$SKIP_FULL" -eq 0 ]]; then echo "quick + full"; else echo "quick"; fi)
- 目标task（热点编号）：${FULL_HOTSPOT_TASKS:-N/A}
- 本轮唯一变量：${DAILY_SINGLE_CHANGE:-TODO}
- 变量取值：DEVICE_KEY=${DEVICE_KEY}; RPC_TRACKER_HOST=${RPC_TRACKER_HOST}; RPC_TRACKER_PORT=${RPC_TRACKER_PORT}
- 固定条件（target/shape/线程/测量参数）：target=${TARGET}; shape_buckets=${SHAPE_BUCKETS}; threads=${THREADS:-N/A}; quick_repeat=${QUICK_REPEAT:-N/A}; full_timeout_sec=${FULL_TIMEOUT_SEC:-N/A}
- 预期收益：在 ARMv8 RPC runner 条件下维持 baseline -> current 的可解释变化
- 实际结果：quick(${quick_status}) ${quick_baseline}ms -> ${quick_current}ms; ${quick_samples}$(if [[ "$SKIP_FULL" -eq 0 ]]; then printf '; full(%s) %sms -> %sms' "$full_status" "$full_baseline" "$full_current"; fi)
- 是否复现：$(if [[ "$SIMULATE" -eq 1 ]]; then echo "离线模拟（非真机）"; else echo "待真机确认"; fi)
- 失败样本信息（可选）：若失败，见 readiness/daily/log 报告
- 下一步：$(if [[ "$SIMULATE" -eq 1 ]]; then echo "替换为真机 tracker/server 与真实 TVM 命令后重跑"; else echo "执行夜间 full 热点并复查稳定性"; fi)

## 产物

- readiness：$READINESS_FILE
- run env snapshot：$RUN_ENV_FILE
- rpc command templates：$COMMAND_TEMPLATE_FILE
- quick report：$QUICK_REPORT
- full report：$FULL_REPORT
- daily report：$DAILY_REPORT_FILE_RESOLVED
EOF

echo "RPC first round completed"
echo "  readiness:        $READINESS_FILE"
echo "  run env:          $RUN_ENV_FILE"
echo "  command template: $COMMAND_TEMPLATE_FILE"
echo "  quick report:     $QUICK_REPORT"
echo "  full report:      $FULL_REPORT"
echo "  daily report:     $DAILY_REPORT_FILE_RESOLVED"
echo "  experiment:       $EXPERIMENT_RECORD_FILE"
