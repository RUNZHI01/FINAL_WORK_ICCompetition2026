#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ROOT="${LOCAL_ROOT:-$(git -C "${SCRIPT_DIR}/.." rev-parse --show-toplevel)}"
WORK_ROOT="${WORK_ROOT:-$(pwd)/submission-work}"
OUTPUT="${OUTPUT:-$(pwd)/iccomp2026-submission.tar.gz}"
CLEAN_DIR="${WORK_ROOT}/submission-clean"

rm -rf "${CLEAN_DIR}"
mkdir -p "${WORK_ROOT}"

if ! git -C "${LOCAL_ROOT}" diff --quiet || ! git -C "${LOCAL_ROOT}" diff --cached --quiet; then
    echo "local repository has uncommitted changes; commit and push before packaging from the remote source." >&2
    exit 1
fi

git clone "${REPO_URL}" "${CLEAN_DIR}"

if [ "$(git -C "${LOCAL_ROOT}" rev-parse HEAD)" != "$(git -C "${CLEAN_DIR}" rev-parse HEAD)" ]; then
    echo "local HEAD differs from the freshly cloned remote HEAD; push or checkout the submitted commit first." >&2
    exit 1
fi

tar \
    --exclude-vcs \
    --exclude='.venv' \
    --exclude='.venv_*' \
    --exclude='build' \
    --exclude='liboqs/build' \
    --exclude='tongsuo-dist*' \
    --exclude='**/__pycache__' \
    --exclude='**/.pytest_cache' \
    -czf "${OUTPUT}" \
    -C "${CLEAN_DIR}" \
    .

echo "submission package written to: ${OUTPUT}"
