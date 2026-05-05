#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_ENV_FILE="$SESSION_DIR/config/local.env"

usage() {
  cat <<'EOF'
Usage:
  wait_for_ssh_then_rerun_quick.sh --env <path> [options]

Options:
  --prefix <execution_prefix>      Prefix for the fresh EXECUTION_ID
  --max-wait-sec <n>               Stop waiting after n seconds (default: 3600)
  --check-interval-sec <n>         Seconds between retries (default: 300)
  --ssh-timeout-sec <n>            Per-probe SSH timeout passed to recheck script (default: 12)

What it does:
  - Repeatedly invokes rerun_quick_after_ssh_recovery.sh at a low frequency.
  - Exits immediately when the recheck succeeds.
  - Stops after --max-wait-sec instead of waiting forever.

Notes:
  - Intended to replace manual periodic SSH probing.
  - Safe to rerun: the underlying recheck script only mints a fresh EXECUTION_ID after SSH is reachable.
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
EXEC_PREFIX="quick_rpc_tune_recheck"
MAX_WAIT_SEC=3600
CHECK_INTERVAL_SEC=300
SSH_TIMEOUT_SEC=12

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --prefix)
      EXEC_PREFIX="${2:-}"
      shift 2
      ;;
    --max-wait-sec)
      MAX_WAIT_SEC="${2:-}"
      shift 2
      ;;
    --check-interval-sec)
      CHECK_INTERVAL_SEC="${2:-}"
      shift 2
      ;;
    --ssh-timeout-sec)
      SSH_TIMEOUT_SEC="${2:-}"
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

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

for value_name in MAX_WAIT_SEC CHECK_INTERVAL_SEC SSH_TIMEOUT_SEC; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" -lt 1 ]]; then
    echo "ERROR: ${value_name} must be a positive integer (got: $value)." >&2
    exit 1
  fi
done

RECHECK_SCRIPT="$SCRIPT_DIR/rerun_quick_after_ssh_recovery.sh"
if [[ ! -x "$RECHECK_SCRIPT" ]]; then
  echo "ERROR: recheck script is missing or not executable: $RECHECK_SCRIPT" >&2
  exit 1
fi

start_epoch="$(date +%s)"
attempt=0

while true; do
  now_epoch="$(date +%s)"
  elapsed="$((now_epoch - start_epoch))"
  if [[ "$elapsed" -ge "$MAX_WAIT_SEC" ]]; then
    echo "Wait budget exhausted without SSH recovery."
    echo "  elapsed_sec: $elapsed"
    echo "  max_wait_sec: $MAX_WAIT_SEC"
    exit 124
  fi

  attempt="$((attempt + 1))"
  echo "[$(date -Iseconds)] attempt=$attempt elapsed_sec=$elapsed action=recheck"

  set +e
  bash "$RECHECK_SCRIPT" \
    --env "$ENV_FILE" \
    --prefix "$EXEC_PREFIX" \
    --ssh-timeout-sec "$SSH_TIMEOUT_SEC"
  rc=$?
  set -e

  if [[ "$rc" -eq 0 ]]; then
    echo "[$(date -Iseconds)] recheck succeeded"
    exit 0
  fi

  if [[ "$rc" -ne 124 ]]; then
    echo "[$(date -Iseconds)] recheck failed with non-timeout rc=$rc; aborting"
    exit "$rc"
  fi

  sleep_for="$CHECK_INTERVAL_SEC"
  remaining="$((MAX_WAIT_SEC - ( $(date +%s) - start_epoch ) ))"
  if [[ "$remaining" -lt "$sleep_for" ]]; then
    sleep_for="$remaining"
  fi
  if [[ "$sleep_for" -le 0 ]]; then
    continue
  fi

  echo "[$(date -Iseconds)] remote still unavailable; sleeping_sec=$sleep_for"
  sleep "$sleep_for"
done
