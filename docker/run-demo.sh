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
    JSCC_LINK_MODE OPENAMP_DEMO_LINK_MODE \
    MLKEM_TRANSPORT_MODE MLKEM_AUTH_ENABLED \
    OPENAMP_SSH_RUNNER OPENAMP_SSH_DOCKER_IMAGE; do
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
