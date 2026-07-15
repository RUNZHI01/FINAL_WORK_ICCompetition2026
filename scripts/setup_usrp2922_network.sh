#!/usr/bin/env bash
set -euo pipefail

# Configure NetworkManager profiles for directly connected NI USRP-2920/2922/N210
# Ethernet links.
#
# Canonical profile names:
#   USRP2922-Host   上位机侧 USRP 控制链路
#   USRP2922-Board  板端侧 USRP 控制链路
#
# Modes:
#   local-loopback      configure two NICs on this host: Host + Board
#   host-init           configure only the upper-host side link
#   board-init          configure only the board-side link
#   deactivate-local    disable Host + Board profiles
#   deactivate-host     disable Host profile
#   deactivate-board    disable Board profile
#   cleanup-stale       remove old USRP2922 / A / B profiles and disable legacy wired profiles
#   status              show current wired/Tailscale/USRP routing state
#
# The local-loopback mode uses /32 host addresses plus explicit /32 routes so
# two devices can safely remain in 192.168.10.x on two independent NICs.

MODE="${1:-help}"

HOST_CON="${USRP2922_HOST_CON:-USRP2922-Host}"
BOARD_CON="${USRP2922_BOARD_CON:-USRP2922-Board}"

HOST_IFACE="${USRP2922_HOST_IFACE:-${USRP2922_IFACE:-enp4s0}}"
BOARD_IFACE="${USRP2922_BOARD_IFACE:-${USRP2922_IFACE:-enp4s0}}"
LOCAL_HOST_IFACE="${USRP2922_LOCAL_HOST_IFACE:-${USRP2922_HOST_IFACE:-enp4s0}}"
LOCAL_BOARD_IFACE="${USRP2922_LOCAL_BOARD_IFACE:-${USRP2922_BOARD_IFACE:-eno1}}"

HOST_ADDR="${USRP2922_HOST_ADDR:-192.168.10.1/32}"
BOARD_ADDR="${USRP2922_BOARD_ADDR:-192.168.10.11/32}"
HOST_DEVICE="${USRP2922_HOST_DEVICE:-192.168.10.2}"
BOARD_DEVICE="${USRP2922_BOARD_DEVICE:-192.168.10.22}"

STALE_USRP_CONNECTIONS="${USRP2922_STALE_CONNECTIONS:-USRP2922,USRP2922-A,USRP2922-B}"
LEGACY_WIRED_CONNECTIONS="${USRP2922_LEGACY_CONNECTIONS:-Win11File,Wired connection 1,Wired connection 2}"
DISABLE_SAMBA="${USRP2922_DISABLE_SAMBA:-1}"
SKIP_CLEANUP="${USRP2922_SKIP_CLEANUP:-0}"
PROBE_UHD="${USRP2922_PROBE_UHD:-1}"
PING_COUNT="${USRP2922_PING_COUNT:-2}"
PING_TIMEOUT_SEC="${USRP2922_PING_TIMEOUT_SEC:-1}"

usage() {
    cat <<EOF
Usage:
  sudo $0 local-loopback
  sudo $0 host-init
  sudo $0 board-init
  sudo $0 deactivate-local
  sudo $0 deactivate-host
  sudo $0 deactivate-board
  sudo $0 cleanup-stale
       $0 status

Default local-loopback mapping:
  ${HOST_CON}:  ${LOCAL_HOST_IFACE} ${HOST_ADDR} -> ${HOST_DEVICE}
  ${BOARD_CON}: ${LOCAL_BOARD_IFACE} ${BOARD_ADDR} -> ${BOARD_DEVICE}

Default single-side mapping:
  host-init:  ${HOST_CON} on ${HOST_IFACE} ${HOST_ADDR} -> ${HOST_DEVICE}
  board-init: ${BOARD_CON} on ${BOARD_IFACE} ${BOARD_ADDR} -> ${BOARD_DEVICE}

Useful overrides:
  USRP2922_HOST_IFACE=enp4s0
  USRP2922_BOARD_IFACE=eno1
  USRP2922_HOST_ADDR=192.168.10.1/32
  USRP2922_BOARD_ADDR=192.168.10.11/32
  USRP2922_HOST_DEVICE=192.168.10.2
  USRP2922_BOARD_DEVICE=192.168.10.22
  USRP2922_SKIP_CLEANUP=1
  USRP2922_PROBE_UHD=0
  USRP2922_PING_COUNT=1

Notes:
  - Device IPs are persistent on the USRP side; this script only configures host NICs.
  - WiFi, tailscale0, docker0 and virbr0 are not modified.
  - Legacy Win11File / Wired connection profiles are disabled by default, not deleted.
EOF
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "请用 sudo 运行：sudo $0 ${MODE}" >&2
        exit 1
    fi
}

