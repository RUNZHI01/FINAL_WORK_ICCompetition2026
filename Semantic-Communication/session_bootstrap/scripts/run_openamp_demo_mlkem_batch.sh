#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
LAUNCHER="${OPENAMP_DEMO_MLKEM_BATCH_LAUNCHER:-$SCRIPT_DIR/run_openamp_demo.sh}"
PYTHON_BIN="${OPENAMP_DEMO_MLKEM_BATCH_PYTHON:-python3}"

HOST="127.0.0.1"
PORT="18090"
BOARD_HOST="${OPENAMP_DEMO_BOARD_HOST:-100.121.87.73}"
BOARD_USER="${OPENAMP_DEMO_BOARD_USER:-user}"
BOARD_PORT="${OPENAMP_DEMO_BOARD_PORT:-22}"
PASSWORD=""
RUNTIME_PASSWORD=""
PROMPT_PASSWORD=0
PROBE_STARTUP=1
POST_PROBE_BOARD=1
STRICT_LIVE=1
ALLOW_PREFLIGHT_DEGRADED=0
KEEP_SERVER=0
PROBE_ENV=""
OUTPUT_DIR=""
START_INDEX=0
COUNT=300
MAX_ERRORS=10
EXTRA_LAUNCHER_ARGS=()

WAIT_STEPS="${OPENAMP_DEMO_MLKEM_BATCH_WAIT_STEPS:-100}"
WAIT_SEC="${OPENAMP_DEMO_MLKEM_BATCH_WAIT_SEC:-0.5}"
POLL_STEPS="${OPENAMP_DEMO_MLKEM_BATCH_POLL_STEPS:-240}"
POLL_SEC="${OPENAMP_DEMO_MLKEM_BATCH_POLL_SEC:-1.0}"

usage() {
  cat <<'EOF'
Usage: run_openamp_demo_mlkem_batch.sh [options]

Batch real-machine ML-KEM verification flow:
  1) launch openamp demo backend once
  2) inject board session credentials
  3) enable ML-KEM toggle
  4) run current inference for image_index in [start, start+count)
  5) capture per-item JSONL + batch summary for evidence

Options:
  --host <host>             Demo server bind host (default: 127.0.0.1)
  --port <port>             Demo server bind port (default: 18090)
  --board-host <ip>         Board SSH host (default: 100.121.87.73)
  --board-user <user>       Board SSH user (default: user)
  --board-port <port>       Board SSH port (default: 22)
  --password <value>        Runtime board password
  --prompt-password         Prompt once for runtime board password
  --probe-env <path>        Forward probe env file to launcher
  --start-index <n>         First image index (default: 0)
  --count <n>               Number of images (default: 300)
  --max-errors <n>          Abort after n failed items (default: 10)
  --no-probe-startup        Disable launcher startup probe
  --no-post-probe-board     Skip POST /api/probe-board after startup
  --allow-control-preflight-degraded
                            Continue ML-KEM data path when control STATUS preflight times out
  --allow-fallback          Do not fail when any item is fallback/error
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
    --start-index)
      START_INDEX="${2:?missing value for --start-index}"
      shift 2
      ;;
    --count)
      COUNT="${2:?missing value for --count}"
      shift 2
      ;;
    --max-errors)
      MAX_ERRORS="${2:?missing value for --max-errors}"
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
    --allow-control-preflight-degraded)
      ALLOW_PREFLIGHT_DEGRADED=1
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
  OUTPUT_DIR="$PROJECT_ROOT/session_bootstrap/tmp/openamp_demo_mlkem_batch_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$OUTPUT_DIR"

LAUNCHER_LOG="$OUTPUT_DIR/launcher.log"
HEALTH_JSON="$OUTPUT_DIR/api_health.json"
BOARD_ACCESS_JSON="$OUTPUT_DIR/api_board_access.json"
PROBE_BOARD_JSON="$OUTPUT_DIR/api_probe_board.json"
CRYPTO_TOGGLE_JSON="$OUTPUT_DIR/api_crypto_toggle.json"
CRYPTO_STATUS_JSON="$OUTPUT_DIR/api_crypto_status.json"
SYSTEM_STATUS_JSON="$OUTPUT_DIR/api_system_status.json"
EVENT_SPINE_JSON="$OUTPUT_DIR/api_event_spine.json"
RESULTS_JSONL="$OUTPUT_DIR/batch_results.jsonl"
BATCH_SUMMARY_JSON="$OUTPUT_DIR/batch_summary.json"
FINAL_SUMMARY_JSON="$OUTPUT_DIR/summary.json"

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

