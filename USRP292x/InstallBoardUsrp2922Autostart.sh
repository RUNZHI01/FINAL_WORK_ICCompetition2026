#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BOARD_HOME="${BOARD_HOME:-/home/user}"
TARGET_USRP_DIR="${BOARD_HOME}/USRP292x"
TARGET_SCRIPTS_DIR="${BOARD_HOME}/scripts"
SERVICE_NAME="usrp2922-board-autostart.service"

sudo_cmd=()
if [[ "$(id -u)" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        sudo_cmd=(sudo)
    else
        echo "sudo is required to install the systemd service" >&2
        exit 1
    fi
fi

require_file() {
    local path="$1"
    if [[ ! -s "${path}" ]]; then
        echo "missing file: ${path}" >&2
        exit 1
    fi
}

install_if_needed() {
    local mode="$1"
    local source_path="$2"
    local target_path="$3"
    local source_real
    local target_real
    source_real="$(readlink -f "${source_path}")"
    target_real="$(readlink -f "${target_path}" 2>/dev/null || true)"
    if [[ -n "${target_real}" && "${source_real}" == "${target_real}" ]]; then
        chmod "${mode}" "${target_path}"
        return
    fi
    install -m "${mode}" "${source_path}" "${target_path}"
}

require_file "${SCRIPT_DIR}/BoardUsrp2922BootConnect.sh"
require_file "${SCRIPT_DIR}/SetupUsrp2922BoardNetwork.sh"
require_file "${SCRIPT_DIR}/Usrp2922Network.sh"
require_file "${SCRIPT_DIR}/${SERVICE_NAME}"
require_file "${REPO_ROOT}/scripts/setup_usrp2922_network.sh"

echo "[usrp2922-autostart] installing board USRP scripts"
install -d -m 0755 "${TARGET_USRP_DIR}" "${TARGET_SCRIPTS_DIR}"
install_if_needed 0755 "${SCRIPT_DIR}/BoardUsrp2922BootConnect.sh" "${TARGET_USRP_DIR}/BoardUsrp2922BootConnect.sh"
install_if_needed 0755 "${SCRIPT_DIR}/SetupUsrp2922BoardNetwork.sh" "${TARGET_USRP_DIR}/SetupUsrp2922BoardNetwork.sh"
install_if_needed 0755 "${SCRIPT_DIR}/Usrp2922Network.sh" "${TARGET_USRP_DIR}/Usrp2922Network.sh"
install_if_needed 0755 "${REPO_ROOT}/scripts/setup_usrp2922_network.sh" "${TARGET_SCRIPTS_DIR}/setup_usrp2922_network.sh"

echo "[usrp2922-autostart] installing systemd service"
"${sudo_cmd[@]}" install -m 0644 "${SCRIPT_DIR}/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
"${sudo_cmd[@]}" systemctl daemon-reload
"${sudo_cmd[@]}" systemctl enable usrp2922-board-autostart.service
"${sudo_cmd[@]}" systemctl start usrp2922-board-autostart.service
"${sudo_cmd[@]}" systemctl --no-pager --full status usrp2922-board-autostart.service || true

echo "[usrp2922-autostart] installed: ${SERVICE_NAME}"
