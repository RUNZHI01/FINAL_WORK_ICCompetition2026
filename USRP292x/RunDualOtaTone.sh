#!/usr/bin/env bash
set -euo pipefail

# Run one-host, two-USRP official-example OTA tone test.
# RX starts first, TX sends a finite sine waveform, then the capture is analyzed.

TX_ARGS="${TX_ARGS:-addr=192.168.10.2}"
RX_ARGS="${RX_ARGS:-addr=192.168.10.22}"
FREQ="${FREQ:-1000000000}"
RATE="${RATE:-1000000}"
TONE="${TONE:-200000}"
TX_GAIN="${TX_GAIN:-10}"
# Keep RX gain unset by default. Ubuntu UHD 4.6 rx_samples_to_file currently
# trips a N210/SBX channel-index bug when --gain is passed.
RX_GAIN="${RX_GAIN:-}"
AMPL="${AMPL:-0.05}"
TX_NSAMPS="${TX_NSAMPS:-3000000}"
RX_DURATION="${RX_DURATION:-4}"
RX_ANT="${RX_ANT:-RX2}"
OUT_FILE="${OUT_FILE:-USRP292x/DualOtaToneRx.dat}"
RX_LOG="${RX_LOG:-USRP292x/DualOtaToneRx.log}"
TX_LOG="${TX_LOG:-USRP292x/DualOtaToneTx.log}"

mkdir -p "$(dirname "${OUT_FILE}")"

cleanup() {
    if [[ -n "${rx_pid:-}" ]] && kill -0 "${rx_pid}" 2>/dev/null; then
        kill "${rx_pid}" 2>/dev/null || true
        wait "${rx_pid}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

DEVICE_ARGS="${RX_ARGS}" \
RATE="${RATE}" \
FREQ="${FREQ}" \
GAIN="${RX_GAIN}" \
ANT="${RX_ANT}" \
DURATION="${RX_DURATION}" \
OUT_FILE="${OUT_FILE}" \
./USRP292x/OtaRxCapture.sh >"${RX_LOG}" 2>&1 &
rx_pid=$!

sleep 1

DEVICE_ARGS="${TX_ARGS}" \
RATE="${RATE}" \
FREQ="${FREQ}" \
GAIN="${TX_GAIN}" \
AMPL="${AMPL}" \
WAVE_FREQ="${TONE}" \
NSAMPS="${TX_NSAMPS}" \
./USRP292x/OtaTxWaveform.sh >"${TX_LOG}" 2>&1

wait "${rx_pid}"
rx_pid=""

python3 USRP292x/AnalyzeLoopbackCapture.py "${OUT_FILE}" \
    --rate "${RATE}" \
    --expected-tone "${TONE}"
