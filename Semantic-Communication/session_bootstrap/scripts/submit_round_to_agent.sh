#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_BASE_ENV="$SESSION_DIR/config/rpc_armv8.phytium_pi.2026-03-01.env"
DEFAULT_SESSION="main"
DEFAULT_LOCK_FILE="/tmp/tvm_metaschedule_agent_submit.lock"
OC_LIVE_BIN="/home/tianxing/.local/bin/oc-live"

usage() {
  cat <<'EOF'
Usage:
  submit_round_to_agent.sh [--base-env <path>] [--session <session_key>] [--run-tag <tag>] [--skip-full]

Flow:
  1) 生成唯一轮次 env（prepare_round_env.sh）
  2) 通过 oc-live 提交到指定 session（默认 main）
  3) Agent 按固定步骤执行：readiness -> quick -> full -> daily

Notes:
  - 该脚本用于“保持会话上下文共享”的无人值守触发。
  - 使用 flock 防重复提交。
EOF
}

BASE_ENV="$DEFAULT_BASE_ENV"
SESSION_KEY="$DEFAULT_SESSION"
RUN_TAG=""
SKIP_FULL=0
LOCK_FILE="$DEFAULT_LOCK_FILE"

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
    --session)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --session requires a value." >&2
        exit 1
      fi
      SESSION_KEY="$2"
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

if [[ -x "$OC_LIVE_BIN" ]]; then
  :
elif command -v oc-live >/dev/null 2>&1; then
  OC_LIVE_BIN="$(command -v oc-live)"
else
  echo "ERROR: oc-live not found (expected: /home/tianxing/.local/bin/oc-live)." >&2
  exit 127
fi

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
  echo "ERROR: another submit is in progress (lock: $LOCK_FILE_RESOLVED)" >&2
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

RUN_DATE="${DAILY_REPORT_DATE:-$(date +%F)}"
DAILY_OUTPUT="${DAILY_REPORT_FILE:-./session_bootstrap/reports/daily_${RUN_DATE}.md}"
DAILY_OUTPUT_RESOLVED="$(resolve_path "$DAILY_OUTPUT")"
RUN_ENV_RESOLVED="$(resolve_path "$RUN_ENV")"

FULL_LINE='3) bash ./session_bootstrap/scripts/run_full_placeholder.sh --env "'"$RUN_ENV_RESOLVED"'"'
if [[ "$SKIP_FULL" -eq 1 ]]; then
  FULL_LINE='3) （已跳过）full 阶段本轮不执行'
fi

PROMPT="$(
  cat <<EOF
在目录 /home/tianxing/tvm_metaschedule_execution_project 执行本轮自动化（无需再次询问我）：
1) bash ./session_bootstrap/scripts/check_rpc_readiness.sh --env "$RUN_ENV_RESOLVED"
2) bash ./session_bootstrap/scripts/run_quick.sh --env "$RUN_ENV_RESOLVED"
$FULL_LINE
4) bash ./session_bootstrap/scripts/summarize_to_daily.sh --env "$RUN_ENV_RESOLVED" --date "$RUN_DATE" --output "$DAILY_OUTPUT_RESOLVED"

执行要求：
- 每一步完成后立刻汇报：status + 关键产物路径。
- 如果某一步失败：停止后续步骤，并汇报失败日志路径与退出码。
- 最后一条消息必须给出本轮汇总（quick/full/daily 三项状态）。

本轮参数：
- run_env: $RUN_ENV_RESOLVED
- execution_id: ${EXECUTION_ID:-N/A}
- full_execution_id: ${FULL_EXECUTION_ID:-N/A}
- daily_report: $DAILY_OUTPUT_RESOLVED
EOF
)"

echo "[submit] session=$SESSION_KEY"
echo "[submit] run_env=$RUN_ENV_RESOLVED"
echo "[submit] execution_id=${EXECUTION_ID:-N/A}"
echo "[submit] full_execution_id=${FULL_EXECUTION_ID:-N/A}"
echo "[submit] daily_report=$DAILY_OUTPUT_RESOLVED"

"$OC_LIVE_BIN" "$PROMPT" "$SESSION_KEY"
