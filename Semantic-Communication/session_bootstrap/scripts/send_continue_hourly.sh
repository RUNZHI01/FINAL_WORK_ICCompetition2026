#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SESSION_DIR/.." && pwd)"
OPENCLAW_ROOT="/home/tianxing/agent-lab/openclaw"
OPENCLAW_CONFIG_FILE="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
DEFAULT_SESSION="main"
DEFAULT_MESSAGE="继续"
DEFAULT_PROJECT_FOCUS="tvm-飞腾派项目"
DEFAULT_PROJECT_GUIDE_PATHS="session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md|session_bootstrap/tasks/赛题对齐执行追踪板_2026-03-13.md|session_bootstrap/README.md"
DEFAULT_INTERVAL_MINUTES=20
DEFAULT_HISTORY_LIMIT=12
DEFAULT_MAX_UNCHANGED_TAIL_SKIPS=1
DEFAULT_SCHEDULE_MODE="clock"
DEFAULT_WAIT_TIMEOUT_MINUTES=240
DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS=15
DEFAULT_AGENT_WAIT_POLL_SECONDS=3
DEFAULT_LOCK_WAIT_SECONDS=5
DEFAULT_REPLACE_GRACE_SECONDS=8
DEFAULT_LOG_FILE="$SESSION_DIR/logs/continue_hourly_main.log"
DEFAULT_LOCK_FILE="/tmp/oc_continue_hourly_main.lock"
DEFAULT_STATE_FILE="$SESSION_DIR/state/continue_hourly_main.state.json"
OC_GATEWAY_ENSURE_BIN="/home/tianxing/.local/bin/oc-gateway-ensure"
AUTO_CONTINUE_MARKER="[auto-continue]"
OPENCLAW_GATEWAY_CALL_BIN="$OPENCLAW_ROOT/dist/index.js"
OPENCLAW_GATEWAY_LOG_FILE="$OPENCLAW_ROOT/.ikun-gateway.log"
WAIT_FOR_SESSION_IDLE_HELPER="$SESSION_DIR/scripts/wait_for_gateway_session_idle.ts"
RETRY_RESUBMIT_RC=75

usage() {
  cat <<'EOF'
Usage:
  send_continue_hourly.sh (--start-at <time> | --start-in-min <n>) [options]

Examples:
  bash scripts/send_continue_hourly.sh --start-at "23:00"
  bash scripts/send_continue_hourly.sh --start-in-min 1 --count 8
  bash scripts/send_continue_hourly.sh --start-at "2026-03-06 23:00" --count 8
  nohup bash scripts/send_continue_hourly.sh --start-at "23:00" > /tmp/send_continue_hourly.out 2>&1 &

Options:
  --start-at <time>       Absolute start time. "HH:MM", "HH:MM:SS", or "YYYY-MM-DD HH:MM[:SS]".
  --start-in-min <n>      Relative start offset in minutes, for example 1 means one minute from now.
  --session <key>         Session key to append to. Default: main.
  --message <text>        Message to send. Default: 继续.
  --project-focus <text> Lock auto-continue to a fixed project. Default: tvm-飞腾派项目.
  --interval-min <n>      Repeat interval in minutes. Default: 20.
  --count <n>             Send n times then exit. Default: 0 (run forever).
  --history-limit <n>     Pull the last n chat items for anchoring. Default: 12.
  --max-unchanged-skips <n>
                          When chat tail has not changed, skip at most n consecutive ticks before resending. Default: 1.
  --schedule-mode <mode>  `clock` = fixed wall clock; `after-complete` = wait for the main session's previous task to finish, then continue. Default: clock.
  --wait-timeout-min <n>  Max minutes to wait for a submitted run to finish in `after-complete` mode. Use 0 to wait without limit. Default: 240.
  --lock-wait-sec <n>     On lock conflict, wait up to n seconds for the old sender to release. Default: 5.
  --replace-existing      If lock is still held, terminate the existing sender that holds the same lock and take over.
  --replace-grace-sec <n> Grace period before escalating from TERM to KILL when replacing. Default: 8.
  --log-file <path>       Log file path. Default: session_bootstrap/logs/continue_hourly_main.log.
  --lock-file <path>      Lock file path. Default: /tmp/oc_continue_hourly_main.lock.
  --state-file <path>     State file path. Default: session_bootstrap/state/continue_hourly_main.state.json.
  --always-send           Disable unchanged-tail skipping; always send on schedule.
  --dry-run               Print schedule only; do not send.
  -h, --help              Show this help.

Notes:
  - Default session is `main`, so messages continue in the same main conversation history.
  - The sent message is auto-anchored to recent chat history to prefer the latest context.
  - Assistant replies produced by a previous auto-continue are not reused as the next anchor.
  - By default, the script skips a tick when the visible chat tail has not changed since the last successful auto-send.
  - Transient gateway/run errors such as `Connection error.` / `fetch failed` / HTTP 502-504 are retried automatically every 15 seconds until the tick succeeds or a non-retryable error appears.
  - In `after-complete` mode, the next send is scheduled after the previous run finishes, so total wall-clock runtime is not simply `count * interval`.
  - If the specified start time is already in the past, the script advances to the next hourly slot.
EOF
}

