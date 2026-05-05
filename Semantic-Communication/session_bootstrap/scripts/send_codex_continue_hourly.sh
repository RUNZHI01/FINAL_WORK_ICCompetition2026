#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_BASENAME="$(basename "$SCRIPT_PATH")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SESSION_DIR/.." && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
AUTO_CONTINUE_MARKER="[auto-continue]"

DEFAULT_MESSAGE_FALLBACK="继续"
DEFAULT_MESSAGE_FILE="$SESSION_DIR/tasks/codex_continue_current_work_prompt.txt"
DEFAULT_MESSAGE="$DEFAULT_MESSAGE_FALLBACK"
DEFAULT_PROJECT_FOCUS="tvm-飞腾派项目"
DEFAULT_PROJECT_GUIDE_PATHS="session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md|session_bootstrap/tasks/赛题对齐执行追踪板_2026-03-13.md|session_bootstrap/README.md"
DEFAULT_INTERVAL_MINUTES=20
DEFAULT_HISTORY_LIMIT=12
DEFAULT_MAX_UNCHANGED_TAIL_SKIPS=1
DEFAULT_SCHEDULE_MODE="clock"
DEFAULT_WAIT_TIMEOUT_MINUTES=240
DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS=15
DEFAULT_LOCK_WAIT_SECONDS=5
DEFAULT_REPLACE_GRACE_SECONDS=8
DEFAULT_SANDBOX_MODE="danger-full-access"
DEFAULT_APPROVAL_POLICY="never"
DEFAULT_MESSAGE_MODE="plain"

usage() {
  cat <<'EOF'
Usage:
  send_codex_continue_hourly.sh (--start-at <time> | --start-in-min <n>) --resume-id <id> [options]

Examples:
  bash scripts/send_codex_continue_hourly.sh \
    --resume-id 019d1bb1-cd26-7711-947b-a58c3c956253 \
    --start-in-min 1 \
    --count 8

  bash scripts/send_codex_continue_hourly.sh \
    --resume-id 019d1bb1-cd26-7711-947b-a58c3c956253 \
    --start-at "23:00" \
    --interval-min 7 \
    --replace-existing \
    --always-send

Options:
  --start-at <time>       Absolute start time. "HH:MM", "HH:MM:SS", or "YYYY-MM-DD HH:MM[:SS]".
  --start-in-min <n>      Relative start offset in minutes, for example 1 means one minute from now.
  --resume-id <id>        Codex resume/session id to continue.
  --cd <dir>              Working directory to pass to `codex exec -C ... resume`. By default the
                          script resolves the original cwd from the local Codex session file.
  --message <text>        Message to send. Overrides the repo default prompt file when provided.
  --message-file <path>   Read the message text from a file.
  --message-mode <mode>   `plain` = send only the raw message; `anchored` = prepend recent local
                          session context. Default: plain.
  --project-focus <text>  Fixed project scope injected into the continue prompt.
  --project-guide-paths <paths>
                          Pipe-separated project guide paths injected into the continue prompt.
  --interval-min <n>      Repeat interval in minutes. Default: 20.
  --count <n>             Send n times then exit. Default: 0 (run forever).
  --history-limit <n>     Pull the last n user/assistant items from the local session JSONL for
                          anchored mode and tail-change detection. Default: 12.
  --max-unchanged-skips <n>
                          When the visible tail has not changed, skip at most n consecutive ticks
                          before resending. Default: 1.
  --schedule-mode <mode>  `clock` = fixed wall clock; `after-complete` = wait interval after the
                          previous Codex run completes. Default: clock.
  --wait-timeout-min <n>  Max minutes to wait for one `codex exec resume` invocation. Use 0 to
                          wait without limit. Default: 240.
  --lock-wait-sec <n>     On lock conflict, wait up to n seconds for the old sender to release.
                          Default: 5.
  --replace-existing      If lock is still held, terminate the existing sender that holds the
                          same lock and take over.
  --replace-grace-sec <n> Grace period before escalating from TERM to KILL when replacing.
                          Default: 8.
  --log-file <path>       Log file path. Default: session_bootstrap/logs/codex_continue_<id>.log.
  --lock-file <path>      Lock file path. Default: /tmp/codex_continue_<id>.lock.
  --state-file <path>     State file path. Default:
                          session_bootstrap/state/codex_continue_<id>.state.json.
  --model <name>          Optional model override passed to Codex.
  --profile <name>        Optional Codex profile override.
  --sandbox <mode>        Codex sandbox mode. Default: danger-full-access.
  --ask-for-approval <policy>
                          Codex approval policy. Default: never.
  --config <key=value>    Extra Codex config override. Repeatable.
  --skip-git-repo-check   Forward `--skip-git-repo-check` to Codex. This script already enables
                          it by default for non-interactive resume automation.
  --always-send           Disable unchanged-tail skipping; always send on schedule.
  --dry-run               Print schedule only; do not send.
  -h, --help              Show this help.

Notes:
  - The script resolves the original workspace from ~/.codex/sessions for the given resume id,
    then passes that path via `codex exec -C ... resume`.
  - By default the script sends only the raw message text.
  - If `session_bootstrap/tasks/codex_continue_current_work_prompt.txt` exists and neither
    `--message` nor `--message-file` is provided, that file becomes the default message.
  - Use `--message-mode anchored` if you want the old auto-anchored prompt behavior.
  - Assistant replies produced by a previous auto-continue are not reused as the next anchor.
  - Transient connection errors are retried automatically every 15 seconds until the tick
    succeeds or a non-retryable error appears.
EOF
}

