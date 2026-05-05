#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/rpc_armv8.example.env"

usage() {
  cat <<'EOF'
Usage:
  rpc_print_cmd_templates.sh [--env <path>] [--output <path>]

Notes:
  - 输出 tracker / rpc_server / client(quick+full) 可执行命令模板。
  - 不会实际启动任何进程。
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
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

PYTHON_BIN="${TVM_PYTHON:-python3}"
TRACKER_BIND_HOST="${RPC_TRACKER_BIND_HOST:-0.0.0.0}"
TRACKER_HOST="${RPC_TRACKER_HOST:-127.0.0.1}"
TRACKER_PORT="${RPC_TRACKER_PORT:-9190}"
SERVER_HOST="${RPC_SERVER_HOST:-0.0.0.0}"
SERVER_PORT="${RPC_SERVER_PORT:-9090}"
SERVER_PORT_END="${RPC_SERVER_PORT_END:-9099}"
DEVICE_KEY_VALUE="${DEVICE_KEY:-armv8}"
ENV_FILE_RESOLVED="$(resolve_path "$ENV_FILE")"

CONTENT="$(
  cat <<EOF
# RPC Command Templates

- generated_at: $(date -Iseconds)
- env_file: $ENV_FILE_RESOLVED

## 1) Tracker（开发机，builder/orchestrator 侧）

\`\`\`bash
$PYTHON_BIN -m tvm.exec.rpc_tracker --host "$TRACKER_BIND_HOST" --port "$TRACKER_PORT"
\`\`\`

## 2) RPC Server（ARMv8 真机，runner 侧）

\`\`\`bash
$PYTHON_BIN -m tvm.exec.rpc_server --tracker "$TRACKER_HOST:$TRACKER_PORT" --key "$DEVICE_KEY_VALUE" --host "$SERVER_HOST" --port "$SERVER_PORT" --port-end "$SERVER_PORT_END"
\`\`\`

## 3) Client（开发机，quick/full 触发）

\`\`\`bash
bash "$SESSION_DIR/scripts/run_quick.sh" --env "$ENV_FILE_RESOLVED"
bash "$SESSION_DIR/scripts/run_full_placeholder.sh" --env "$ENV_FILE_RESOLVED"
\`\`\`

## 4) Client（一键首轮闭环入口）

\`\`\`bash
bash "$SESSION_DIR/scripts/run_rpc_first_round.sh" --env "$ENV_FILE_RESOLVED"
\`\`\`

## 5) 当前 env 中的 quick/full payload 命令

\`\`\`bash
# quick
${QUICK_BASELINE_CMD:-<missing QUICK_BASELINE_CMD>}
${QUICK_CURRENT_CMD:-<missing QUICK_CURRENT_CMD>}

# full
${FULL_BASELINE_CMD:-<missing FULL_BASELINE_CMD>}
${FULL_CURRENT_CMD:-<missing FULL_CURRENT_CMD>}
\`\`\`

## 6) RPC Tune 闭环（笔记本搜索/编译 + 飞腾派测量）

### 6a) 准备：拉取模型文件到本机

\`\`\`bash
bash "$SESSION_DIR/scripts/manage_rpc_services.sh" --env "$ENV_FILE_RESOLVED" prepare
\`\`\`

### 6b) 启动 RPC 服务

\`\`\`bash
bash "$SESSION_DIR/scripts/manage_rpc_services.sh" --env "$ENV_FILE_RESOLVED" start-all
\`\`\`

### 6c) 一键 tune + quick + full + daily 闭环

\`\`\`bash
bash "$SESSION_DIR/scripts/run_rpc_tune.sh" --env "$ENV_FILE_RESOLVED"
\`\`\`

### 6d) 仅 tune + quick（跳过 full）

\`\`\`bash
bash "$SESSION_DIR/scripts/run_rpc_tune.sh" --env "$ENV_FILE_RESOLVED" --skip-full
\`\`\`

### 6e) 本机 smoke test（不需要飞腾派）

\`\`\`bash
bash "$SESSION_DIR/scripts/run_rpc_tune.sh" --env "$ENV_FILE_RESOLVED" --runner local --skip-services
\`\`\`

### 6f) 停止 RPC 服务

\`\`\`bash
bash "$SESSION_DIR/scripts/manage_rpc_services.sh" --env "$ENV_FILE_RESOLVED" stop-all
\`\`\`

### 6g) Tune 参数（当前 env）

- ONNX_MODEL_PATH: ${ONNX_MODEL_PATH:-<not set>}
- TUNE_INPUT_SHAPE: ${TUNE_INPUT_SHAPE:-<not set>}
- TUNE_TOTAL_TRIALS: ${TUNE_TOTAL_TRIALS:-<not set>}
- TUNE_OUTPUT_DIR: ${TUNE_OUTPUT_DIR:-<not set>}
- TUNE_RUNNER: ${TUNE_RUNNER:-rpc}
- TUNE_EXISTING_DB: ${TUNE_EXISTING_DB:-<not set>}
EOF
)"

if [[ -n "$OUTPUT_FILE" ]]; then
  output_resolved="$(resolve_path "$OUTPUT_FILE")"
  mkdir -p "$(dirname "$output_resolved")"
  printf '%s\n' "$CONTENT" >"$output_resolved"
  echo "RPC command template generated: $output_resolved"
else
  printf '%s\n' "$CONTENT"
fi
