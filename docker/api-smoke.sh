#!/usr/bin/env bash
set -euo pipefail

export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"
export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-0}"
export REMOTE_PASS="${REMOTE_PASS:-}"
export PHYTIUM_PI_PASSWORD="${PHYTIUM_PI_PASSWORD:-}"

SERVER_LOG="${SERVER_LOG:-/tmp/iccomp-api-smoke-server.log}"
rm -f "${SERVER_LOG}"

python /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py \
    --host 127.0.0.1 \
    --port 8079 \
    >"${SERVER_LOG}" 2>&1 &
server_pid="$!"

cleanup() {
    if kill -0 "${server_pid}" >/dev/null 2>&1; then
        kill "${server_pid}" >/dev/null 2>&1 || true
        wait "${server_pid}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

for _ in $(seq 1 25); do
    if curl -fsS "http://127.0.0.1:8079/api/health" >/dev/null 2>&1; then
        break
    fi
    if ! kill -0 "${server_pid}" >/dev/null 2>&1; then
        cat "${SERVER_LOG}" >&2 || true
        exit 1
    fi
    sleep 1
done

curl -fsS "http://127.0.0.1:8079/api/snapshot" > /tmp/iccomp-snapshot.json
curl -fsS \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"image_index":0,"mode":"current"}' \
    "http://127.0.0.1:8079/api/run-inference" > /tmp/iccomp-inference.json
curl -fsS \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"image_index":0,"max_inputs":1}' \
    "http://127.0.0.1:8079/api/run-baseline" > /tmp/iccomp-baseline.json

python - <<'PY'
import base64
import json
import os
from pathlib import Path

MIN_IMAGE_BYTES = int(os.environ.get("ICCOMP_API_SMOKE_MIN_IMAGE_BYTES", "50000"))
EXPECTED_EXECUTION_MODE = os.environ.get("ICCOMP_API_SMOKE_EXPECTED_EXECUTION_MODE", "prerecorded")


def assert_image_data_uri(payload: dict, key: str) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.startswith("data:image/"):
        raise SystemExit(f"{key} is not an image data URI")
    try:
        encoded = value.split(",", 1)[1]
        image_bytes = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"{key} is not valid base64: {exc}") from exc
    if len(image_bytes) < MIN_IMAGE_BYTES:
        raise SystemExit(f"{key} is too small and likely a placeholder: {len(image_bytes)} bytes")


snapshot = json.loads(Path("/tmp/iccomp-snapshot.json").read_text())
inference = json.loads(Path("/tmp/iccomp-inference.json").read_text())
baseline = json.loads(Path("/tmp/iccomp-baseline.json").read_text())

if not isinstance(snapshot, dict) or len(snapshot) < 5:
    raise SystemExit("snapshot payload is unexpectedly small")
if inference.get("status") not in {"success", "fallback", "ok"}:
    raise SystemExit(f"unexpected inference status: {inference.get('status')!r}")
if inference.get("execution_mode") != EXPECTED_EXECUTION_MODE:
    raise SystemExit(
        f"unexpected inference execution_mode: {inference.get('execution_mode')!r}; "
        f"expected {EXPECTED_EXECUTION_MODE!r}"
    )
assert_image_data_uri(inference, "original_image_b64")
assert_image_data_uri(inference, "reconstructed_image_b64")
assert_image_data_uri(baseline, "original_image_b64")
assert_image_data_uri(baseline, "reconstructed_image_b64")

print("api-smoke-ok")
PY
