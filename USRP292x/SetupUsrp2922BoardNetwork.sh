#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
    help|-h|--help)
        cat <<EOF
Usage:
  sudo $0

Purpose:
  板端/RX 侧 USRP2922 网口恢复：
  板端网口 192.168.10.11/32 -> USRP 192.168.10.22

Advanced:
  Set USRP2922_BOARD_IFACE=<iface> when auto-detection selects the wrong NIC.
EOF
        exit 0
        ;;
esac

echo "[板端] 配置板端侧 USRP2922 网口：192.168.10.11/32 -> 192.168.10.22"
exec "${PROJECT_ROOT}/USRP292x/Usrp2922Network.sh" board-init "$@"
