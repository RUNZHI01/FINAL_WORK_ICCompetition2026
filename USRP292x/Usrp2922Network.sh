#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL_SCRIPT="${PROJECT_ROOT}/scripts/setup_usrp2922_network.sh"
MODE="${1:-host-init}"
HOST_DEVICE_CANDIDATE="${USRP2922_HOST_DEVICE:-192.168.10.2}"
BOARD_DEVICE_CANDIDATE="${USRP2922_BOARD_DEVICE:-192.168.10.22}"

usage() {
    cat <<EOF
Usage:
  ./USRP292x/Usrp2922Network.sh detect
  ./USRP292x/Usrp2922Network.sh probe
  sudo ./USRP292x/Usrp2922Network.sh auto-init
  sudo ./USRP292x/Usrp2922Network.sh host-init
  sudo ./USRP292x/Usrp2922Network.sh board-init
  sudo ./USRP292x/Usrp2922Network.sh local-loopback
  ./USRP292x/Usrp2922Network.sh status
  sudo ./USRP292x/Usrp2922Network.sh deactivate-host
  sudo ./USRP292x/Usrp2922Network.sh deactivate-board
  sudo ./USRP292x/Usrp2922Network.sh deactivate-local

Purpose:
  USRP2922 wired profile setup wrapper.
  It auto-detects Ethernet interface names and forwards them to the canonical
  NetworkManager script at scripts/setup_usrp2922_network.sh.

Default address plan:
  host-init   -> host NIC ${USRP2922_HOST_ADDR:-192.168.10.1/32} -> device ${USRP2922_HOST_DEVICE:-192.168.10.2}
  board-init  -> board NIC ${USRP2922_BOARD_ADDR:-192.168.10.11/32} -> device ${USRP2922_BOARD_DEVICE:-192.168.10.22}

Notes:
  - probe shows whether this Ethernet NIC can already reach .2 or .22.
  - auto-init selects host-init / board-init based on that probe result.
  - On a single-Ethernet upper host, use host-init by default.
  - local-loopback requires two Ethernet NICs on the same machine.
  - Override auto-detection with:
      USRP2922_HOST_IFACE=<iface>
      USRP2922_BOARD_IFACE=<iface>
      USRP2922_LOCAL_HOST_IFACE=<iface>
      USRP2922_LOCAL_BOARD_IFACE=<iface>
EOF
}

require_cmd() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "missing command: ${cmd}" >&2
        exit 1
    fi
}

discover_ethernet_ifaces() {
    nmcli -t -f DEVICE,TYPE device status 2>/dev/null \
        | awk -F: '$2 == "ethernet" && $1 != "" {print $1}'
}

print_detect_report() {
    local -a ifaces=("$@")
    echo "[detect] Ethernet interfaces"
    if [[ "${#ifaces[@]}" -eq 0 ]]; then
        echo "  none"
        return 1
    fi

    local idx=0
    for iface in "${ifaces[@]}"; do
        idx=$((idx + 1))
        echo "  ${idx}. ${iface}"
        nmcli -t -f GENERAL.STATE,GENERAL.CONNECTION device show "${iface}" 2>/dev/null || true
        ip -br addr show "${iface}" 2>/dev/null || true
        echo "  probe ${HOST_DEVICE_CANDIDATE}: $(probe_device_ip "${iface}" "${HOST_DEVICE_CANDIDATE}")"
        echo "  probe ${BOARD_DEVICE_CANDIDATE}: $(probe_device_ip "${iface}" "${BOARD_DEVICE_CANDIDATE}")"
        echo
    done

    local host_iface="${ifaces[0]}"
    local board_iface="${ifaces[0]}"
    if [[ "${#ifaces[@]}" -ge 2 ]]; then
        board_iface="${ifaces[1]}"
    fi

    echo "[recommend]"
    echo "  Local single-USRP host:"
    echo "    sudo USRP2922_HOST_IFACE=${host_iface} ./USRP292x/Usrp2922Network.sh host-init"
    echo
    echo "  Peer / board-side host:"
    echo "    sudo USRP2922_BOARD_IFACE=${board_iface} ./USRP292x/Usrp2922Network.sh board-init"
    if [[ "${#ifaces[@]}" -ge 2 ]]; then
        echo
        echo "  Same-machine dual-NIC loopback:"
        echo "    sudo USRP2922_LOCAL_HOST_IFACE=${host_iface} USRP2922_LOCAL_BOARD_IFACE=${board_iface} \\"
        echo "      ./USRP292x/Usrp2922Network.sh local-loopback"
    fi
}

probe_device_ip() {
    local iface="$1"
    local ip_addr="$2"
    if ping -c 1 -W 1 -I "${iface}" "${ip_addr}" >/dev/null 2>&1; then
        printf 'reachable'
    else
        printf 'unreachable'
    fi
}