require_nmcli() {
    if ! command -v nmcli >/dev/null 2>&1; then
        echo "未找到 nmcli；请先确认 NetworkManager 已安装。" >&2
        exit 1
    fi
}

connection_exists() {
    local name="$1"
    [[ -n "${name}" ]] && nmcli -t -f NAME connection show | grep -Fxq "${name}"
}

disable_samba_if_requested() {
    if [[ "${DISABLE_SAMBA}" == "1" ]]; then
        echo "[samba] disable smbd/nmbd/samba-ad-dc if present"
        systemctl disable --now smbd nmbd samba-ad-dc 2>/dev/null || true
    fi
}

for_csv_item() {
    local csv="$1"
    local callback="$2"
    local item
    IFS=',' read -r -a items <<< "${csv}"
    for item in "${items[@]}"; do
        [[ -n "${item}" ]] || continue
        "${callback}" "${item}"
    done
}

delete_connection_if_exists() {
    local name="$1"
    if connection_exists "${name}"; then
        echo "[cleanup] delete stale USRP profile: ${name}"
        nmcli connection down "${name}" 2>/dev/null || true
        nmcli connection delete "${name}" >/dev/null
    fi
}

disable_connection_if_exists() {
    local name="$1"
    if connection_exists "${name}"; then
        echo "[cleanup] disable legacy wired profile: ${name}"
        nmcli connection modify "${name}" connection.autoconnect no || true
        nmcli connection down "${name}" 2>/dev/null || true
    fi
}

cleanup_stale_profiles() {
    if [[ "${SKIP_CLEANUP}" == "1" ]]; then
        echo "[cleanup] skipped by USRP2922_SKIP_CLEANUP=1"
        return
    fi
    for_csv_item "${STALE_USRP_CONNECTIONS}" delete_connection_if_exists
    for_csv_item "${LEGACY_WIRED_CONNECTIONS}" disable_connection_if_exists
}

configure_link() {
    local con="$1"
    local iface="$2"
    local host_addr="$3"
    local device_addr="$4"

    echo "[configure] ${con}: ${iface} ${host_addr} -> ${device_addr}"
    if connection_exists "${con}"; then
        nmcli connection modify "${con}" \
            connection.interface-name "${iface}" \
            connection.autoconnect yes \
            ipv4.method manual \
            ipv4.addresses "${host_addr}" \
            ipv4.gateway "" \
            ipv4.dns "" \
            ipv4.never-default yes \
            ipv4.routes "${device_addr}/32 0.0.0.0 10" \
            ipv6.method disabled
    else
        nmcli connection add type ethernet ifname "${iface}" con-name "${con}" \
            connection.autoconnect yes \
            ipv4.method manual \
            ipv4.addresses "${host_addr}" \
            ipv4.never-default yes \
            ipv4.routes "${device_addr}/32 0.0.0.0 10" \
            ipv6.method disabled
    fi

    nmcli connection up "${con}"
    ip -br addr show "${iface}" || true
    ip route get "${device_addr}" || true
}

deactivate_link() {
    local con="$1"
    if connection_exists "${con}"; then
        echo "[deactivate] ${con}"
        nmcli connection modify "${con}" connection.autoconnect no || true
        nmcli connection down "${con}" 2>/dev/null || true
    else
        echo "[deactivate] ${con}: not found"
    fi
}