BOARD_ACCESS_PAYLOAD=$(
  "$PYTHON_BIN" - <<'PY' "$BOARD_HOST" "$BOARD_USER" "$RUNTIME_PASSWORD" "$BOARD_PORT"
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

"$PYTHON_BIN" - <<'PY' \
  "$API_BASE" \
  "$START_INDEX" \
  "$COUNT" \
  "$POLL_STEPS" \
  "$POLL_SEC" \
  "$MAX_ERRORS" \
  "$ALLOW_PREFLIGHT_DEGRADED" \
  "$RESULTS_JSONL" \
  "$BATCH_SUMMARY_JSON"
from __future__ import annotations
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

(
    api_base,
    start_index,
    count,
    poll_steps,
    poll_sec,
    max_errors,
    allow_preflight_degraded,
    results_jsonl,
    summary_json,
  ) = sys.argv[1:10]

start_index_i = int(start_index)
count_i = int(count)
poll_steps_i = int(poll_steps)
poll_sec_f = float(poll_sec)
max_errors_i = int(max_errors)
allow_preflight_degraded_b = str(allow_preflight_degraded).strip() in {"1", "true", "True"}

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
results_path = Path(results_jsonl)
summary_path = Path(summary_json)
results_path.parent.mkdir(parents=True, exist_ok=True)


def call_json(method: str, path: str, payload: dict | None = None, timeout: float = 12.0) -> dict:
    data = None
    if method.upper() != "GET":
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        api_base.rstrip("/") + path,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method.upper(),
    )
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def poll_if_running(payload: dict) -> dict:
    request_state = str(payload.get("request_state") or "")
    job_id = str(payload.get("job_id") or "").strip()
    if request_state != "running" or not job_id:
        return payload

    final_payload = payload
    for _ in range(poll_steps_i):
        current = call_json("GET", f"/api/inference-progress?job_id={job_id}", timeout=8.0)
        final_payload = current
        if str(current.get("request_state") or "") == "completed":
            break
        time.sleep(poll_sec_f)
    return final_payload


total = count_i
processed_count = 0
success_live = 0
success_any = 0
fallback_count = 0
error_count = 0
sha_match_true = 0
fail_indices: list[int] = []
started_at = time.time()

with results_path.open("w", encoding="utf-8") as handle:
    for offset in range(total):
        index = start_index_i + offset
        record: dict[str, object] = {
            "image_index": index,
            "status": "error",
            "status_category": "request_error",
            "execution_mode": "",
            "sha256_match": None,
            "message": "",
            "elapsed_ms": None,
        }

        t0 = time.monotonic()
        retry_budget = 2
        final_payload: dict[str, object] = {}
        crypto_status: dict[str, object] = {}
        last_error = ""

        for attempt in range(retry_budget + 1):
          try:
            launch_payload = call_json(
              "POST",
              "/api/run-inference",
              payload={
                "mode": "current",
                "image_index": index,
                "allow_preflight_degraded": allow_preflight_degraded_b,
              },
              timeout=190.0,
            )
            final_payload = poll_if_running(launch_payload)
            crypto_status = call_json("GET", "/api/crypto-status", timeout=8.0)

            status = str(final_payload.get("status") or "")
            status_category = str(final_payload.get("status_category") or "")
            if status == "fallback" and status_category == "control_preflight_failed" and attempt < retry_budget:
              last_error = f"preflight_failed_retry_{attempt + 1}"
              try:
                call_json("POST", "/api/recover", payload={}, timeout=20.0)
              except Exception:
                pass
              time.sleep(1.0)
              continue
            break
          except Exception as exc:
            last_error = f"request_failed: {exc}"
            if attempt < retry_budget:
              try:
                call_json("POST", "/api/recover", payload={}, timeout=20.0)
              except Exception:
                pass
              time.sleep(1.0)
              continue
            final_payload = {
              "status": "error",
              "status_category": "request_error",
              "execution_mode": "",
              "message": last_error,
            }
            crypto_status = {}

        status = str(final_payload.get("status") or "")
        status_category = str(final_payload.get("status_category") or "")
        execution_mode = str(final_payload.get("execution_mode") or "")
        sha = crypto_status.get("last_sha256_match")

        record.update(
            {
                "status": status,
                "status_category": status_category,
                "execution_mode": execution_mode,
                "sha256_match": sha,
                "message": str(final_payload.get("message") or last_error),
                "job_id": str(final_payload.get("job_id") or ""),
                "control_guard_state": crypto_status.get("control_guard_state"),
                "control_last_fault_code": crypto_status.get("control_last_fault_code"),
            }
        )

        if status == "success":
            success_any += 1
        if status == "success" and status_category == "success" and execution_mode == "live":
            success_live += 1
        else:
            fail_indices.append(index)
        if status == "fallback":
            fallback_count += 1
        if status not in {"success", "fallback"}:
            error_count += 1
        if sha is True:
            sha_match_true += 1

        record["elapsed_ms"] = round((time.monotonic() - t0) * 1000.0, 3)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        processed_count += 1

        if (offset + 1) % 10 == 0 or (offset + 1) == total:
            print(f"[mlkem-batch] progress {offset + 1}/{total} live_success={success_live} failures={len(fail_indices)}")

        if len(fail_indices) >= max_errors_i > 0:
            print(f"[mlkem-batch] abort: failure count reached max_errors={max_errors_i}")
            break

