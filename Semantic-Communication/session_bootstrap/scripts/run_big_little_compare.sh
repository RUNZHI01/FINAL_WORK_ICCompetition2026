#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_big_little_compare.sh [options]

Options:
  --env <path>             Optional env file to source before running.
  --run-id <id>            Override the local compare run_id.
  --serial-cmd <command>   Override the serial command.
  --pipeline-cmd <command> Override the pipeline command.
  --allow-overwrite        Allow overwriting an existing local run_id.
  -h, --help               Show this message.

Defaults:
  serial command   -> BIG_LITTLE_SERIAL_CMD or
                      when REMOTE_MODE=local and BIG_LITTLE_DRY_RUN=1:
                      BIG_LITTLE_OUTPUT_PREFIX=<prefix>_serial_mock
                      BIG_LITTLE_REPORT_PREFIX=<prefix>_serial_mock
                      bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --execution-mode serial
                      otherwise:
                      bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
  pipeline command -> BIG_LITTLE_PIPELINE_CMD or
                      bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current

Board-state capture:
  When REMOTE_MODE=ssh, this wrapper will by default capture read-only board-state
  snapshots before the serial run, before the pipeline run, and after the pipeline
  run using big_little_topology_probe.py. Set BIG_LITTLE_CAPTURE_BOARD_STATE=0 to
  disable that probe.
EOF
}

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

is_local_mock_compare() {
  local remote_mode_raw="${REMOTE_MODE:-}"
  local remote_mode
  remote_mode="$(printf '%s' "$remote_mode_raw" | tr '[:upper:]' '[:lower:]')"
  [[ "$remote_mode" == "local" && "${BIG_LITTLE_DRY_RUN:-0}" == "1" ]]
}

build_local_mock_serial_cmd() {
  local output_prefix="${BIG_LITTLE_OUTPUT_PREFIX:-big_little_pipeline}_serial_mock"
  local report_prefix="${BIG_LITTLE_REPORT_PREFIX:-big_little_pipeline}_serial_mock"
  printf 'BIG_LITTLE_OUTPUT_PREFIX=%q BIG_LITTLE_REPORT_PREFIX=%q bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --execution-mode serial\n' \
    "$output_prefix" \
    "$report_prefix"
}

parse_last_json_line() {
  python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
for raw in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
    line = raw.strip()
    if not line:
        continue
    try:
        payload = json.loads(line)
    except Exception:
        continue
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)
raise SystemExit(1)
PY
}

