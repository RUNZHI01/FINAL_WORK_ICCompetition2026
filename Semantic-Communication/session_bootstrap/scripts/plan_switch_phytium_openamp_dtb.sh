#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONNECT_SCRIPT="$SCRIPT_DIR/connect_phytium_pi.sh"

DEFAULT_HOST="100.121.87.73"
DEFAULT_USER="user"
DEFAULT_PORT="22"

BOOT_LINK="/boot/phytium-pi-board.dtb"
DEFAULT_DTB="phytium-pi-board-v3.dtb"
OPENAMP_DTB="phytium-pi-board-v3-openamp.dtb"

ENV_FILE=""
HOST=""
USER_NAME=""
PORT=""
PASS=""
EXECUTE=0
ACTION="switch"

usage() {
  cat <<'EOF'
Usage:
  plan_switch_phytium_openamp_dtb.sh [--env <path>] [--host <host>] [--user <user>] [--port <port>] [--pass <password>]
  plan_switch_phytium_openamp_dtb.sh [--env <path>] [--rollback] [--apply]

Behavior:
  - Default mode is plan-only. It prints the intended remote checks, backup, and symlink switch.
  - --apply executes the selected action remotely.
  - --rollback switches the managed symlink back to phytium-pi-board-v3.dtb.
  - --rollback without --apply is still plan-only.
  - The script never reboots the board automatically.

Examples:
  bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
    --env ./session_bootstrap/config/phytium_pi_login.env

  bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
    --env ./session_bootstrap/config/phytium_pi_login.env \
    --apply

  bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
    --env ./session_bootstrap/config/phytium_pi_login.env \
    --rollback \
    --apply
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --user)
      USER_NAME="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --pass)
      PASS="${2:-}"
      shift 2
      ;;
    --apply)
      EXECUTE=1
      shift
      ;;
    --rollback)
      ACTION="rollback"
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

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: env file not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

HOST="${HOST:-${PHYTIUM_PI_HOST:-$DEFAULT_HOST}}"
USER_NAME="${USER_NAME:-${PHYTIUM_PI_USER:-$DEFAULT_USER}}"
PORT="${PORT:-${PHYTIUM_PI_PORT:-$DEFAULT_PORT}}"
PASS="${PASS:-${PHYTIUM_PI_PASSWORD:-}}"

if [[ ! -f "$CONNECT_SCRIPT" ]]; then
  echo "ERROR: SSH helper not found: $CONNECT_SCRIPT" >&2
  exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [[ "$PORT" -lt 1 ]] || [[ "$PORT" -gt 65535 ]]; then
  echo "ERROR: --port must be an integer in [1, 65535]." >&2
  exit 1
fi

TARGET_DTB="$OPENAMP_DTB"
ACTION_LABEL="switch-to-openamp"
if [[ "$ACTION" == "rollback" ]]; then
  TARGET_DTB="$DEFAULT_DTB"
  ACTION_LABEL="rollback-to-default"
fi

print_plan() {
  local mode_label
  if [[ "$EXECUTE" -eq 1 ]]; then
    mode_label="execute"
  else
    mode_label="plan-only"
  fi

  cat <<EOF
[phytium-openamp-dtb] mode=$mode_label action=$ACTION_LABEL
Remote:
  host=$HOST
  user=$USER_NAME
  port=$PORT
  helper=$CONNECT_SCRIPT
Managed paths:
  boot_link=$BOOT_LINK
  default_dtb=/boot/$DEFAULT_DTB
  openamp_dtb=/boot/$OPENAMP_DTB
Target symlink value:
  $TARGET_DTB
Remote sequence:
  1. Check that $BOOT_LINK is a symlink and currently points to either $DEFAULT_DTB or $OPENAMP_DTB.
  2. Check that /boot/$DEFAULT_DTB and /boot/$OPENAMP_DTB both exist.
  3. Backup the current symlink to $BOOT_LINK.backup.<timestamp>.
  4. Update $BOOT_LINK -> $TARGET_DTB.
  5. Print the resulting symlink and stop without rebooting.
Validation after manual reboot:
  - ls -l /sys/class/remoteproc
  - test -d /sys/class/remoteproc/remoteproc0
  - ls -l /sys/bus/rpmsg/devices
  - ls -l /dev/rpmsg* /dev/rpmsg_ctrl* 2>/dev/null || true
EOF

  if [[ "$EXECUTE" -eq 0 ]]; then
    echo "[phytium-openamp-dtb] No remote changes have been made."
  fi
}

