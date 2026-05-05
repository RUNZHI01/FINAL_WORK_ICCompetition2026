#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

DEFAULT_PHYTIUM_ENV="$SESSION_DIR/config/rpc_armv8.phytium_pi.2026-03-01.env"
DEFAULT_SNAPDRAGON_ENV="$SESSION_DIR/config/rpc_armv8.lenovo.2026-03-01.env"
DEFAULT_MODE="local"
DEFAULT_SESSION="main"
DEFAULT_HISTORY_FILE="./session_bootstrap/reports/dispatch_history.csv"
DEFAULT_PROBE_TIMEOUT_SEC=8

usage() {
  cat <<'EOF'
Usage:
  dispatch_round.sh [--mode local|agent] [--session <name>] [--run-tag <tag>]
                    [--phytium-env <path>] [--snapdragon-env <path>]
                    [--target phytium|snapdragon] [--auto-detect]
                    [--force-target phytium|snapdragon]
                    [--probe-timeout-sec <sec>] [--history-file <path>]
                    [--prep-skip-full]

Flow:
  1) 手动指定目标（推荐）或自动探测飞腾派是否可达
  2) phytium -> 跑 final；snapdragon -> 跑 prep
  3) 调用既有执行器（auto_round_local.sh 或 submit_round_to_agent.sh）
  4) 落盘 dispatch_history.csv，记录任务与设备对应关系

Notes:
  - 本脚本只做调度，不改你 quick/full/daily 的核心执行逻辑。
  - 推荐显式传 --target；只有传 --auto-detect 才会自动探测。
EOF
}

MODE="$DEFAULT_MODE"
SESSION_KEY="$DEFAULT_SESSION"
RUN_TAG=""
PHYTIUM_ENV="$DEFAULT_PHYTIUM_ENV"
SNAPDRAGON_ENV="$DEFAULT_SNAPDRAGON_ENV"
TARGET=""
AUTO_DETECT=0
PROBE_TIMEOUT_SEC="$DEFAULT_PROBE_TIMEOUT_SEC"
HISTORY_FILE="$DEFAULT_HISTORY_FILE"
PREP_SKIP_FULL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --mode requires a value." >&2
        exit 1
      fi
      MODE="$2"
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
    --force-target)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --force-target requires phytium|snapdragon." >&2
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --target)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --target requires phytium|snapdragon." >&2
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --auto-detect)
      AUTO_DETECT=1
      shift
      ;;
    --probe-timeout-sec)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --probe-timeout-sec requires a number." >&2
        exit 1
      fi
      PROBE_TIMEOUT_SEC="$2"
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
    --prep-skip-full)
      PREP_SKIP_FULL=1
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

csv_escape() {
  local value="${1:-}"
  value="${value//\"/\"\"}"
  printf '"%s"' "$value"
}

run_with_timeout() {
  local timeout_sec="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "${timeout_sec}s" "$@"
  else
    "$@"
  fi
}

probe_phytium() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 2
  fi

  # shellcheck source=/dev/null
  set -a
  source "$env_file"
  set +a

  local host="${REMOTE_HOST:-${RPC_TRACKER_HOST:-}}"
  local user="${REMOTE_USER:-}"
  local pass="${REMOTE_PASS:-}"
  local port="${REMOTE_SSH_PORT:-22}"

  if [[ -z "$host" ]]; then
    return 2
  fi

  if [[ -n "$user" && -n "$pass" && -x "$SCRIPT_DIR/ssh_with_password.sh" ]]; then
    run_with_timeout "$PROBE_TIMEOUT_SEC" \
      bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$host" \
      --user "$user" \
      --pass "$pass" \
      --port "$port" \
      -- "echo __phytium_probe_ok__" >/dev/null 2>&1
    return $?
  fi

  if command -v nc >/dev/null 2>&1; then
    run_with_timeout "$PROBE_TIMEOUT_SEC" nc -z "$host" "$port" >/dev/null 2>&1
    return $?
  fi

  run_with_timeout "$PROBE_TIMEOUT_SEC" bash -lc "exec 3<>/dev/tcp/${host}/${port}" >/dev/null 2>&1
}

if [[ "$MODE" != "local" && "$MODE" != "agent" ]]; then
  echo "ERROR: --mode must be local|agent." >&2
  exit 1
fi