json_file_is_valid() {
  python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(1)
try:
    json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

write_board_state_error_json() {
  local output_path="$1"
  local label="$2"
  local reason="$3"
  local returncode="${4:-1}"
  python3 - "$output_path" "$label" "$reason" "$returncode" <<'PY'
import json
import sys
from pathlib import Path

payload = {
    "status": "error",
    "source": "run_big_little_compare.sh",
    "label": sys.argv[2],
    "reason": sys.argv[3],
    "returncode": int(sys.argv[4]),
}
Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

capture_board_state_snapshot() {
  local label="$1"
  local json_path="$2"
  local raw_path="$3"
  local tmp_output
  local rc=0
  local -a probe_args
  tmp_output="$(mktemp)"
  probe_args=(ssh --json-only)
  if [[ -n "$ENV_FILE" ]]; then
    probe_args+=(--env "$ENV_FILE")
  fi
  if [[ -n "${REMOTE_HOST:-}" ]]; then
    probe_args+=(--host "$REMOTE_HOST")
  fi
  if [[ -n "${REMOTE_USER:-}" ]]; then
    probe_args+=(--user "$REMOTE_USER")
  fi
  probe_args+=(--password "${REMOTE_PASS:-}")
  probe_args+=(--port "${REMOTE_SSH_PORT:-22}")
  probe_args+=(--write-raw "$raw_path")

  {
    echo "[$(date -Iseconds)] board_state[$label] start"
    echo "board_state_json=$json_path"
    echo "board_state_raw=$raw_path"
  } >>"$LOG_FILE"

  set +e
  python3 "$SCRIPT_DIR/big_little_topology_probe.py" "${probe_args[@]}" >"$tmp_output" 2>>"$LOG_FILE"
  rc=$?
  set -e

  if json_file_is_valid "$tmp_output"; then
    mv "$tmp_output" "$json_path"
  else
    rm -f "$tmp_output"
    write_board_state_error_json "$json_path" "$label" "topology probe did not emit valid JSON" "$rc"
  fi

  {
    echo "[$(date -Iseconds)] board_state[$label] done rc=$rc"
  } >>"$LOG_FILE"

  return 0
}

render_compare_report() {
  local serial_json_file="$1"
  local pipeline_json_file="$2"
  local report_json="$3"
  local report_md="$4"
  local run_id="$5"
  local env_file="$6"
  local serial_cmd="$7"
  local pipeline_cmd="$8"
  local remote_mode="$9"
  local board_state_capture_enabled="${10}"
  local board_state_capture_reason="${11}"
  local pre_serial_board_json="${12}"
  local pre_pipeline_board_json="${13}"
  local post_pipeline_board_json="${14}"
  local pre_serial_board_raw="${15}"
  local pre_pipeline_board_raw="${16}"
  local post_pipeline_board_raw="${17}"
  python3 - "$serial_json_file" "$pipeline_json_file" "$report_json" "$report_md" "$run_id" "$env_file" "$serial_cmd" "$pipeline_cmd" "$remote_mode" "$board_state_capture_enabled" "$board_state_capture_reason" "$pre_serial_board_json" "$pre_pipeline_board_json" "$post_pipeline_board_json" "$pre_serial_board_raw" "$pre_pipeline_board_raw" "$post_pipeline_board_raw" <<'PY'
import json
import sys
from pathlib import Path

serial_payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pipeline_payload = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
report_json = Path(sys.argv[3])
report_md = Path(sys.argv[4])
run_id = sys.argv[5]
env_file = sys.argv[6] or None
serial_cmd = sys.argv[7]
pipeline_cmd = sys.argv[8]
remote_mode = sys.argv[9]
board_state_capture_enabled = sys.argv[10] == "1"
board_state_capture_reason = sys.argv[11]
pre_serial_board_json = sys.argv[12]
pre_pipeline_board_json = sys.argv[13]
post_pipeline_board_json = sys.argv[14]
pre_serial_board_raw = sys.argv[15]
pre_pipeline_board_raw = sys.argv[16]
post_pipeline_board_raw = sys.argv[17]


def unwrap(payload):
    if isinstance(payload, dict) and "pipeline" in payload:
        return payload["pipeline"]
    return payload


def total_wall_ms(payload):
    core = unwrap(payload)
    if core.get("total_wall_ms") is not None:
        return float(core["total_wall_ms"])
    samples = core.get("run_samples_ms") or []
    load_ms = float(core.get("load_ms") or 0.0)
    vm_init_ms = float(core.get("vm_init_ms") or 0.0)
    return round(load_ms + vm_init_ms + sum(float(value) for value in samples), 3)


def processed_count(payload):
    core = unwrap(payload)
    value = core.get("processed_count")
    if value is None:
        value = core.get("run_count")
    return int(value or 0)


def load_optional_json(raw_path):
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return {"status": "missing", "path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        return {"status": "invalid_json", "path": str(path), "error": str(err)}


def online_cpus(snapshot):
    if not isinstance(snapshot, dict):
        return None
    topology = snapshot.get("topology")
    if not isinstance(topology, dict):
        return None
    cpus = topology.get("online_cpus")
    if not isinstance(cpus, list):
        return None
    try:
        return [int(value) for value in cpus]
    except Exception:
        return None


def snapshot_status(snapshot):
    if not isinstance(snapshot, dict):
        return "missing"
    return str(snapshot.get("status", "missing"))


def format_cpu_list(cpus):
    if not cpus:
        return "NA"
    return ",".join(str(int(cpu)) for cpu in cpus)


serial_core = unwrap(serial_payload)
pipeline_core = unwrap(pipeline_payload)
serial_total_ms = total_wall_ms(serial_payload)
pipeline_total_ms = total_wall_ms(pipeline_payload)
serial_count = processed_count(serial_payload)
pipeline_count = processed_count(pipeline_payload)
serial_ips = None if serial_total_ms <= 0 or serial_count <= 0 else round(serial_count / (serial_total_ms / 1000.0), 3)
pipeline_ips = None if pipeline_total_ms <= 0 or pipeline_count <= 0 else round(pipeline_count / (pipeline_total_ms / 1000.0), 3)
uplift_pct = None
if serial_ips and pipeline_ips:
    uplift_pct = round(((pipeline_ips / serial_ips) - 1.0) * 100.0, 3)

status = "ok"
if serial_core.get("status", "ok") != "ok" or pipeline_core.get("status", "ok") != "ok":
    status = "error"

pre_serial_board_state = load_optional_json(pre_serial_board_json)
pre_pipeline_board_state = load_optional_json(pre_pipeline_board_json)
post_pipeline_board_state = load_optional_json(post_pipeline_board_json)

pre_serial_online = online_cpus(pre_serial_board_state)
pre_pipeline_online = online_cpus(pre_pipeline_board_state)
post_pipeline_online = online_cpus(post_pipeline_board_state)
available_online_sets = [
    tuple(cpus)
    for cpus in (pre_serial_online, pre_pipeline_online, post_pipeline_online)
    if cpus
]
online_cpu_changed = None if len(available_online_sets) < 2 else len(set(available_online_sets)) > 1

board_state_capture_status = "skipped"
if board_state_capture_enabled:
    snapshot_statuses = [
        snapshot_status(pre_serial_board_state),
        snapshot_status(pre_pipeline_board_state),
        snapshot_status(post_pipeline_board_state),
    ]
    board_state_capture_status = "ok" if all(value == "ok" for value in snapshot_statuses) else "warning"

board_state = {
    "capture_enabled": board_state_capture_enabled,
    "capture_status": board_state_capture_status,
    "capture_reason": board_state_capture_reason,
    "remote_mode": remote_mode,
    "summary": {
        "pre_serial_status": snapshot_status(pre_serial_board_state),
        "pre_pipeline_status": snapshot_status(pre_pipeline_board_state),
        "post_pipeline_status": snapshot_status(post_pipeline_board_state),
        "pre_serial_online_cpus": pre_serial_online,
        "pre_pipeline_online_cpus": pre_pipeline_online,
        "post_pipeline_online_cpus": post_pipeline_online,
        "online_cpu_changed_across_compare": online_cpu_changed,
    },
    "snapshots": {
        "pre_serial": {
            "json_path": pre_serial_board_json or None,
            "raw_path": pre_serial_board_raw or None,
            "payload": pre_serial_board_state,
        },
        "pre_pipeline": {
            "json_path": pre_pipeline_board_json or None,
            "raw_path": pre_pipeline_board_raw or None,
            "payload": pre_pipeline_board_state,
        },
        "post_pipeline": {
            "json_path": post_pipeline_board_json or None,
            "raw_path": post_pipeline_board_raw or None,
            "payload": post_pipeline_board_state,
        },
    },
}

payload = {
    "status": status,
    "run_id": run_id,
    "runner": "run_big_little_compare.sh",
    "env_file": env_file,
    "remote_mode": remote_mode,
    "serial_command": serial_cmd,
    "pipeline_command": pipeline_cmd,
    "serial": serial_payload,
    "pipeline": pipeline_payload,
    "comparison": {
        "serial_total_wall_ms": serial_total_ms,
        "pipeline_total_wall_ms": pipeline_total_ms,
        "serial_processed_count": serial_count,
        "pipeline_processed_count": pipeline_count,
        "serial_images_per_sec": serial_ips,
        "pipeline_images_per_sec": pipeline_ips,
        "throughput_uplift_pct": uplift_pct,
    },
    "board_state": board_state,
}

lines = [
    "# big.LITTLE Compare Report",
    "",
    f"- status: {status}",
    f"- run_id: {run_id}",
    f"- env_file: {env_file}",
    f"- serial_total_wall_ms: {serial_total_ms}",
    f"- pipeline_total_wall_ms: {pipeline_total_ms}",
    f"- serial_images_per_sec: {serial_ips}",
    f"- pipeline_images_per_sec: {pipeline_ips}",
    f"- throughput_uplift_pct: {uplift_pct}",
    "",
    "## Commands",
    "",
    f"- serial: `{serial_cmd}`",
    f"- pipeline: `{pipeline_cmd}`",
    "",
    "## Board State",
    "",
    f"- capture_status: {board_state_capture_status}",
    f"- capture_reason: {board_state_capture_reason}",
    f"- pre_serial_status: {board_state['summary']['pre_serial_status']}",
    f"- pre_serial_online_cpus: {format_cpu_list(pre_serial_online)}",
    f"- pre_pipeline_status: {board_state['summary']['pre_pipeline_status']}",
    f"- pre_pipeline_online_cpus: {format_cpu_list(pre_pipeline_online)}",
    f"- post_pipeline_status: {board_state['summary']['post_pipeline_status']}",
    f"- post_pipeline_online_cpus: {format_cpu_list(post_pipeline_online)}",
    f"- online_cpu_changed_across_compare: {online_cpu_changed}",
]

report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
PY
}

ENV_FILE=""
RUN_ID_OVERRIDE=""
SERIAL_CMD_OVERRIDE=""
PIPELINE_CMD_OVERRIDE=""
ALLOW_OVERWRITE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --serial-cmd)
      SERIAL_CMD_OVERRIDE="${2:-}"
      shift 2
      ;;
    --pipeline-cmd)
      PIPELINE_CMD_OVERRIDE="${2:-}"
      shift 2
      ;;
    --allow-overwrite)
      ALLOW_OVERWRITE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: env file not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -n "$SERIAL_CMD_OVERRIDE" ]]; then
  SERIAL_CMD="$SERIAL_CMD_OVERRIDE"