run_remote_action() {
  PHYTIUM_PI_HOST="$HOST" \
  PHYTIUM_PI_USER="$USER_NAME" \
  PHYTIUM_PI_PORT="$PORT" \
  PHYTIUM_PI_PASSWORD="$PASS" \
  bash "$CONNECT_SCRIPT" -- bash -s -- "$ACTION" "$BOOT_LINK" "$DEFAULT_DTB" "$OPENAMP_DTB" <<'SH'
set -euo pipefail

action="$1"
boot_link="$2"
default_dtb="$3"
openamp_dtb="$4"

boot_dir="$(dirname "$boot_link")"
default_path="$boot_dir/$default_dtb"
openamp_path="$boot_dir/$openamp_dtb"

if [[ "$action" == "rollback" ]]; then
  target_dtb="$default_dtb"
  action_label="rollback-to-default"
else
  target_dtb="$openamp_dtb"
  action_label="switch-to-openamp"
fi

if [[ ! -e "$default_path" ]]; then
  echo "ERROR: missing default dtb: $default_path" >&2
  exit 1
fi

if [[ ! -e "$openamp_path" ]]; then
  echo "ERROR: missing openamp dtb: $openamp_path" >&2
  exit 1
fi

if [[ ! -L "$boot_link" ]]; then
  echo "ERROR: managed boot link is not a symlink: $boot_link" >&2
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  as_root=()
elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  as_root=(sudo -n)
elif [[ -w "$boot_dir" ]]; then
  as_root=()
else
  echo "ERROR: need root or passwordless sudo to modify $boot_link" >&2
  exit 1
fi

current_target_raw="$(readlink "$boot_link" || true)"
current_target_base="$(basename "$current_target_raw")"

if [[ -z "$current_target_raw" ]]; then
  echo "ERROR: failed to resolve current symlink target for $boot_link" >&2
  exit 1
fi

if [[ "$current_target_base" != "$default_dtb" && "$current_target_base" != "$openamp_dtb" ]]; then
  echo "ERROR: current symlink target is outside the conservative allowlist: $current_target_raw" >&2
  exit 1
fi

stamp="$(date +%Y%m%d_%H%M%S)"
backup_path="${boot_link}.backup.${stamp}"

echo "[phytium-openamp-dtb] action=$action_label"
echo "[phytium-openamp-dtb] current link:"
ls -l "$boot_link"
echo "[phytium-openamp-dtb] candidate dtbs:"
ls -l "$default_path" "$openamp_path"
echo "[phytium-openamp-dtb] creating backup: $backup_path"
"${as_root[@]}" cp -a "$boot_link" "$backup_path"

if [[ "$current_target_base" == "$target_dtb" ]]; then
  echo "[phytium-openamp-dtb] already points to $target_dtb; backup kept, no relink needed."
else
  echo "[phytium-openamp-dtb] switching $boot_link -> $target_dtb"
  "${as_root[@]}" ln -sfn "$target_dtb" "$boot_link"
fi

echo "[phytium-openamp-dtb] result link:"
ls -l "$boot_link"
echo "[phytium-openamp-dtb] backup link:"
ls -l "$backup_path"
echo "[phytium-openamp-dtb] reboot is intentionally not performed by this script."
SH
}

print_plan

if [[ "$EXECUTE" -eq 1 ]]; then
  run_remote_action
fi
