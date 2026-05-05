#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ssh_with_password.sh --host <ip_or_host> --user <user> --pass <password> [--port <port>] -- <remote command>

Example:
  bash ./session_bootstrap/scripts/ssh_with_password.sh \
    --host 10.194.7.123 --user user --pass user -- \
    "hostname && whoami"
EOF
}

HOST=""
SSH_USER=""
SSH_PASS=""
PORT="22"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --user)
      SSH_USER="${2:-}"
      shift 2
      ;;
    --pass)
      SSH_PASS="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --)
      shift
      break
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

if [[ -z "$HOST" || -z "$SSH_USER" || -z "$SSH_PASS" ]]; then
  echo "ERROR: --host/--user/--pass are required." >&2
  usage >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  echo "ERROR: remote command is required after --" >&2
  usage >&2
  exit 1
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ERROR: ssh not found in PATH." >&2
  exit 1
fi

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

build_remote_command() {
  if [[ $# -eq 1 ]]; then
    printf '%s' "$1"
    return 0
  fi

  local remote_command=""
  local arg=""
  for arg in "$@"; do
    if [[ -n "$remote_command" ]]; then
      remote_command+=" "
    fi
    remote_command+="$(shell_quote "$arg")"
  done
  printf '%s' "$remote_command"
}

REMOTE_COMMAND="$(build_remote_command "$@")"
SSH_OPTIONS=(
  -p "$PORT"
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
)
if [[ "${SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER:-0}" != "1" ]]; then
  SSH_CONTROL_DIR="${TMPDIR:-/tmp}/ssh_mux"
  mkdir -p "$SSH_CONTROL_DIR"
  chmod 700 "$SSH_CONTROL_DIR" >/dev/null 2>&1 || true
  SSH_OPTIONS+=(
    -o ControlMaster=auto
    -o ControlPersist=60
    -o ControlPath="$SSH_CONTROL_DIR/%C"
  )
fi

ASKPASS_FILE="$(mktemp /tmp/ssh_askpass_XXXXXX.sh)"
cleanup() {
  rm -f "$ASKPASS_FILE"
}
trap cleanup EXIT

cat >"$ASKPASS_FILE" <<'EOF'
#!/bin/sh
printf '%s\n' "${SSH_ASKPASS_PASSWORD:-}"
EOF
chmod 700 "$ASKPASS_FILE"

SSH_ASKPASS_PASSWORD="$SSH_PASS" \
DISPLAY="${DISPLAY:-:0}" \
SSH_ASKPASS="$ASKPASS_FILE" \
SSH_ASKPASS_REQUIRE=force \
setsid -w \
ssh \
  "${SSH_OPTIONS[@]}" \
  "${SSH_USER}@${HOST}" \
  "$REMOTE_COMMAND"
