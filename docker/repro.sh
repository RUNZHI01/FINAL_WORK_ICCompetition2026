#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-iccomp-ubuntu-minimal}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() {
    printf '[repro] %s\n' "$*"
}

log "initializing submodules"
git -C "${PROJECT_ROOT}" submodule sync --recursive
git -C "${PROJECT_ROOT}" submodule update --init --recursive

log "building Docker image: ${IMAGE_NAME}"
docker build \
    -f "${PROJECT_ROOT}/docker/ubuntu-minimal.Dockerfile" \
    -t "${IMAGE_NAME}" \
    "${PROJECT_ROOT}"

log "checking Python dependencies"
docker run --rm "${IMAGE_NAME}" python docker/check_deps.py

log "running minimal reproducibility tests"
docker run --rm "${IMAGE_NAME}" pytest -q \
    mlkem_link/tests/test_auth.py \
    mlkem_link/tests/test_session.py \
    mlkem_link/tests/test_tui_remote_tcp_server.py \
    scripts/test_latent_transport.py \
    scripts/test_fit.py

log "checking prerecorded demo API"
docker run --rm "${IMAGE_NAME}" bash docker/api-smoke.sh

log "running Electron smoke test with Xvfb"
docker run --rm "${IMAGE_NAME}" bash docker/electron-smoke.sh

log "reproducibility validation completed"
