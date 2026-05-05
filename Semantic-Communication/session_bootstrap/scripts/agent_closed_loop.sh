#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

DEFAULT_PHYTIUM_ENV="$SESSION_DIR/config/rpc_armv8.phytium_pi.2026-03-01.env"
DEFAULT_SNAPDRAGON_ENV="$SESSION_DIR/config/rpc_armv8.lenovo.2026-03-01.env"
DEFAULT_TARGET="phytium"
DEFAULT_ROUNDS=3
DEFAULT_SESSION="main"
DEFAULT_WORK_DIR="./session_bootstrap/config/agent_loops"
DEFAULT_DECISION_DIR="./session_bootstrap/reports/agent_decisions"
DEFAULT_HISTORY_FILE="./session_bootstrap/reports/agent_loop_history.csv"
DEFAULT_LOCK_FILE="/tmp/tvm_metaschedule_agent_closed_loop.lock"
DEFAULT_OC_LIVE_BIN="/home/tianxing/.local/bin/oc-live"
DEFAULT_DELTA_WAIT_SEC=90

usage() {
  cat <<'EOF'
Usage:
  agent_closed_loop.sh [--target phytium|snapdragon] [--rounds N] [--session <name>]
                       [--run-tag <tag>] [--phytium-env <path>] [--snapdragon-env <path>]
                       [--work-dir <path>] [--decision-dir <path>] [--history-file <path>]
                       [--lock-file <path>] [--delta-wait-sec <sec>]
                       [--prep-skip-full] [--allow-command-edits]
                       [--require-agent-delta]

Flow:
  1) 选择目标设备（phytium=final，snapdragon=prep），复制 base env 为工作 env
  2) 每轮执行本地自动化（readiness -> quick -> full -> daily）
  3) 非最后一轮：提交给 Agent 分析本轮结果并产出 delta env
  4) 应用 delta 到工作 env，进入下一轮

Notes:
  - 该脚本体现“Agent 决策 + Local 执行”闭环。
  - Agent 决策通过 oc-live 提交到指定 session（默认 main）。
  - 为安全起见，默认不允许 Agent 修改 QUICK/FULL 命令；可用 --allow-command-edits 放开。
EOF
}

TARGET="$DEFAULT_TARGET"
ROUNDS="$DEFAULT_ROUNDS"
SESSION_KEY="$DEFAULT_SESSION"
RUN_TAG=""
PHYTIUM_ENV="$DEFAULT_PHYTIUM_ENV"
SNAPDRAGON_ENV="$DEFAULT_SNAPDRAGON_ENV"
WORK_DIR="$DEFAULT_WORK_DIR"
DECISION_DIR="$DEFAULT_DECISION_DIR"
HISTORY_FILE="$DEFAULT_HISTORY_FILE"
LOCK_FILE="$DEFAULT_LOCK_FILE"
DELTA_WAIT_SEC="$DEFAULT_DELTA_WAIT_SEC"
PREP_SKIP_FULL=0
ALLOW_COMMAND_EDITS=0
REQUIRE_AGENT_DELTA=0
OC_LIVE_BIN="$DEFAULT_OC_LIVE_BIN"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --target requires phytium|snapdragon." >&2
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --rounds)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --rounds requires a number." >&2
        exit 1
      fi
      ROUNDS="$2"
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
    --phytium-env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --phytium-env requires a path." >&2
        exit 1
      fi
      PHYTIUM_ENV="$2"
      shift 2
      ;;
    --snapdragon-env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --snapdragon-env requires a path." >&2
        exit 1
      fi
      SNAPDRAGON_ENV="$2"
      shift 2
      ;;
    --work-dir)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --work-dir requires a path." >&2
        exit 1
      fi
      WORK_DIR="$2"
      shift 2
      ;;
    --decision-dir)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --decision-dir requires a path." >&2
        exit 1
      fi
      DECISION_DIR="$2"
      shift 2
      ;;
    --history-file)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --history-file requires a path." >&2
        exit 1
      fi
      HISTORY_FILE="$2"
      shift 2
      ;;
    --lock-file)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --lock-file requires a path." >&2
        exit 1
      fi
      LOCK_FILE="$2"
      shift 2
      ;;
    --delta-wait-sec)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --delta-wait-sec requires a number." >&2
        exit 1
      fi
      DELTA_WAIT_SEC="$2"
      shift 2
      ;;
    --prep-skip-full)
      PREP_SKIP_FULL=1
      shift
      ;;
    --allow-command-edits)
      ALLOW_COMMAND_EDITS=1
      shift
      ;;
    --require-agent-delta)
      REQUIRE_AGENT_DELTA=1
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

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

