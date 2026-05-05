#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
LAUNCHER="${OPENAMP_DEMO_MLKEM_ONCE_LAUNCHER:-$SCRIPT_DIR/run_openamp_demo.sh}"
PYTHON_BIN="${OPENAMP_DEMO_MLKEM_ONCE_PYTHON:-python3}"

HOST="127.0.0.1"
PORT="18089"
BOARD_HOST="${OPENAMP_DEMO_BOARD_HOST:-100.121.87.73}"
BOARD_USER="${OPENAMP_DEMO_BOARD_USER:-user}"
BOARD_PORT="${OPENAMP_DEMO_BOARD_PORT:-22}"
PASSWORD=""
RUNTIME_PASSWORD=""
PROMPT_PASSWORD=0
PROBE_STARTUP=1
POST_PROBE_BOARD=1
STRICT_LIVE=1
IMAGE_INDEX=0
OUTPUT_DIR=""
PROBE_ENV=""
KEEP_SERVER=0
EXTRA_LAUNCHER_ARGS=()

WAIT_STEPS="${OPENAMP_DEMO_MLKEM_ONCE_WAIT_STEPS:-80}"
WAIT_SEC="${OPENAMP_DEMO_MLKEM_ONCE_WAIT_SEC:-0.5}"
POLL_STEPS="${OPENAMP_DEMO_MLKEM_ONCE_POLL_STEPS:-240}"
POLL_SEC="${OPENAMP_DEMO_MLKEM_ONCE_POLL_SEC:-1.0}"

usage() {
  cat <<'EOF'
Usage: run_openamp_demo_mlkem_once.sh [options]

One-shot real-machine flow:
  1) launch openamp demo backend
  2) inject board session credentials
  3) enable ML-KEM toggle
  4) run current inference once
  5) capture /api outputs and emit summary

Options:
  --host <host>             Demo server bind host (default: 127.0.0.1)
  --port <port>             Demo server bind port (default: 18089)
  --board-host <ip>         Board SSH host (default: 100.121.87.73)
  --board-user <user>       Board SSH user (default: user)
  --board-port <port>       Board SSH port (default: 22)
  --password <value>        Runtime board password
  --prompt-password         Prompt once for runtime board password
  --probe-env <path>        Forward probe env file to launcher
  --image-index <n>         Inference image index (default: 0)
  --no-probe-startup        Disable launcher startup probe
  --no-post-probe-board     Skip POST /api/probe-board after startup
  --allow-fallback          Do not fail when inference is fallback/error
  --keep-server             Keep demo backend running after capture
  --output-dir <dir>        Output directory for captured JSON/logs
  -- <args...>              Forward additional args to run_openamp_demo.sh
  -h, --help                Show this help
EOF
}

while (($#)); do
  case "$1" in
    --host)
      HOST="${2:?missing value for --host}"
      shift 2
      ;;
    --port)
      PORT="${2:?missing value for --port}"
      shift 2
      ;;
    --board-host)
      BOARD_HOST="${2:?missing value for --board-host}"
      shift 2
      ;;
    --board-user)
      BOARD_USER="${2:?missing value for --board-user}"
      shift 2
      ;;
    --board-port)
      BOARD_PORT="${2:?missing value for --board-port}"
      shift 2
      ;;
    --password)
      PASSWORD="${2:?missing value for --password}"
      shift 2
      ;;
    --prompt-password)
      PROMPT_PASSWORD=1
      shift
      ;;
    --probe-env)
      PROBE_ENV="${2:?missing value for --probe-env}"
      shift 2
      ;;
    --image-index)
      IMAGE_INDEX="${2:?missing value for --image-index}"
      shift 2
      ;;
    --no-probe-startup)
      PROBE_STARTUP=0
      shift
      ;;
    --no-post-probe-board)
      POST_PROBE_BOARD=0
      shift
      ;;
    --allow-fallback)
      STRICT_LIVE=0
      shift
      ;;
    --keep-server)
      KEEP_SERVER=1
      shift
      ;;
    --output-dir)
      OUTPUT_DIR="${2:?missing value for --output-dir}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_LAUNCHER_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_LAUNCHER_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$PASSWORD" && "$PROMPT_PASSWORD" -eq 1 ]]; then
  echo "Refusing to combine --password with --prompt-password." >&2
  exit 2
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$PROJECT_ROOT/session_bootstrap/tmp/openamp_demo_mlkem_once_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$OUTPUT_DIR"