duration_sec = round(time.time() - started_at, 3)
summary = {
    "start_index": start_index_i,
    "requested_count": total,
  "processed_count": processed_count,
    "duration_sec": duration_sec,
    "success_any_count": success_any,
    "success_live_count": success_live,
    "fallback_count": fallback_count,
    "error_count": error_count,
    "sha_match_true_count": sha_match_true,
    "failure_indices": fail_indices,
    "all_live_success": success_live == total,
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("[mlkem-batch] summary:")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

request_json "GET" "/api/crypto-status" "$CRYPTO_STATUS_JSON"
request_json "GET" "/api/system-status" "$SYSTEM_STATUS_JSON"
request_json "GET" "/api/event-spine?limit=50" "$EVENT_SPINE_JSON"

"$PYTHON_BIN" - <<'PY' \
  "$HEALTH_JSON" \
  "$BOARD_ACCESS_JSON" \
  "$PROBE_BOARD_JSON" \
  "$CRYPTO_TOGGLE_JSON" \
  "$CRYPTO_STATUS_JSON" \
  "$SYSTEM_STATUS_JSON" \
  "$EVENT_SPINE_JSON" \
  "$BATCH_SUMMARY_JSON" \
  "$FINAL_SUMMARY_JSON" \
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
    crypto_status_json,
    system_status_json,
    event_spine_json,
    batch_summary_json,
    final_summary_json,
    post_probe_board,
    strict_live,
) = sys.argv[1:12]

health = json.loads(Path(health_json).read_text(encoding="utf-8"))
board_access = json.loads(Path(board_access_json).read_text(encoding="utf-8"))
probe_board = json.loads(Path(probe_board_json).read_text(encoding="utf-8")) if post_probe_board == "1" and Path(probe_board_json).exists() else None
crypto_toggle = json.loads(Path(crypto_toggle_json).read_text(encoding="utf-8"))
crypto_status = json.loads(Path(crypto_status_json).read_text(encoding="utf-8"))
system_status = json.loads(Path(system_status_json).read_text(encoding="utf-8"))
event_spine = json.loads(Path(event_spine_json).read_text(encoding="utf-8"))
batch = json.loads(Path(batch_summary_json).read_text(encoding="utf-8"))

summary = {
    "health_status": health.get("status"),
    "board_connection_ready": (board_access.get("board_access") or {}).get("connection_ready"),
    "crypto_enabled": bool(crypto_toggle.get("enabled")),
    "batch": batch,
    "crypto_channel_state": crypto_status.get("channel_state"),
    "crypto_kem_backend": crypto_status.get("kem_backend"),
    "crypto_cipher_suite": crypto_status.get("cipher_suite"),
    "control_guard_state": crypto_status.get("control_guard_state"),
    "control_last_fault_code": crypto_status.get("control_last_fault_code"),
    "control_job_req_count": crypto_status.get("control_job_req_count"),
    "control_heartbeat_lost_count": crypto_status.get("control_heartbeat_lost_count"),
    "control_safe_stop_triggered_count": crypto_status.get("control_safe_stop_triggered_count"),
    "event_count": (event_spine.get("aggregate") or {}).get("event_count"),
    "mode_effective_label": (system_status.get("execution_mode") or {}).get("label"),
    "probe_board_status": probe_board.get("status") if probe_board else None,
    "probe_board_reachable": probe_board.get("reachable") if probe_board else None,
}
Path(final_summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("[mlkem-batch] final summary:")
print(f"  health_status: {summary['health_status']}")
print(f"  board_connection_ready: {summary['board_connection_ready']}")
print(f"  crypto_enabled: {summary['crypto_enabled']}")
print(f"  requested_count: {batch.get('requested_count')}")
print(f"  processed_count: {batch.get('processed_count')}")
print(f"  success_live_count: {batch.get('success_live_count')}")
print(f"  fallback_count: {batch.get('fallback_count')}")
print(f"  error_count: {batch.get('error_count')}")
print(f"  all_live_success: {batch.get('all_live_success')}")
print(f"  channel: {summary['crypto_channel_state']} | kem={summary['crypto_kem_backend']} | suite={summary['crypto_cipher_suite']}")
print(f"  control: guard={summary['control_guard_state']} fault={summary['control_last_fault_code']} job_req={summary['control_job_req_count']}")
if probe_board:
    print(f"  probe_board: status={summary['probe_board_status']} reachable={summary['probe_board_reachable']}")
print(f"[mlkem-batch] capture_dir: {Path(final_summary_json).parent}")

if strict_live == "1" and not bool(batch.get("all_live_success")):
    raise SystemExit(4)
PY

echo "[mlkem-batch] done"