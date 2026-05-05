#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<'EOF'
Usage:
  ./tui_start.sh --encrypt [args...]
  ./tui_start.sh --usrp [args...]
  ./tui_start.sh --help

Notes:
  - 不带参数时仅显示此帮助，不自动启动任何 TUI
  - 模式专属参数请在对应模式后追加，例如：
      ./tui_start.sh --encrypt --help
      ./tui_start.sh --usrp --help
EOF
}

if [[ $# -eq 0 ]]; then
    usage
    exit 0
fi

case "${1:-}" in
    --help|-h|help)
        usage
        exit 0
        ;;
    --usrp|usrp)
        shift
        exec "$ROOT_DIR/usrp292x_tui_start.sh" "$@"
        ;;
    --encrypt|encrypt)
        shift
        exec "$ROOT_DIR/encrypt_tui_start.sh" "$@"
        ;;
    *)
        exec "$ROOT_DIR/encrypt_tui_start.sh" "$@"
        ;;
esac
