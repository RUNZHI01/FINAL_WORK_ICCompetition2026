#!/usr/bin/env bash
set -euo pipefail

# Official UHD single-direction OTA TX smoke.
# Use on the transmitter host with one NI USRP-2922 / N210 device.

DEVICE_ARGS="${DEVICE_ARGS:-addr=192.168.10.2}"
RATE="${RATE:-1000000}"
FREQ="${FREQ:-1000000000}"
GAIN="${GAIN:-0}"
AMPL="${AMPL:-0.05}"
ANT="${ANT:-TX/RX}"
WAVE_TYPE="${WAVE_TYPE:-SINE}"
WAVE_FREQ="${WAVE_FREQ:-100000}"
BW="${BW:-0}"
NSAMPS="${NSAMPS:-0}"

cmd=(
    /usr/libexec/uhd/examples/tx_waveforms
    --args "${DEVICE_ARGS}"
    --rate "${RATE}"
    --freq "${FREQ}"
    --gain "${GAIN}"
    --ampl "${AMPL}"
    --ant "${ANT}"
    --wave-type "${WAVE_TYPE}"
    --wave-freq "${WAVE_FREQ}"
    --nsamps "${NSAMPS}"
)

if [[ "${BW}" != "0" ]]; then
    cmd+=(--bw "${BW}")
fi

exec "${cmd[@]}"
