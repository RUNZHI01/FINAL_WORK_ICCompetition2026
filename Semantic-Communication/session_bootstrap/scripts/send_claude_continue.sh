#!/usr/bin/env bash
# send_claude_continue.sh — Keep a Claude Code session alive with auto-continue
#
# Dual-mode approach:
#   Mode A (primary):  claude -p "continue" --continue --dangerously-skip-permissions
#   Mode B (fallback): tmux send-keys to an already-running Claude session
#
# Usage:
#   ./send_claude_continue.sh [OPTIONS]
#
# Options:
#   --start-in-min N      Wait N minutes before first send (default: 1)
#   --count N             Total number of continue prompts to send (default: 600)
#   --interval-min N      Minutes between sends (default: 5)
#   --schedule-mode MODE  "clock" (align to minute boundary) or "fixed" (default: clock)
#   --session-id ID       Resume specific session ID (default: auto --continue)
#   --mode A|B|auto       Force mode A, B, or auto-detect (default: auto)
#   --tmux-session NAME   Bind to specific tmux session name (mode B only)
#   --no-restart          Don't try to restart Claude if it's not running
#   --log-dir DIR         Directory for logs (default: /tmp/claude-continue)
#   --replace-existing    Kill any previous instance of this script
#   --prompt TEXT         Custom prompt instead of "continue" (default: "continue")
#   --help                Show this help
#
set -euo pipefail

# ======================== Defaults ========================
START_IN_MIN="${START_IN_MIN:-1}"
COUNT="${COUNT:-600}"
INTERVAL_MIN="${INTERVAL_MIN:-5}"
SCHEDULE_MODE="${SCHEDULE_MODE:-clock}"
SESSION_ID="${SESSION_ID:-}"
FORCE_MODE="${FORCE_MODE:-auto}"
TMUX_SESSION="${TMUX_SESSION:-}"
NO_RESTART="${NO_RESTART:-0}"
LOG_DIR="${LOG_DIR:-/tmp/claude-continue}"
REPLACE_EXISTING="${REPLACE_EXISTING:-0}"
CUSTOM_PROMPT="${CUSTOM_PROMPT:-continue}"
HISTORY_LIMIT="${HISTORY_LIMIT:-100}"

# ======================== Argument Parsing ========================
while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-in-min)    START_IN_MIN="$2"; shift 2 ;;
    --count)           COUNT="$2"; shift 2 ;;
    --interval-min)    INTERVAL_MIN="$2"; shift 2 ;;
    --schedule-mode)    SCHEDULE_MODE="$2"; shift 2 ;;
    --session-id)      SESSION_ID="$2"; shift 2 ;;
    --mode)            FORCE_MODE="$2"; shift 2 ;;
    --tmux-session)    TMUX_SESSION="$2"; shift 2 ;;
    --no-restart)      NO_RESTART=1; shift ;;
    --log-dir)         LOG_DIR="$2"; shift 2 ;;
    --replace-existing) REPLACE_EXISTING=1; shift ;;
    --prompt)          CUSTOM_PROMPT="$2"; shift 2 ;;
    --history-limit)   HISTORY_LIMIT="$2"; shift 2 ;;
    --help|-h)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ======================== Setup ========================
INTERVAL_SEC=$((INTERVAL_MIN * 60))
LOG_FILE="$LOG_DIR/continue_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="$LOG_DIR/continue.pid"
HISTORY_FILE="$LOG_DIR/history.jsonl"

mkdir -p "$LOG_DIR"

# ======================== Logging ========================

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$msg" | tee -a "$LOG_FILE"
}

log_verbose() {
  [[ -n "${VERBOSE:-}" ]] && log "[verbose] $*"
}

# ======================== Process Management ========================

kill_existing() {
  if [[ -f "$PID_FILE" ]]; then
    local old_pid
    old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      log "Killing existing instance (PID $old_pid)..."
      kill "$old_pid" 2>/dev/null || true
      sleep 1
      # Force kill if still running
      if kill -0 "$old_pid" 2>/dev/null; then
        kill -9 "$old_pid" 2>/dev/null || true
      fi
    fi
    rm -f "$PID_FILE"
  fi
}