field_from_summary() {
  local file="$1"
  local key="$2"
  grep -E "^- ${key}:" "$file" | head -n 1 | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

csv_escape() {
  local value="${1:-}"
  value="${value//\"/\"\"}"
  printf '"%s"' "$value"
}

sanitize_token() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//'
}

assignment_from_file() {
  local file="$1"
  local key="$2"
  grep -E "^${key}=" "$file" | tail -n 1 || true
}

check_prep_alignment_with_final() {
  local final_env="$1"
  local prep_env="$2"
  local mismatch=0
  local key final_line prep_line
  local keys=(MODEL_NAME TARGET SHAPE_BUCKETS THREADS)

  echo "[loop] alignment-check final_env=$final_env prep_env=$prep_env"
  for key in "${keys[@]}"; do
    final_line="$(assignment_from_file "$final_env" "$key")"
    prep_line="$(assignment_from_file "$prep_env" "$key")"

    if [[ -z "$final_line" || -z "$prep_line" ]]; then
      echo "ERROR: alignment key missing: $key (final='$final_line', prep='$prep_line')" >&2
      mismatch=1
      continue
    fi

    if [[ "$final_line" != "$prep_line" ]]; then
      echo "ERROR: prep/final mismatch on $key" >&2
      echo "  final: $final_line" >&2
      echo "  prep : $prep_line" >&2
      mismatch=1
    fi
  done

  if [[ "$mismatch" -ne 0 ]]; then
    echo "ERROR: snapdragon prep must keep phytium final target parameters aligned." >&2
    return 1
  fi

  echo "[loop] alignment-check passed"
  return 0
}

apply_delta_to_env() {
  local base_env="$1"
  local delta_env="$2"
  local output_env="$3"
  local allow_command_edits="$4"

  declare -A updates=()
  declare -a update_order=()
  local raw key

  while IFS= read -r raw || [[ -n "$raw" ]]; do
    [[ -z "$raw" ]] && continue
    [[ "$raw" =~ ^[[:space:]]*# ]] && continue
    if [[ ! "$raw" =~ ^[A-Z][A-Z0-9_]*= ]]; then
      echo "[warn] ignore invalid delta line: $raw"
      continue
    fi

    key="${raw%%=*}"
    case "$key" in
      EXECUTION_ID|FULL_EXECUTION_ID|DAILY_REPORT_FILE|DAILY_REPORT_DATE)
        echo "[warn] ignore reserved key in delta: $key"
        continue
        ;;
      QUICK_BASELINE_CMD|QUICK_CURRENT_CMD|FULL_BASELINE_CMD|FULL_CURRENT_CMD)
        if [[ "$allow_command_edits" -ne 1 ]]; then
          echo "[warn] command edit blocked (use --allow-command-edits to enable): $key"
          continue
        fi
        ;;
    esac

    updates["$key"]="$raw"
    update_order+=("$key")
  done <"$delta_env"

  local tmp_file
  tmp_file="$(mktemp)"
  while IFS= read -r raw || [[ -n "$raw" ]]; do
    if [[ "$raw" =~ ^([A-Z][A-Z0-9_]*)= ]]; then
      key="${BASH_REMATCH[1]}"
      if [[ -n "${updates[$key]+x}" ]]; then
        printf '%s\n' "${updates[$key]}" >>"$tmp_file"
        unset 'updates[$key]'
        continue
      fi
    fi
    printf '%s\n' "$raw" >>"$tmp_file"
  done <"$base_env"

  local item
  for item in "${update_order[@]}"; do
    if [[ -n "${updates[$item]+x}" ]]; then
      printf '%s\n' "${updates[$item]}" >>"$tmp_file"
      unset 'updates[$item]'
    fi
  done

  mv "$tmp_file" "$output_env"
}

