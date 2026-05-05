#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_HOST="100.121.87.73"
DEFAULT_USER="user"
DEFAULT_PORT="22"

usage() {
  cat <<'EOF'
Usage:
  connect_phytium_pi.sh [--env <path>] [-- <remote command ...>]
  connect_phytium_pi.sh [--env <path>] [remote command ...]

Notes:
  - 默认连接 user@100.121.87.73:22。
  - 可通过 --env 指定 env 文件覆盖连接参数。
  - 传入远端命令时执行命令；不传命令时进入交互 shell。
  - 若设置了密码变量且系统存在 sshpass，将自动走非交互登录。
EOF
}

ENV_FILE=""
REMOTE_ARGS=()

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
    --)
      shift
      REMOTE_ARGS=("$@")
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      REMOTE_ARGS=("$@")
      break
      ;;
  esac
done

if ! command -v ssh >/dev/null 2>&1; then
  echo "ERROR: ssh not found in PATH." >&2
  exit 1
fi

PHYTIUM_PI_HOST="${PHYTIUM_PI_HOST:-$DEFAULT_HOST}"
PHYTIUM_PI_USER="${PHYTIUM_PI_USER:-$DEFAULT_USER}"
PHYTIUM_PI_PORT="${PHYTIUM_PI_PORT:-$DEFAULT_PORT}"
PHYTIUM_PI_PASSWORD="${PHYTIUM_PI_PASSWORD:-}"

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: env file not found: $ENV_FILE" >&2
    echo "Hint: copy $SESSION_DIR/config/phytium_pi_login.example.env to a local *.env file." >&2
    exit 1
  fi

  # shellcheck source=/dev/null
  set -a
  source "$ENV_FILE"
  set +a

  PHYTIUM_PI_HOST="${PHYTIUM_PI_HOST:-$DEFAULT_HOST}"
  PHYTIUM_PI_USER="${PHYTIUM_PI_USER:-$DEFAULT_USER}"
  PHYTIUM_PI_PORT="${PHYTIUM_PI_PORT:-$DEFAULT_PORT}"
  PHYTIUM_PI_PASSWORD="${PHYTIUM_PI_PASSWORD:-}"
fi

if [[ -z "$PHYTIUM_PI_HOST" || -z "$PHYTIUM_PI_USER" ]]; then
  echo "ERROR: PHYTIUM_PI_HOST/PHYTIUM_PI_USER must not be empty." >&2
  exit 1
fi

if ! [[ "$PHYTIUM_PI_PORT" =~ ^[0-9]+$ ]] || [[ "$PHYTIUM_PI_PORT" -lt 1 ]] || [[ "$PHYTIUM_PI_PORT" -gt 65535 ]]; then
  echo "ERROR: PHYTIUM_PI_PORT must be an integer in [1, 65535]." >&2
  exit 1
fi

TARGET="${PHYTIUM_PI_USER}@${PHYTIUM_PI_HOST}"

if [[ -n "$PHYTIUM_PI_PASSWORD" ]] && command -v sshpass >/dev/null 2>&1; then
  if [[ "${#REMOTE_ARGS[@]}" -eq 0 ]]; then
    SSHPASS="$PHYTIUM_PI_PASSWORD" exec sshpass -e ssh -p "$PHYTIUM_PI_PORT" "$TARGET"
  fi
  SSHPASS="$PHYTIUM_PI_PASSWORD" exec sshpass -e ssh -p "$PHYTIUM_PI_PORT" "$TARGET" "${REMOTE_ARGS[@]}"
fi

if [[ -n "$PHYTIUM_PI_PASSWORD" ]] && ! command -v sshpass >/dev/null 2>&1; then
  echo "INFO: 已设置 PHYTIUM_PI_PASSWORD，但未检测到 sshpass，改为普通 ssh（将交互输入密码）。" >&2
fi

if [[ "${#REMOTE_ARGS[@]}" -eq 0 ]]; then
  exec ssh -p "$PHYTIUM_PI_PORT" "$TARGET"
fi

exec ssh -p "$PHYTIUM_PI_PORT" "$TARGET" "${REMOTE_ARGS[@]}"
