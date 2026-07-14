#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
    help|-h|--help)
        cat <<EOF
Usage:
  sudo $0

Purpose:
  上位机/TX 侧 USRP2922 网口恢复：
  本机网口 192.168.10.1/32 -> USRP 192.168.10.2

Advanced:
  Set USRP2922_HOST_IFACE=<iface> when auto-detection selects the wrong NIC.
EOF
        exit 0
        ;;
esac

echo "[上位机] 配置上位机侧 USRP2922 网口：192.168.10.1/32 -> 192.168.10.2"
exec "${PROJECT_ROOT}/USRP292x/Usrp2922Network.sh" host-init "$@"
