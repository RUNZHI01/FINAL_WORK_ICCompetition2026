#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOARD_IFACE="${USRP2922_BOARD_IFACE:-eth0}"
BOARD_DEVICE="${USRP2922_BOARD_DEVICE:-192.168.10.22}"
TRIES="${USRP2922_BOOT_CONNECT_TRIES:-30}"
INTERVAL_SEC="${USRP2922_BOOT_CONNECT_INTERVAL_SEC:-2}"

ping_usrp() {
    ping -c 1 -W 1 -I "${BOARD_IFACE}" "${BOARD_DEVICE}" >/dev/null 2>&1
}

run_fast_recovery() {
    USRP2922_BOARD_IFACE="${BOARD_IFACE}" \
    USRP2922_BOARD_DEVICE="${BOARD_DEVICE}" \
    USRP2922_PROBE_UHD=0 \
    USRP2922_SKIP_CLEANUP=1 \
    USRP2922_DISABLE_SAMBA=0 \
    USRP2922_PING_COUNT=1 \
        "${SCRIPT_DIR}/SetupUsrp2922BoardNetwork.sh"
}

echo "[usrp2922-boot] waiting for ${BOARD_IFACE} -> ${BOARD_DEVICE}"

for attempt in $(seq 1 "${TRIES}"); do
    if ping_usrp; then
        echo "[usrp2922-boot] link ready on attempt ${attempt}"
        exit 0
    fi

    if [[ "${attempt}" == "1" || $((attempt % 5)) == "0" ]]; then
        echo "[usrp2922-boot] recovery attempt ${attempt}/${TRIES}"
        run_fast_recovery || true
        if ping_usrp; then
            echo "[usrp2922-boot] link ready after recovery"
            exit 0
        fi
    fi

    sleep "${INTERVAL_SEC}"
done

echo "[usrp2922-boot] link not ready after ${TRIES} attempts" >&2
exit 1