SESSION_KEY="$DEFAULT_SESSION"
MESSAGE="$DEFAULT_MESSAGE"
PROJECT_FOCUS="$DEFAULT_PROJECT_FOCUS"
PROJECT_GUIDE_PATHS="$DEFAULT_PROJECT_GUIDE_PATHS"
INTERVAL_MINUTES="$DEFAULT_INTERVAL_MINUTES"
START_AT=""
START_IN_MIN=""
COUNT=0
LOG_FILE="$DEFAULT_LOG_FILE"
LOCK_FILE="$DEFAULT_LOCK_FILE"
STATE_FILE="$DEFAULT_STATE_FILE"
DRY_RUN=0
HISTORY_LIMIT="$DEFAULT_HISTORY_LIMIT"
MAX_UNCHANGED_TAIL_SKIPS="$DEFAULT_MAX_UNCHANGED_TAIL_SKIPS"
SCHEDULE_MODE="$DEFAULT_SCHEDULE_MODE"
WAIT_TIMEOUT_MINUTES="$DEFAULT_WAIT_TIMEOUT_MINUTES"
TRANSIENT_RETRY_DELAY_SECONDS="$DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS"
AGENT_WAIT_POLL_SECONDS="$DEFAULT_AGENT_WAIT_POLL_SECONDS"
LOCK_WAIT_SECONDS="$DEFAULT_LOCK_WAIT_SECONDS"
REPLACE_EXISTING=0
REPLACE_GRACE_SECONDS="$DEFAULT_REPLACE_GRACE_SECONDS"
ALWAYS_SEND=0
LOG_FILE_EXPLICIT=0
LOCK_FILE_EXPLICIT=0
STATE_FILE_EXPLICIT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-at)
      [[ $# -ge 2 ]] || { echo "ERROR: --start-at requires a value." >&2; exit 1; }
      START_AT="$2"
      shift 2
      ;;
    --start-in-min)
      [[ $# -ge 2 ]] || { echo "ERROR: --start-in-min requires a value." >&2; exit 1; }
      START_IN_MIN="$2"
      shift 2
      ;;
    --session)
      [[ $# -ge 2 ]] || { echo "ERROR: --session requires a value." >&2; exit 1; }
      SESSION_KEY="$2"
      shift 2
      ;;
    --message)
      [[ $# -ge 2 ]] || { echo "ERROR: --message requires a value." >&2; exit 1; }
      MESSAGE="$2"
      shift 2
      ;;
    --project-focus)
      [[ $# -ge 2 ]] || { echo "ERROR: --project-focus requires a value." >&2; exit 1; }
      PROJECT_FOCUS="$2"
      shift 2
      ;;
    --interval-min)
      [[ $# -ge 2 ]] || { echo "ERROR: --interval-min requires a value." >&2; exit 1; }
      INTERVAL_MINUTES="$2"
      shift 2
      ;;
    --count)
      [[ $# -ge 2 ]] || { echo "ERROR: --count requires a value." >&2; exit 1; }
      COUNT="$2"
      shift 2
      ;;
    --history-limit)
      [[ $# -ge 2 ]] || { echo "ERROR: --history-limit requires a value." >&2; exit 1; }
      HISTORY_LIMIT="$2"
      shift 2
      ;;
    --max-unchanged-skips)
      [[ $# -ge 2 ]] || { echo "ERROR: --max-unchanged-skips requires a value." >&2; exit 1; }
      MAX_UNCHANGED_TAIL_SKIPS="$2"
      shift 2
      ;;
    --schedule-mode)
      [[ $# -ge 2 ]] || { echo "ERROR: --schedule-mode requires a value." >&2; exit 1; }
      SCHEDULE_MODE="$2"
      shift 2
      ;;
    --wait-timeout-min)
      [[ $# -ge 2 ]] || { echo "ERROR: --wait-timeout-min requires a value." >&2; exit 1; }
      WAIT_TIMEOUT_MINUTES="$2"
      shift 2
      ;;
    --lock-wait-sec)
      [[ $# -ge 2 ]] || { echo "ERROR: --lock-wait-sec requires a value." >&2; exit 1; }
      LOCK_WAIT_SECONDS="$2"
      shift 2
      ;;
    --replace-existing)
      REPLACE_EXISTING=1
      shift
      ;;
    --replace-grace-sec)
      [[ $# -ge 2 ]] || { echo "ERROR: --replace-grace-sec requires a value." >&2; exit 1; }
      REPLACE_GRACE_SECONDS="$2"
      shift 2
      ;;
    --log-file)
      [[ $# -ge 2 ]] || { echo "ERROR: --log-file requires a value." >&2; exit 1; }
      LOG_FILE="$2"
      LOG_FILE_EXPLICIT=1
      shift 2
      ;;
    --lock-file)
      [[ $# -ge 2 ]] || { echo "ERROR: --lock-file requires a value." >&2; exit 1; }
      LOCK_FILE="$2"
      LOCK_FILE_EXPLICIT=1
      shift 2
      ;;
    --state-file)
      [[ $# -ge 2 ]] || { echo "ERROR: --state-file requires a value." >&2; exit 1; }
      STATE_FILE="$2"
      STATE_FILE_EXPLICIT=1
      shift 2
      ;;
    --always-send)
      ALWAYS_SEND=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ -n "$START_AT" && -n "$START_IN_MIN" ]]; then
  echo "ERROR: use either --start-at or --start-in-min, not both." >&2
  usage >&2
  exit 1
fi

if [[ -z "$START_AT" && -z "$START_IN_MIN" ]]; then
  echo "ERROR: --start-at or --start-in-min is required." >&2
  usage >&2
  exit 1
fi

if [[ -n "$START_IN_MIN" ]] && { ! [[ "$START_IN_MIN" =~ ^[0-9]+$ ]] || [[ "$START_IN_MIN" -le 0 ]]; }; then
  echo "ERROR: --start-in-min must be a positive integer." >&2
  exit 1
fi

if ! [[ "$INTERVAL_MINUTES" =~ ^[0-9]+$ ]] || [[ "$INTERVAL_MINUTES" -le 0 ]]; then
  echo "ERROR: --interval-min must be a positive integer." >&2
  exit 1
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --count must be a non-negative integer." >&2
  exit 1
fi

if ! [[ "$HISTORY_LIMIT" =~ ^[0-9]+$ ]] || [[ "$HISTORY_LIMIT" -le 0 ]]; then
  echo "ERROR: --history-limit must be a positive integer." >&2
  exit 1
fi

if ! [[ "$MAX_UNCHANGED_TAIL_SKIPS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-unchanged-skips must be a non-negative integer." >&2
  exit 1
fi

if [[ "$SCHEDULE_MODE" != "clock" && "$SCHEDULE_MODE" != "after-complete" ]]; then
  echo "ERROR: --schedule-mode must be 'clock' or 'after-complete'." >&2
  exit 1
fi

if ! [[ "$WAIT_TIMEOUT_MINUTES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --wait-timeout-min must be a non-negative integer." >&2
  exit 1
fi

if ! [[ "$TRANSIENT_RETRY_DELAY_SECONDS" =~ ^[0-9]+$ ]] || [[ "$TRANSIENT_RETRY_DELAY_SECONDS" -le 0 ]]; then
  echo "ERROR: transient retry delay must be a positive integer." >&2
  exit 1
fi

if ! [[ "$AGENT_WAIT_POLL_SECONDS" =~ ^[0-9]+$ ]] || [[ "$AGENT_WAIT_POLL_SECONDS" -le 0 ]]; then
  echo "ERROR: agent wait poll interval must be a positive integer." >&2
  exit 1
fi

if ! [[ "$LOCK_WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --lock-wait-sec must be a non-negative integer." >&2
  exit 1
fi

if ! [[ "$REPLACE_GRACE_SECONDS" =~ ^[0-9]+$ ]] || [[ "$REPLACE_GRACE_SECONDS" -le 0 ]]; then
  echo "ERROR: --replace-grace-sec must be a positive integer." >&2
  exit 1
fi

if [[ -z "$SESSION_KEY" ]]; then
  echo "ERROR: --session cannot be empty." >&2
  exit 1
fi

if [[ -z "$MESSAGE" ]]; then
  echo "ERROR: --message cannot be empty." >&2
  exit 1
fi

if [[ -z "$PROJECT_FOCUS" ]]; then
  echo "ERROR: --project-focus cannot be empty." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found." >&2
  exit 127
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm not found." >&2
  exit 127
fi

if ! command -v flock >/dev/null 2>&1; then
  echo "ERROR: flock not found." >&2
  exit 127
fi

if [[ -x "$OC_GATEWAY_ENSURE_BIN" ]]; then
  :
elif command -v oc-gateway-ensure >/dev/null 2>&1; then
  OC_GATEWAY_ENSURE_BIN="$(command -v oc-gateway-ensure)"
else
  echo "ERROR: oc-gateway-ensure not found." >&2
  exit 127
fi

if [[ ! -d "$OPENCLAW_ROOT" ]]; then
  echo "ERROR: OpenClaw repo not found: $OPENCLAW_ROOT" >&2
  exit 1
fi

if [[ ! -f "$OPENCLAW_GATEWAY_CALL_BIN" ]]; then
  echo "ERROR: OpenClaw gateway call entry not found: $OPENCLAW_GATEWAY_CALL_BIN" >&2
  exit 1
fi

if [[ "$SCHEDULE_MODE" == "after-complete" && ! -f "$WAIT_FOR_SESSION_IDLE_HELPER" ]]; then
  echo "ERROR: session idle helper not found: $WAIT_FOR_SESSION_IDLE_HELPER" >&2
  exit 1
fi

sanitize_session_slug() {
  local raw="$1"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//')"
  [[ -n "$raw" ]] || raw="session"
  printf '%s\n' "$raw"
}

SESSION_SLUG="$(sanitize_session_slug "$SESSION_KEY")"
if (( LOG_FILE_EXPLICIT == 0 )); then
  LOG_FILE="$SESSION_DIR/logs/continue_hourly_${SESSION_SLUG}.log"
fi
if (( LOCK_FILE_EXPLICIT == 0 )); then
  LOCK_FILE="/tmp/oc_continue_hourly_${SESSION_SLUG}.lock"
fi
if (( STATE_FILE_EXPLICIT == 0 )); then
  STATE_FILE="$SESSION_DIR/state/continue_hourly_${SESSION_SLUG}.state.json"
fi

INTERVAL_SEC=$((INTERVAL_MINUTES * 60))
if (( WAIT_TIMEOUT_MINUTES == 0 )); then
  WAIT_TIMEOUT_MS=0
else
  WAIT_TIMEOUT_MS=$((WAIT_TIMEOUT_MINUTES * 60 * 1000))
fi

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$LOCK_FILE")"
mkdir -p "$(dirname "$STATE_FILE")"

lock_info() {
  local message="$1"
  printf '[%s] %s\n' "$(date '+%F %T %z')" "$message" >&2
}

find_lock_holder_pids() {
  local lslocks_output=""
  if command -v lslocks >/dev/null 2>&1; then
    lslocks_output="$(lslocks -n -r -o PID,TYPE,PATH,COMMAND 2>/dev/null | awk -v path="$LOCK_FILE" '$3 == path && $2 == "FLOCK" {print $1}' | paste -sd' ' -)"
    if [[ -n "$lslocks_output" ]]; then
      printf '%s\n' "$lslocks_output"
      return 0
    fi
  fi

  LOCK_FILE="$LOCK_FILE" SELF_PID="$$" python3 - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

lock_path = Path(os.environ["LOCK_FILE"])
if not lock_path.exists():
    raise SystemExit(0)

try:
    target_stat = lock_path.stat()
except FileNotFoundError:
    raise SystemExit(0)

self_pid = int(os.environ["SELF_PID"])
holders: list[str] = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    pid = int(proc.name)
    if pid == self_pid:
        continue
    fd_dir = proc / "fd"
    try:
        for fd in fd_dir.iterdir():
            try:
                fd_stat = fd.stat()
            except OSError:
                continue
            if fd_stat.st_ino == target_stat.st_ino and fd_stat.st_dev == target_stat.st_dev:
                holders.append(str(pid))
                break
    except OSError:
        continue

print(" ".join(holders))
PY
}

run_openclaw_gateway_call() {
  local method="$1"
  local params_json="$2"
  local cli_timeout_ms="${3:-30000}"
  sync_gateway_auth_env_from_config
  local -a cmd=(node "$OPENCLAW_GATEWAY_CALL_BIN" gateway call "$method" --json --timeout "$cli_timeout_ms" --params "$params_json")
  if [[ -n "${OPENCLAW_GATEWAY_URL_OVERRIDE:-}" ]]; then
    cmd+=(--url "$OPENCLAW_GATEWAY_URL_OVERRIDE")
  fi
  if [[ -n "${OPENCLAW_GATEWAY_TOKEN_OVERRIDE:-}" ]]; then
    cmd+=(--token "$OPENCLAW_GATEWAY_TOKEN_OVERRIDE")
  fi
  if [[ -n "${OPENCLAW_GATEWAY_PASSWORD_OVERRIDE:-}" ]]; then
    cmd+=(--password "$OPENCLAW_GATEWAY_PASSWORD_OVERRIDE")
  fi
  "${cmd[@]}"
}

load_gateway_connection_from_config() {
  if [[ ! -f "$OPENCLAW_CONFIG_FILE" ]]; then
    return 0
  fi

  node - "$OPENCLAW_CONFIG_FILE" <<'NODE'
const fs = require("fs");

const configPath = process.argv[2];

try {
  const raw = fs.readFileSync(configPath, "utf8");
  const cfg = JSON.parse(raw);
  const gateway = cfg?.gateway ?? {};
  const remote = gateway?.remote ?? {};
  const mode = gateway?.mode === "remote" ? "remote" : "local";
  const tlsEnabled = gateway?.tls?.enabled === true;
  const port =
    Number.isFinite(gateway?.port) && Number(gateway.port) > 0 ? Number(gateway.port) : 18789;
  const remoteUrl = typeof remote?.url === "string" ? remote.url.trim() : "";
  const localUrl = `${tlsEnabled ? "wss" : "ws"}://127.0.0.1:${port}`;
  const url = mode === "remote" && remoteUrl ? remoteUrl : localUrl;

  const authToken = typeof gateway?.auth?.token === "string" ? gateway.auth.token.trim() : "";
  const remoteToken = typeof remote?.token === "string" ? remote.token.trim() : "";
  const authPassword =
    typeof gateway?.auth?.password === "string" ? gateway.auth.password.trim() : "";
  const remotePassword =
    typeof remote?.password === "string" ? remote.password.trim() : "";

  const token = authToken || remoteToken;
  const password = authPassword || remotePassword;
  process.stdout.write([url, token, password].join("\t"));
} catch {}
NODE
}

OPENCLAW_GATEWAY_URL_OVERRIDE=""
OPENCLAW_GATEWAY_TOKEN_OVERRIDE=""
OPENCLAW_GATEWAY_PASSWORD_OVERRIDE=""

sync_gateway_auth_env_from_config() {
  local connection=""
  local config_url=""
  local config_token=""
  local config_password=""
  connection="$(load_gateway_connection_from_config)"
  if [[ -n "$connection" ]]; then
    IFS=$'\t' read -r config_url config_token config_password <<<"$connection"
  fi

  OPENCLAW_GATEWAY_URL_OVERRIDE="${config_url:-}"
  OPENCLAW_GATEWAY_TOKEN_OVERRIDE="${config_token:-}"
  OPENCLAW_GATEWAY_PASSWORD_OVERRIDE="${config_password:-}"

  if [[ -n "$OPENCLAW_GATEWAY_TOKEN_OVERRIDE" ]]; then
    export OPENCLAW_GATEWAY_TOKEN="$OPENCLAW_GATEWAY_TOKEN_OVERRIDE"
  fi
}

describe_pid_cmd() {
  local pid="$1"
  ps -p "$pid" -o args= 2>/dev/null || true
}

describe_pid_pgid() {
  local pid="$1"
  ps -p "$pid" -o pgid= 2>/dev/null | tr -d ' ' || true
}

wait_for_lock_release() {
  local timeout_sec="$1"
  local deadline=$((SECONDS + timeout_sec))
  while true; do
    if flock -n 9; then
      return 0
    fi
    if (( timeout_sec == 0 || SECONDS >= deadline )); then
      return 1
    fi
    sleep 0.2
  done
}

terminate_existing_sender() {
  local pids_text="$1"
  local signal_name="$2"
  local changed=0
  local pid cmd pgid
  for pid in $pids_text; do
    [[ -n "$pid" ]] || continue
    cmd="$(describe_pid_cmd "$pid")"
    if [[ -z "$cmd" ]]; then
      continue
    fi
    if [[ "$cmd" == *"send_continue_hourly.sh"* ]]; then
      pgid="$(describe_pid_pgid "$pid")"
      if [[ -n "$pgid" ]]; then
        lock_info "sending SIG${signal_name} to existing sender pid=$pid pgid=$pgid"
        kill "-$signal_name" "-$pgid" 2>/dev/null || true
      else
        lock_info "sending SIG${signal_name} to existing sender pid=$pid"
        kill "-$signal_name" "$pid" 2>/dev/null || true
      fi
    else
      lock_info "sending SIG${signal_name} to inherited lock holder pid=$pid cmd=${cmd}"
      kill "-$signal_name" "$pid" 2>/dev/null || true
    fi
    changed=1
  done
  return "$changed"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  if wait_for_lock_release "$LOCK_WAIT_SECONDS"; then
    :
  else
    holders="$(find_lock_holder_pids)"
    if (( REPLACE_EXISTING == 1 )) && [[ -n "${holders:-}" ]]; then
      terminate_existing_sender "$holders" TERM || true
      if ! wait_for_lock_release "$REPLACE_GRACE_SECONDS"; then
        holders="$(find_lock_holder_pids)"
        if [[ -n "${holders:-}" ]]; then
          terminate_existing_sender "$holders" KILL || true
        fi
        if ! wait_for_lock_release 2; then
          echo "ERROR: existing sender still holds lock after replace attempt (lock: $LOCK_FILE)." >&2
          exit 3
        fi
      fi
    else
      echo "ERROR: another sender is already running (lock: $LOCK_FILE)." >&2
      if [[ -n "${holders:-}" ]]; then
        echo "HOLDER: ${holders}" >&2
      fi
      echo "TIP: rerun with --replace-existing to take over automatically." >&2
      exit 3
    fi
  fi
fi

kv_label() {
  case "$1" in
    session)
      printf '%s' '会话'
      ;;
    next_fire)
      printf '%s' '下次时间'
      ;;
    interval)
      printf '%s' '间隔'
      ;;
    count)
      printf '%s' '次数'
      ;;
    dry_run)
      printf '%s' '演练模式'
      ;;
    base_msg)
      printf '%s' '基础指令'
      ;;
    scheduled)
      printf '%s' '计划时间'
      ;;
    retry)
      printf '%s' '重试'
      ;;
    retry_after)
      printf '%s' '重试等待'
      ;;
    error)
      printf '%s' '错误'
      ;;
    run_id)
      printf '%s' '运行ID'
      ;;
    status)
      printf '%s' '状态'
      ;;
    schedule_mode)
      printf '%s' '调度模式'
      ;;
    wait_timeout)
      printf '%s' '等待上限'
      ;;
    waited)
      printf '%s' '等待耗时'
      ;;
    raw)
      printf '%s' '原始返回'
      ;;
    sends)
      printf '%s' '已发送'
      ;;
    attempt)
      printf '%s' '尝试'
      ;;
    at)
      printf '%s' '触发时间'
      ;;
    *)
      printf '%s' "$1"
      ;;
  esac
}

