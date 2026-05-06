#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="${ELECTRON_SMOKE_LOG:-/tmp/iccomp-electron-smoke.log}"
TIMEOUT_SEC="${ELECTRON_SMOKE_TIMEOUT_SEC:-120}"
rm -f "${LOG_FILE}"

xvfb-run -a --server-args="-screen 0 1280x800x24" \
    docker/start-electron-prod-demo.sh >"${LOG_FILE}" 2>&1 &
app_pid="$!"

cleanup() {
    if kill -0 "${app_pid}" >/dev/null 2>&1; then
        kill "${app_pid}" >/dev/null 2>&1 || true
        wait "${app_pid}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

deadline=$((SECONDS + TIMEOUT_SEC))
while [ "${SECONDS}" -lt "${deadline}" ]; do
    if ! kill -0 "${app_pid}" >/dev/null 2>&1; then
        cat "${LOG_FILE}" >&2 || true
        exit 1
    fi

    if curl -fsS "http://127.0.0.1:8079/api/health" >/dev/null 2>&1; then
        echo "electron-smoke-ok"
        exit 0
    fi

    sleep 1
done

cat "${LOG_FILE}" >&2 || true
echo "Electron smoke test timed out after ${TIMEOUT_SEC}s" >&2
exit 1