elif [[ -n "${BIG_LITTLE_SERIAL_CMD:-}" ]]; then
  SERIAL_CMD="$BIG_LITTLE_SERIAL_CMD"
elif is_local_mock_compare; then
  SERIAL_CMD="$(build_local_mock_serial_cmd)"
else
  SERIAL_CMD='bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current'
fi

PIPELINE_CMD="${PIPELINE_CMD_OVERRIDE:-${BIG_LITTLE_PIPELINE_CMD:-bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current}}"
REMOTE_MODE_EFFECTIVE="$(printf '%s' "${REMOTE_MODE:-ssh}" | tr '[:upper:]' '[:lower:]')"
BOARD_STATE_CAPTURE="${BIG_LITTLE_CAPTURE_BOARD_STATE:-}"
if [[ -z "$BOARD_STATE_CAPTURE" ]]; then
  if [[ "$REMOTE_MODE_EFFECTIVE" == "ssh" ]]; then
    BOARD_STATE_CAPTURE="1"
  else
    BOARD_STATE_CAPTURE="0"
  fi
fi
BOARD_STATE_CAPTURE_REASON="BIG_LITTLE_CAPTURE_BOARD_STATE=0"
if [[ "$BOARD_STATE_CAPTURE" == "1" && "$REMOTE_MODE_EFFECTIVE" != "ssh" ]]; then
  BOARD_STATE_CAPTURE="0"
  BOARD_STATE_CAPTURE_REASON="REMOTE_MODE is not ssh"
