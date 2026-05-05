#!/usr/bin/env bash
set -euo pipefail

# Level 1 quick OTA file test:
#   reference wire blob -> chunked QPSK sc16 -> tx_samples_from_file
#   OtaRxCaptureGain -> QpskFileLink decode -> BER/PER

RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="${RUN_DIR:-USRP292x/qpsk_runs/${RUN_ID}}"
INPUT="${INPUT:-USRP292x/payloads/source_latent_wire_blob.bin}"
TX_ARGS="${TX_ARGS:-addr=192.168.10.2}"
RX_ARGS="${RX_ARGS:-addr=192.168.10.22}"
TX_CONTROL_HOST="${TX_CONTROL_HOST:-}"
TX_CONTROL_PORT="${TX_CONTROL_PORT:-29221}"
RX_CONTROL_HOST="${RX_CONTROL_HOST:-}"
RX_CONTROL_PORT="${RX_CONTROL_PORT:-29220}"
USE_PERSISTENT_TX="${USE_PERSISTENT_TX:-0}"
USE_PERSISTENT_RX="${USE_PERSISTENT_RX:-0}"
FREQ="${FREQ:-500000000}"
RATE="${RATE:-5000000}"
TX_GAIN="${TX_GAIN:-25}"
RX_GAIN="${RX_GAIN:-20}"
RX_ANT="${RX_ANT:-RX2}"
AMPLITUDE="${AMPLITUDE:-3000}"
CHUNK_BYTES="${CHUNK_BYTES:-4096}"
ONLY_CHUNKS="${ONLY_CHUNKS:-}"
WARMUP_SAMPLES="${WARMUP_SAMPLES:-250000}"
TAIL_SAMPLES="${TAIL_SAMPLES:-250000}"
TX_SPB="${TX_SPB:-1000}"
FRAME_CANDIDATES="${FRAME_CANDIDATES:-64}"
ALLOW_DECODE_FAIL="${ALLOW_DECODE_FAIL:-0}"
RX_DURATION="${RX_DURATION:-}"
PERSISTENT_RX_TX_DELAY="${PERSISTENT_RX_TX_DELAY:-0.05}"
RX_WAIT_TIMEOUT="${RX_WAIT_TIMEOUT:-}"
TX_WAIT_TIMEOUT="${TX_WAIT_TIMEOUT:-10}"

if [[ -n "${TX_CONTROL_HOST}" ]]; then
    USE_PERSISTENT_TX=1
fi

if [[ -n "${RX_CONTROL_HOST}" ]]; then
    USE_PERSISTENT_RX=1
fi

if [[ "${USE_PERSISTENT_RX}" == "1" && "${USE_PERSISTENT_TX}" == "1" ]]; then
    RX_DURATION="${RX_DURATION:-2.3}"
    RX_WAIT_TIMEOUT="${RX_WAIT_TIMEOUT:-10}"
    SEARCH_START_SEC="${SEARCH_START_SEC:-0.05}"
    SEARCH_END_SEC="${SEARCH_END_SEC:-2.20}"
elif [[ "${USE_PERSISTENT_RX}" == "1" ]]; then
    RX_DURATION="${RX_DURATION:-5.5}"
    RX_WAIT_TIMEOUT="${RX_WAIT_TIMEOUT:-12}"
    SEARCH_START_SEC="${SEARCH_START_SEC:-1.0}"
    SEARCH_END_SEC="${SEARCH_END_SEC:-5.3}"
else
    RX_DURATION="${RX_DURATION:-2.3}"
    RX_WAIT_TIMEOUT="${RX_WAIT_TIMEOUT:-10}"
    SEARCH_START_SEC="${SEARCH_START_SEC:-1.30}"
    SEARCH_END_SEC="${SEARCH_END_SEC:-2.20}"
fi

mkdir -p "${RUN_DIR}"

