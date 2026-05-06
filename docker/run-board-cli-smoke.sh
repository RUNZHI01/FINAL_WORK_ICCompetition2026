#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
REMOTE_HOST="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-100.121.87.73}}"
REMOTE_USER="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"
REMOTE_PASS="${REMOTE_PASS:-${PHYTIUM_PI_PASSWORD:-}}"
TAILSCALE_STATE_VOLUME="${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}"
TAILSCALE_PING_TARGET="${TAILSCALE_PING_TARGET:-${REMOTE_HOST}}"
BOARD_CLI_MAX_INPUTS="${BOARD_CLI_MAX_INPUTS:-300}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -z "${REMOTE_PASS}" ]; then
    if [ -t 0 ]; then
        read -r -s -p "Enter board SSH password: " REMOTE_PASS
        printf '\n'
    fi
fi

if [ -z "${REMOTE_PASS}" ]; then
    echo "board SSH password is required for board CLI smoke." >&2
    exit 1
fi

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    docker build \
        -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${PROJECT_ROOT}"
fi

SMOKE_SCRIPT="$(cat <<'SH'
set -euo pipefail
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
RUN_ROOT="/home/user/iccomp_repo_selfcontained_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
printf '[board-cli-smoke] remote run root: %s\n' "${RUN_ROOT}"
"${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"
tar -C /repo \
  --exclude='.git' \
  --exclude='Semantic-Communication/.git' \
  --exclude='liboqs/.git' \
  --exclude='Tongsuo/.git' \
  --exclude='board_deps/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*' \
  -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
"${ssh_common[@]}" "bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
printf '[board-cli-smoke] output root: %s\n' "${RUN_ROOT}"
SH
)"
LOCAL_SCRIPT_B64="$(printf '%s' "${SMOKE_SCRIPT}" | base64 -w 0)"

docker run --rm \
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    --device=/dev/net/tun \
    -v "${TAILSCALE_STATE_VOLUME}:/var/lib/tailscale" \
    -v "${PROJECT_ROOT}:/repo:ro" \
    -e "TAILSCALE_PING_TARGET=${TAILSCALE_PING_TARGET}" \
    -e "TS_LOGIN_WAIT_SEC=8" \
    -e "REMOTE_HOST=${REMOTE_HOST}" \
    -e "REMOTE_USER=${REMOTE_USER}" \
    -e "SSHPASS=${REMOTE_PASS}" \
    -e "BOARD_CLI_MAX_INPUTS=${BOARD_CLI_MAX_INPUTS}" \
    -e "LOCAL_SCRIPT_B64=${LOCAL_SCRIPT_B64}" \
    "${IMAGE_NAME}" \
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'