cleanup() {
  log "Cleaning up..."
  rm -f "$PID_FILE"
  log "Stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM SIGHUP

# ======================== History ========================

record_history() {
  local mode="$1" status="$2" detail="${3:-}"
  local entry
  entry="$(jq -n \
    --arg ts "$(date -Iseconds)" \
    --arg mode "$mode" \
    --arg status "$status" \
    --arg detail "$detail" \
    '{timestamp: $ts, mode: $mode, status: $status, detail: $detail}')"
  echo "$entry" >> "$HISTORY_FILE"
  # Trim to limit
  if [[ $(wc -l < "$HISTORY_FILE") -gt $HISTORY_LIMIT ]]; then
    tail -n "$HISTORY_LIMIT" "$HISTORY_FILE" > "$HISTORY_FILE.tmp"
    mv "$HISTORY_FILE.tmp" "$HISTORY_FILE"
  fi
}

# ======================== Mode Detection ========================

detect_mode() {
  if [[ "$FORCE_MODE" != "auto" ]]; then
    echo "$FORCE_MODE"
    return
  fi

  # Check if tmux is available and has a Claude session
  if command -v tmux &>/dev/null; then
    local tmux_sessions
    tmux_sessions="$(tmux list-sessions -F '#{session_name}' 2>/dev/null || true)"
    if [[ -n "$tmux_sessions" ]]; then
      for sess in $tmux_sessions; do
        if tmux list-panes -t "$sess" -F '#{pane_pid}' 2>/dev/null | while read -r pid; do
          if ps -p "$pid" -o args= 2>/dev/null | grep -qE 'claude|Claude'; then
            echo "B"
            return
          fi
        done; then
          :
        fi
      done
    fi
  fi

  # Check if claude CLI is available
  if command -v claude &>/dev/null; then
    echo "A"
    return
  fi

  echo "none"
}

# ======================== Mode A: claude -p --continue ========================

run_mode_a() {
  local session_flag=""
  if [[ -n "$SESSION_ID" ]]; then
    session_flag="--resume $SESSION_ID"
  else
    session_flag="--continue"
  fi

  local cmd
  # Build the claude command with max permissions
  cmd="claude -p $(printf '%q' "$CUSTOM_PROMPT") $session_flag --dangerously-skip-permissions --verbose"

  log "[Mode A] Executing: $cmd"

  # Execute with timeout (max 4 minutes per invocation to avoid blocking the schedule)
  local output
  local exit_code=0
  output="$(timeout 240 bash -c "$cmd" 2>&1)" || exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    log "[Mode A] Success (response length: $(echo "$output" | wc -c) bytes)"
    record_history "A" "success" "response_$(echo "$output" | wc -c)_bytes"
    return 0
  elif [[ $exit_code -eq 124 ]]; then
    log "[Mode A] Timeout after 240s (Claude may still be processing)"
    record_history "A" "timeout" "240s_limit"
    return 0  # Don't fail on timeout, Claude might still be working
  else
    log "[Mode A] Failed with exit code $exit_code"
    log "[Mode A] Output: $(echo "$output" | tail -5)"
    record_history "A" "failed" "exit_$exit_code"
    return 1
  fi
}

# ======================== Mode B: tmux send-keys ========================

find_tmux_target() {
  if [[ -n "$TMUX_SESSION" ]]; then
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
      echo "$TMUX_SESSION"
      return 0
    else
      log "[Mode B] Specified tmux session '$TMUX_SESSION' not found"
      return 1
    fi
  fi

  # Auto-detect: find tmux session with Claude
  local tmux_sessions
  tmux_sessions="$(tmux list-sessions -F '#{session_name}' 2>/dev/null || true)"
  for sess in $tmux_sessions; do
    while read -r pid; do
      if ps -p "$pid" -o args= 2>/dev/null | grep -qE 'claude|Claude'; then
        echo "$sess"
        return 0
      fi
    done < <(tmux list-panes -t "$sess" -F '#{pane_pid}' 2>/dev/null)
  done

  return 1
}

check_claude_idle_in_tmux() {
  local target="$1"
  # Heuristic: check if the last line in the pane looks like a prompt
  # Claude Code shows a prompt when idle
  local last_line
  last_line="$(tmux capture-pane -t "$target" -p | tail -1 2>/dev/null || true)"

  # If last line contains common prompt patterns, Claude is idle
  if echo "$last_line" | grep -qE '^\S+>\s*$|^\?\s|press.*enter|continue|y/n'; then
    return 0  # idle
  fi

  # Check CPU usage of the claude process
  local pane_pid
  pane_pid="$(tmux list-panes -t "$target" -F '#{pane_pid}' 2>/dev/null | head -1)"
  if [[ -n "$pane_pid" ]] && ps -p "$pane_pid" -o %cpu= 2>/dev/null | awk '{exit ($1 < 1) ? 0 : 1}'; then
    return 0  # low CPU, likely idle
  fi

  return 1  # busy
}

run_mode_b() {
  local target
  target="$(find_tmux_target)" || {
    log "[Mode B] No Claude tmux session found"
    record_history "B" "failed" "no_tmux_session"
    return 1
  }

  # Wait for Claude to be idle (max 60 seconds)
  local wait_count=0
  while [[ $wait_count -lt 12 ]]; do
    if check_claude_idle_in_tmux "$target"; then
      break
    fi
    log_verbose "[Mode B] Claude still busy, waiting 5s..."
    sleep 5
    wait_count=$((wait_count + 1))
  done

  if [[ $wait_count -ge 12 ]]; then
    log "[Mode B] Claude still busy after 60s, sending anyway (may queue)"
  fi

  log "[Mode B] Sending '$CUSTOM_PROMPT' to tmux session '$target'"
  tmux send-keys -t "$target" "$CUSTOM_PROMPT" Enter

  record_history "B" "sent" "tmux:$target"
  return 0
}

# ======================== Restart Claude ========================

try_restart_claude() {
  if [[ "$NO_RESTART" -eq 1 ]]; then
    log "Auto-restart disabled (--no-restart)"
    return 1
  fi

  if ! command -v claude &>/dev/null; then
    log "claude CLI not found, cannot restart"
    return 1
  fi

  log "Attempting to start Claude in a new tmux session..."

  local sess_name="${TMUX_SESSION:-claude-auto-$(date +%s)}"

  # Check if tmux is available
  if ! command -v tmux &>/dev/null; then
    log "tmux not available, cannot auto-restart"
    return 1
  fi

  # Start Claude in a new tmux session
  tmux new-session -d -s "$sess_name" \
    "claude --dangerously-skip-permissions --verbose 2>&1 | tee -a '$LOG_DIR/claude_$(date +%Y%m%d_%H%M%S).log'" \
    || {
      log "Failed to start Claude in tmux"
      return 1
    }

  TMUX_SESSION="$sess_name"
  log "Claude started in tmux session '$sess_name'"

  # Wait for Claude to initialize
  sleep 10
  return 0
}

# ======================== Wait Calculations ========================

calc_clock_wait() {
  local now
  now="$(date +%s)"
  local min
  min="$((now / 60))"
  local next
  next="$(((min / INTERVAL_MIN + 1) * INTERVAL_MIN * 60))"
  local wait
  wait="$((next - now))"
  if [[ $wait -lt 0 ]]; then
    wait="$((wait + INTERVAL_MIN * 60))"
  fi
  echo "$wait"
}

# ======================== Main ========================

# Check dependencies
for cmd in jq; do
  if ! command -v "$cmd" &>/dev/null; then
    log "ERROR: $cmd is required but not found"
    exit 1
  fi
done

# Kill existing if requested
if [[ "$REPLACE_EXISTING" -eq 1 ]]; then
  kill_existing
fi

# Write PID file
echo "$$" > "$PID_FILE"

log "========================================"
log "Claude Code Continue Scheduler"
log "========================================"
log "Mode:           $FORCE_MODE (auto-detect if 'auto')"
log "Schedule:       $SCHEDULE_MODE, every $INTERVAL_MIN min"
log "Count:          $COUNT"
log "Start in:       $START_IN_MIN min"
log "Session ID:     ${SESSION_ID:-auto (--continue)}"
log "Custom prompt:  $CUSTOM_PROMPT"
log "Log file:       $LOG_FILE"
log "History file:   $HISTORY_FILE"
log "PID file:       $PID_FILE"
log "No restart:     $NO_RESTART"
log "========================================"
echo ""

# Detect mode
current_mode="$(detect_mode)"
log "Detected mode: $current_mode"

if [[ "$current_mode" == "none" ]]; then
  log "ERROR: Cannot detect Claude (no tmux session with claude, and claude CLI not found)"
  log "Either start Claude in tmux first, or ensure 'claude' CLI is in PATH"
  exit 1
fi

# Initial wait
if [[ $START_IN_MIN -gt 0 ]]; then
  log "Waiting $START_IN_MIN minutes before first send..."
  sleep $((START_IN_MIN * 60))
fi

# Main loop
sent=0
consecutive_failures=0
MAX_FAILURES=5

while [[ $sent -lt $COUNT ]]; do
  sent=$((sent + 1))
  log "--- [$sent/$COUNT] ---"

  # Re-detect mode each iteration (in case situation changed)
  if [[ "$FORCE_MODE" == "auto" ]]; then
    current_mode="$(detect_mode)"
    log_verbose "Current mode: $current_mode"
  else
    current_mode="$FORCE_MODE"
  fi

  local_result=0

  case "$current_mode" in
    A)
      run_mode_a || local_result=$?
      ;;
    B)
      run_mode_b || local_result=$?
      ;;
    *)
      log "Unknown mode '$current_mode', trying Mode A as fallback"
      run_mode_a || local_result=$?
      ;;
  esac

  if [[ $local_result -eq 0 ]]; then
    consecutive_failures=0
  else
    consecutive_failures=$((consecutive_failures + 1))
    log "Consecutive failures: $consecutive_failures"

    if [[ $consecutive_failures -ge $MAX_FAILURES ]]; then
      log "Too many failures ($consecutive_failures), attempting restart..."
      if try_restart_claude; then
        consecutive_failures=0
        current_mode="B"  # Switch to tmux mode since we just started in tmux
      else
        log "Restart failed. Waiting extra 5 minutes before retry..."
        sleep 300
      fi
    fi
  fi

  if [[ $sent -ge $COUNT ]]; then
    break
  fi

  # Calculate next wait
  if [[ "$SCHEDULE_MODE" == "clock" ]]; then
    wait_sec="$(calc_clock_wait)"
  else
    wait_sec="$INTERVAL_SEC"
  fi

  log "Next send in $((wait_sec / 60)) min $((wait_sec % 60)) sec"
  sleep "$wait_sec"
done

log "========================================"
log "Done. Sent $sent '$CUSTOM_PROMPT' prompts."
log "History: $HISTORY_FILE"
log "========================================"
cleanup