if [[ "$TARGET" != "phytium" && "$TARGET" != "snapdragon" ]]; then
  echo "ERROR: --target must be phytium|snapdragon." >&2
  exit 1
fi

if ! [[ "$ROUNDS" =~ ^[0-9]+$ ]] || [[ "$ROUNDS" -lt 1 ]]; then
  echo "ERROR: --rounds must be a positive integer." >&2
  exit 1
fi

if ! [[ "$DELTA_WAIT_SEC" =~ ^[0-9]+$ ]] || [[ "$DELTA_WAIT_SEC" -lt 0 ]]; then
  echo "ERROR: --delta-wait-sec must be a non-negative integer." >&2
  exit 1
fi

if ! command -v flock >/dev/null 2>&1; then
  echo "ERROR: flock command not found. Install util-linux first." >&2
  exit 1
fi

if [[ -x "$OC_LIVE_BIN" ]]; then
  :
elif command -v oc-live >/dev/null 2>&1; then
  OC_LIVE_BIN="$(command -v oc-live)"
else
  echo "ERROR: oc-live not found. agent closed loop requires OpenClaw session runtime." >&2
  exit 127
fi

PHYTIUM_ENV_RESOLVED="$(resolve_path "$PHYTIUM_ENV")"
SNAPDRAGON_ENV_RESOLVED="$(resolve_path "$SNAPDRAGON_ENV")"
WORK_DIR_RESOLVED="$(resolve_path "$WORK_DIR")"
DECISION_DIR_RESOLVED="$(resolve_path "$DECISION_DIR")"
HISTORY_FILE_RESOLVED="$(resolve_path "$HISTORY_FILE")"
LOCK_FILE_RESOLVED="$(resolve_path "$LOCK_FILE")"

if [[ ! -f "$PHYTIUM_ENV_RESOLVED" ]]; then
  echo "ERROR: phytium env not found: $PHYTIUM_ENV_RESOLVED" >&2
  exit 1
fi
if [[ ! -f "$SNAPDRAGON_ENV_RESOLVED" ]]; then
  echo "ERROR: snapdragon env not found: $SNAPDRAGON_ENV_RESOLVED" >&2
  exit 1
fi

mkdir -p "$WORK_DIR_RESOLVED" "$DECISION_DIR_RESOLVED" "$(dirname "$HISTORY_FILE_RESOLVED")" "$(dirname "$LOCK_FILE_RESOLVED")"
exec 9>"$LOCK_FILE_RESOLVED"
if ! flock -n 9; then
  echo "ERROR: another agent_closed_loop is running (lock: $LOCK_FILE_RESOLVED)" >&2
  exit 3
fi

if [[ -z "$RUN_TAG" ]]; then
  RUN_TAG="agent_loop_$(date +%Y%m%d_%H%M%S)"
fi
RUN_TAG="$(sanitize_token "$RUN_TAG")"
if [[ -z "$RUN_TAG" ]]; then
  RUN_TAG="agent_loop"
fi

if [[ "$TARGET" == "phytium" ]]; then
  STAGE="final"
  BASE_ENV="$PHYTIUM_ENV_RESOLVED"
else
  STAGE="prep"
  BASE_ENV="$SNAPDRAGON_ENV_RESOLVED"
  check_prep_alignment_with_final "$PHYTIUM_ENV_RESOLVED" "$SNAPDRAGON_ENV_RESOLVED"
fi

WORK_ENV="$WORK_DIR_RESOLVED/${RUN_TAG}_${TARGET}_working.env"
cp "$BASE_ENV" "$WORK_ENV"

if [[ ! -f "$HISTORY_FILE_RESOLVED" ]]; then
  echo "\"timestamp\",\"run_tag\",\"iter\",\"target\",\"stage\",\"session\",\"run_rc\",\"summary_file\",\"quick_report\",\"full_report\",\"daily_report\",\"delta_file\",\"delta_applied\",\"work_env\"" >"$HISTORY_FILE_RESOLVED"
