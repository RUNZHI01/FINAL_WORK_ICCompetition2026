#!/usr/bin/env bash
set -euo pipefail

# Minimal UHD RX capture with explicit channel 0 gain setting.
# This is used only to bypass rx_samples_to_file --gain on N210/SBX.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${SCRIPT_DIR}/OtaRxCaptureGain"

if [[ ! -x "${BIN}" ]]; then
    echo "Missing ${BIN}; run ${SCRIPT_DIR}/BuildOtaTools.sh first." >&2
    exit 1
fi

DEVICE_ARGS="${DEVICE_ARGS:-addr=192.168.10.22}"
RATE="${RATE:-219298}"
FREQ="${FREQ:-500000000}"
GAIN="${GAIN:-20}"
ANT="${ANT:-RX2}"
BW="${BW:-0}"
SETUP="${SETUP:-0.5}"
DURATION="${DURATION:-4}"
NSAMPS="${NSAMPS:-0}"
OUT_FILE="${OUT_FILE:-USRP292x/OtaRxCaptureGain.dat}"
WIREFMT="${WIREFMT:-sc16}"
CHANNEL="${CHANNEL:-0}"

mkdir -p "$(dirname "${OUT_FILE}")"

cmd=(
    "${BIN}"
    --args "${DEVICE_ARGS}"
    --file "${OUT_FILE}"
    --rate "${RATE}"
    --freq "${FREQ}"
    --gain "${GAIN}"
    --ant "${ANT}"
    --channel "${CHANNEL}"
    --wirefmt "${WIREFMT}"
    --setup "${SETUP}"
    --stats
)

if [[ "${DURATION}" != "0" ]]; then
    cmd+=(--duration "${DURATION}")
fi

if [[ "${NSAMPS}" != "0" ]]; then
    cmd+=(--nsamps "${NSAMPS}")
fi

if [[ "${BW}" != "0" ]]; then
    cmd+=(--bw "${BW}")
fi

exec "${cmd[@]}"