TX_SC16="${RUN_DIR}/tx_qpsk.sc16"
MANIFEST="${RUN_DIR}/manifest.json"
RX_SC16="${RUN_DIR}/rx_capture.sc16"
DECODED="${RUN_DIR}/decoded_wire_blob.bin"
SUMMARY_JSON="${RUN_DIR}/decode_summary.json"
RX_LOG="${RUN_DIR}/rx.log"
TX_LOG="${RUN_DIR}/tx.log"
DECODE_LOG="${RUN_DIR}/decode.log"

python3 USRP292x/QpskFileLink.py make \
    --input "${INPUT}" \
    --out-sc16 "${TX_SC16}" \
    --manifest "${MANIFEST}" \
    --rate "${RATE}" \
    --chunk-bytes "${CHUNK_BYTES}" \
    --only-chunks "${ONLY_CHUNKS}" \
    --amplitude "${AMPLITUDE}" \
    --warmup-samples "${WARMUP_SAMPLES}" \
    --tail-samples "${TAIL_SAMPLES}"

cleanup() {
    if [[ -n "${rx_pid:-}" ]] && kill -0 "${rx_pid}" 2>/dev/null; then
        kill "${rx_pid}" 2>/dev/null || true
        wait "${rx_pid}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if [[ "${USE_PERSISTENT_RX}" == "1" ]]; then
    python3 USRP292x/OtaRxControl.py \
        --host "${RX_CONTROL_HOST}" \
        --port "${RX_CONTROL_PORT}" \
        capture \
        --file "${RX_SC16}" \
        --duration "${RX_DURATION}" >"${RX_LOG}" 2>&1
    sleep "${PERSISTENT_RX_TX_DELAY}"
else
    DEVICE_ARGS="${RX_ARGS}" \
    RATE="${RATE}" \
    FREQ="${FREQ}" \
    GAIN="${RX_GAIN}" \
    ANT="${RX_ANT}" \
    DURATION="${RX_DURATION}" \
    OUT_FILE="${RX_SC16}" \
    ./USRP292x/OtaRxCaptureGain.sh >"${RX_LOG}" 2>&1 &
    rx_pid=$!
    sleep 1
fi

if [[ "${USE_PERSISTENT_TX}" == "1" ]]; then
    python3 USRP292x/OtaTxControl.py \
        --host "${TX_CONTROL_HOST}" \
        --port "${TX_CONTROL_PORT}" \
        --timeout "${TX_WAIT_TIMEOUT}" \
        send \
        --file "${TX_SC16}" >"${TX_LOG}" 2>&1
else
    /usr/libexec/uhd/examples/tx_samples_from_file \
        --args "${TX_ARGS}" \
        --file "${TX_SC16}" \
        --type short \
        --rate "${RATE}" \
        --freq "${FREQ}" \
        --gain "${TX_GAIN}" \
        --ant TX/RX \
        --spb "${TX_SPB}" \
        --wirefmt sc16 >"${TX_LOG}" 2>&1
fi

if [[ "${USE_PERSISTENT_RX}" == "1" ]]; then
    python3 USRP292x/OtaRxControl.py \
        --host "${RX_CONTROL_HOST}" \
        --port "${RX_CONTROL_PORT}" \
        wait \
        --wait-timeout "${RX_WAIT_TIMEOUT}" >>"${RX_LOG}" 2>&1
else
    wait "${rx_pid}"
    rx_pid=""
fi

set +e
python3 USRP292x/QpskFileLink.py decode \
    --rx-sc16 "${RX_SC16}" \
    --manifest "${MANIFEST}" \
    --reference "${INPUT}" \
    --out-bin "${DECODED}" \
    --summary-json "${SUMMARY_JSON}" \
    --search-start-sec "${SEARCH_START_SEC}" \
    --search-end-sec "${SEARCH_END_SEC}" \
    --frame-candidates "${FRAME_CANDIDATES}" | tee "${DECODE_LOG}"
decode_status="${PIPESTATUS[0]}"
set -e

echo "run_dir=${RUN_DIR}"
echo "decode_status=${decode_status}"
if [[ "${ALLOW_DECODE_FAIL}" != "1" && "${decode_status}" != "0" ]]; then
    exit "${decode_status}"
fi