kv_line() {
  local key="$1"
  local value="${2:-}"
  local label
  label="$(kv_label "$key")"
  printf '%-10s: %s' "$label" "$value"
}

single_line_text() {
  printf '%s' "$1" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g'
}

is_transient_connection_error_text() {
  local normalized
  normalized="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  [[ -n "$normalized" ]] || return 1

  case "$normalized" in
    *"connection error."*|*"connection error"*|*"typeerror: fetch failed"*|*"fetch failed"*|*"network error"*|*"bad gateway"*|*"gateway timeout"*|*"service unavailable"*|*"upstream connect error"*|*"socket hang up"*|*"connection reset"*|*"connection refused"*|*"connection aborted"*|*"econnreset"*|*"econnrefused"*|*"etimedout"*|*"ehostunreach"*|*"enetunreach"*|*"eai_again"*|*"und_err_connect"*|*"und_err_socket"*|*"und_err_headers_timeout"*|*"und_err_body_timeout"*|*"und_err_connect_timeout"*|*"und_err_dns_resolve_failed"*)
      return 0
      ;;
  esac

  [[ "$normalized" =~ http[[:space:]]*50(2|3|4) ]]
}

log_transient_retry() {
  local status_text="$1"
  local run_id="$2"
  local retry_count="$3"
  local error_text="$4"
  local scheduled_ts="${5:-}"
  local -a lines=()

  lines+=("$(kv_line session "$SESSION_KEY")")
  if [[ -n "$scheduled_ts" ]]; then
    lines+=("$(kv_line scheduled "$(format_ts "$scheduled_ts")")")
  fi
  if [[ -n "$run_id" ]]; then
    lines+=("$(kv_line run_id "$run_id")")
  fi
  lines+=("$(kv_line retry "$retry_count")")
  lines+=("$(kv_line status "$status_text")")
  lines+=("$(kv_line error "$(single_line_text "$error_text")")")
  lines+=("$(kv_line retry_after "${TRANSIENT_RETRY_DELAY_SECONDS} sec")")
  log_block "retrying" "${lines[@]}"
}

