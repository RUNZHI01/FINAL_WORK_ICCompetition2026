#!/usr/bin/env bash
set -euo pipefail

# Single-device OTA self-loop smoke for NI USRP-2922 / N210 + SBX.
# This uses the official UHD C++ example directly and only stores outputs
# under USRP292x/.

DEVICE_ARGS="${DEVICE_ARGS:-addr=192.168.10.2}"
RATE="${RATE:-1000000}"
FREQ="${FREQ:-915000000}"
TX_GAIN="${TX_GAIN:-0}"
RX_GAIN="${RX_GAIN:-0}"
AMPL="${AMPL:-0.02}"
WAVE_FREQ="${WAVE_FREQ:-50000}"
NSAMPS="${NSAMPS:-200000}"
SETTLING="${SETTLING:-0.2}"
OUT_FILE="${OUT_FILE:-USRP292x/AntennaLoopbackShort.dat}"

mkdir -p "$(dirname "${OUT_FILE}")"

exec /usr/libexec/uhd/examples/txrx_loopback_to_file \
    --tx-args "${DEVICE_ARGS}" \
    --rx-args "${DEVICE_ARGS}" \
    --file "${OUT_FILE}" \
    --type short \
    --nsamps "${NSAMPS}" \
    --settling "${SETTLING}" \
    --tx-rate "${RATE}" \
    --rx-rate "${RATE}" \
    --tx-freq "${FREQ}" \
    --rx-freq "${FREQ}" \
    --ampl "${AMPL}" \
    --tx-gain "${TX_GAIN}" \
    --rx-gain "${RX_GAIN}" \
    --tx-ant TX/RX \
    --rx-ant RX2 \
    --wave-type SINE \
    --wave-freq "${WAVE_FREQ}"