RESUME_ID=""
WORKDIR=""
WORKDIR_EXPLICIT=0
SESSION_FILE=""
SESSION_FILE_RESOLVED=0
MESSAGE="$DEFAULT_MESSAGE"
MESSAGE_FILE=""
MESSAGE_MODE="$DEFAULT_MESSAGE_MODE"
PROJECT_FOCUS="$DEFAULT_PROJECT_FOCUS"
PROJECT_GUIDE_PATHS="$DEFAULT_PROJECT_GUIDE_PATHS"
INTERVAL_MINUTES="$DEFAULT_INTERVAL_MINUTES"
START_AT=""
START_IN_MIN=""
COUNT=0
HISTORY_LIMIT="$DEFAULT_HISTORY_LIMIT"
MAX_UNCHANGED_TAIL_SKIPS="$DEFAULT_MAX_UNCHANGED_TAIL_SKIPS"
SCHEDULE_MODE="$DEFAULT_SCHEDULE_MODE"
WAIT_TIMEOUT_MINUTES="$DEFAULT_WAIT_TIMEOUT_MINUTES"
TRANSIENT_RETRY_DELAY_SECONDS="$DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS"
LOCK_WAIT_SECONDS="$DEFAULT_LOCK_WAIT_SECONDS"
REPLACE_EXISTING=0
REPLACE_GRACE_SECONDS="$DEFAULT_REPLACE_GRACE_SECONDS"
DRY_RUN=0
ALWAYS_SEND=0
MODEL=""
PROFILE=""
SANDBOX_MODE="$DEFAULT_SANDBOX_MODE"
APPROVAL_POLICY="$DEFAULT_APPROVAL_POLICY"
SKIP_GIT_REPO_CHECK=1
CODEX_CONFIG_OVERRIDES=()
LOG_FILE=""
LOCK_FILE=""
STATE_FILE=""
LOG_FILE_EXPLICIT=0
LOCK_FILE_EXPLICIT=0
STATE_FILE_EXPLICIT=0
MESSAGE_EXPLICIT=0
MESSAGE_FILE_EXPLICIT=0

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
    --resume-id)
      [[ $# -ge 2 ]] || { echo "ERROR: --resume-id requires a value." >&2; exit 1; }
      RESUME_ID="$2"
      shift 2
      ;;
    --cd|--cwd|--workdir)
      [[ $# -ge 2 ]] || { echo "ERROR: $1 requires a value." >&2; exit 1; }
      WORKDIR="$2"
      WORKDIR_EXPLICIT=1
      shift 2
      ;;
    --message)
      [[ $# -ge 2 ]] || { echo "ERROR: --message requires a value." >&2; exit 1; }
      MESSAGE="$2"
      MESSAGE_EXPLICIT=1
      shift 2
      ;;
    --message-file)
      [[ $# -ge 2 ]] || { echo "ERROR: --message-file requires a value." >&2; exit 1; }
      MESSAGE_FILE="$2"
      MESSAGE_FILE_EXPLICIT=1
      shift 2
      ;;
    --message-mode)
      [[ $# -ge 2 ]] || { echo "ERROR: --message-mode requires a value." >&2; exit 1; }
      MESSAGE_MODE="$2"
      shift 2
      ;;
    --project-focus)
      [[ $# -ge 2 ]] || { echo "ERROR: --project-focus requires a value." >&2; exit 1; }
      PROJECT_FOCUS="$2"
      shift 2
      ;;
    --project-guide-paths)
      [[ $# -ge 2 ]] || { echo "ERROR: --project-guide-paths requires a value." >&2; exit 1; }
      PROJECT_GUIDE_PATHS="$2"
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
    --model)
      [[ $# -ge 2 ]] || { echo "ERROR: --model requires a value." >&2; exit 1; }
      MODEL="$2"
      shift 2
      ;;
    --profile)
      [[ $# -ge 2 ]] || { echo "ERROR: --profile requires a value." >&2; exit 1; }
      PROFILE="$2"
      shift 2
      ;;
    --sandbox)
      [[ $# -ge 2 ]] || { echo "ERROR: --sandbox requires a value." >&2; exit 1; }
      SANDBOX_MODE="$2"
      shift 2
      ;;
    --ask-for-approval)
      [[ $# -ge 2 ]] || { echo "ERROR: --ask-for-approval requires a value." >&2; exit 1; }
      APPROVAL_POLICY="$2"
      shift 2
      ;;
    --config)
      [[ $# -ge 2 ]] || { echo "ERROR: --config requires a value." >&2; exit 1; }
      CODEX_CONFIG_OVERRIDES+=("$2")
      shift 2
      ;;
    --skip-git-repo-check)
      SKIP_GIT_REPO_CHECK=1
      shift
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

load_message_from_file() {
  local message_path="$1"
  if [[ ! -f "$message_path" ]]; then
    echo "ERROR: message file not found: $message_path" >&2
    exit 1
  fi
  if [[ ! -r "$message_path" ]]; then
    echo "ERROR: message file is not readable: $message_path" >&2
    exit 1
  fi
  MESSAGE="$(<"$message_path")"
}

if (( MESSAGE_EXPLICIT == 1 && MESSAGE_FILE_EXPLICIT == 1 )); then
  echo "ERROR: pass only one of --message or --message-file." >&2
  exit 1
fi

if (( MESSAGE_FILE_EXPLICIT == 1 )); then
  load_message_from_file "$MESSAGE_FILE"
elif (( MESSAGE_EXPLICIT == 0 )) && [[ -f "$DEFAULT_MESSAGE_FILE" ]]; then
  MESSAGE_FILE="$DEFAULT_MESSAGE_FILE"
  load_message_from_file "$MESSAGE_FILE"
fi

if [[ -n "$START_AT" && -n "$START_IN_MIN" ]]; then
  echo "ERROR: use either --start-at or --start-in-min, not both." >&2
  exit 1
fi

if [[ -z "$START_AT" && -z "$START_IN_MIN" ]]; then
  echo "ERROR: --start-at or --start-in-min is required." >&2
  exit 1
fi

if [[ -z "$RESUME_ID" ]]; then
  echo "ERROR: --resume-id is required." >&2
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

if ! [[ "$LOCK_WAIT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --lock-wait-sec must be a non-negative integer." >&2
  exit 1
fi

if ! [[ "$REPLACE_GRACE_SECONDS" =~ ^[0-9]+$ ]] || [[ "$REPLACE_GRACE_SECONDS" -le 0 ]]; then
  echo "ERROR: --replace-grace-sec must be a positive integer." >&2
  exit 1
fi

if [[ -z "$MESSAGE" ]]; then
  echo "ERROR: --message cannot be empty." >&2
  exit 1
fi

case "$MESSAGE_MODE" in
  plain|anchored)
    ;;
  *)
    echo "ERROR: --message-mode must be one of: plain, anchored." >&2
    exit 1
    ;;
esac

case "$SANDBOX_MODE" in
  read-only|workspace-write|danger-full-access)
    ;;
  *)
    echo "ERROR: --sandbox must be one of: read-only, workspace-write, danger-full-access." >&2
    exit 1
    ;;
esac

case "$APPROVAL_POLICY" in
  untrusted|on-failure|on-request|never)
    ;;
  *)
    echo "ERROR: --ask-for-approval must be one of: untrusted, on-failure, on-request, never." >&2
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found." >&2
  exit 127
fi

if ! command -v flock >/dev/null 2>&1; then
  echo "ERROR: flock not found." >&2
  exit 127
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "ERROR: codex not found." >&2
  exit 127
fi

if (( WAIT_TIMEOUT_MINUTES > 0 )) && ! command -v timeout >/dev/null 2>&1; then
  echo "ERROR: timeout not found, but --wait-timeout-min is non-zero." >&2
  exit 127
fi

sanitize_slug() {
  local raw="$1"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//')"
  [[ -n "$raw" ]] || raw="session"
  printf '%s\n' "$raw"
}

resolve_session_context() {
  CODEX_HOME_DIR="$CODEX_HOME_DIR" RESUME_ID="$RESUME_ID" python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

resume_id = os.environ["RESUME_ID"]
root = Path(os.environ["CODEX_HOME_DIR"]) / "sessions"
if not root.is_dir():
    raise SystemExit(1)

matches = []
for path in root.rglob(f"*{resume_id}.jsonl"):
    try:
        stat = path.stat()
    except OSError:
        continue
    matches.append((stat.st_mtime, path))

if not matches:
    raise SystemExit(1)

matches.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
session_path = matches[0][1]
cwd = ""

try:
    with session_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw_line in fh:
            try:
                obj = json.loads(raw_line)
            except Exception:
                continue
            if obj.get("type") != "session_meta":
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            payload_id = str(payload.get("id") or "")
            if payload_id and payload_id != resume_id:
                continue
            cwd = str(payload.get("cwd") or "")
            break
except OSError:
    raise SystemExit(1)

print(f"{session_path}\t{cwd}")
PY
}

inspect_resume_target() {
  CODEX_HOME_DIR="$CODEX_HOME_DIR" RESUME_ID="$RESUME_ID" WORKDIR="$WORKDIR" python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path


def text_of(message: dict) -> str:
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    return " ".join(" ".join(part.split()) for part in parts if part and part.strip())


def compact(text: str, limit: int = 120) -> str:
    normalized = " ".join(text.split()).replace("\t", " ")
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


root = Path(os.environ["CODEX_HOME_DIR"]) / "sessions"
resume_id = os.environ["RESUME_ID"]
workdir = os.environ["WORKDIR"]
if not root.is_dir():
    raise SystemExit(1)

target = None
latest_same_cwd = None

for path in root.rglob("*.jsonl"):
    try:
        stat = path.stat()
    except OSError:
        continue

    session_id = ""
    session_cwd = ""
    message_count = 0
    last_user = ""

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for raw_line in fh:
                try:
                    obj = json.loads(raw_line)
                except Exception:
                    continue
                if obj.get("type") == "session_meta":
                    payload = obj.get("payload")
                    if isinstance(payload, dict):
                        session_id = str(payload.get("id") or session_id)
                        session_cwd = str(payload.get("cwd") or session_cwd)
                    continue
                if obj.get("type") != "response_item":
                    continue
                payload = obj.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != "message":
                    continue
                message_count += 1
                if payload.get("role") == "user":
                    text = text_of(payload)
                    if text:
                        last_user = compact(text)
    except OSError:
        continue

    record = (
        int(stat.st_mtime),
        str(path),
        session_id,
        session_cwd,
        message_count,
        last_user,
    )

    if session_id == resume_id and (
        target is None or (record[0], record[1]) > (target[0], target[1])
    ):
        target = record

    if session_cwd == workdir and (
        latest_same_cwd is None
        or (record[0], record[1]) > (latest_same_cwd[0], latest_same_cwd[1])
    ):
        latest_same_cwd = record

if target is None:
    raise SystemExit(1)

values = [
    str(target[0]),
    target[1],
    target[2],
    target[3],
    str(target[4]),
    target[5],
]
if latest_same_cwd is None:
    values.extend(["", "", "", "", "", ""])
else:
    values.extend(
        [
            str(latest_same_cwd[0]),
            latest_same_cwd[1],
            latest_same_cwd[2],
            latest_same_cwd[3],
            str(latest_same_cwd[4]),
            latest_same_cwd[5],
        ]
    )
print("\t".join(values))
PY
}

SESSION_SLUG="$(sanitize_slug "$RESUME_ID")"
if (( LOG_FILE_EXPLICIT == 0 )); then
  LOG_FILE="$SESSION_DIR/logs/codex_continue_${SESSION_SLUG}.log"
fi
if (( LOCK_FILE_EXPLICIT == 0 )); then
  LOCK_FILE="/tmp/codex_continue_${SESSION_SLUG}.lock"
fi
if (( STATE_FILE_EXPLICIT == 0 )); then
  STATE_FILE="$SESSION_DIR/state/codex_continue_${SESSION_SLUG}.state.json"
fi

resolved_context="$(resolve_session_context 2>/dev/null || true)"
if [[ -n "$resolved_context" ]]; then
  IFS=$'\t' read -r SESSION_FILE resolved_workdir <<<"$resolved_context"
  SESSION_FILE_RESOLVED=1
else
  SESSION_FILE=""
fi

if (( WORKDIR_EXPLICIT == 0 )); then
  WORKDIR="${resolved_workdir:-}"
fi

if [[ -z "$WORKDIR" ]]; then
  echo "ERROR: unable to resolve the original workspace for resume id $RESUME_ID. Pass --cd explicitly." >&2
  exit 1
fi

if [[ ! -d "$WORKDIR" ]]; then
  echo "ERROR: resolved workdir does not exist: $WORKDIR" >&2
  exit 1
fi

RESUME_TARGET_INFO="$(inspect_resume_target 2>/dev/null || true)"
RESUME_TARGET_MTIME=""
RESUME_TARGET_PATH=""
RESUME_TARGET_MESSAGE_COUNT=""
RESUME_TARGET_LAST_USER=""
LATEST_WORKDIR_SESSION_MTIME=""
LATEST_WORKDIR_SESSION_PATH=""
LATEST_WORKDIR_SESSION_ID=""
LATEST_WORKDIR_SESSION_MESSAGE_COUNT=""
LATEST_WORKDIR_SESSION_LAST_USER=""
if [[ -n "$RESUME_TARGET_INFO" ]]; then
  IFS=$'\t' read -r \
    RESUME_TARGET_MTIME \
    RESUME_TARGET_PATH \
    _resume_target_id \
    _resume_target_cwd \
    RESUME_TARGET_MESSAGE_COUNT \
    RESUME_TARGET_LAST_USER \
    LATEST_WORKDIR_SESSION_MTIME \
    LATEST_WORKDIR_SESSION_PATH \
    LATEST_WORKDIR_SESSION_ID \
    _latest_workdir_cwd \
    LATEST_WORKDIR_SESSION_MESSAGE_COUNT \
    LATEST_WORKDIR_SESSION_LAST_USER <<<"$RESUME_TARGET_INFO"
fi

INTERVAL_SEC=$((INTERVAL_MINUTES * 60))
if (( WAIT_TIMEOUT_MINUTES == 0 )); then
  WAIT_TIMEOUT_SECONDS=0
else
  WAIT_TIMEOUT_SECONDS=$((WAIT_TIMEOUT_MINUTES * 60))
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
holders = []
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
    if [[ "$cmd" == *"$SCRIPT_BASENAME"* ]]; then
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
    resume_id) printf '%s' 'resume_id' ;;
    workdir) printf '%s' 'workdir' ;;
    session_file) printf '%s' 'session_file' ;;
    next_fire) printf '%s' 'next_fire' ;;
    interval) printf '%s' 'interval' ;;
    count) printf '%s' 'count' ;;
    dry_run) printf '%s' 'dry_run' ;;
    base_msg) printf '%s' 'message' ;;
    scheduled) printf '%s' 'scheduled' ;;
    retry) printf '%s' 'retry' ;;
    retry_after) printf '%s' 'retry_after' ;;
    error) printf '%s' 'error' ;;
    status) printf '%s' 'status' ;;
    schedule_mode) printf '%s' 'schedule_mode' ;;
    wait_timeout) printf '%s' 'wait_timeout' ;;
    message_mode) printf '%s' 'message_mode' ;;
    sandbox) printf '%s' 'sandbox' ;;
    approval) printf '%s' 'approval' ;;
    message_file) printf '%s' 'message_file' ;;
    sends) printf '%s' 'sends' ;;
    at) printf '%s' 'at' ;;
    reply) printf '%s' 'reply' ;;
    usage) printf '%s' 'usage' ;;
    *) printf '%s' "$1" ;;
  esac
}