format_preview_lines() {
  local message="$1"
  MESSAGE="$message" python3 - <<'PY'
import os
import textwrap

message = os.environ["MESSAGE"]
normalized_lines = []
for raw in message.splitlines():
    line = " ".join(raw.split())
    if not line:
        continue
    wrapped = textwrap.wrap(line, width=96) or [line]
    normalized_lines.extend(wrapped)

if not normalized_lines:
    print("预览      : <空>")
    raise SystemExit(0)

limit = 6
for idx, line in enumerate(normalized_lines[:limit]):
    prefix = "预览      : " if idx == 0 else "            "
    print(f"{prefix}{line}")
if len(normalized_lines) > limit:
    print("            …")
PY
}

log_block() {
  local title="$1"
  shift || true
  local now
  local emoji="ℹ️"
  local display_title="$title"
  now="$(date '+%F %T %z')"
  case "$title" in
    started)
      emoji="🚀"
      display_title="启动"
      ;;
    dry-run)
      emoji="🧪"
      display_title="演练"
      ;;
    submitted)
      emoji="✅"
      display_title="已提交"
      ;;
    submit-failed)
      emoji="❌"
      display_title="提交失败"
      ;;
    next-fire)
      emoji="⏰"
      display_title="下次发送"
      ;;
    skipped)
      emoji="⏭️"
      display_title="跳过"
      ;;
    waiting)
      emoji="⏳"
      display_title="等待上一轮"
      ;;
    retrying)
      emoji="🔁"
      display_title="重试中"
      ;;
    completed)
      emoji="🎉"
      display_title="完成"
      ;;
    stopped)
      emoji="🛑"
      display_title="停止"
      ;;
  esac
  {
    printf '[%s] %s %s\n' "$now" "$emoji" "$display_title"
    local item
    for item in "$@"; do
      [[ -z "$item" ]] && continue
      printf '  %s\n' "$item"
    done
  } | tee -a "$LOG_FILE"
}

