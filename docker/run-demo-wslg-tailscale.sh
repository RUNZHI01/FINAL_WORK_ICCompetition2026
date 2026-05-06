#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
CONTAINER_NAME="${CONTAINER_NAME:-iccomp-electron-prod-wslg-tailscale-$(date +%H%M%S)}"
TAILSCALE_STATE_VOLUME="${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-iccomp-demo}"
TAILSCALE_PING_TARGET="${TAILSCALE_PING_TARGET:-100.121.87.73}"
REMOTE_HOST="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-${TAILSCALE_PING_TARGET}}}"
REMOTE_USER="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() {
    printf '[wslg-demo] %s\n' "$*"
}

die() {
    printf '[wslg-demo] %s\n' "$*" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || die "docker CLI is not available inside WSL."
[ -d /mnt/wslg/.X11-unix ] || die "WSLg X11 socket directory is missing: /mnt/wslg/.X11-unix"
[ -d /mnt/wslg/runtime-dir ] || die "WSLg runtime directory is missing: /mnt/wslg/runtime-dir"

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    log "image ${IMAGE_NAME} not found; building it first"
    docker build \
        -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${PROJECT_ROOT}"
fi

if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
    die "container ${CONTAINER_NAME} already exists. Choose another CONTAINER_NAME or remove the old container yourself."
fi

docker_args=(
    run --rm -d
    --name "${CONTAINER_NAME}"
    --cap-add=NET_ADMIN
    --cap-add=NET_RAW
    --device=/dev/net/tun
    -v "${TAILSCALE_STATE_VOLUME}:/var/lib/tailscale"
    -v /mnt/wslg/.X11-unix:/tmp/.X11-unix:rw
    -v /mnt/wslg/runtime-dir:/mnt/wslg/runtime-dir:rw
    -e ENABLE_TAILSCALE=1
    -e DISPLAY="${DISPLAY:-:0}"
    -e WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
    -e XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir
    -e QT_X11_NO_MITSHM=1
    -e LIBGL_ALWAYS_SOFTWARE=1
    -e COCKPIT_OPEN_DEVTOOLS="${COCKPIT_OPEN_DEVTOOLS:-0}"
    -e TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME}"
    -e TAILSCALE_PING_TARGET="${TAILSCALE_PING_TARGET}"
    -e REMOTE_HOST="${REMOTE_HOST}"
    -e PHYTIUM_PI_HOST="${REMOTE_HOST}"
    -e REMOTE_USER="${REMOTE_USER}"
    -e PHYTIUM_PI_USER="${REMOTE_USER}"
)

if [ -e /mnt/wslg/PulseServer ]; then
    docker_args+=(
        -v /mnt/wslg/PulseServer:/mnt/wslg/PulseServer:rw
        -e PULSE_SERVER=/mnt/wslg/PulseServer
    )
fi

for name in \
    TS_AUTHKEY TAILSCALE_AUTHKEY \
    TS_ACCEPT_DNS TAILSCALE_ACCEPT_DNS \
    TS_ACCEPT_ROUTES TAILSCALE_ACCEPT_ROUTES \
    TS_EXTRA_ARGS TAILSCALE_EXTRA_ARGS \
    REMOTE_PASS PHYTIUM_PI_PASSWORD \
    MLKEM_REMOTE_PYTHON MLKEM_REMOTE_OQS_INSTALL_PATH \
    MLKEM_REMOTE_LD_LIBRARY_PATH MLKEM_REMOTE_TONGSUO_SIG_BRIDGE \
    MLKEM_REMOTE_TONGSUO_KEM_BRIDGE MLKEM_REMOTE_RUN_LOGGER_DIR; do
    if [ -n "${!name:-}" ]; then
        docker_args+=(-e "${name}=${!name}")
    fi
done

log "starting native Electron cockpit with WSLg and Tailscale"
log "container=${CONTAINER_NAME}"
log "tailscale_target=${TAILSCALE_PING_TARGET}; state_volume=${TAILSCALE_STATE_VOLUME}"

docker "${docker_args[@]}" "${IMAGE_NAME}" bash docker/start-electron-prod-demo.sh

sleep "${DEMO_STARTUP_LOG_DELAY_SEC:-8}"
docker ps -a --filter "name=${CONTAINER_NAME}" --format '{{.Names}} {{.Status}}'
docker logs --tail "${DEMO_LOG_TAIL:-100}" "${CONTAINER_NAME}" || true

log "stop with: docker stop ${CONTAINER_NAME}"
