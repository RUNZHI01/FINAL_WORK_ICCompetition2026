#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
CONTAINER_NAME="${CONTAINER_NAME:-iccomp-tailscale-login}"
TAILSCALE_STATE_VOLUME="${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-iccomp-demo}"
TS_ACCEPT_DNS="${TS_ACCEPT_DNS:-false}"
TS_ACCEPT_ROUTES="${TS_ACCEPT_ROUTES:-true}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() {
    printf '[tailscale-login] %s\n' "$*"
}

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    log "image ${IMAGE_NAME} not found; building it first"
    docker build \
        -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${PROJECT_ROOT}"
fi

docker_args=(
    run --rm -i
    --name "${CONTAINER_NAME}"
    --cap-add=NET_ADMIN
    --cap-add=NET_RAW
    --device=/dev/net/tun
    -v "${TAILSCALE_STATE_VOLUME}:/var/lib/tailscale"
    -e TS_LOGIN_MODE=interactive
    -e "TAILSCALE_HOSTNAME=${TAILSCALE_HOSTNAME}"
    -e "TS_ACCEPT_DNS=${TS_ACCEPT_DNS}"
    -e "TS_ACCEPT_ROUTES=${TS_ACCEPT_ROUTES}"
)

if [ -t 0 ]; then
    docker_args+=(--tty)
fi

for name in TAILSCALE_PING_TARGET TS_EXTRA_ARGS TAILSCALE_EXTRA_ARGS; do
    if [ -n "${!name:-}" ]; then
        docker_args+=(-e "${name}=${!name}")
    fi
done

log "using state volume: ${TAILSCALE_STATE_VOLUME}"
log "open the printed login URL in your browser, finish auth, then this command will return"
exec docker "${docker_args[@]}" "${IMAGE_NAME}" bash docker/start-tailscale.sh