compute_initial_fire_ts() {
  START_AT="$START_AT" START_IN_MIN="$START_IN_MIN" INTERVAL_SEC="$INTERVAL_SEC" python3 - <<'PY'
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

start_raw = os.environ["START_AT"].strip()
start_in_min_raw = os.environ["START_IN_MIN"].strip()
interval = int(os.environ["INTERVAL_SEC"])
now = datetime.now().replace(microsecond=0)

if start_in_min_raw:
    target = now + timedelta(minutes=int(start_in_min_raw))
    print(int(target.timestamp()))
    sys.exit(0)

parsed = None
time_only = False
for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
    try:
        parsed = datetime.strptime(start_raw, fmt)
        time_only = fmt.startswith("%H")
        break
    except ValueError:
        continue

if parsed is None:
    print("invalid --start-at format", file=sys.stderr)
    sys.exit(2)

if time_only:
    parsed = now.replace(hour=parsed.hour, minute=parsed.minute, second=parsed.second, microsecond=0)

target_ts = int(parsed.timestamp())
now_ts = int(now.timestamp())
if target_ts < now_ts:
    steps = ((now_ts - target_ts) // interval) + 1
    target_ts += steps * interval

print(target_ts)
PY
}

advance_future_fire_ts() {
  local current_ts="$1"
  local now_ts
  now_ts="$(date +%s)"
  if (( current_ts > now_ts )); then
    printf '%s\n' "$current_ts"
    return 0
  fi
  local delta=$((now_ts - current_ts))
  local steps=$((delta / INTERVAL_SEC + 1))
  printf '%s\n' $((current_ts + steps * INTERVAL_SEC))
}

format_ts() {
  date -d "@$1" '+%F %T %z'
}

format_wait_timeout() {
  if (( WAIT_TIMEOUT_MINUTES == 0 )); then
    printf '%s\n' '无限'
  else
    printf '%s min\n' "$WAIT_TIMEOUT_MINUTES"
  fi
}

sleep_until() {
  local target_ts="$1"
  while true; do
    local now_ts
    now_ts="$(date +%s)"
    local remain=$((target_ts - now_ts))
    if (( remain <= 0 )); then
      break
    fi
    if (( remain > 60 )); then
      sleep 60
    else
      sleep "$remain"
    fi
  done
}

build_submit_params() {
  local run_id="$1"
  local message_text="$2"
  SESSION_KEY="$SESSION_KEY" MESSAGE="$message_text" RUN_ID="$run_id" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "sessionKey": os.environ["SESSION_KEY"],
            "message": os.environ["MESSAGE"],
            "idempotencyKey": os.environ["RUN_ID"],
        },
        ensure_ascii=False,
    )
)
PY
}

build_history_params() {
  SESSION_KEY="$SESSION_KEY" HISTORY_LIMIT="$HISTORY_LIMIT" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "sessionKey": os.environ["SESSION_KEY"],
            "limit": int(os.environ["HISTORY_LIMIT"]),
        },
        ensure_ascii=False,
    )
)
PY
}

extract_history_anchor() {
  local output
  if ! output="$(run_openclaw_gateway_call chat.history "$(build_history_params)" 30000 2>&1)"; then
    return 1
  fi

  JSON_INPUT="$output" AUTO_CONTINUE_MARKER="$AUTO_CONTINUE_MARKER" python3 - <<'PY'
from __future__ import annotations

import json
import os
import sys
from hashlib import sha1
from datetime import datetime


def load_json_maybe_noisy(text: str):
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    last_obj = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text[i:])
        except Exception:
            continue
        tail = text[i + end :].strip()
        if not tail:
            last_obj = obj
    if last_obj is not None:
        return last_obj

    for i in range(len(text) - 1, -1, -1):
        if text[i] != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
            return obj
        except Exception:
            continue
    return None