LAUNCHER_LOG="$OUTPUT_DIR/launcher.log"
SUMMARY_JSON="$OUTPUT_DIR/summary.json"
HEALTH_JSON="$OUTPUT_DIR/api_health.json"
BOARD_ACCESS_JSON="$OUTPUT_DIR/api_board_access.json"
PROBE_BOARD_JSON="$OUTPUT_DIR/api_probe_board.json"
CRYPTO_TOGGLE_JSON="$OUTPUT_DIR/api_crypto_toggle.json"
RUN_INFERENCE_JSON="$OUTPUT_DIR/api_run_inference.json"
FINAL_INFERENCE_JSON="$OUTPUT_DIR/api_final_inference.json"
CRYPTO_STATUS_JSON="$OUTPUT_DIR/api_crypto_status.json"
SYSTEM_STATUS_JSON="$OUTPUT_DIR/api_system_status.json"
EVENT_SPINE_JSON="$OUTPUT_DIR/api_event_spine.json"

API_BASE="http://${HOST}:${PORT}"
DEMO_PID=""

prompt_password() {
  local -n out_ref="$1"
  if [[ -t 0 ]]; then
    read -r -s -p "OpenAMP demo runtime password: " out_ref
    printf '\n' >&2
  else
    IFS= read -r out_ref
  fi
}

cleanup() {
  local rc=$?
  if [[ "$KEEP_SERVER" -eq 0 ]] && [[ -n "$DEMO_PID" ]] && kill -0 "$DEMO_PID" 2>/dev/null; then
    kill "$DEMO_PID" 2>/dev/null || true
    wait "$DEMO_PID" 2>/dev/null || true
  fi
  exit "$rc"
}
trap cleanup EXIT

wait_for_health() {
  local attempt=0
  while ((attempt < WAIT_STEPS)); do
    if "$PYTHON_BIN" - <<'PY' "$API_BASE"
from __future__ import annotations
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request(base + "/api/health", headers={"Accept": "application/json"})
try:
    with opener.open(request, timeout=1.5) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if str(payload.get("status") or "").strip().lower() == "ok" else 1)
PY
    then
      return 0
    fi
    if [[ -n "$DEMO_PID" ]] && ! kill -0 "$DEMO_PID" 2>/dev/null; then
      return 1
    fi
    attempt=$((attempt + 1))
    sleep "$WAIT_SEC"
  done
  return 1
}