recommend_mode_for_iface() {
    local iface="$1"
    if [[ "$(probe_device_ip "${iface}" "${HOST_DEVICE_CANDIDATE}")" == "reachable" ]]; then
        printf 'host-init'
        return
    fi
    if [[ "$(probe_device_ip "${iface}" "${BOARD_DEVICE_CANDIDATE}")" == "reachable" ]]; then
        printf 'board-init'
        return
    fi
    printf 'unknown'
}

forward_to_canonical() {
    if [[ ! -x "${CANONICAL_SCRIPT}" ]]; then
        echo "canonical script not found or not executable: ${CANONICAL_SCRIPT}" >&2
        exit 1
    fi
    exec "${CANONICAL_SCRIPT}" "$@"
}

main() {
    case "${MODE}" in
        help|-h|--help)
            usage
            return
            ;;
    esac

    require_cmd nmcli
    require_cmd ip

    mapfile -t ETH_IFACES < <(discover_ethernet_ifaces)
    HOST_AUTO_IFACE="${ETH_IFACES[0]:-}"
    BOARD_AUTO_IFACE="${ETH_IFACES[0]:-}"
    if [[ "${#ETH_IFACES[@]}" -ge 2 ]]; then
        BOARD_AUTO_IFACE="${ETH_IFACES[1]}"
    fi

    case "${MODE}" in
        detect)
            print_detect_report "${ETH_IFACES[@]}"
            ;;
        probe)
            if [[ "${#ETH_IFACES[@]}" -eq 0 ]]; then
                echo "no Ethernet interface detected" >&2
                exit 1
            fi
            for iface in "${ETH_IFACES[@]}"; do
                echo "${iface}: $(recommend_mode_for_iface "${iface}")"
            done
            ;;
        host-init|host)
            if [[ -z "${HOST_AUTO_IFACE}" && -z "${USRP2922_HOST_IFACE:-}" ]]; then
                echo "no Ethernet interface detected for host-init; run detect first" >&2
                exit 1
            fi
            export USRP2922_HOST_IFACE="${USRP2922_HOST_IFACE:-${HOST_AUTO_IFACE}}"
            forward_to_canonical host-init
            ;;
        board-init|board)
            if [[ -z "${BOARD_AUTO_IFACE}" && -z "${USRP2922_BOARD_IFACE:-}" ]]; then
                echo "no Ethernet interface detected for board-init; run detect first" >&2
                exit 1
            fi
            export USRP2922_BOARD_IFACE="${USRP2922_BOARD_IFACE:-${BOARD_AUTO_IFACE}}"
            forward_to_canonical board-init
            ;;
        local-loopback|local|dualhost)
            if [[ "${#ETH_IFACES[@]}" -lt 2 && ( -z "${USRP2922_LOCAL_HOST_IFACE:-}" || -z "${USRP2922_LOCAL_BOARD_IFACE:-}" ) ]]; then
                echo "local-loopback requires two Ethernet NICs; detected: ${#ETH_IFACES[@]}" >&2
                echo "use host-init instead, or set USRP2922_LOCAL_HOST_IFACE / USRP2922_LOCAL_BOARD_IFACE explicitly" >&2
                exit 1
            fi
            export USRP2922_LOCAL_HOST_IFACE="${USRP2922_LOCAL_HOST_IFACE:-${HOST_AUTO_IFACE}}"
            export USRP2922_LOCAL_BOARD_IFACE="${USRP2922_LOCAL_BOARD_IFACE:-${BOARD_AUTO_IFACE}}"
            forward_to_canonical local-loopback
            ;;
        auto-init|auto)
            if [[ -z "${HOST_AUTO_IFACE}" ]]; then
                echo "no Ethernet interface detected for auto-init; run detect first" >&2
                exit 1
            fi
            auto_mode="$(recommend_mode_for_iface "${HOST_AUTO_IFACE}")"
            case "${auto_mode}" in
                host-init)
                    export USRP2922_HOST_IFACE="${USRP2922_HOST_IFACE:-${HOST_AUTO_IFACE}}"
                    echo "[auto] ${HOST_AUTO_IFACE}: detected ${HOST_DEVICE_CANDIDATE}, applying host-init"
                    forward_to_canonical host-init
                    ;;
                board-init)
                    export USRP2922_BOARD_IFACE="${USRP2922_BOARD_IFACE:-${HOST_AUTO_IFACE}}"
                    echo "[auto] ${HOST_AUTO_IFACE}: detected ${BOARD_DEVICE_CANDIDATE}, applying board-init"
                    forward_to_canonical board-init
                    ;;
                *)
                    echo "[auto] ${HOST_AUTO_IFACE}: neither ${HOST_DEVICE_CANDIDATE} nor ${BOARD_DEVICE_CANDIDATE} responded" >&2
                    echo "check cable / power, or run detect for details" >&2
                    exit 1
                    ;;
            esac
            ;;
        deactivate-host|deactivate-board|deactivate-local|deactivate-local-loopback|deactivate-dualhost|cleanup-stale|status)
            forward_to_canonical "${MODE}"
            ;;
        *)
            echo "unknown mode: ${MODE}" >&2
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"
