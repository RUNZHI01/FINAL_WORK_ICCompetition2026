#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

cd "$ROOT_DIR"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "[usrp_tui_start] 缺少虚拟环境: $VENV_PYTHON" >&2
    echo "[usrp_tui_start] 先执行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
fi

mkdir -p "$ROOT_DIR/artifacts/usrp_latent_demo_live"

DEFAULT_INPUT_LATENT="${USRP_TUI_INPUT_LATENT:-/tmp/usrp_single_image_baseline.npz}"
DEFAULT_ARTIFACT_ROOT="${USRP_TUI_ARTIFACT_ROOT:-$ROOT_DIR/artifacts/usrp_latent_demo_live}"
DEFAULT_OTA_PATH="${USRP_TUI_OTA_PATH:-spool}"
DEFAULT_SPOOL_COUNT="${USRP_TUI_SPOOL_COUNT:-1}"
DEFAULT_SPOOL_MAX_ATTEMPTS="${USRP_TUI_SPOOL_MAX_ATTEMPTS:-2}"
DEFAULT_BOARD_HOST="${USRP_TUI_BOARD_HOST:-100.121.87.73}"
DEFAULT_BOARD_USER="${USRP_TUI_BOARD_USER:-user}"
DEFAULT_BOARD_PASS="${USRP_TUI_BOARD_PASS:-user}"
DEFAULT_BOARD_PORT="${USRP_TUI_BOARD_PORT:-22}"
DEFAULT_LOCAL_SERIAL_ARGS="${USRP_TUI_LOCAL_SERIAL_ARGS:-serial=31E74E3}"
DEFAULT_REMOTE_SERIAL_ARGS="${USRP_TUI_REMOTE_SERIAL_ARGS:-serial=31DDAB3}"
DEFAULT_REMOTE_BUILD_DIR="${USRP_TUI_REMOTE_BUILD_DIR:-/home/user/usrp_tensor_codex_20260423_spool_1/usrp_tensor/build_spool}"
DEFAULT_REMOTE_INFER_TIMEOUT="${USRP_TUI_REMOTE_INFER_TIMEOUT:-300}"

ARGS=(
    "$ROOT_DIR/scripts/usrp_latent_demo.py"
    "--input-latent" "$DEFAULT_INPUT_LATENT"
    "--artifact-root" "$DEFAULT_ARTIFACT_ROOT"
    "--ota-path" "$DEFAULT_OTA_PATH"
    "--spool-count" "$DEFAULT_SPOOL_COUNT"
    "--spool-max-attempts" "$DEFAULT_SPOOL_MAX_ATTEMPTS"
    "--board-host" "$DEFAULT_BOARD_HOST"
    "--board-user" "$DEFAULT_BOARD_USER"
    "--board-pass" "$DEFAULT_BOARD_PASS"
    "--board-port" "$DEFAULT_BOARD_PORT"
    "--local-serial-args" "$DEFAULT_LOCAL_SERIAL_ARGS"
    "--remote-serial-args" "$DEFAULT_REMOTE_SERIAL_ARGS"
    "--remote-build-dir" "$DEFAULT_REMOTE_BUILD_DIR"
    "--chunk-bytes" "${USRP_TUI_CHUNK_BYTES:-8192}"
    "--remote-infer-timeout" "$DEFAULT_REMOTE_INFER_TIMEOUT"
    "--freq" "${USRP_TUI_FREQ:-915000000}"
    "--rate" "${USRP_TUI_RATE:-2500000}"
    "--ota-wait" "${USRP_TUI_OTA_WAIT:-0.4}"
    "--start-pad-samps" "${USRP_TUI_START_PAD_SAMPS:-250000}"
    "--repeat" "${USRP_TUI_REPEAT:-3}"
    "--frame-repeat" "${USRP_TUI_FRAME_REPEAT:-1}"
    "--rx-spb" "${USRP_TUI_RX_SPB:-10000}"
    "--rx-setup" "${USRP_TUI_RX_SETUP:-0.1}"
    "--decode-workers" "${USRP_TUI_DECODE_WORKERS:-2}"
    "--no-frame-timeout" "${USRP_TUI_NO_FRAME_TIMEOUT:-20.0}"
    "--tx-gain" "${USRP_TUI_TX_GAIN:-60.0}"
    "--rx-gain" "${USRP_TUI_RX_GAIN:-60.0}"
    "--warmup-frames" "${USRP_TUI_WARMUP_FRAMES:-1}"
    "--warmup-repeats" "${USRP_TUI_WARMUP_REPEATS:-1}"
    "--warmup-rounds" "${USRP_TUI_WARMUP_ROUNDS:-1}"
    "--round-gap-ms" "${USRP_TUI_ROUND_GAP_MS:-128}"
    "--tail-pad-samps" "${USRP_TUI_TAIL_PAD_SAMPS:-2000}"
    "--first-frame-extra-repeats" "${USRP_TUI_FIRST_FRAME_EXTRA_REPEATS:-0}"
    "--last-frame-extra-repeats" "${USRP_TUI_LAST_FRAME_EXTRA_REPEATS:-1}"
    "--payload-search-order" "${USRP_TUI_PAYLOAD_SEARCH_ORDER:-phase-first}"
    "--frame-order" "${USRP_TUI_FRAME_ORDER:-tail-first}"
)

exec "$VENV_PYTHON" "${ARGS[@]}" "$@"