request_json() {
  local method="$1"
  local path="$2"
  local output_path="$3"
  local payload_json="${4-}"
  if [[ -z "$payload_json" ]]; then
    payload_json="{}"
  fi
  local timeout_sec="${5:-8.0}"

  "$PYTHON_BIN" - <<'PY' "$API_BASE" "$method" "$path" "$output_path" "$payload_json" "$timeout_sec"
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

base, method, path, output_path, payload_json, timeout_sec = sys.argv[1:7]
data = None
if method.upper() != "GET":
    data = payload_json.encode("utf-8")
request = urllib.request.Request(
    base.rstrip("/") + path,
    data=data,
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    method=method.upper(),
)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
  with opener.open(request, timeout=float(timeout_sec)) as response:
    payload = json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
  raw = exc.read().decode("utf-8", errors="replace")
  try:
    detail = json.loads(raw)
  except Exception:
    detail = {"raw": raw}
  raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

launch_demo() {
  local -a launch_args=("--host" "$HOST" "--port" "$PORT")
  if [[ "$PROBE_STARTUP" -eq 1 ]]; then
    launch_args+=("--probe-startup")
  fi
  if [[ -n "$PROBE_ENV" ]]; then
    launch_args+=("--probe-env" "$PROBE_ENV")
  fi
  launch_args+=("${EXTRA_LAUNCHER_ARGS[@]}")

  if [[ "$PROMPT_PASSWORD" -eq 1 ]]; then
    local runtime_password=""
    prompt_password runtime_password
    RUNTIME_PASSWORD="$runtime_password"
    env REMOTE_PASS="$runtime_password" PHYTIUM_PI_PASSWORD="$runtime_password" \
      bash "$LAUNCHER" "${launch_args[@]}" >"$LAUNCHER_LOG" 2>&1 &
  elif [[ -n "$PASSWORD" ]]; then
    RUNTIME_PASSWORD="$PASSWORD"
    env REMOTE_PASS="$PASSWORD" PHYTIUM_PI_PASSWORD="$PASSWORD" \
      bash "$LAUNCHER" "${launch_args[@]}" >"$LAUNCHER_LOG" 2>&1 &
  else
    bash "$LAUNCHER" "${launch_args[@]}" >"$LAUNCHER_LOG" 2>&1 &
  fi
  DEMO_PID="$!"
}

poll_inference_if_running() {
  local input_json="$1"
  local output_json="$2"
  "$PYTHON_BIN" - <<'PY' "$API_BASE" "$input_json" "$output_json" "$POLL_STEPS" "$POLL_SEC"
from __future__ import annotations
import json
import sys
import time
import urllib.request
from pathlib import Path

base, input_json, output_json, poll_steps, poll_sec = sys.argv[1:6]
payload = json.loads(Path(input_json).read_text(encoding="utf-8"))
request_state = str(payload.get("request_state") or "")
job_id = str(payload.get("job_id") or "").strip()

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
if request_state != "running" or not job_id:
    Path(output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0)

final_payload = payload
for _ in range(int(poll_steps)):
    request = urllib.request.Request(
        base.rstrip("/") + f"/api/inference-progress?job_id={job_id}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with opener.open(request, timeout=8.0) as response:
        current = json.loads(response.read().decode("utf-8"))
    final_payload = current
    if str(current.get("request_state") or "") == "completed":
      break
    time.sleep(float(poll_sec))

Path(output_json).write_text(json.dumps(final_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0)
PY
}

launch_demo

if ! wait_for_health; then
  if [[ -n "$DEMO_PID" ]] && ! kill -0 "$DEMO_PID" 2>/dev/null; then
    echo "ERROR: demo launcher exited before ${API_BASE} became healthy" >&2
  else
    echo "ERROR: demo health endpoint did not become ready at ${API_BASE}" >&2
  fi
  echo "launcher_log=${LAUNCHER_LOG}" >&2
  exit 1
fi

request_json "GET" "/api/health" "$HEALTH_JSON"
BOARD_ACCESS_PAYLOAD=$("$PYTHON_BIN" - <<'PY' "$BOARD_HOST" "$BOARD_USER" "$RUNTIME_PASSWORD" "$BOARD_PORT"
from __future__ import annotations
import json
import sys

host, user, password, port = sys.argv[1:5]
print(json.dumps({"host": host, "user": user, "password": password, "port": str(port)}, ensure_ascii=False))
PY
)
request_json "POST" "/api/session/board-access" "$BOARD_ACCESS_JSON" "$BOARD_ACCESS_PAYLOAD"
if [[ "$POST_PROBE_BOARD" -eq 1 ]]; then
  request_json "POST" "/api/probe-board" "$PROBE_BOARD_JSON" "{}" "12.0"
fi
request_json "POST" "/api/crypto-toggle" "$CRYPTO_TOGGLE_JSON" '{"enabled":true}'
RUN_INFERENCE_PAYLOAD=$("$PYTHON_BIN" - <<'PY' "$IMAGE_INDEX"
from __future__ import annotations
import json
import sys

image_index = int(sys.argv[1])
print(json.dumps({"mode": "current", "image_index": image_index}, ensure_ascii=False))
PY
)
request_json "POST" "/api/run-inference" "$RUN_INFERENCE_JSON" "$RUN_INFERENCE_PAYLOAD" "190.0"
poll_inference_if_running "$RUN_INFERENCE_JSON" "$FINAL_INFERENCE_JSON"
request_json "GET" "/api/crypto-status" "$CRYPTO_STATUS_JSON"
request_json "GET" "/api/system-status" "$SYSTEM_STATUS_JSON"
request_json "GET" "/api/event-spine?limit=20" "$EVENT_SPINE_JSON"

"$PYTHON_BIN" - <<'PY' \
  "$HEALTH_JSON" \
  "$BOARD_ACCESS_JSON" \
  "$PROBE_BOARD_JSON" \
  "$CRYPTO_TOGGLE_JSON" \
  "$FINAL_INFERENCE_JSON" \
  "$CRYPTO_STATUS_JSON" \
  "$SYSTEM_STATUS_JSON" \
  "$EVENT_SPINE_JSON" \
  "$SUMMARY_JSON" \
  "$POST_PROBE_BOARD" \
  "$STRICT_LIVE"
from __future__ import annotations
import json
import sys
from pathlib import Path

(
    health_json,
    board_access_json,
    probe_board_json,
    crypto_toggle_json,
    final_inference_json,
    crypto_status_json,
    system_status_json,
    event_spine_json,
    summary_json,
    post_probe_board,
    strict_live,
) = sys.argv[1:12]

health = json.loads(Path(health_json).read_text(encoding="utf-8"))
board_access = json.loads(Path(board_access_json).read_text(encoding="utf-8"))
probe_board = json.loads(Path(probe_board_json).read_text(encoding="utf-8")) if post_probe_board == "1" and Path(probe_board_json).exists() else None
crypto_toggle = json.loads(Path(crypto_toggle_json).read_text(encoding="utf-8"))
inference = json.loads(Path(final_inference_json).read_text(encoding="utf-8"))
crypto_status = json.loads(Path(crypto_status_json).read_text(encoding="utf-8"))
system_status = json.loads(Path(system_status_json).read_text(encoding="utf-8"))
event_spine = json.loads(Path(event_spine_json).read_text(encoding="utf-8"))

status = str(inference.get("status") or "").lower()
category = str(inference.get("status_category") or "")
execution_mode = str(inference.get("execution_mode") or "")
message = str(inference.get("message") or "")

live_success = status == "success" and category == "success" and execution_mode == "live"

summary = {
    "health_status": health.get("status"),
    "board_connection_ready": (board_access.get("board_access") or {}).get("connection_ready"),
    "crypto_enabled": bool(crypto_toggle.get("enabled")),
    "inference_status": inference.get("status"),
    "inference_status_category": category,
    "inference_execution_mode": execution_mode,
    "inference_message": message,
    "crypto_channel_state": crypto_status.get("channel_state"),
    "crypto_kem_backend": crypto_status.get("kem_backend"),
    "crypto_cipher_suite": crypto_status.get("cipher_suite"),
    "crypto_sha_match": crypto_status.get("last_sha256_match"),
    "control_guard_state": crypto_status.get("control_guard_state"),
    "control_last_fault_code": crypto_status.get("control_last_fault_code"),
    "control_job_req_count": crypto_status.get("control_job_req_count"),
    "control_heartbeat_lost_count": crypto_status.get("control_heartbeat_lost_count"),
    "control_safe_stop_triggered_count": crypto_status.get("control_safe_stop_triggered_count"),
    "event_count": (event_spine.get("aggregate") or {}).get("event_count"),
    "live_success": live_success,
    "probe_board_status": probe_board.get("status") if probe_board else None,
    "probe_board_reachable": probe_board.get("reachable") if probe_board else None,
    "mode_effective_label": (system_status.get("execution_mode") or {}).get("label"),
}

Path(summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("[mlkem-once] summary:")
print(f"  health_status: {summary['health_status']}")
print(f"  board_connection_ready: {summary['board_connection_ready']}")
print(f"  crypto_enabled: {summary['crypto_enabled']}")
print(f"  inference: status={summary['inference_status']} category={summary['inference_status_category']} mode={summary['inference_execution_mode']}")
print(f"  message: {summary['inference_message']}")
print(f"  channel: {summary['crypto_channel_state']} | kem={summary['crypto_kem_backend']} | suite={summary['crypto_cipher_suite']} | sha_match={summary['crypto_sha_match']}")
print(f"  control: guard={summary['control_guard_state']} fault={summary['control_last_fault_code']} job_req={summary['control_job_req_count']} hb_lost={summary['control_heartbeat_lost_count']} safe_stop={summary['control_safe_stop_triggered_count']}")
print(f"  event_count: {summary['event_count']}")
if probe_board:
    print(f"  probe_board: status={summary['probe_board_status']} reachable={summary['probe_board_reachable']}")
print(f"[mlkem-once] capture_dir: {Path(summary_json).parent}")

if strict_live == "1" and not live_success:
    raise SystemExit(3)
PY

echo "[mlkem-once] done"