kv_line() {
  local key="$1"
  local value="${2:-}"
  local label
  label="$(kv_label "$key")"
  printf '%-12s: %s' "$label" "$value"
}

single_line_text() {
  printf '%s' "$1" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g'
}

is_transient_connection_error_text() {
  local normalized
  normalized="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  [[ -n "$normalized" ]] || return 1

  case "$normalized" in
    *"connection error."*|*"connection error"*|*"typeerror: fetch failed"*|*"fetch failed"*|*"network error"*|*"bad gateway"*|*"gateway timeout"*|*"service unavailable"*|*"upstream connect error"*|*"socket hang up"*|*"connection reset"*|*"connection refused"*|*"connection aborted"*|*"econnreset"*|*"econnrefused"*|*"etimedout"*|*"ehostunreach"*|*"enetunreach"*|*"eai_again"*|*"und_err_connect"*|*"und_err_socket"*|*"und_err_headers_timeout"*|*"und_err_body_timeout"*|*"und_err_connect_timeout"*|*"und_err_dns_resolve_failed"*|*"rate limit"*|*"temporarily unavailable"*)
      return 0
      ;;
  esac

  [[ "$normalized" =~ http[[:space:]]*50(2|3|4) ]]
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
    print("preview     : <empty>")
    raise SystemExit(0)