def text_of(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return " ".join(content.split())
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(" ".join(text.split()))
        return " ".join(parts)
    return ""


def stable_payload_fingerprint(payload):
    if payload is None:
        return ""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha1(encoded.encode("utf-8")).hexdigest()


def norm_timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return ""


def is_internal_user_message(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return False
    prefixes = (
        "System:",
        "An async command you ran earlier has completed.",
        "A scheduled reminder has been triggered.",
        "A scheduled cron event was triggered.",
    )
    return normalized.startswith(prefixes)


def is_malformed_assistant_message(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return False
    bad_fragments = (
        "to=functions.",
        "to=multi_tool_use.parallel",
        "to=functions.exec",
        "to=functions.process",
        "to=functions.shell_command",
    )
    return any(fragment in normalized for fragment in bad_fragments)


obj = load_json_maybe_noisy(os.environ["JSON_INPUT"])
if obj is None:
    sys.exit(1)
if isinstance(obj, dict) and isinstance(obj.get("result"), dict):
    obj = obj["result"]

messages = obj.get("messages")
if not isinstance(messages, list):
    sys.exit(1)

marker = os.environ["AUTO_CONTINUE_MARKER"]
entries = []
for raw in messages:
    if not isinstance(raw, dict):
        continue
    role = raw.get("role")
    if role not in {"user", "assistant"}:
        continue
    text = text_of(raw)
    if not text:
        continue
    entries.append(
        {
            "role": role,
            "text": text,
            "timestamp": norm_timestamp(raw.get("timestamp")),
            "is_auto_user": role == "user" and text.startswith(marker),
            "is_internal_user": role == "user" and is_internal_user_message(text),
        }
    )


def compact_entry(entry):
    if not isinstance(entry, dict):
        return None
    return {
        "role": entry.get("role"),
        "text": entry.get("text"),
        "timestamp": entry.get("timestamp"),
    }


def latest_non_auto_user(entries):
    for entry in reversed(entries):
        if (
            entry.get("role") == "user"
            and not entry.get("is_auto_user")
            and not entry.get("is_internal_user")
        ):
            return compact_entry(entry)
    return None


def assistant_replied_to_auto_user(entries, assistant_index):
    for index in range(assistant_index - 1, -1, -1):
        candidate = entries[index]
        if candidate.get("role") != "user":
            continue
        return bool(candidate.get("is_auto_user"))
    return False


def latest_non_auto_assistant(entries):
    for index in range(len(entries) - 1, -1, -1):
        candidate = entries[index]
        if candidate.get("role") != "assistant":
            continue
        if is_malformed_assistant_message(str(candidate.get("text") or "")):
            continue
        if assistant_replied_to_auto_user(entries, index):
            continue
        return compact_entry(candidate)
    return None


latest_user = latest_non_auto_user(entries)
latest_assistant = latest_non_auto_assistant(entries)
latest_visible = compact_entry(entries[-1]) if entries else None
anchor_payload = {
    "latest_user": latest_user,
    "latest_assistant": latest_assistant,
}

print(
    json.dumps(
        {
            "latest_user": latest_user,
            "latest_assistant": latest_assistant,
            "latest_visible": latest_visible,
            "anchor_fingerprint": stable_payload_fingerprint(anchor_payload),
            "tail_fingerprint": stable_payload_fingerprint(latest_visible),
        },
        ensure_ascii=False,
    )
)
PY
}

build_effective_message_from_anchor() {
  local anchor_json="${1:-}"
  ANCHOR_JSON="$anchor_json" \
  AUTO_CONTINUE_MARKER="$AUTO_CONTINUE_MARKER" \
  PROJECT_FOCUS="$PROJECT_FOCUS" \
  PROJECT_ROOT="$REPO_ROOT" \
  PROJECT_GUIDE_PATHS="$PROJECT_GUIDE_PATHS" \
  RAW_MESSAGE="$MESSAGE" \
  python3 - <<'PY'
from __future__ import annotations

import json
import os


def clip(text: str, limit: int = 280) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


raw_message = os.environ["RAW_MESSAGE"].strip()
marker = os.environ["AUTO_CONTINUE_MARKER"].strip()
project_focus = os.environ["PROJECT_FOCUS"].strip()
project_root = os.environ["PROJECT_ROOT"].strip()
project_guide_paths = [
    item.strip()
    for item in os.environ.get("PROJECT_GUIDE_PATHS", "").split("|")
    if item.strip()
]
anchor_raw = os.environ["ANCHOR_JSON"].strip()
anchor = {}
if anchor_raw:
    try:
        anchor = json.loads(anchor_raw)
    except Exception:
        anchor = {}

latest_user = anchor.get("latest_user") or {}
latest_assistant = anchor.get("latest_assistant") or {}

lines = [
    f"{marker} 继续当前会话最近的上下文；优先依据本会话最近聊天记录，不要优先回到更早的 memory、旧任务或旧待办。",
]

if project_focus:
    scope_line = f"固定项目: {project_focus}。"
    if project_root:
        scope_line += f" 工作区: {project_root}。"
    scope_line += " 所有后续动作必须服务于这个项目；不要切换到其他工程、其他仓库或无关 side quest。"
    lines.append(scope_line)
    lines.append(
        f"如果最近聊天记录与 {project_focus} 无关，把那些内容只当作背景，不要偏航；当前应继续推进这个项目。"
    )
    if project_guide_paths:
        lines.append(
            "若当前子任务已完成、最近上下文不明确，或刚刚做完一个局部事项，"
            "回到这些项目入口挑选并推进下一个未完成事项: "
            + "；".join(project_guide_paths)
        )
    lines.append(
        f"完成一个子任务后，继续衔接 {project_focus} 的下一个未完成事项，而不是开始别的项目。"
    )

user_text = latest_user.get("text") if isinstance(latest_user, dict) else None
user_ts = latest_user.get("timestamp") if isinstance(latest_user, dict) else None
if isinstance(user_text, str) and user_text.strip():
    prefix = "最近一条非自动用户消息"
    if isinstance(user_ts, str) and user_ts.strip():
        prefix += f"（{user_ts}）"
    lines.append(f"{prefix}: {clip(user_text)}")

assistant_text = latest_assistant.get("text") if isinstance(latest_assistant, dict) else None
assistant_ts = latest_assistant.get("timestamp") if isinstance(latest_assistant, dict) else None
if isinstance(assistant_text, str) and assistant_text.strip():
    prefix = "最近一条助手消息"
    if isinstance(assistant_ts, str) and assistant_ts.strip():
        prefix += f"（{assistant_ts}）"
    lines.append(f"{prefix}: {clip(assistant_text)}")

if raw_message:
    lines.append(f"本次附加指令: {raw_message}")

lines.append("如果当前没有明确未完成事项，先用一句话说明你理解的“继续对象”，再继续执行。")
print("\n".join(lines))
PY
}

read_state_field() {
  local anchor_json="$1"
  local field_name="$2"
  STATE_FILE="$STATE_FILE" ANCHOR_JSON="$anchor_json" FIELD_NAME="$field_name" python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

state_path = Path(os.environ["STATE_FILE"])
anchor_raw = os.environ["ANCHOR_JSON"].strip()
field_name = os.environ["FIELD_NAME"].strip()
if not anchor_raw or not state_path.is_file():
    raise SystemExit(1)

try:
    anchor = json.loads(anchor_raw)
except Exception:
    raise SystemExit(1)

try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

last_success = state.get("last_success")
if not isinstance(last_success, dict):
    raise SystemExit(1)

anchor_fp = str(anchor.get("anchor_fingerprint") or "")
tail_fp = str(anchor.get("tail_fingerprint") or "")
values = {
    "same_anchor": "1" if anchor_fp and anchor_fp == str(last_success.get("anchor_fingerprint") or "") else "0",
    "same_tail": "1" if tail_fp and tail_fp == str(last_success.get("tail_fingerprint") or "") else "0",
    "last_run_id": str(last_success.get("run_id") or ""),
    "unchanged_tail_skips": str(last_success.get("unchanged_tail_skips") or 0),
}
value = values.get(field_name)
if value is None:
    raise SystemExit(1)
print(value)
PY
}

write_submit_state() {
  local anchor_json="$1"
  local run_id="$2"
  local scheduled_ts="$3"
  local submit_status="$4"
  STATE_FILE="$STATE_FILE" \
  ANCHOR_JSON="$anchor_json" \
  SESSION_KEY="$SESSION_KEY" \
  RUN_ID="$run_id" \
  SCHEDULED_TS="$scheduled_ts" \
  SUBMIT_STATUS="$submit_status" \
  python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

state_path = Path(os.environ["STATE_FILE"])
state_path.parent.mkdir(parents=True, exist_ok=True)

anchor_raw = os.environ["ANCHOR_JSON"].strip()
anchor = {}
if anchor_raw:
    try:
        anchor = json.loads(anchor_raw)
    except Exception:
        anchor = {}

payload = {
    "session": os.environ["SESSION_KEY"],
    "last_success": {
        "run_id": os.environ["RUN_ID"],
        "submit_status": os.environ["SUBMIT_STATUS"],
        "submitted_at": os.environ["SCHEDULED_TS"],
        "anchor_fingerprint": str(anchor.get("anchor_fingerprint") or ""),
        "tail_fingerprint": str(anchor.get("tail_fingerprint") or ""),
        "latest_visible": anchor.get("latest_visible"),
        "unchanged_tail_skips": 0,
    },
}
state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_skip_state() {
  local anchor_json="$1"
  local scheduled_ts="$2"
  STATE_FILE="$STATE_FILE" \
  ANCHOR_JSON="$anchor_json" \
  SESSION_KEY="$SESSION_KEY" \
  SCHEDULED_TS="$scheduled_ts" \
  python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

state_path = Path(os.environ["STATE_FILE"])
state_path.parent.mkdir(parents=True, exist_ok=True)

state = {}
if state_path.is_file():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

last_success = state.get("last_success")
if not isinstance(last_success, dict):
    last_success = {}

current = int(last_success.get("unchanged_tail_skips") or 0)
last_success["unchanged_tail_skips"] = current + 1
last_success["last_skipped_at"] = os.environ["SCHEDULED_TS"]
state["session"] = os.environ["SESSION_KEY"]
state["last_success"] = last_success
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

parse_submit_result() {
  JSON_INPUT="$1" python3 - <<'PY'
import json
import os
import sys

text = os.environ["JSON_INPUT"].strip()
if not text:
    sys.exit(0)

try:
    obj = json.loads(text)
except Exception:
    decoder = json.JSONDecoder()
    obj = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except Exception:
            continue
    if obj is None:
        sys.exit(0)

if isinstance(obj, dict) and isinstance(obj.get("result"), dict):
    obj = obj["result"]

run_id = "" if obj.get("runId") is None else str(obj.get("runId"))
status = "" if obj.get("status") is None else str(obj.get("status"))
print(f"{run_id}\t{status}")
PY
}

build_agent_wait_params() {
  local run_id="$1"
  local timeout_ms="$2"
  RUN_ID="$run_id" POLL_TIMEOUT_MS="$timeout_ms" python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "runId": os.environ["RUN_ID"],
            "timeoutMs": int(os.environ["POLL_TIMEOUT_MS"]),
        },
        ensure_ascii=False,
    )
)
PY
}

parse_agent_wait_result() {
  JSON_INPUT="$1" python3 - <<'PY'
import json
import os
import sys

text = os.environ["JSON_INPUT"].strip()
if not text:
    sys.exit(0)

try:
    obj = json.loads(text)
except Exception:
    decoder = json.JSONDecoder()
    obj = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except Exception:
            continue
    if obj is None:
        sys.exit(0)

if isinstance(obj, dict) and isinstance(obj.get("result"), dict):
    obj = obj["result"]

run_id = "" if obj.get("runId") is None else str(obj.get("runId"))
status = "" if obj.get("status") is None else str(obj.get("status"))
error = "" if obj.get("error") is None else str(obj.get("error"))
print(f"{run_id}\t{status}\t{error}")
PY
}

find_gateway_run_error() {
  local run_id="$1"
  if [[ ! -f "$OPENCLAW_GATEWAY_LOG_FILE" ]]; then
    return 1
  fi

  RUN_ID="$run_id" GATEWAY_LOG_FILE="$OPENCLAW_GATEWAY_LOG_FILE" python3 - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

run_id = os.environ["RUN_ID"]
log_path = Path(os.environ["GATEWAY_LOG_FILE"])
ansi_re = re.compile(r"\x1b\[[0-9;]*m")
needle = f"embedded run agent end: runId={run_id} isError=true error="
latest = ""

try:
    with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw_line in fh:
            line = ansi_re.sub("", raw_line.rstrip("\n"))
            pos = line.find(needle)
            if pos >= 0:
                latest = line[pos + len(needle) :].strip()
except OSError:
    raise SystemExit(1)

if not latest:
    raise SystemExit(1)

print(latest)
PY
}

wait_for_run_completion() {
  local run_id="$1"
  local output=""
  local parsed=""
  local retry_count=0
  local wait_deadline=0
  if (( WAIT_TIMEOUT_MS > 0 )); then
    wait_deadline=$(( $(date +%s) + WAIT_TIMEOUT_MS / 1000 ))
  fi
  local poll_timeout_ms=$((AGENT_WAIT_POLL_SECONDS * 1000))
  local gateway_error=""
  local logged_gateway_error=""

  while true; do
    if gateway_error="$(find_gateway_run_error "$run_id" 2>/dev/null || true)" && [[ -n "$gateway_error" ]]; then
      if [[ "$gateway_error" != "$logged_gateway_error" ]]; then
        logged_gateway_error="$gateway_error"
        if is_transient_connection_error_text "$gateway_error"; then
          retry_count=$((retry_count + 1))
          log_transient_retry "从网关日志确认本轮 run 因瞬时连接错误结束，准备重新提交" "$run_id" "$retry_count" "$gateway_error"
          return "$RETRY_RESUBMIT_RC"
        fi

        log_block "submit-failed" \
          "$(kv_line session "$SESSION_KEY")" \
          "$(kv_line run_id "$run_id")" \
          "$(kv_line status "本轮 run 异常结束")" \
          "$(kv_line error "$gateway_error")"
        return 1
      fi
    fi

    if (( wait_deadline > 0 && $(date +%s) >= wait_deadline )); then
      log_block "submit-failed" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line run_id "${run_id}")" \
        "$(kv_line status "等待 run 完成超时")" \
        "$(kv_line error "timeout")"
      return 1
    fi

    if ! output="$(run_openclaw_gateway_call agent.wait "$(build_agent_wait_params "$run_id" "$poll_timeout_ms")" $((poll_timeout_ms + 15000)) 2>&1)"; then
      if is_transient_connection_error_text "$output"; then
        retry_count=$((retry_count + 1))
        log_transient_retry "等待 run 状态时遇到瞬时连接错误，继续等待" "$run_id" "$retry_count" "$output"
        sleep "$TRANSIENT_RETRY_DELAY_SECONDS"
        continue
      fi

      log_block "submit-failed" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line run_id "$run_id")" \
        "$(kv_line status "等待 run 完成失败")" \
        "$(kv_line error "$(single_line_text "$output")")"
      return 1
    fi

    parsed="$(parse_agent_wait_result "$output" 2>/dev/null || true)"
    if [[ -z "$parsed" ]]; then
      log_block "submitted" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line run_id "$run_id")" \
        "$(kv_line status "等待 run 结束返回不可解析结果")" \
        "$(kv_line raw "$(single_line_text "$output")")"
      return 1
    fi

    local waited_run_id waited_status waited_error
    IFS=$'\t' read -r waited_run_id waited_status waited_error <<<"$parsed"
    case "$waited_status" in
      ok)
        log_block "submitted" \
          "$(kv_line session "$SESSION_KEY")" \
          "$(kv_line run_id "${waited_run_id:-$run_id}")" \
          "$(kv_line status "本轮 run 已完成")"
        return 0
        ;;
      error)
        if is_transient_connection_error_text "${waited_error:-}"; then
          retry_count=$((retry_count + 1))
          log_transient_retry "本轮 run 因瞬时连接错误结束，准备重新提交" "${waited_run_id:-$run_id}" "$retry_count" "${waited_error:-Connection error.}"
          return "$RETRY_RESUBMIT_RC"
        fi

        log_block "submit-failed" \
          "$(kv_line session "$SESSION_KEY")" \
          "$(kv_line run_id "${waited_run_id:-$run_id}")" \
          "$(kv_line status "本轮 run 异常结束")" \
          "$(kv_line error "${waited_error:-unknown}")"
        return 1
        ;;
      timeout|*)
        if gateway_error="$(find_gateway_run_error "$run_id" 2>/dev/null || true)" && [[ -n "$gateway_error" ]]; then
          if is_transient_connection_error_text "$gateway_error"; then
            retry_count=$((retry_count + 1))
            log_transient_retry "等待返回 timeout，但网关日志确认是瞬时连接错误，准备重新提交" "${waited_run_id:-$run_id}" "$retry_count" "$gateway_error"
            return "$RETRY_RESUBMIT_RC"
          fi

          log_block "submit-failed" \
            "$(kv_line session "$SESSION_KEY")" \
            "$(kv_line run_id "${waited_run_id:-$run_id}")" \
            "$(kv_line status "本轮 run 异常结束")" \
            "$(kv_line error "$gateway_error")"
          return 1
        fi
        sleep "$AGENT_WAIT_POLL_SECONDS"
        continue
        ;;
    esac
  done
}

