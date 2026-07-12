#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
CONTAINER_NAME="${CONTAINER_NAME:-iccomp-electron-demo}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() {
    printf '[demo] %s\n' "$*"
}

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    log "image ${IMAGE_NAME} not found; building it first"
    docker build \
        -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${PROJECT_ROOT}"
fi

docker_args=(--rm -it --name "${CONTAINER_NAME}")

for name in \
    ICCOMP_COCKPIT_PROFILE \
    REMOTE_HOST PHYTIUM_PI_HOST \
    REMOTE_USER PHYTIUM_PI_USER \
    REMOTE_PASS PHYTIUM_PI_PASSWORD \
    REMOTE_SSH_PORT PHYTIUM_PI_PORT \
    OPENAMP_DEMO_INPUT_SOURCE_MODE \
    REMOTE_USRP_RX_DIR REMOTE_RX_RUN_ROOT REMOTE_USRP_PROJECT_ROOT \
    RX_ARM_WAIT_MS RX_STOP_WAIT_MS \
    REMOTE_USRP_DECODE_PYTHON OPENAMP_DEMO_REMOTE_DECODE_PYTHON \
    JSCC_LINK_MODE OPENAMP_DEMO_LINK_MODE \
    ANALOG_IN_PROCESS_LOCAL_CODEC ANALOG_WARMUP_LOCAL_CODEC \
    ANALOG_SPS ANALOG_AMPLITUDE ANALOG_RX_TAIL_SEC ANALOG_RX_POST_QUANTIZE ANALOG_REMOTE_DECODED_FORMAT \
    ANALOG_REMOTE_STALL_SNAPSHOT ANALOG_REMOTE_STALL_SNAPSHOT_THRESHOLD_SEC ANALOG_REMOTE_STALL_SNAPSHOT_LIMIT \
    ANALOG_RX_WAIT_TIMEOUT_SEC ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC \
    ANALOG_RX_ARM_STATUS_TIMEOUT_SEC ANALOG_RX_ARM_STATUS_POLL_SEC \
    ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC ANALOG_RX_STOP_DRAIN_POLL_SEC \
    PERSISTENT_RX_TX_DELAY ANALOG_REMOTE_CLEANUP_MODE ANALOG_REMOTE_DECODE_WORKER ANALOG_REMOTE_DECODE_WORKER_PREFIX \
    ANALOG_PRECONNECT_CONTROL ANALOG_PRECONNECT_RX_CAPTURE_CONTROL ANALOG_RX_SESSION_CONTROL \
    ANALOG_RX_BATCH_SESSION_CONTROL ANALOG_RX_BATCH_SESSION_MAX_IMAGES \
    ANALOG_PIPELINE_DEPTH \
    ANALOG_DECODE_PIPELINE_WARMUP ANALOG_DECODE_WARMUP_SHAPE \
    ANALOG_REMOTE_DECODE_RESULT_MODE ANALOG_REMOTE_DECODED_OUTPUT_DIR \
    ANALOG_REMOTE_DECODE_RESPONSE_MODE ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY \
    ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC \
    ANALOG_REMOTE_DECODE_ASSET_PROBE_TIMEOUT_SEC ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC \
    ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK \
    ANALOG_RX_SC16_MMAP ANALOG_RX_CLIPPING_DECIMATION \
    ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS ANALOG_MIN_SYNC_METRIC ANALOG_ROBUST_SYNC \
    OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT USRP_SHUTDOWN_CONTROL_AFTER_TRANSPORT \
    USRP_MAX_ARQ_ROUNDS MLKEM_USRP_MAX_ARQ_ROUNDS \
    MLKEM_TRANSPORT_MODE MLKEM_USRP_MODE MLKEM_CIPHER_SUITE MLKEM_AUTH_ENABLED MLKEM_AUTH_SIG_POLICY \
    OPENAMP_SSH_RUNNER OPENAMP_SSH_DOCKER_IMAGE SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER \
    OPENAMP_USRP_TX_RUNNER OPENAMP_USRP_TX_DOCKER_IMAGE OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET \
    OPENAMP_TVM_BATCH_RUNNER OPENAMP_DEMO_TVM_BATCH_RUNNER OPENAMP_TVM_BATCH_EXIT_GRACE_SEC; do
    if [ -n "${!name:-}" ]; then
        docker_args+=(-e "${name}=${!name}")
    fi
done

if [ "${ENABLE_TAILSCALE:-0}" = "1" ]; then
    docker_args+=(--cap-add=NET_ADMIN --cap-add=NET_RAW --device=/dev/net/tun)
    docker_args+=(-v "${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}:/var/lib/tailscale")
    docker_args+=(-e ENABLE_TAILSCALE=1)
    for name in \
        TS_AUTHKEY TAILSCALE_AUTHKEY \
        TS_HOSTNAME TAILSCALE_HOSTNAME \
        TS_ACCEPT_DNS TAILSCALE_ACCEPT_DNS \
        TS_ACCEPT_ROUTES TAILSCALE_ACCEPT_ROUTES \
        TS_EXTRA_ARGS TAILSCALE_EXTRA_ARGS \
        TAILSCALE_PING_TARGET; do
        if [ -n "${!name:-}" ]; then
            docker_args+=(-e "${name}=${!name}")
        fi
    done
fi

if [ -n "${DISPLAY:-}" ]; then
    docker_args+=(-e "DISPLAY=${DISPLAY}")
    if [ -d /tmp/.X11-unix ]; then
        docker_args+=(-v /tmp/.X11-unix:/tmp/.X11-unix)
    fi
    if [ -d /mnt/wslg ]; then
        docker_args+=(-v /mnt/wslg:/mnt/wslg)
        docker_args+=(-e "XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir")
        if [ -n "${WAYLAND_DISPLAY:-}" ]; then
            docker_args+=(-e "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}")
        fi
        if [ -n "${PULSE_SERVER:-}" ]; then
            docker_args+=(-e "PULSE_SERVER=${PULSE_SERVER}")
        fi
    fi
    if [ -n "${XAUTHORITY:-}" ] && [ -f "${XAUTHORITY}" ]; then
        docker_args+=(-v "${XAUTHORITY}:/tmp/.docker.xauth:ro" -e XAUTHORITY=/tmp/.docker.xauth)
    fi
else
    log "DISPLAY is empty. Start an X11/Wayland bridge first, then rerun this script."
    log "For headless verification only, use ./docker/repro.sh; it runs Electron under Xvfb."
    exit 1
fi

log "starting the production Electron cockpit inside Docker"
if [ "${ENABLE_TAILSCALE:-0}" = "1" ]; then
    log "tailscale enabled; state volume=${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}"
fi
exec docker run "${docker_args[@]}" "${IMAGE_NAME}" bash docker/start-electron-prod-demo.sh