probe_link() {
    local label="$1"
    local iface="$2"
    local device_addr="$3"

    echo "[probe] ${label}: ${iface} -> ${device_addr}"
    if ping -c "${PING_COUNT}" -W "${PING_TIMEOUT_SEC}" -I "${iface}" "${device_addr}"; then
        if [[ "${PROBE_UHD}" == "1" ]] && command -v uhd_find_devices >/dev/null 2>&1; then
            uhd_find_devices --args "addr=${device_addr}" || true
        elif [[ "${PROBE_UHD}" != "1" ]]; then
            echo "[probe] ${label}: UHD probe skipped by USRP2922_PROBE_UHD=0"
        fi
    else
        echo "[probe] ${label}: ping failed"
    fi
}

show_status() {
    echo "[status] NetworkManager devices"
    nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null || true
    echo
    echo "[status] USRP-related profiles"
    nmcli -t -f NAME,UUID,TYPE,DEVICE,AUTOCONNECT connection show 2>/dev/null \
        | grep -E '(^USRP2922|^Win11File|^Wired connection)' || true
    echo
    echo "[status] addresses"
    ip -br addr
    echo
    echo "[status] routes"
    ip route show table main
    echo
    echo "[status] route probes"
    ip route get "${HOST_DEVICE}" || true
    ip route get "${BOARD_DEVICE}" || true
}

finish_routes() {
    ip route flush cache || true
}

run_local_loopback() {
    require_root
    require_nmcli
    disable_samba_if_requested
    cleanup_stale_profiles
    configure_link "${HOST_CON}" "${LOCAL_HOST_IFACE}" "${HOST_ADDR}" "${HOST_DEVICE}"
    configure_link "${BOARD_CON}" "${LOCAL_BOARD_IFACE}" "${BOARD_ADDR}" "${BOARD_DEVICE}"
    finish_routes
    probe_link "${HOST_CON}" "${LOCAL_HOST_IFACE}" "${HOST_DEVICE}"
    probe_link "${BOARD_CON}" "${LOCAL_BOARD_IFACE}" "${BOARD_DEVICE}"
}

run_host_init() {
    require_root
    require_nmcli
    disable_samba_if_requested
    cleanup_stale_profiles
    configure_link "${HOST_CON}" "${HOST_IFACE}" "${HOST_ADDR}" "${HOST_DEVICE}"
    finish_routes
    probe_link "${HOST_CON}" "${HOST_IFACE}" "${HOST_DEVICE}"
}

run_board_init() {
    require_root
    require_nmcli
    disable_samba_if_requested
    cleanup_stale_profiles
    configure_link "${BOARD_CON}" "${BOARD_IFACE}" "${BOARD_ADDR}" "${BOARD_DEVICE}"
    finish_routes
    probe_link "${BOARD_CON}" "${BOARD_IFACE}" "${BOARD_DEVICE}"
}

run_deactivate_local() {
    require_root
    require_nmcli
    deactivate_link "${HOST_CON}"
    deactivate_link "${BOARD_CON}"
    finish_routes
}

run_deactivate_host() {
    require_root
    require_nmcli
    deactivate_link "${HOST_CON}"
    finish_routes
}

run_deactivate_board() {
    require_root
    require_nmcli
    deactivate_link "${BOARD_CON}"
    finish_routes
}

case "${MODE}" in
    local-loopback|local|dualhost)
        run_local_loopback
        ;;
    host-init|host)
        run_host_init
        ;;
    board-init|board)
        run_board_init
        ;;
    deactivate-local|deactivate-local-loopback|deactivate-dualhost)
        run_deactivate_local
        ;;
    deactivate-host)
        run_deactivate_host
        ;;
    deactivate-board)
        run_deactivate_board
        ;;
    cleanup-stale)
        require_root
        require_nmcli
        cleanup_stale_profiles
        ;;
    status)
        require_nmcli
        show_status
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "unknown mode: ${MODE}" >&2
        usage >&2
        exit 2
        ;;
esac