fi

echo "[loop] run_tag=$RUN_TAG target=$TARGET stage=$STAGE rounds=$ROUNDS session=$SESSION_KEY"
echo "[loop] base_env=$BASE_ENV"
echo "[loop] work_env=$WORK_ENV"

ITER=1
while [[ "$ITER" -le "$ROUNDS" ]]; do
  ROUND_TAG="${RUN_TAG}_${TARGET}_r$(printf '%02d' "$ITER")"
  ROUND_STDOUT="$DECISION_DIR_RESOLVED/${ROUND_TAG}.local.stdout.log"
  ROUND_SUMMARY=""
  RUN_RC=0

  echo "[loop] iter=$ITER/$ROUNDS round_tag=$ROUND_TAG start"
  RUN_CMD=(bash "$SCRIPT_DIR/auto_round_local.sh" --base-env "$WORK_ENV" --run-tag "$ROUND_TAG")
  if [[ "$TARGET" == "snapdragon" && "$PREP_SKIP_FULL" -eq 1 ]]; then
    RUN_CMD+=(--skip-full)
  fi

  set +e
  (
    # Prevent lock FD inheritance into child trees.
    exec 9>&-
    "${RUN_CMD[@]}"
  ) | tee "$ROUND_STDOUT"
  RUN_RC=$?
  set -e

  ROUND_SUMMARY="$(sed -n 's/.*summary_file=//p' "$ROUND_STDOUT" | tail -n 1)"
  if [[ -z "$ROUND_SUMMARY" || ! -f "$ROUND_SUMMARY" ]]; then
    ROUND_SUMMARY="$(ls -1t "$PROJECT_DIR"/session_bootstrap/reports/auto_round_summary_*.md 2>/dev/null | head -n 1 || true)"
  fi

  QUICK_REPORT=""
  FULL_REPORT=""
  DAILY_REPORT=""
  if [[ -n "$ROUND_SUMMARY" && -f "$ROUND_SUMMARY" ]]; then
    QUICK_REPORT="$(field_from_summary "$ROUND_SUMMARY" "quick_report")"
    FULL_REPORT="$(field_from_summary "$ROUND_SUMMARY" "full_report")"
    DAILY_REPORT="$(field_from_summary "$ROUND_SUMMARY" "daily_report")"
  fi

  DELTA_FILE=""
  DELTA_APPLIED=0

  if [[ "$ITER" -lt "$ROUNDS" ]]; then
    DELTA_FILE="$DECISION_DIR_RESOLVED/${ROUND_TAG}.delta.env"
    DECISION_NOTE="$DECISION_DIR_RESOLVED/${ROUND_TAG}.decision.md"
    AGENT_STDOUT="$DECISION_DIR_RESOLVED/${ROUND_TAG}.agent.stdout.log"
    rm -f "$DELTA_FILE" "$DECISION_NOTE"
    AGENT_SUBMIT_TS="$(date +%s)"

    AGENT_PROMPT="$(
      cat <<EOF
请作为 MetaSchedule 外环策略代理，为“下一轮”产出 env 增量文件。

工作目录：/home/tianxing/tvm_metaschedule_execution_project
当前轮次信息：
- target: $TARGET
- stage: $STAGE
- iter: $ITER/$ROUNDS
- summary: ${ROUND_SUMMARY:-N/A}
- quick_report: ${QUICK_REPORT:-N/A}
- full_report: ${FULL_REPORT:-N/A}
- daily_report: ${DAILY_REPORT:-N/A}
- current_work_env: $WORK_ENV

你必须完成两个文件：
1) delta 文件（必做）：$DELTA_FILE
2) 决策说明（必做）：$DECISION_NOTE

delta 文件规则（严格遵守）：
- 仅允许 KEY=VALUE 行；可含注释行（# 开头）
- 不要输出 markdown，不要解释文本
- 不允许写这些键：EXECUTION_ID, FULL_EXECUTION_ID, DAILY_REPORT_FILE, DAILY_REPORT_DATE
- 默认不要改 QUICK/FULL 命令本体，优先调整预算/重复次数/单变量实验参数
- 若建议“不改参数”，请写：# no_change