elif [[ "$BOARD_STATE_CAPTURE" == "1" ]]; then
  BOARD_STATE_CAPTURE_REASON="automatic ssh topology snapshots enabled"
elif [[ "$REMOTE_MODE_EFFECTIVE" != "ssh" ]]; then
  BOARD_STATE_CAPTURE_REASON="REMOTE_MODE is not ssh"
fi
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${RUN_ID_OVERRIDE:-big_little_compare_${STAMP}}"
LOG_FILE="$LOG_DIR_RESOLVED/${RUN_ID}.log"
REPORT_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.json"
REPORT_MD="$REPORT_DIR_RESOLVED/${RUN_ID}.md"
SERIAL_RAW="$REPORT_DIR_RESOLVED/${RUN_ID}.serial.raw.log"
PIPELINE_RAW="$REPORT_DIR_RESOLVED/${RUN_ID}.pipeline.raw.log"
PRE_SERIAL_BOARD_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.pre_serial.board_state.json"
PRE_SERIAL_BOARD_RAW="$REPORT_DIR_RESOLVED/${RUN_ID}.pre_serial.board_state.raw.txt"
PRE_PIPELINE_BOARD_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.pre_pipeline.board_state.json"
PRE_PIPELINE_BOARD_RAW="$REPORT_DIR_RESOLVED/${RUN_ID}.pre_pipeline.board_state.raw.txt"
POST_PIPELINE_BOARD_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.post_pipeline.board_state.json"
POST_PIPELINE_BOARD_RAW="$REPORT_DIR_RESOLVED/${RUN_ID}.post_pipeline.board_state.raw.txt"

