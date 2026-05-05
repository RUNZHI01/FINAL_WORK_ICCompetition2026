#!/usr/bin/env bash
set -euo pipefail

# Official UHD single-direction OTA RX capture.
# Use on the receiver host with one NI USRP-2922 / N210 device.

DEVICE_ARGS="${DEVICE_ARGS:-addr=192.168.10.22}"
RATE="${RATE:-1000000}"
FREQ="${FREQ:-1000000000}"
GAIN="${GAIN:-}"
ANT="${ANT:-RX2}"
BW="${BW:-0}"
SETUP="${SETUP:-0.5}"
DURATION="${DURATION:-3}"
NSAMPS="${NSAMPS:-0}"
OUT_FILE="${OUT_FILE:-USRP292x/OtaRxCapture.dat}"
WIREFMT="${WIREFMT:-sc16}"
CHANNELS="${CHANNELS:-0}"

mkdir -p "$(dirname "${OUT_FILE}")"

cmd=(
    /usr/libexec/uhd/examples/rx_samples_to_file
    --args "${DEVICE_ARGS}"
    --file "${OUT_FILE}"
    --type short
    --rate "${RATE}"
    --freq "${FREQ}"
    --ant "${ANT}"
    --channels "${CHANNELS}"
    --wirefmt "${WIREFMT}"
    --setup "${SETUP}"
    --stats
)

if [[ "${DURATION}" != "0" ]]; then
    cmd+=(--duration "${DURATION}")
fi

if [[ -n "${GAIN}" ]]; then
    cmd+=(--gain "${GAIN}")
fi

if [[ "${NSAMPS}" != "0" ]]; then
    cmd+=(--nsamps "${NSAMPS}")
fi

if [[ "${BW}" != "0" ]]; then
    cmd+=(--bw "${BW}")
fi

exec "${cmd[@]}"