LAST_IDLE_WAIT_STATUS=""
LAST_IDLE_WAIT_REASON=""
LAST_IDLE_WAIT_MS=""
LAST_IDLE_WAIT_OUTPUT=""

wait_for_target_session_idle() {
  local output=""
  local rc=0

  sync_gateway_auth_env_from_config
  if output="$(pnpm --dir "$OPENCLAW_ROOT" exec tsx "$WAIT_FOR_SESSION_IDLE_HELPER" --session "$SESSION_KEY" --timeout-ms "$WAIT_TIMEOUT_MS" --history-limit "$HISTORY_LIMIT" 2>&1)"; then
    rc=0
  else
    rc=$?
  fi

  LAST_IDLE_WAIT_OUTPUT="$output"
  LAST_IDLE_WAIT_STATUS=""
  LAST_IDLE_WAIT_REASON=""
  LAST_IDLE_WAIT_MS=""

  if (( rc != 0 )); then
    return "$rc"
  fi

  local parsed_output="$output"
  parsed_output="${parsed_output//$'\r'/}"
  parsed_output="${parsed_output%%$'\n'*}"
  IFS=$'\t' read -r LAST_IDLE_WAIT_STATUS LAST_IDLE_WAIT_REASON LAST_IDLE_WAIT_MS <<<"$parsed_output"
  return 0
}

run_chat_send_with_retry() {
  local local_run_id="$1"
  local message_text="$2"
  local scheduled_ts="$3"
  local retry_count=0
  local output=""

  while true; do
    if output="$(run_openclaw_gateway_call chat.send "$(build_submit_params "$local_run_id" "$message_text")" 30000 2>&1)"; then
      LAST_GATEWAY_OUTPUT="$output"
      return 0
    fi

    LAST_GATEWAY_OUTPUT="$output"
    if is_transient_connection_error_text "$output"; then
      retry_count=$((retry_count + 1))
      log_transient_retry "提交时遇到瞬时连接错误，沿用同一请求重试" "$local_run_id" "$retry_count" "$output" "$scheduled_ts"
      sleep "$TRANSIENT_RETRY_DELAY_SECONDS"
      continue
    fi

    return 1
  done
}