if [[ "$ALLOW_OVERWRITE" != "1" ]]; then
  existing_outputs=()
  [[ -e "$LOG_FILE" ]] && existing_outputs+=("$LOG_FILE")
  [[ -e "$REPORT_JSON" ]] && existing_outputs+=("$REPORT_JSON")
  [[ -e "$REPORT_MD" ]] && existing_outputs+=("$REPORT_MD")
  [[ -e "$SERIAL_RAW" ]] && existing_outputs+=("$SERIAL_RAW")
  [[ -e "$PIPELINE_RAW" ]] && existing_outputs+=("$PIPELINE_RAW")
  [[ -e "$PRE_SERIAL_BOARD_JSON" ]] && existing_outputs+=("$PRE_SERIAL_BOARD_JSON")
  [[ -e "$PRE_SERIAL_BOARD_RAW" ]] && existing_outputs+=("$PRE_SERIAL_BOARD_RAW")
  [[ -e "$PRE_PIPELINE_BOARD_JSON" ]] && existing_outputs+=("$PRE_PIPELINE_BOARD_JSON")
  [[ -e "$PRE_PIPELINE_BOARD_RAW" ]] && existing_outputs+=("$PRE_PIPELINE_BOARD_RAW")
  [[ -e "$POST_PIPELINE_BOARD_JSON" ]] && existing_outputs+=("$POST_PIPELINE_BOARD_JSON")
  [[ -e "$POST_PIPELINE_BOARD_RAW" ]] && existing_outputs+=("$POST_PIPELINE_BOARD_RAW")
  if [[ "${#existing_outputs[@]}" -gt 0 ]]; then
    printf 'ERROR: run artifacts already exist for RUN_ID=%s\n' "$RUN_ID" >&2
    printf 'Refusing to overwrite:\n' >&2
    printf '  %s\n' "${existing_outputs[@]}" >&2
    echo "Hint: use --run-id with a fresh value or pass --allow-overwrite." >&2
    exit 1
  fi
fi

