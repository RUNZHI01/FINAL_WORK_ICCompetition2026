#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
REMOTE_HOST="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-100.121.87.73}}"
REMOTE_USER="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"
REMOTE_PASS="${REMOTE_PASS:-${PHYTIUM_PI_PASSWORD:-}}"
TAILSCALE_STATE_VOLUME="${TAILSCALE_STATE_VOLUME:-iccomp-tailscale-state}"
TAILSCALE_PING_TARGET="${TAILSCALE_PING_TARGET:-${REMOTE_HOST}}"
BOARD_CLI_MAX_INPUTS="${BOARD_CLI_MAX_INPUTS:-300}"
BOARD_DEPS_CACHE_ROOT="${BOARD_DEPS_CACHE_ROOT:-/home/user/iccomp_board_deps_cache}"
BOARD_CLI_REFRESH_CACHE="${BOARD_CLI_REFRESH_CACHE:-0}"
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
SCRIPT_START_TS="$(date +%s)"

log() {
    printf '[board-cli-smoke] %s\n' "$*"
}

elapsed_since() {
    local start_ts="$1"
    local now_ts
    now_ts="$(date +%s)"
    printf '%ss' "$((now_ts - start_ts))"
}

human_bytes() {
    if command -v numfmt >/dev/null 2>&1; then
        numfmt --to=iec-i --suffix=B "$1"
    else
        printf '%s bytes' "$1"
    fi
}

run_step() {
    local label="$1"
    shift
    local step_start
    step_start="$(date +%s)"
    log "start: ${label}"
    "$@"
    log "done: ${label} ($(elapsed_since "${step_start}"))"
}

tar_excludes=(
    --exclude='.git'
    --exclude='Semantic-Communication/.git'
    --exclude='liboqs/.git'
    --exclude='Tongsuo/.git'
    --exclude='board_deps/openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*'
)

tailscale_start="$(date +%s)"
log "start: start tailscale"
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
log "done: start tailscale ($(elapsed_since "${tailscale_start}"))"
RUN_ROOT="/home/user/iccomp_repo_selfcontained_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
log "remote run root: ${RUN_ROOT}"
run_step "create remote run directory" "${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"

payload_bytes="$(du -sb "${tar_excludes[@]}" /repo | awk '{print $1}')"
log "upload payload apparent size: $(human_bytes "${payload_bytes}")"
log "uploading repository archive; compressed transfer is usually similar because runtimes and models are already compressed"
upload_start="$(date +%s)"
tar -C /repo "${tar_excludes[@]}" -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
log "done: upload and remote extract ($(elapsed_since "${upload_start}"))"
remote_repo_size="$("${ssh_common[@]}" "du -sh '${REMOTE_REPO}' | awk '{print \$1}'")"
log "remote repo size: ${remote_repo_size}"

if [ "${BOARD_CLI_REFRESH_CACHE:-0}" = "1" ]; then
    cache_start="$(date +%s)"
    log "refreshing reusable dependency cache: ${BOARD_DEPS_CACHE_ROOT}"
    "${ssh_common[@]}" "rm -rf '${BOARD_DEPS_CACHE_ROOT}.new' '${BOARD_DEPS_CACHE_ROOT}.old' && mkdir -p '${BOARD_DEPS_CACHE_ROOT}.new' && cp -a '${REMOTE_REPO}/board_deps' '${BOARD_DEPS_CACHE_ROOT}.new/board_deps' && if [ -e '${BOARD_DEPS_CACHE_ROOT}' ]; then mv '${BOARD_DEPS_CACHE_ROOT}' '${BOARD_DEPS_CACHE_ROOT}.old'; fi && mv '${BOARD_DEPS_CACHE_ROOT}.new' '${BOARD_DEPS_CACHE_ROOT}' && rm -rf '${BOARD_DEPS_CACHE_ROOT}.old'"
    log "done: refresh dependency cache ($(elapsed_since "${cache_start}"))"
fi

benchmark_start="$(date +%s)"
log "running isolated TVM/MNN/PyTorch benchmark; BOARD_CLI_MAX_INPUTS=${BOARD_CLI_MAX_INPUTS}"
"${ssh_common[@]}" "BOARD_CLI_MAX_INPUTS='${BOARD_CLI_MAX_INPUTS}' bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
log "done: isolated benchmark ($(elapsed_since "${benchmark_start}"))"
if "${ssh_common[@]}" "test -f '${RUN_ROOT}/logs/demo-kpi-summary.json'"; then
    log "demo KPI summary:"
    "${ssh_common[@]}" "cat '${RUN_ROOT}/logs/demo-kpi-summary.json'"
fi
run_size="$("${ssh_common[@]}" "du -sh '${RUN_ROOT}' | awk '{print \$1}'")"
log "remote run size: ${run_size}"
log "output root: ${RUN_ROOT}"
log "total elapsed: $(elapsed_since "${SCRIPT_START_TS}")"
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
    -e "BOARD_DEPS_CACHE_ROOT=${BOARD_DEPS_CACHE_ROOT}" \
    -e "BOARD_CLI_REFRESH_CACHE=${BOARD_CLI_REFRESH_CACHE}" \
    -e "LOCAL_SCRIPT_B64=${LOCAL_SCRIPT_B64}" \
    "${IMAGE_NAME}" \
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'
