#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BOARD_HOME="${BOARD_HOME:-/home/user}"
BOARD_DOWNLOADS="${BOARD_DOWNLOADS:-${BOARD_HOME}/Downloads}"
JSCC_ROOT="${JSCC_ROOT:-${BOARD_DOWNLOADS}/jscc-test}"
FIRMWARE_DIR="${FIRMWARE_DIR:-/lib/firmware}"
BOOT_DIR="${BOOT_DIR:-/boot}"

sudo_cmd=()
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        sudo_cmd=(sudo)
    else
        echo "sudo is required to install /usr/local/tongsuo" >&2
        exit 1
    fi
fi

require_file() {
    local path="$1"
    if [ ! -s "${path}" ]; then
        echo "missing dependency file: ${path}" >&2
        exit 1
    fi
}

require_file "${SCRIPT_DIR}/crypto/liboqs-dist-aarch64.tar.gz"
require_file "${SCRIPT_DIR}/crypto/tongsuo-runtime-aarch64.tar.gz"
require_file "${SCRIPT_DIR}/crypto/libtongsuo_sig_bridge.so"
require_file "${SCRIPT_DIR}/tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz"
require_file "${SCRIPT_DIR}/tvm/baseline/optimized_model.so"
require_file "${SCRIPT_DIR}/tvm/current/optimized_model.so"
require_file "${SCRIPT_DIR}/tvm/current_legacy/optimized_model.so"
require_file "${SCRIPT_DIR}/mnn/origin/model1.mnn"
require_file "${SCRIPT_DIR}/inputs/places365-latents.tar.gz"
require_file "${SCRIPT_DIR}/inputs/mnn-encoder-outputs.tar.gz"
require_file "${SCRIPT_DIR}/tools/gen_identity_keys.py"
require_file "${SCRIPT_DIR}/openamp/firmware/openamp_core0.elf"
require_file "${SCRIPT_DIR}/openamp/firmware/phytium-pi-board-v3-openamp.dtb"
require_file "${SCRIPT_DIR}/openamp/runtime/openamp-demo-runtime-services.tar.gz"
require_file "${SCRIPT_DIR}/crypto/public_keys/board-auth-public-keys.tar.gz"
require_file "${SCRIPT_DIR}/runtime/mlkem-remote-runtime-snapshot.tar.gz"

echo "[board-deps] installing liboqs runtime"
mkdir -p "${BOARD_HOME}"
tar -xzf "${SCRIPT_DIR}/crypto/liboqs-dist-aarch64.tar.gz" -C "${BOARD_HOME}"

echo "[board-deps] installing Tongsuo runtime"
"${sudo_cmd[@]}" mkdir -p /usr/local
gzip -dc "${SCRIPT_DIR}/crypto/tongsuo-runtime-aarch64.tar.gz" | "${sudo_cmd[@]}" tar -C /usr/local -xf -

echo "[board-deps] installing OpenAMP firmware and boot DTBs"
"${sudo_cmd[@]}" mkdir -p "${FIRMWARE_DIR}" "${BOOT_DIR}"
"${sudo_cmd[@]}" install -m 0644 "${SCRIPT_DIR}/openamp/firmware/openamp_core0.elf" "${FIRMWARE_DIR}/openamp_core0.elf"
"${sudo_cmd[@]}" install -m 0644 "${SCRIPT_DIR}/openamp/firmware/phytium-pi-board-v3-openamp.dtb" "${BOOT_DIR}/phytium-pi-board-v3-openamp.dtb"

echo "[board-deps] installing crypto bridge and key generator"
install -m 0755 "${SCRIPT_DIR}/crypto/libtongsuo_sig_bridge.so" "${BOARD_HOME}/libtongsuo_sig_bridge.so"
install -m 0644 "${SCRIPT_DIR}/tools/gen_identity_keys.py" "${BOARD_HOME}/gen_identity_keys.py"

echo "[board-deps] installing TVM runtime"
tar -xzf "${SCRIPT_DIR}/tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz" -C /

echo "[board-deps] installing TVM artifacts"
mkdir -p \
    "${BOARD_DOWNLOADS}/5.1TVM优化结果/tvm_tune_logs" \
    "${JSCC_ROOT}/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs" \
    "${JSCC_ROOT}/jscc/tvm_tune_logs"
install -m 0644 "${SCRIPT_DIR}/tvm/baseline/optimized_model.so" \
    "${BOARD_DOWNLOADS}/5.1TVM优化结果/tvm_tune_logs/optimized_model.so"
install -m 0644 "${SCRIPT_DIR}/tvm/current/optimized_model.so" \
    "${JSCC_ROOT}/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so"
install -m 0644 "${SCRIPT_DIR}/tvm/current_legacy/optimized_model.so" \
    "${JSCC_ROOT}/jscc/tvm_tune_logs/optimized_model.so"

echo "[board-deps] installing MNN model"
mkdir -p "${BOARD_DOWNLOADS}/MNNversion/origin"
install -m 0644 "${SCRIPT_DIR}/mnn/origin/model1.mnn" \
    "${BOARD_DOWNLOADS}/MNNversion/origin/model1.mnn"

echo "[board-deps] installing input tensors"
mkdir -p "${JSCC_ROOT}"
tar -xzf "${SCRIPT_DIR}/inputs/places365-latents.tar.gz" -C "${JSCC_ROOT}"
tar -xzf "${SCRIPT_DIR}/inputs/mnn-encoder-outputs.tar.gz" -C "${JSCC_ROOT}"

echo "[board-deps] installing OpenAMP runtime services"
mkdir -p "${BOARD_HOME}"
tar -xzf "${SCRIPT_DIR}/openamp/runtime/openamp-demo-runtime-services.tar.gz" -C "${BOARD_HOME}"

echo "[board-deps] installing public board auth keys"
mkdir -p "${BOARD_HOME}/keys"
tar -xzf "${SCRIPT_DIR}/crypto/public_keys/board-auth-public-keys.tar.gz" -C "${BOARD_HOME}/keys"
chmod 644 "${BOARD_HOME}/keys"/*.pub

echo "[board-deps] installing ML-KEM remote runtime snapshot"
tar -xzf "${SCRIPT_DIR}/runtime/mlkem-remote-runtime-snapshot.tar.gz" -C "${BOARD_HOME}"

echo "[board-deps] syncing current mlkem_link package for init.sh --board"
if [ -d "${REPO_ROOT}/mlkem_link" ]; then
    if [ -e "${BOARD_HOME}/mlkem_link" ]; then
        backup_path="${BOARD_HOME}/mlkem_link.backup.$(date +%Y%m%d%H%M%S)"
        mv "${BOARD_HOME}/mlkem_link" "${backup_path}"
        echo "[board-deps] previous mlkem_link moved to ${backup_path}"
    fi
    cp -R "${REPO_ROOT}/mlkem_link" "${BOARD_HOME}/mlkem_link"
fi

"${SCRIPT_DIR}/verify-board-deps.sh"

cat <<EOF
[board-deps] installed.

Recommended runtime exports:
export MLKEM_REMOTE_OQS_INSTALL_PATH=${BOARD_HOME}/liboqs-dist
export MLKEM_REMOTE_LD_LIBRARY_PATH=${BOARD_HOME}/liboqs-dist/lib:/usr/local/tongsuo/lib
export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE=${BOARD_HOME}/libtongsuo_sig_bridge.so
export MLKEM_REMOTE_TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so
EOF