{
  echo "[$(date -Iseconds)] big.LITTLE compare started"
  echo "run_id=$RUN_ID"
  echo "env_file=${ENV_FILE:-NA}"
  echo "serial_cmd=$SERIAL_CMD"
  echo "pipeline_cmd=$PIPELINE_CMD"
  echo "remote_mode=$REMOTE_MODE_EFFECTIVE"
  echo "board_state_capture=$BOARD_STATE_CAPTURE"
  echo "board_state_capture_reason=$BOARD_STATE_CAPTURE_REASON"
} >"$LOG_FILE"

SERIAL_JSON_FILE="$(mktemp)"
PIPELINE_JSON_FILE="$(mktemp)"
SERIAL_TMP="$(mktemp)"
PIPELINE_TMP="$(mktemp)"

if [[ "$BOARD_STATE_CAPTURE" == "1" ]]; then
  capture_board_state_snapshot "pre_serial" "$PRE_SERIAL_BOARD_JSON" "$PRE_SERIAL_BOARD_RAW"
fi

set +e
bash -lc "cd \"$PROJECT_DIR\" && $SERIAL_CMD" >"$SERIAL_TMP" 2>&1
SERIAL_RC=$?
set -e
cat "$SERIAL_TMP" >>"$SERIAL_RAW"
cat "$SERIAL_TMP" >>"$LOG_FILE"
if ! parse_last_json_line "$SERIAL_TMP" >"$SERIAL_JSON_FILE"; then
  echo "ERROR: failed to parse serial JSON output. See $SERIAL_RAW" >&2
  exit "${SERIAL_RC:-1}"
fi
if [[ "$SERIAL_RC" -ne 0 ]]; then
  echo "ERROR: serial command failed. See $SERIAL_RAW" >&2
  exit "$SERIAL_RC"
fi

if [[ "$BOARD_STATE_CAPTURE" == "1" ]]; then
  capture_board_state_snapshot "pre_pipeline" "$PRE_PIPELINE_BOARD_JSON" "$PRE_PIPELINE_BOARD_RAW"
fi

set +e
bash -lc "cd \"$PROJECT_DIR\" && $PIPELINE_CMD" >"$PIPELINE_TMP" 2>&1
PIPELINE_RC=$?
set -e
cat "$PIPELINE_TMP" >>"$PIPELINE_RAW"
cat "$PIPELINE_TMP" >>"$LOG_FILE"

if [[ "$BOARD_STATE_CAPTURE" == "1" ]]; then
  capture_board_state_snapshot "post_pipeline" "$POST_PIPELINE_BOARD_JSON" "$POST_PIPELINE_BOARD_RAW"
fi

if ! parse_last_json_line "$PIPELINE_TMP" >"$PIPELINE_JSON_FILE"; then
  echo "ERROR: failed to parse pipeline JSON output. See $PIPELINE_RAW" >&2
  exit "${PIPELINE_RC:-1}"
fi
if [[ "$PIPELINE_RC" -ne 0 ]]; then
  echo "ERROR: pipeline command failed. See $PIPELINE_RAW" >&2
  exit "$PIPELINE_RC"
fi

COMPARE_STDOUT="$(render_compare_report "$SERIAL_JSON_FILE" "$PIPELINE_JSON_FILE" "$REPORT_JSON" "$REPORT_MD" "$RUN_ID" "${ENV_FILE:-}" "$SERIAL_CMD" "$PIPELINE_CMD" "$REMOTE_MODE_EFFECTIVE" "$BOARD_STATE_CAPTURE" "$BOARD_STATE_CAPTURE_REASON" "$PRE_SERIAL_BOARD_JSON" "$PRE_PIPELINE_BOARD_JSON" "$POST_PIPELINE_BOARD_JSON" "$PRE_SERIAL_BOARD_RAW" "$PRE_PIPELINE_BOARD_RAW" "$POST_PIPELINE_BOARD_RAW")"
printf '%s\n' "$COMPARE_STDOUT"