建议优先调整键（按需要选择）：
- QUICK_REPEAT / QUICK_TIMEOUT_SEC / FULL_TIMEOUT_SEC
- FULL_HOTSPOT_TASKS / FULL_TRIALS_PER_TASK
- REMOTE_SNR_BASELINE / REMOTE_SNR_CURRENT
- REMOTE_BATCH_BASELINE / REMOTE_BATCH_CURRENT
- DAILY_SINGLE_CHANGE / DAILY_NEXT_CHANGE

执行要求：
- 直接在终端写入上述两个文件并覆盖旧文件
- 最后只回复一行状态：delta_ready 或 delta_no_change
EOF
    )"

    echo "[loop] iter=$ITER agent decision submit -> $SESSION_KEY"
    set +e
    (
      # Prevent lock FD inheritance into agent subprocesses.
      exec 9>&-
      "$OC_LIVE_BIN" "$AGENT_PROMPT" "$SESSION_KEY"
    ) >"$AGENT_STDOUT" 2>&1
    AGENT_RC=$?
    set -e
    echo "[loop] iter=$ITER agent rc=$AGENT_RC log=$AGENT_STDOUT"

    FOUND_DELTA=0
    WAIT_LEFT="$DELTA_WAIT_SEC"
    while [[ "$WAIT_LEFT" -ge 0 ]]; do
      if [[ -f "$DELTA_FILE" ]]; then
        DELTA_MTIME="$(date -r "$DELTA_FILE" +%s 2>/dev/null || echo 0)"
        if [[ "$DELTA_MTIME" -ge "$AGENT_SUBMIT_TS" ]]; then
          FOUND_DELTA=1
          break
        fi
      fi
      if [[ "$WAIT_LEFT" -eq 0 ]]; then
        break
      fi
      sleep 3
      if [[ "$WAIT_LEFT" -lt 3 ]]; then
        WAIT_LEFT=0
      else
        WAIT_LEFT="$((WAIT_LEFT - 3))"
      fi
    done

    if [[ "$FOUND_DELTA" -eq 1 ]]; then
      apply_delta_to_env "$WORK_ENV" "$DELTA_FILE" "$WORK_ENV" "$ALLOW_COMMAND_EDITS"
      DELTA_APPLIED=1
      echo "[loop] iter=$ITER delta applied from $DELTA_FILE"
    else
      echo "[loop] iter=$ITER no usable delta file produced within ${DELTA_WAIT_SEC}s"
      if [[ "$REQUIRE_AGENT_DELTA" -eq 1 ]]; then
        echo "ERROR: agent delta is required but missing: $DELTA_FILE" >&2
        exit 4
      fi
    fi
  fi

  {
    csv_escape "$(date -Iseconds)"
    printf ','
    csv_escape "$RUN_TAG"
    printf ','
    csv_escape "$ITER"
    printf ','
    csv_escape "$TARGET"
    printf ','
    csv_escape "$STAGE"
    printf ','
    csv_escape "$SESSION_KEY"
    printf ','
    csv_escape "$RUN_RC"
    printf ','
    csv_escape "${ROUND_SUMMARY:-}"
    printf ','
    csv_escape "${QUICK_REPORT:-}"
    printf ','
    csv_escape "${FULL_REPORT:-}"
    printf ','
    csv_escape "${DAILY_REPORT:-}"
    printf ','
    csv_escape "${DELTA_FILE:-}"
    printf ','
    csv_escape "$DELTA_APPLIED"
    printf ','
    csv_escape "$WORK_ENV"
    printf '\n'
  } >>"$HISTORY_FILE_RESOLVED"

  if [[ "$RUN_RC" -ne 0 ]]; then
    echo "[loop] iter=$ITER failed rc=$RUN_RC, stop loop"
    exit "$RUN_RC"
  fi

  ITER="$((ITER + 1))"
done

echo "[loop] completed run_tag=$RUN_TAG target=$TARGET rounds=$ROUNDS"
echo "[loop] history_file=$HISTORY_FILE_RESOLVED"
echo "[loop] final_work_env=$WORK_ENV"
