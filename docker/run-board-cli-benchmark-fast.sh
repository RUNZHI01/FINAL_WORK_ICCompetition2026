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
BOARD_CLI_FAST_KEEP_WORK="${BOARD_CLI_FAST_KEEP_WORK:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -z "${REMOTE_PASS}" ] && [ -t 0 ]; then
    read -r -s -p "Enter board SSH password: " REMOTE_PASS
    printf '\n'
fi

if [ -z "${REMOTE_PASS}" ]; then
    echo "board SSH password is required for board CLI fast benchmark." >&2
    exit 1
fi

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    docker build \
        -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${PROJECT_ROOT}"
fi

BENCHMARK_SCRIPT="$(cat <<'SH'
set -euo pipefail
SCRIPT_START_TS="$(date +%s)"

log() {
    printf '[board-cli-fast] %s\n' "$*"
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

fast_tar_excludes=(
    --exclude='.git'
    --exclude='Semantic-Communication/.git'
    --exclude='liboqs'
    --exclude='Tongsuo'
    --exclude='board_deps/runtime'
    --exclude='board_deps/openamp'
    --exclude='board_deps/tvm'
    --exclude='board_deps/mnn'
    --exclude='board_deps/pytorch'
    --exclude='board_deps/inputs'
    --exclude='board_deps/crypto'
    --exclude='board_deps/usrp'
    --exclude='**/node_modules'
    --exclude='**/__pycache__'
    --exclude='**/.pytest_cache'
)

tailscale_start="$(date +%s)"
log "start: start tailscale"
bash docker/start-tailscale.sh >/tmp/tailscale-start.log 2>&1
log "done: start tailscale ($(elapsed_since "${tailscale_start}"))"

RUN_ROOT="/home/user/iccomp_benchmark_fast_$(date +%Y%m%d_%H%M%S)"
REMOTE_REPO="${RUN_ROOT}/repo"
CACHE_ROOT="${BOARD_DEPS_CACHE_ROOT:-/home/user/iccomp_board_deps_cache}"
CACHE_BOARD_DEPS="${CACHE_ROOT}/board_deps"
CACHE_RUNTIME="${CACHE_ROOT}/runtime"
ssh_common=(sshpass -e ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")
ssh_stream=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/tmp/known_hosts -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "${REMOTE_USER}@${REMOTE_HOST}")

log "remote run root: ${RUN_ROOT}"
log "dependency cache root: ${CACHE_ROOT}"

cache_check='set -e
cache="$1"
for p in \
  runtime/tvm_py310.tar.gz \
  runtime/mnn_py312.tar.gz.part-00 \
  runtime/mnn_py312.tar.gz.part-01 \
  runtime/mnn_py312.tar.gz.part-02 \
  tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz \
  tvm/current/optimized_model.so \
  mnn/origin/model1.mnn \
  pytorch/compressed_gan.pt \
  inputs/places365-latents.tar.gz \
  inputs/mnn-encoder-outputs.tar.gz
do
  if [ ! -e "${cache}/${p}" ]; then
    echo "missing cache dependency: ${cache}/${p}" >&2
    exit 44
  fi
done'

if ! printf '%s' "${cache_check}" | "${ssh_stream[@]}" "bash -s -- '${CACHE_BOARD_DEPS}'"; then
    log "dependency cache is missing or incomplete."
    log "create it once with: BOARD_CLI_REFRESH_CACHE=1 docker/run-board-cli-smoke.*"
    exit 44
fi

log "start: create remote run directory"
dir_start="$(date +%s)"
"${ssh_common[@]}" "rm -rf '${RUN_ROOT}' && mkdir -p '${REMOTE_REPO}'"
log "done: create remote run directory ($(elapsed_since "${dir_start}"))"

payload_bytes="$(du -sb "${fast_tar_excludes[@]}" /repo | awk '{print $1}')"
log "upload payload apparent size: $(human_bytes "${payload_bytes}")"
log "uploading code overlay without board_deps runtime/model/input payloads"
upload_start="$(date +%s)"
tar -C /repo "${fast_tar_excludes[@]}" -czf - . | "${ssh_stream[@]}" "tar -xzf - -C '${REMOTE_REPO}'"
log "done: upload code overlay ($(elapsed_since "${upload_start}"))"

link_start="$(date +%s)"
log "start: link cached board_deps into remote repo"
"${ssh_common[@]}" "mkdir -p '${REMOTE_REPO}/board_deps' && for d in runtime inputs tvm mnn pytorch crypto; do rm -rf '${REMOTE_REPO}/board_deps/'\"\$d\"; ln -s '${CACHE_BOARD_DEPS}/'\"\$d\" '${REMOTE_REPO}/board_deps/'\"\$d\"; done"
log "done: link cached board_deps ($(elapsed_since "${link_start}"))"

runtime_start="$(date +%s)"
log "start: prepare cached Python runtimes"
"${ssh_common[@]}" "set -e; mkdir -p '${CACHE_RUNTIME}'; if [ ! -d '${CACHE_RUNTIME}/tvm_py310' ]; then tar -xzf '${CACHE_BOARD_DEPS}/runtime/tvm_py310.tar.gz' -C '${CACHE_RUNTIME}'; fi; if [ ! -d '${CACHE_RUNTIME}/mnn_py312' ]; then cat '${CACHE_BOARD_DEPS}'/runtime/mnn_py312.tar.gz.part-* | tar -xzf - -C '${CACHE_RUNTIME}'; fi"
log "done: prepare cached Python runtimes ($(elapsed_since "${runtime_start}"))"

benchmark_start="$(date +%s)"
log "running fast TVM/MNN/PyTorch benchmark; BOARD_CLI_MAX_INPUTS=${BOARD_CLI_MAX_INPUTS}"
"${ssh_common[@]}" "BOARD_CLI_MAX_INPUTS='${BOARD_CLI_MAX_INPUTS}' BOARD_CLI_RUNTIME_CACHE='${CACHE_RUNTIME}' bash '${REMOTE_REPO}/board_deps/scripts/run-isolated-cli-smoke.sh' '${REMOTE_REPO}' '${RUN_ROOT}'"
log "done: fast benchmark ($(elapsed_since "${benchmark_start}"))"

if "${ssh_common[@]}" "test -f '${RUN_ROOT}/logs/demo-kpi-summary.json'"; then
    log "demo KPI summary:"
    "${ssh_common[@]}" "cat '${RUN_ROOT}/logs/demo-kpi-summary.json'"
fi

if [ "${BOARD_CLI_FAST_KEEP_WORK:-0}" != "1" ]; then
    cleanup_start="$(date +%s)"
    log "start: clean transient fast benchmark work tree"
    "${ssh_common[@]}" "rm -rf '${REMOTE_REPO}' '${RUN_ROOT}/work' '${RUN_ROOT}/runtime'"
    log "done: clean transient fast benchmark work tree ($(elapsed_since "${cleanup_start}"))"
fi

run_size="$("${ssh_common[@]}" "du -sh '${RUN_ROOT}' | awk '{print \$1}'")"
log "remote run size: ${run_size}"
log "output root: ${RUN_ROOT}"
log "total elapsed: $(elapsed_since "${SCRIPT_START_TS}")"
SH
)"
LOCAL_SCRIPT_B64="$(printf '%s' "${BENCHMARK_SCRIPT}" | base64 -w 0)"

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
    -e "BOARD_CLI_FAST_KEEP_WORK=${BOARD_CLI_FAST_KEEP_WORK}" \
    -e "LOCAL_SCRIPT_B64=${LOCAL_SCRIPT_B64}" \
    "${IMAGE_NAME}" \
    bash -lc 'cd /repo && printf "%s" "$LOCAL_SCRIPT_B64" | base64 -d | bash'
