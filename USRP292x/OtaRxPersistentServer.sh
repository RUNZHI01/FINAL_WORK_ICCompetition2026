#!/usr/bin/env bash
set -euo pipefail

# Persistent UHD RX server controlled by a small TCP line protocol.
# Bind to 0.0.0.0 when the control path should come from Tailscale.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${SCRIPT_DIR}/OtaRxPersistentServer"

if [[ ! -x "${BIN}" ]]; then
    echo "Missing ${BIN}; run ${SCRIPT_DIR}/BuildOtaTools.sh first." >&2
    exit 1
fi

DEVICE_ARGS="${DEVICE_ARGS:-addr=192.168.10.22}"
BIND_ADDR="${BIND_ADDR:-0.0.0.0}"
PORT="${PORT:-29220}"
RATE="${RATE:-5000000}"
FREQ="${FREQ:-500000000}"
GAIN="${GAIN:-15}"
ANT="${ANT:-RX2}"
BW="${BW:-0}"
SETUP="${SETUP:-0.5}"
WIREFMT="${WIREFMT:-sc16}"
CHANNEL="${CHANNEL:-0}"

cmd=(
    "${BIN}"
    --args "${DEVICE_ARGS}"
    --bind "${BIND_ADDR}"
    --port "${PORT}"
    --rate "${RATE}"
    --freq "${FREQ}"
    --gain "${GAIN}"
    --ant "${ANT}"
    --channel "${CHANNEL}"
    --wirefmt "${WIREFMT}"
    --setup "${SETUP}"
)

if [[ "${BW}" != "0" ]]; then
    cmd+=(--bw "${BW}")
fi

exec "${cmd[@]}"