submit_once() {
  local scheduled_ts="$1"
  local anchor_json=""
  local effective_message=""

  sync_gateway_auth_env_from_config
  "$OC_GATEWAY_ENSURE_BIN"
  if [[ "$SCHEDULE_MODE" == "after-complete" ]]; then
    local idle_wait_rc=0
    if wait_for_target_session_idle; then
      idle_wait_rc=0
    else
      idle_wait_rc=$?
    fi
    if (( idle_wait_rc != 0 )); then
      local wait_error_text="${LAST_IDLE_WAIT_OUTPUT:-unknown}"
      log_block "submit-failed" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
        "$(kv_line status "发送前等待主会话上一轮任务结束失败")" \
        "$(kv_line error "$(single_line_text "$wait_error_text")")"
      return 1
    fi
    if [[ "$LAST_IDLE_WAIT_STATUS" == "idle-after-wait" ]]; then
      log_block "waiting" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
        "$(kv_line status "${LAST_IDLE_WAIT_REASON:-已等到上一轮结束}")" \
        "$(kv_line waited "${LAST_IDLE_WAIT_MS:-0} ms")"
    fi
  fi
  anchor_json="$(extract_history_anchor 2>/dev/null || true)"
  effective_message="$(build_effective_message_from_anchor "$anchor_json")"

  if (( ALWAYS_SEND == 0 )); then
    local same_tail=""
    local unchanged_tail_skips=0
    same_tail="$(read_state_field "$anchor_json" same_tail 2>/dev/null || true)"
    unchanged_tail_skips="$(read_state_field "$anchor_json" unchanged_tail_skips 2>/dev/null || true)"
    if [[ "$same_tail" == "1" ]]; then
      if [[ -z "$unchanged_tail_skips" ]]; then
        unchanged_tail_skips=0
      fi
      if (( unchanged_tail_skips < MAX_UNCHANGED_TAIL_SKIPS )); then
        write_skip_state "$anchor_json" "$scheduled_ts"
        local last_run_id=""
        last_run_id="$(read_state_field "$anchor_json" last_run_id 2>/dev/null || true)"
        log_block "skipped" \
          "$(kv_line session "$SESSION_KEY")" \
          "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
          "$(kv_line status "会话尾部无新变化，先跳过本轮（${unchanged_tail_skips}/${MAX_UNCHANGED_TAIL_SKIPS}）")" \
          "$(kv_line run_id "${last_run_id:-unknown}")"
        return 10
      fi
    fi
  fi

  if (( DRY_RUN == 1 )); then
    local -a preview_lines=()
    while IFS= read -r line; do
      preview_lines+=("$line")
    done < <(format_preview_lines "$effective_message")
    log_block "dry-run" \
      "$(kv_line session "$SESSION_KEY")" \
      "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
      "$(kv_line interval "${INTERVAL_MINUTES} min")" \
      "$(kv_line count "$COUNT")" \
      "$(kv_line status "$([[ "$ALWAYS_SEND" -eq 1 ]] && printf '%s' '始终发送' || printf '尾部变化时发送（最多连续跳过 %s 次）' "$MAX_UNCHANGED_TAIL_SKIPS")")" \
      "${preview_lines[@]}"
    return 0
  fi

  local -a preview_lines=()
  while IFS= read -r line; do
    preview_lines+=("$line")
  done < <(format_preview_lines "$effective_message")

  while true; do
    local local_run_id="continue-${SESSION_KEY}-$(date +%s)-$RANDOM"
    local output=""
    if ! run_chat_send_with_retry "$local_run_id" "$effective_message" "$scheduled_ts"; then
      output="${LAST_GATEWAY_OUTPUT:-}"
      log_block "submit-failed" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
        "$(kv_line error "$(single_line_text "$output")")"
      return 1
    fi
    output="${LAST_GATEWAY_OUTPUT:-}"

    local parsed=""
    parsed="$(parse_submit_result "$output" 2>/dev/null || true)"
    if [[ -n "$parsed" ]]; then
      local run_id status
      IFS=$'\t' read -r run_id status <<<"$parsed"
      write_submit_state "$anchor_json" "${run_id:-$local_run_id}" "$scheduled_ts" "${status:-unknown}"
      log_block "submitted" \
        "$(kv_line session "$SESSION_KEY")" \
        "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
        "$(kv_line run_id "${run_id:-$local_run_id}")" \
        "$(kv_line status "${status:-unknown}")" \
        "${preview_lines[@]}"
      if [[ "$SCHEDULE_MODE" == "after-complete" && -n "$run_id" ]]; then
        local wait_rc=0
        wait_for_run_completion "$run_id" || wait_rc=$?
        if (( wait_rc == 0 )); then
          return 0
        fi
        if (( wait_rc == RETRY_RESUBMIT_RC )); then
          sleep "$TRANSIENT_RETRY_DELAY_SECONDS"
          continue
        fi
        return 1
      fi
      return 0
    fi

    write_submit_state "$anchor_json" "$local_run_id" "$scheduled_ts" "unknown"
    log_block "submitted" \
      "$(kv_line session "$SESSION_KEY")" \
      "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
      "$(kv_line raw "$(single_line_text "$output")")" \
      "${preview_lines[@]}"
    return 0
  done
}

trap 'log_block "stopped" "$(kv_line session "$SESSION_KEY")"; exit 130' INT TERM

NEXT_FIRE_TS="$(compute_initial_fire_ts)"
SENT=0

log_block "started" \
  "$(kv_line session "$SESSION_KEY")" \
  "$(kv_line next_fire "$(format_ts "$NEXT_FIRE_TS")")" \
  "$(kv_line interval "${INTERVAL_MINUTES} min")" \
  "$(kv_line count "$COUNT")" \
  "$(kv_line dry_run "$DRY_RUN")" \
  "$(kv_line status "$([[ "$ALWAYS_SEND" -eq 1 ]] && printf '%s' '始终发送' || printf '尾部变化时发送（最多连续跳过 %s 次）' "$MAX_UNCHANGED_TAIL_SKIPS")")" \
  "$(kv_line schedule_mode "$SCHEDULE_MODE")" \
  "$(kv_line wait_timeout "$(format_wait_timeout)")" \
  "$(kv_line base_msg "$MESSAGE")"

while true; do
  sleep_until "$NEXT_FIRE_TS"
  submit_rc=0
  if submit_once "$NEXT_FIRE_TS"; then
    submit_rc=0
  else
    submit_rc=$?
  fi
  if (( submit_rc == 0 )); then
    SENT=$((SENT + 1))
  fi
  if (( COUNT > 0 && SENT >= COUNT )); then
    log_block "completed" \
      "$(kv_line session "$SESSION_KEY")" \
      "$(kv_line sends "$SENT")"
    exit 0
  fi
  if [[ "$SCHEDULE_MODE" == "after-complete" ]]; then
    NEXT_FIRE_TS=$(( $(date +%s) + INTERVAL_SEC ))
  else
    NEXT_FIRE_TS=$((NEXT_FIRE_TS + INTERVAL_SEC))
    NEXT_FIRE_TS="$(advance_future_fire_ts "$NEXT_FIRE_TS")"
  fi
  log_block "next-fire" \
    "$(kv_line session "$SESSION_KEY")" \
    "$(kv_line at "$(format_ts "$NEXT_FIRE_TS")")" \
    "$(kv_line sends "$SENT")"
done