if [[ -n "$TARGET" && "$TARGET" != "phytium" && "$TARGET" != "snapdragon" ]]; then
  echo "ERROR: --target must be phytium|snapdragon." >&2
  exit 1
fi

if [[ ! "$PROBE_TIMEOUT_SEC" =~ ^[0-9]+$ || "$PROBE_TIMEOUT_SEC" -lt 1 ]]; then
  echo "ERROR: --probe-timeout-sec must be a positive integer." >&2
  exit 1
fi

PHYTIUM_ENV_RESOLVED="$(resolve_path "$PHYTIUM_ENV")"
SNAPDRAGON_ENV_RESOLVED="$(resolve_path "$SNAPDRAGON_ENV")"
HISTORY_FILE_RESOLVED="$(resolve_path "$HISTORY_FILE")"

if [[ ! -f "$PHYTIUM_ENV_RESOLVED" ]]; then
  echo "ERROR: phytium env not found: $PHYTIUM_ENV_RESOLVED" >&2
  exit 1
fi
if [[ ! -f "$SNAPDRAGON_ENV_RESOLVED" ]]; then
  echo "ERROR: snapdragon env not found: $SNAPDRAGON_ENV_RESOLVED" >&2
  exit 1
fi

target=""
stage=""
decision=""
probe_status="not_run"

if [[ -n "$TARGET" ]]; then
  target="$TARGET"
  decision="manual_target"
  probe_status="skipped_manual_target"
elif [[ "$AUTO_DETECT" -eq 1 ]]; then
  if probe_phytium "$PHYTIUM_ENV_RESOLVED"; then
    target="phytium"
    decision="auto_probe"
    probe_status="reachable"
  else
    target="snapdragon"
    decision="auto_probe"
    probe_status="unreachable"
  fi
else
  echo "ERROR: please specify --target phytium|snapdragon (recommended), or enable --auto-detect." >&2
  exit 1
fi

if [[ "$target" == "phytium" ]]; then
  stage="final"
  base_env="$PHYTIUM_ENV_RESOLVED"
else
  stage="prep"
  base_env="$SNAPDRAGON_ENV_RESOLVED"
fi

if [[ -z "$RUN_TAG" ]]; then
  RUN_TAG="auto_dispatch"
fi
EFFECTIVE_RUN_TAG="${RUN_TAG}_${target}_${stage}"

if [[ "$MODE" == "local" ]]; then
  RUN_CMD=(bash "$SCRIPT_DIR/auto_round_local.sh" --base-env "$base_env" --run-tag "$EFFECTIVE_RUN_TAG")
else
  RUN_CMD=(bash "$SCRIPT_DIR/submit_round_to_agent.sh" --base-env "$base_env" --run-tag "$EFFECTIVE_RUN_TAG" --session "$SESSION_KEY")
fi

if [[ "$stage" == "prep" && "$PREP_SKIP_FULL" -eq 1 ]]; then
  RUN_CMD+=(--skip-full)
fi

echo "[dispatch] mode=$MODE session=$SESSION_KEY"
echo "[dispatch] decision=$decision probe=$probe_status"
echo "[dispatch] target=$target stage=$stage"
echo "[dispatch] base_env=$base_env"
echo "[dispatch] run_tag=$EFFECTIVE_RUN_TAG"

set +e
"${RUN_CMD[@]}"
run_rc=$?
set -e

mkdir -p "$(dirname "$HISTORY_FILE_RESOLVED")"
if [[ ! -f "$HISTORY_FILE_RESOLVED" ]]; then
  echo "\"timestamp\",\"mode\",\"session\",\"decision\",\"probe_status\",\"target\",\"stage\",\"base_env\",\"run_tag\",\"run_rc\"" >"$HISTORY_FILE_RESOLVED"
fi

{
  csv_escape "$(date -Iseconds)"
  printf ','
  csv_escape "$MODE"
  printf ','
  csv_escape "$SESSION_KEY"
  printf ','
  csv_escape "$decision"
  printf ','
  csv_escape "$probe_status"
  printf ','
  csv_escape "$target"
  printf ','
  csv_escape "$stage"
  printf ','
  csv_escape "$base_env"
  printf ','
  csv_escape "$EFFECTIVE_RUN_TAG"
  printf ','
  csv_escape "$run_rc"
  printf '\n'
} >>"$HISTORY_FILE_RESOLVED"

echo "[dispatch] history_file=$HISTORY_FILE_RESOLVED"

exit "$run_rc"