limit = 6
for idx, line in enumerate(normalized_lines[:limit]):
    prefix = "preview     : " if idx == 0 else "             "
    print(f"{prefix}{line}")
if len(normalized_lines) > limit:
    print("             ...")
PY
}

log_block() {
  local title="$1"
  shift || true
  {
    printf '[%s] %s\n' "$(date '+%F %T %z')" "$title"
    local item
    for item in "$@"; do
      [[ -z "$item" ]] && continue
      printf '  %s\n' "$item"
    done
  } | tee -a "$LOG_FILE"
}

log_transient_retry() {
  local status_text="$1"
  local retry_count="$2"
  local error_text="$3"
  local scheduled_ts="${4:-}"
  local -a lines=()

  lines+=("$(kv_line resume_id "$RESUME_ID")")
  if [[ -n "$scheduled_ts" ]]; then
    lines+=("$(kv_line scheduled "$(format_ts "$scheduled_ts")")")
  fi
  lines+=("$(kv_line retry "$retry_count")")
  lines+=("$(kv_line status "$status_text")")
  lines+=("$(kv_line error "$(single_line_text "$error_text")")")
  lines+=("$(kv_line retry_after "${TRANSIENT_RETRY_DELAY_SECONDS} sec")")
  log_block "retrying" "${lines[@]}"
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
    printf '%s\n' 'unlimited'
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

extract_history_anchor() {
  if [[ ! -f "$SESSION_FILE" ]]; then
    return 1
  fi

  SESSION_FILE="$SESSION_FILE" HISTORY_LIMIT="$HISTORY_LIMIT" AUTO_CONTINUE_MARKER="$AUTO_CONTINUE_MARKER" python3 - <<'PY'
from __future__ import annotations

import json
import os
import sys
from hashlib import sha1
from pathlib import Path


def text_of(message: dict) -> str:
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    return " ".join(" ".join(part.split()) for part in parts if part and part.strip())


def stable_payload_fingerprint(payload) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha1(encoded.encode("utf-8")).hexdigest()


def compact_entry(entry):
    return {
        "role": entry.get("role"),
        "text": entry.get("text"),
        "timestamp": entry.get("timestamp"),
    }


def is_internal_user_message(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return False
    prefixes = (
        "# AGENTS.md instructions",
        "<environment_context>",
        "System:",
        "An async command you ran earlier has completed.",
        "A scheduled reminder has been triggered.",
        "A scheduled cron event was triggered.",
    )
    return normalized.startswith(prefixes) or "<environment_context>" in normalized


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
        if assistant_replied_to_auto_user(entries, index):
            continue
        return compact_entry(candidate)
    return None


session_file = Path(os.environ["SESSION_FILE"])
history_limit = int(os.environ["HISTORY_LIMIT"])
marker = os.environ["AUTO_CONTINUE_MARKER"]
entries = []

with session_file.open("r", encoding="utf-8", errors="ignore") as fh:
    for raw_line in fh:
        try:
            obj = json.loads(raw_line)
        except Exception:
            continue
        if obj.get("type") != "response_item":
            continue
        payload = obj.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = text_of(payload)
        if not text:
            continue
        entries.append(
            {
                "role": role,
                "text": text,
                "timestamp": str(obj.get("timestamp") or ""),
                "is_auto_user": role == "user" and text.startswith(marker),
                "is_internal_user": role == "user" and is_internal_user_message(text),
            }
        )

entries = entries[-history_limit:]
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
  PROJECT_ROOT="$WORKDIR" \
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
  RESUME_ID="$RESUME_ID" \
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
    "resume_id": os.environ["RESUME_ID"],
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
  local scheduled_ts="$1"
  STATE_FILE="$STATE_FILE" \
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
state["last_success"] = last_success
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

LAST_CODEX_STDOUT_FILE=""
LAST_CODEX_STDERR_FILE=""
LAST_CODEX_LAST_MESSAGE_FILE=""

cleanup_last_codex_files() {
  [[ -n "$LAST_CODEX_STDOUT_FILE" && -f "$LAST_CODEX_STDOUT_FILE" ]] && rm -f "$LAST_CODEX_STDOUT_FILE"
  [[ -n "$LAST_CODEX_STDERR_FILE" && -f "$LAST_CODEX_STDERR_FILE" ]] && rm -f "$LAST_CODEX_STDERR_FILE"
  [[ -n "$LAST_CODEX_LAST_MESSAGE_FILE" && -f "$LAST_CODEX_LAST_MESSAGE_FILE" ]] && rm -f "$LAST_CODEX_LAST_MESSAGE_FILE"
  LAST_CODEX_STDOUT_FILE=""
  LAST_CODEX_STDERR_FILE=""
  LAST_CODEX_LAST_MESSAGE_FILE=""
}

collect_last_codex_output() {
  local output=""
  if [[ -n "$LAST_CODEX_STDOUT_FILE" && -f "$LAST_CODEX_STDOUT_FILE" ]]; then
    output+="$(cat "$LAST_CODEX_STDOUT_FILE")"
  fi
  if [[ -n "$LAST_CODEX_STDERR_FILE" && -f "$LAST_CODEX_STDERR_FILE" ]]; then
    if [[ -n "$output" ]]; then
      output+=$'\n'
    fi
    output+="$(cat "$LAST_CODEX_STDERR_FILE")"
  fi
  printf '%s' "$output"
}

parse_codex_exec_output() {
  local stdout_file="$1"
  JSONL_FILE="$stdout_file" python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

path = Path(os.environ["JSONL_FILE"])
thread_id = ""
usage = {}

try:
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except Exception:
                continue
            obj_type = obj.get("type")
            if obj_type == "thread.started":
                thread_id = str(obj.get("thread_id") or "")
            elif obj_type == "turn.completed":
                maybe_usage = obj.get("usage")
                if isinstance(maybe_usage, dict):
                    usage = maybe_usage
except OSError:
    raise SystemExit(1)

print(json.dumps({"thread_id": thread_id, "usage": usage}, ensure_ascii=False))
PY
}

json_field() {
  local json_text="$1"
  local field_name="$2"
  JSON_INPUT="$json_text" FIELD_NAME="$field_name" python3 - <<'PY'
from __future__ import annotations

import json
import os

text = os.environ["JSON_INPUT"].strip()
field_name = os.environ["FIELD_NAME"]
if not text:
    raise SystemExit(1)
obj = json.loads(text)
parts = field_name.split(".")
current = obj
for part in parts:
    if not isinstance(current, dict):
        raise SystemExit(1)
    current = current.get(part)
if current is None:
    raise SystemExit(1)
if isinstance(current, (dict, list)):
    print(json.dumps(current, ensure_ascii=False))
else:
    print(current)
PY
}

read_last_message() {
  if [[ -n "$LAST_CODEX_LAST_MESSAGE_FILE" && -f "$LAST_CODEX_LAST_MESSAGE_FILE" ]]; then
    cat "$LAST_CODEX_LAST_MESSAGE_FILE"
  fi
}

run_codex_resume_once() {
  local prompt_text="$1"
  cleanup_last_codex_files

  LAST_CODEX_STDOUT_FILE="$(mktemp)"
  LAST_CODEX_STDERR_FILE="$(mktemp)"
  LAST_CODEX_LAST_MESSAGE_FILE="$(mktemp)"

  local -a cmd=(
    codex
    --ask-for-approval
    "$APPROVAL_POLICY"
    exec
    --sandbox
    "$SANDBOX_MODE"
    -C
    "$WORKDIR"
  )

  if [[ -n "$MODEL" ]]; then
    cmd+=(--model "$MODEL")
  fi
  if [[ -n "$PROFILE" ]]; then
    cmd+=(--profile "$PROFILE")
  fi
  local config_override
  for config_override in "${CODEX_CONFIG_OVERRIDES[@]}"; do
    cmd+=(--config "$config_override")
  done
  if (( SKIP_GIT_REPO_CHECK == 1 )); then
    cmd+=(--skip-git-repo-check)
  fi
  cmd+=(
    resume
    --json
    -o
    "$LAST_CODEX_LAST_MESSAGE_FILE"
    "$RESUME_ID"
    "$prompt_text"
  )

  if (( WAIT_TIMEOUT_SECONDS > 0 )); then
    timeout --foreground "$WAIT_TIMEOUT_SECONDS" "${cmd[@]}" >"$LAST_CODEX_STDOUT_FILE" 2>"$LAST_CODEX_STDERR_FILE"
  else
    "${cmd[@]}" >"$LAST_CODEX_STDOUT_FILE" 2>"$LAST_CODEX_STDERR_FILE"
  fi
}

run_codex_resume_with_retry() {
  local prompt_text="$1"
  local scheduled_ts="$2"
  local retry_count=0
  local output=""
  local rc=0

  while true; do
    if run_codex_resume_once "$prompt_text"; then
      rc=0
    else
      rc=$?
    fi

    if (( rc == 0 )); then
      return 0
    fi

    output="$(collect_last_codex_output)"
    if (( rc == 124 )); then
      return 124
    fi

    if is_transient_connection_error_text "$output"; then
      retry_count=$((retry_count + 1))
      log_transient_retry "codex exec resume hit a transient error; retrying" "$retry_count" "$output" "$scheduled_ts"
      sleep "$TRANSIENT_RETRY_DELAY_SECONDS"
      continue
    fi
    return "$rc"
  done
}

submit_once() {
  local scheduled_ts="$1"
  local anchor_json=""
  local effective_message=""

  anchor_json="$(extract_history_anchor 2>/dev/null || true)"
  if [[ "$MESSAGE_MODE" == "anchored" ]]; then
    effective_message="$(build_effective_message_from_anchor "$anchor_json")"
  else
    effective_message="$MESSAGE"
  fi

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
        write_skip_state "$scheduled_ts"
        log_block "skipped" \
          "$(kv_line resume_id "$RESUME_ID")" \
          "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
          "$(kv_line status "visible tail unchanged; skipping this tick (${unchanged_tail_skips}/${MAX_UNCHANGED_TAIL_SKIPS})")"
        return 10
      fi
    fi
  fi

  local -a preview_lines=()
  while IFS= read -r line; do
    preview_lines+=("$line")
  done < <(format_preview_lines "$effective_message")

  if (( DRY_RUN == 1 )); then
    log_block "dry-run" \
      "$(kv_line resume_id "$RESUME_ID")" \
      "$(kv_line workdir "$WORKDIR")" \
      "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
      "$(kv_line interval "${INTERVAL_MINUTES} min")" \
      "$(kv_line count "$COUNT")" \
      "$(kv_line status "$([[ "$ALWAYS_SEND" -eq 1 ]] && printf '%s' 'always send' || printf 'send when tail changes (max skip %s)' "$MAX_UNCHANGED_TAIL_SKIPS")")" \
      "${preview_lines[@]}"
    return 0
  fi

  local codex_rc=0
  if run_codex_resume_with_retry "$effective_message" "$scheduled_ts"; then
    codex_rc=0
  else
    codex_rc=$?
  fi

  if (( codex_rc != 0 )); then
    local output
    output="$(collect_last_codex_output)"
    local error_text
    if (( codex_rc == 124 )); then
      error_text="codex exec resume timed out after ${WAIT_TIMEOUT_MINUTES} min"
    elif [[ -n "$output" ]]; then
      error_text="$(single_line_text "$output")"
    else
      error_text="codex exec resume failed with rc=$codex_rc"
    fi
    log_block "submit-failed" \
      "$(kv_line resume_id "$RESUME_ID")" \
      "$(kv_line workdir "$WORKDIR")" \
      "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
      "$(kv_line error "$error_text")"
    cleanup_last_codex_files
    return 1
  fi

  local parsed_json=""
  parsed_json="$(parse_codex_exec_output "$LAST_CODEX_STDOUT_FILE" 2>/dev/null || true)"
  local thread_id=""
  thread_id="$(json_field "$parsed_json" thread_id 2>/dev/null || true)"
  [[ -n "$thread_id" ]] || thread_id="$RESUME_ID"

  local usage_input=""
  local usage_cached=""
  local usage_output=""
  usage_input="$(json_field "$parsed_json" usage.input_tokens 2>/dev/null || true)"
  usage_cached="$(json_field "$parsed_json" usage.cached_input_tokens 2>/dev/null || true)"
  usage_output="$(json_field "$parsed_json" usage.output_tokens 2>/dev/null || true)"

  local usage_summary=""
  if [[ -n "$usage_input" || -n "$usage_cached" || -n "$usage_output" ]]; then
    usage_summary="input=${usage_input:-0}, cached=${usage_cached:-0}, output=${usage_output:-0}"
  fi

  local reply_text=""
  reply_text="$(read_last_message || true)"
  local state_anchor_json="$anchor_json"
  local post_anchor_json=""
  post_anchor_json="$(extract_history_anchor 2>/dev/null || true)"
  if [[ -n "$post_anchor_json" ]]; then
    state_anchor_json="$post_anchor_json"
  fi
  write_submit_state "$state_anchor_json" "$thread_id" "$scheduled_ts" "ok"
  log_block "turn-completed" \
    "$(kv_line resume_id "$RESUME_ID")" \
    "$(kv_line workdir "$WORKDIR")" \
    "$(kv_line scheduled "$(format_ts "$scheduled_ts")")" \
    "$(kv_line status "codex turn completed")" \
    "$(kv_line usage "${usage_summary:-n/a}")" \
    "$(kv_line reply "$(single_line_text "$reply_text")")" \
    "${preview_lines[@]}"
  cleanup_last_codex_files
  return 0
}

trap 'cleanup_last_codex_files; log_block "stopped" "$(kv_line resume_id "$RESUME_ID")"; exit 130' INT TERM

NEXT_FIRE_TS="$(compute_initial_fire_ts)"
SENT=0

log_block "started" \
  "$(kv_line resume_id "$RESUME_ID")" \
  "$(kv_line workdir "$WORKDIR")" \
  "$(kv_line session_file "${SESSION_FILE:-unresolved}")" \
  "$(kv_line next_fire "$(format_ts "$NEXT_FIRE_TS")")" \
  "$(kv_line interval "${INTERVAL_MINUTES} min")" \
  "$(kv_line count "$COUNT")" \
  "$(kv_line dry_run "$DRY_RUN")" \
  "$(kv_line message_mode "$MESSAGE_MODE")" \
  "$(kv_line sandbox "$SANDBOX_MODE")" \
  "$(kv_line approval "$APPROVAL_POLICY")" \
  "$(kv_line message_file "${MESSAGE_FILE:-inline}")" \
  "$(kv_line status "$([[ "$ALWAYS_SEND" -eq 1 ]] && printf '%s' 'always send' || printf 'send when tail changes (max skip %s)' "$MAX_UNCHANGED_TAIL_SKIPS")")" \
  "$(kv_line schedule_mode "$SCHEDULE_MODE")" \
  "$(kv_line wait_timeout "$(format_wait_timeout)")" \
  "$(kv_line base_msg "$(single_line_text "$MESSAGE")")"

if [[ -n "$LATEST_WORKDIR_SESSION_ID" && "$LATEST_WORKDIR_SESSION_ID" != "$RESUME_ID" ]]; then
  log_block "warning" \
    "$(kv_line resume_id "$RESUME_ID")" \
    "$(kv_line status "target session is not the newest session for this workspace")" \
    "target_file : ${RESUME_TARGET_PATH:-${SESSION_FILE:-unknown}}" \
    "target_msgs : ${RESUME_TARGET_MESSAGE_COUNT:-unknown}" \
    "target_user : ${RESUME_TARGET_LAST_USER:-n/a}" \
    "latest_id   : $LATEST_WORKDIR_SESSION_ID" \
    "latest_file : ${LATEST_WORKDIR_SESSION_PATH:-unknown}" \
    "latest_at   : $(format_ts "$LATEST_WORKDIR_SESSION_MTIME")" \
    "latest_msgs : ${LATEST_WORKDIR_SESSION_MESSAGE_COUNT:-unknown}" \
    "latest_user : ${LATEST_WORKDIR_SESSION_LAST_USER:-n/a}" \
    "tip         : if you meant the current workspace conversation, use --resume-id $LATEST_WORKDIR_SESSION_ID"
fi

if [[ "$MESSAGE_MODE" == "plain" && "$MESSAGE" == "$DEFAULT_MESSAGE" ]]; then
  if [[ "$RESUME_TARGET_MESSAGE_COUNT" =~ ^[0-9]+$ ]] && (( RESUME_TARGET_MESSAGE_COUNT <= 10 )); then
    log_block "warning" \
      "$(kv_line resume_id "$RESUME_ID")" \
      "$(kv_line status "target session has very little recorded history; plain '继续' may appear ineffective")" \
      "target_file : ${RESUME_TARGET_PATH:-${SESSION_FILE:-unknown}}" \
      "target_msgs : ${RESUME_TARGET_MESSAGE_COUNT:-unknown}" \
      "target_user : ${RESUME_TARGET_LAST_USER:-n/a}" \
      "tip         : use a richer working session id, or switch to --message-mode anchored"
  fi
fi

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
      "$(kv_line resume_id "$RESUME_ID")" \
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
    "$(kv_line resume_id "$RESUME_ID")" \
    "$(kv_line at "$(format_ts "$NEXT_FIRE_TS")")" \
    "$(kv_line sends "$SENT")"
done
