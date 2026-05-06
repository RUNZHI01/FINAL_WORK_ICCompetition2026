#!/usr/bin/env bash
set -euo pipefail

BOARD_HOME="${BOARD_HOME:-/home/user}"
BOARD_DOWNLOADS="${BOARD_DOWNLOADS:-${BOARD_HOME}/Downloads}"
JSCC_ROOT="${JSCC_ROOT:-${BOARD_DOWNLOADS}/jscc-test}"
FIRMWARE_DIR="${FIRMWARE_DIR:-/lib/firmware}"
BOOT_DIR="${BOOT_DIR:-/boot}"

check_exists() {
    local path="$1"
    if [ ! -e "${path}" ]; then
        echo "missing: ${path}" >&2
        exit 1
    fi
}

check_sha256() {
    local expected="$1"
    local path="$2"
    check_exists "${path}"
    local actual
    actual="$(sha256sum "${path}" | awk '{print $1}')"
    if [ "${actual}" != "${expected}" ]; then
        echo "sha256 mismatch: ${path}" >&2
        echo "  expected: ${expected}" >&2
        echo "  actual:   ${actual}" >&2
        exit 1
    fi
    echo "ok: ${path}"
}

check_exists "${BOARD_HOME}/liboqs-dist/lib/liboqs.so"
check_exists "${BOARD_HOME}/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi"
check_exists "${BOARD_HOME}/tvm_samegen_safe_20260309/build/libtvm.so"
check_exists "${BOARD_HOME}/tvm_samegen_safe_20260309/build/libtvm_runtime.so"
check_exists "${BOARD_HOME}/tvm_samegen_20260307/python/tvm"
check_sha256 b79245f3f9f4a1707974539836e48998cb37efb3b1b409de9e83c86c4a72d18d \
    "${FIRMWARE_DIR}/openamp_core0.elf"
check_sha256 c71a1e0efee6cb00e8bef70be160eb46a2d9c75706756729115c9b889dd3518e \
    "${BOOT_DIR}/phytium-pi-board-v3-openamp.dtb"
check_sha256 d68d0eddc631f2d4f06779af68937000cbffd70ff9b179b7a7768cf8a5b27ec5 \
    /usr/local/tongsuo/lib/libtongsuo_kem_bridge.so
check_sha256 dfb160e93416db75fc095af95af03e533114fe20b1d2393a614edb53d27a0059 \
    "${BOARD_HOME}/libtongsuo_sig_bridge.so"
check_sha256 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849 \
    "${BOARD_DOWNLOADS}/5.1TVM优化结果/tvm_tune_logs/optimized_model.so"
check_sha256 bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb \
    "${JSCC_ROOT}/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so"
check_sha256 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1 \
    "${JSCC_ROOT}/jscc/tvm_tune_logs/optimized_model.so"
check_sha256 d6f7980e36a0f821a5d45a65f8f286239bc260354f80a2ffeb8be2792b87bc77 \
    "${BOARD_DOWNLOADS}/MNNversion/origin/model1.mnn"
check_exists "${JSCC_ROOT}/简化版latent/Places365_val_00000208_latent.pt"
check_exists "${JSCC_ROOT}/encoder_outputs"
check_exists "${BOARD_HOME}/gen_identity_keys.py"
check_exists "${BOARD_HOME}/mlkem_link"
check_exists "${BOARD_HOME}/.openamp-demo/board_position_api_service/board_position_api_service.py"
check_exists "${BOARD_HOME}/keys/server_sm2_identity.pub"
check_exists "${BOARD_HOME}/keys/server_mldsa_identity.pub"

echo "board-deps-ok"
