#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
DEFAULT_SSH_SCRIPT="$SCRIPT_DIR/ssh_with_password.sh"

DEFAULT_ENV_FILE="$SESSION_DIR/tmp/inference_real_reconstruction_compare_run_20260311_212301.env"
DEFAULT_VMSTAT_INTERVAL=1
DEFAULT_REPORT_PREFIX="resource_profile"
DEFAULT_SMOKE_REMOTE_COMMAND='echo resource-profile-smoke host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo finished=$(date -Iseconds)'

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_remote_resource_profile.sh [options]

Purpose:
  Capture practical task-5.3 resource evidence from the remote Phytium Pi
  using only tools confirmed on the board right now:
    - free
    - top
    - vmstat

Default mode:
  Source the trusted env file and wrap the trusted real reconstruction command
  already recorded there. Default trusted variant is current.

Explicit remote-command mode:
  Pass --remote-command '<remote shell command>' to run a cheap or custom
  command on the Pi while collecting free/top snapshots and vmstat samples.

Options:
  --env <path>                     Env file with REMOTE_* SSH settings.
                                   Default: $DEFAULT_ENV_FILE
  --trusted-variant <current|baseline>
                                   Default: current
  --smoke                          Run the built-in cheap remote smoke command.
  --remote-command <command>       Explicit remote command to run over SSH.
  --ssh-script <path>              SSH wrapper to use. Default: $DEFAULT_SSH_SCRIPT
  --label <label>                  Short label included in run_id.
  --run-id <id>                    Override the full run_id.
  --vmstat-interval <seconds>      vmstat sample interval. Default: ${DEFAULT_VMSTAT_INTERVAL}
  --allow-overwrite                Allow overwriting an existing run_id.
  -h, --help                       Show this message.

Examples:
  bash ./session_bootstrap/scripts/run_remote_resource_profile.sh

  bash ./session_bootstrap/scripts/run_remote_resource_profile.sh \\
    --trusted-variant baseline

  bash ./session_bootstrap/scripts/run_remote_resource_profile.sh \\
    --smoke

  bash ./session_bootstrap/scripts/run_remote_resource_profile.sh \\
    --remote-command 'echo smoke-from-$(hostname); sleep 3'

Artifacts:
  - session_bootstrap/logs/<run_id>.log
  - session_bootstrap/reports/<run_id>.md
  - session_bootstrap/reports/<run_id>.json
  - session_bootstrap/reports/<run_id>/

Notes:
  - This wrapper intentionally does not use pidstat, mpstat, perf, sar,
    or /usr/bin/time because they are not available on the target board.
  - Target stdout/stderr is captured to:
      session_bootstrap/reports/<run_id>/target.command.log
EOF
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

resolve_path() {
  local maybe_relative="$1"
  if [[ "$maybe_relative" = /* ]]; then
    printf '%s\n' "$maybe_relative"
  else
    printf '%s\n' "$PROJECT_DIR/$maybe_relative"
  fi
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$1" | tee -a "$LOG_FILE"
}

ssh_exec() {
  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST_VAL" \
    --user "$REMOTE_USER_VAL" \
    --pass "$REMOTE_PASS_VAL" \
    --port "$REMOTE_PORT_VAL" \
    -- \
    "$@"
}

capture_remote_file() {
  local out_file="$1"
  shift

  if ! ssh_exec "$@" >"$out_file" 2>&1; then
    log "ERROR: remote capture failed -> $out_file"
    return 1
  fi
  return 0
}

make_snapshot_script() {
  local body="$1"
  cat <<EOF
set -euo pipefail
printf '# host=%s\n' "\$(hostname)"
printf '# captured_at=%s\n' "\$(date -Iseconds)"
$body
EOF
}

ENV_FILE="$DEFAULT_ENV_FILE"
TRUSTED_VARIANT="current"
REMOTE_COMMAND=""
SSH_SCRIPT_INPUT="$DEFAULT_SSH_SCRIPT"
RUN_LABEL=""
RUN_ID_OVERRIDE=""
VMSTAT_INTERVAL="$DEFAULT_VMSTAT_INTERVAL"
ALLOW_OVERWRITE=0
SMOKE_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --trusted-variant)
      TRUSTED_VARIANT="${2:-}"
      shift 2
      ;;
    --smoke)
      SMOKE_MODE=1
      shift
      ;;
    --remote-command)
      REMOTE_COMMAND="${2:-}"
      shift 2
      ;;
    --ssh-script)
      SSH_SCRIPT_INPUT="${2:-}"
      shift 2
      ;;
    --label)
      RUN_LABEL="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --vmstat-interval)
      VMSTAT_INTERVAL="${2:-}"
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

if [[ "$TRUSTED_VARIANT" != "current" && "$TRUSTED_VARIANT" != "baseline" ]]; then
  echo "ERROR: --trusted-variant must be current or baseline." >&2
  exit 1
fi

if [[ "$SMOKE_MODE" == "1" && -n "$REMOTE_COMMAND" ]]; then
  echo "ERROR: --smoke and --remote-command are mutually exclusive." >&2
  exit 1
fi

if ! [[ "$VMSTAT_INTERVAL" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: --vmstat-interval must be a positive integer." >&2
  exit 1
fi

require_command bash
require_command date
require_command mkdir
require_command python3
require_command tee
require_file "$ENV_FILE" "env file"
SSH_SCRIPT="$(resolve_path "$SSH_SCRIPT_INPUT")"
require_file "$SSH_SCRIPT" "ssh wrapper"

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

REMOTE_MODE_VAL="${REMOTE_MODE:-ssh}"
REMOTE_HOST_VAL="${REMOTE_HOST:-}"
REMOTE_USER_VAL="${REMOTE_USER:-}"
REMOTE_PASS_VAL="${REMOTE_PASS:-}"
REMOTE_PORT_VAL="${REMOTE_SSH_PORT:-22}"
LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"

if [[ "$REMOTE_MODE_VAL" != "ssh" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh for this wrapper (got: $REMOTE_MODE_VAL)." >&2
  exit 1
fi

for var_name in REMOTE_HOST_VAL REMOTE_USER_VAL REMOTE_PASS_VAL; do
  if [[ -z "${!var_name}" ]]; then
    echo "ERROR: Missing required SSH value: ${var_name%_VAL}" >&2
    exit 1
  fi
done

COMMAND_MODE="trusted"
TRUSTED_COMMAND=""
TARGET_DESCRIPTION=""
if [[ "$SMOKE_MODE" == "1" ]]; then
  COMMAND_MODE="smoke"
  REMOTE_COMMAND="$DEFAULT_SMOKE_REMOTE_COMMAND"
  RUN_LABEL_EFFECTIVE="${RUN_LABEL:-smoke}"
  TARGET_DESCRIPTION="remote:bash -lc $(shell_quote "$REMOTE_COMMAND")"
elif [[ -n "$REMOTE_COMMAND" ]]; then
  COMMAND_MODE="remote_command"
  RUN_LABEL_EFFECTIVE="${RUN_LABEL:-remote_cmd}"
  TARGET_DESCRIPTION="remote:bash -lc $(shell_quote "$REMOTE_COMMAND")"
else
  if [[ "$TRUSTED_VARIANT" == "current" ]]; then
    TRUSTED_COMMAND="${INFERENCE_CURRENT_CMD:-}"
  else
    TRUSTED_COMMAND="${INFERENCE_BASELINE_CMD:-}"
  fi
  if [[ -z "$TRUSTED_COMMAND" ]]; then
    echo "ERROR: trusted env is missing the command for variant=$TRUSTED_VARIANT." >&2
    exit 1
  fi
  RUN_LABEL_EFFECTIVE="${RUN_LABEL:-trusted_${TRUSTED_VARIANT}}"
  TARGET_DESCRIPTION="$TRUSTED_COMMAND"
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${RUN_ID_OVERRIDE:-${DEFAULT_REPORT_PREFIX}_${RUN_LABEL_EFFECTIVE}_${STAMP}}"

LOG_FILE="$LOG_DIR_RESOLVED/${RUN_ID}.log"
SUMMARY_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.json"
SUMMARY_MD="$REPORT_DIR_RESOLVED/${RUN_ID}.md"
RAW_DIR="$REPORT_DIR_RESOLVED/${RUN_ID}"
TARGET_LOG="$RAW_DIR/target.command.log"
VMSTAT_FILE="$RAW_DIR/vmstat.log"
FREE_PRE_H_FILE="$RAW_DIR/free_pre_h.txt"
FREE_PRE_M_FILE="$RAW_DIR/free_pre_m.txt"
FREE_POST_H_FILE="$RAW_DIR/free_post_h.txt"
FREE_POST_M_FILE="$RAW_DIR/free_post_m.txt"
TOP_PRE_FILE="$RAW_DIR/top_pre.txt"
TOP_POST_FILE="$RAW_DIR/top_post.txt"
COMMAND_FILE="$RAW_DIR/target.command.sh"
METADATA_FILE="$RAW_DIR/metadata.env"
TOOL_PROBE_FILE="$RAW_DIR/tool_probe.txt"

if [[ "$ALLOW_OVERWRITE" != "1" ]]; then
  existing_outputs=()
  [[ -e "$LOG_FILE" ]] && existing_outputs+=("$LOG_FILE")
  [[ -e "$SUMMARY_JSON" ]] && existing_outputs+=("$SUMMARY_JSON")
  [[ -e "$SUMMARY_MD" ]] && existing_outputs+=("$SUMMARY_MD")
  [[ -e "$RAW_DIR" ]] && existing_outputs+=("$RAW_DIR")
  if [[ "${#existing_outputs[@]}" -gt 0 ]]; then
    printf 'ERROR: run artifacts already exist for RUN_ID=%s\n' "$RUN_ID" >&2
    printf 'Refusing to overwrite:\n' >&2
    printf '  %s\n' "${existing_outputs[@]}" >&2
    echo "Hint: pass --run-id with a fresh value or use --allow-overwrite." >&2
    exit 1
  fi
fi

mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED" "$RAW_DIR"
cp "$ENV_FILE" "$RAW_DIR/env_snapshot.env"

cat >"$COMMAND_FILE" <<EOF
# run_id=$RUN_ID
# command_mode=$COMMAND_MODE
# trusted_variant=$TRUSTED_VARIANT
# target_description=$TARGET_DESCRIPTION
EOF
if [[ "$COMMAND_MODE" == "trusted" ]]; then
  printf '%s\n' "$TRUSTED_COMMAND" >>"$COMMAND_FILE"
else
  printf 'bash %s --host %s --user %s --pass %s --port %s -- bash -lc %s\n' \
    "$(shell_quote "$SSH_SCRIPT")" \
    "$(shell_quote "$REMOTE_HOST_VAL")" \
    "$(shell_quote "$REMOTE_USER_VAL")" \
    "$(shell_quote "<REDACTED>")" \
    "$(shell_quote "$REMOTE_PORT_VAL")" \
    "$(shell_quote "$REMOTE_COMMAND")" \
    >>"$COMMAND_FILE"
fi

cat >"$METADATA_FILE" <<EOF
RUN_ID=$RUN_ID
COMMAND_MODE=$COMMAND_MODE
TRUSTED_VARIANT=$TRUSTED_VARIANT
RUN_LABEL=$(shell_quote "$RUN_LABEL_EFFECTIVE")
ENV_FILE=$(shell_quote "$ENV_FILE")
REMOTE_MODE=$(shell_quote "$REMOTE_MODE_VAL")
REMOTE_HOST=$(shell_quote "$REMOTE_HOST_VAL")
REMOTE_USER=$(shell_quote "$REMOTE_USER_VAL")
REMOTE_PORT=$(shell_quote "$REMOTE_PORT_VAL")
SSH_SCRIPT=$(shell_quote "$SSH_SCRIPT")
VMSTAT_INTERVAL=$(shell_quote "$VMSTAT_INTERVAL")
TARGET_DESCRIPTION=$(shell_quote "$TARGET_DESCRIPTION")
EOF

log "resource profile started"
log "run_id=$RUN_ID"
log "command_mode=$COMMAND_MODE"
log "trusted_variant=$TRUSTED_VARIANT"
log "env_file=$ENV_FILE"
log "ssh_script=$SSH_SCRIPT"
log "raw_dir=$RAW_DIR"

TOOL_PROBE_SCRIPT="$(cat <<'SH'
set -euo pipefail
printf 'host=%s\n' "$(hostname)"
printf 'captured_at=%s\n' "$(date -Iseconds)"
required_missing=0
for tool in bash vmstat free top date hostname; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%s=%s\n' "$tool" "$(command -v "$tool")"
  else
    printf '%s=missing\n' "$tool"
    required_missing=1
  fi
done
for tool in pidstat mpstat perf sar; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%s=%s\n' "$tool" "$(command -v "$tool")"
  else
    printf '%s=missing\n' "$tool"
  fi
done
if [[ -x /usr/bin/time ]]; then
  printf '/usr/bin/time=%s\n' '/usr/bin/time'
else
  printf '/usr/bin/time=missing\n'
fi
printf 'required_missing=%s\n' "$required_missing"
exit 0
SH
)"

set +e
ssh_exec bash -lc "$TOOL_PROBE_SCRIPT" >"$TOOL_PROBE_FILE" 2>&1
TOOL_PROBE_RC=$?
set -e
if [[ ! -s "$TOOL_PROBE_FILE" ]]; then
  echo "ERROR: remote tool probe produced no output; see $TOOL_PROBE_FILE" >&2
  exit 1
fi
if grep -q '^required_missing=1$' "$TOOL_PROBE_FILE"; then
  echo "ERROR: remote required tools missing; see $TOOL_PROBE_FILE" >&2
  exit 1
fi
if [[ "$TOOL_PROBE_RC" -ne 0 ]]; then
  log "WARN: remote tool probe returned rc=$TOOL_PROBE_RC but produced a usable probe file; continuing"
fi

FREE_H_SCRIPT="$(make_snapshot_script "free -h")"
FREE_M_SCRIPT="$(make_snapshot_script "free -m")"
TOP_SCRIPT="$(make_snapshot_script "COLUMNS=512 top -b -n 1")"

if ! capture_remote_file "$FREE_PRE_H_FILE" bash -lc "$FREE_H_SCRIPT"; then
  exit 1
fi
if ! capture_remote_file "$FREE_PRE_M_FILE" bash -lc "$FREE_M_SCRIPT"; then
  exit 1
fi
if ! capture_remote_file "$TOP_PRE_FILE" bash -lc "$TOP_SCRIPT"; then
  exit 1
fi

VMSTAT_SSH_PID=""
VMSTAT_STOPPED=0

stop_vmstat_sampler() {
  if [[ "$VMSTAT_STOPPED" == "1" ]]; then
    return 0
  fi
  VMSTAT_STOPPED=1
  if [[ -n "$VMSTAT_SSH_PID" ]] && kill -0 "$VMSTAT_SSH_PID" >/dev/null 2>&1; then
    kill "$VMSTAT_SSH_PID" >/dev/null 2>&1 || true
    wait "$VMSTAT_SSH_PID" >/dev/null 2>&1 || true
  elif [[ -n "$VMSTAT_SSH_PID" ]]; then
    wait "$VMSTAT_SSH_PID" >/dev/null 2>&1 || true
  fi
  printf '# stopped_local=%s\n' "$(date -Iseconds)" >>"$VMSTAT_FILE"
}

cleanup() {
  stop_vmstat_sampler
}
trap cleanup EXIT

{
  printf '# remote_host=%s\n' "$REMOTE_HOST_VAL"
  printf '# vmstat_interval_seconds=%s\n' "$VMSTAT_INTERVAL"
  printf '# started_local=%s\n' "$(date -Iseconds)"
} >"$VMSTAT_FILE"

log "starting vmstat sampler"
set +e
ssh_exec bash -lc "printf '# started_remote=%s\n' \"\$(date -Iseconds)\"; vmstat $VMSTAT_INTERVAL" >>"$VMSTAT_FILE" 2>&1 &
VMSTAT_SSH_PID=$!
set -e
sleep 1

if ! kill -0 "$VMSTAT_SSH_PID" >/dev/null 2>&1; then
  wait "$VMSTAT_SSH_PID" >/dev/null 2>&1 || true
  log "ERROR: vmstat sampler exited immediately"
  exit 1
fi

run_target_command() {
  if [[ "$COMMAND_MODE" == "trusted" ]]; then
    (
      cd "$PROJECT_DIR"
      bash -lc "$TRUSTED_COMMAND"
    )
    return $?
  fi

  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST_VAL" \
    --user "$REMOTE_USER_VAL" \
    --pass "$REMOTE_PASS_VAL" \
    --port "$REMOTE_PORT_VAL" \
    -- \
    bash -lc "$REMOTE_COMMAND"
}

COMMAND_STARTED_AT="$(date -Iseconds)"
SECONDS=0
log "target command started"
set +e
run_target_command >"$TARGET_LOG" 2>&1
TARGET_EXIT_CODE=$?
set -e
WALL_SECONDS="$SECONDS"
COMMAND_ENDED_AT="$(date -Iseconds)"
log "target command finished exit_code=$TARGET_EXIT_CODE wall_seconds=$WALL_SECONDS"

stop_vmstat_sampler

if ! capture_remote_file "$FREE_POST_H_FILE" bash -lc "$FREE_H_SCRIPT"; then
  exit 1
fi
if ! capture_remote_file "$FREE_POST_M_FILE" bash -lc "$FREE_M_SCRIPT"; then
  exit 1
fi
if ! capture_remote_file "$TOP_POST_FILE" bash -lc "$TOP_SCRIPT"; then
  exit 1
fi

python3 - \
  "$RUN_ID" \
  "$COMMAND_MODE" \
  "$TRUSTED_VARIANT" \
  "$RUN_LABEL_EFFECTIVE" \
  "$ENV_FILE" \
  "$REMOTE_HOST_VAL" \
  "$REMOTE_PORT_VAL" \
  "$VMSTAT_INTERVAL" \
  "$COMMAND_STARTED_AT" \
  "$COMMAND_ENDED_AT" \
  "$WALL_SECONDS" \
  "$TARGET_EXIT_CODE" \
  "$TARGET_DESCRIPTION" \
  "$RAW_DIR" \
  "$SUMMARY_JSON" \
  "$SUMMARY_MD" \
  "$LOG_FILE" \
  "$TARGET_LOG" \
  "$VMSTAT_FILE" \
  "$FREE_PRE_M_FILE" \
  "$FREE_POST_M_FILE" \
  "$FREE_PRE_H_FILE" \
  "$FREE_POST_H_FILE" \
  "$TOP_PRE_FILE" \
  "$TOP_POST_FILE" \
  "$TOOL_PROBE_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

(
    run_id,
    command_mode,
    trusted_variant,
    run_label,
    env_file,
    remote_host,
    remote_port,
    vmstat_interval,
    command_started_at,
    command_ended_at,
    wall_seconds,
    target_exit_code,
    target_description,
    raw_dir,
    summary_json_path,
    summary_md_path,
    wrapper_log_path,
    target_log_path,
    vmstat_path,
    free_pre_m_path,
    free_post_m_path,
    free_pre_h_path,
    free_post_h_path,
    top_pre_path,
    top_post_path,
    tool_probe_path,
) = sys.argv[1:]


def file_size(path_str):
    path = Path(path_str)
    if not path.exists():
        return None
    return path.stat().st_size


def parse_key_value_lines(path_str):
    path = Path(path_str)
    result = {"path": str(path)}
    if not path.exists():
        result["error"] = "missing"
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in raw or raw.startswith("#"):
            continue
        key, value = raw.split("=", 1)
        result[key] = value
    return result


def parse_free(path_str):
    path = Path(path_str)
    result = {"path": str(path)}
    if not path.exists():
        result["error"] = "missing"
        return result
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 7:
                result.update(
                    {
                        "unit": "MiB",
                        "total": int(parts[1]),
                        "used": int(parts[2]),
                        "free": int(parts[3]),
                        "shared": int(parts[4]),
                        "buff_cache": int(parts[5]),
                        "available": int(parts[6]),
                    }
                )
            break
    return result


def parse_vmstat(path_str):
    path = Path(path_str)
    result = {"path": str(path), "raw_row_count": 0, "sample_count": 0}
    if not path.exists():
        result["error"] = "missing"
        return result

    base_fields = [
        "r",
        "b",
        "swpd",
        "free",
        "buff",
        "cache",
        "si",
        "so",
        "bi",
        "bo",
        "in",
        "cs",
        "us",
        "sy",
        "id",
        "wa",
        "st",
    ]
    optional_fields = base_fields + ["gu"]
    rows = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            if line.startswith("# stopped_local="):
                break
            continue
        if line.startswith("procs") or line.startswith("r "):
            continue
        parts = line.split()
        if len(parts) == len(optional_fields):
            fields = optional_fields
        elif len(parts) == len(base_fields):
            fields = base_fields
        else:
            continue
        if not all(re.fullmatch(r"-?\d+", item) for item in parts):
            continue
        rows.append({field: int(value) for field, value in zip(fields, parts)})

    result["raw_row_count"] = len(rows)
    if not rows:
        result["error"] = "no numeric vmstat rows parsed"
        return result

    # `vmstat <interval>` emits a first row aggregated since boot; prefer
    # interval samples if they exist so the summary reflects the profiled run.
    effective_rows = rows[1:] if len(rows) > 1 else rows

    def avg(name):
        return round(sum(row[name] for row in effective_rows) / len(effective_rows), 3)

    result.update(
        {
            "sample_count": len(effective_rows),
            "avg_runnable": avg("r"),
            "max_runnable": max(row["r"] for row in effective_rows),
            "avg_blocked": avg("b"),
            "max_blocked": max(row["b"] for row in effective_rows),
            "min_free_kb": min(row["free"] for row in effective_rows),
            "avg_cpu_user_pct": avg("us"),
            "avg_cpu_system_pct": avg("sy"),
            "avg_cpu_idle_pct": avg("id"),
            "avg_cpu_wait_pct": avg("wa"),
            "max_cpu_wait_pct": max(row["wa"] for row in effective_rows),
            "avg_context_switches_per_sec": avg("cs"),
            "avg_interrupts_per_sec": avg("in"),
        }
    )
    if all("gu" in row for row in effective_rows):
        result["avg_cpu_guest_pct"] = avg("gu")
    if len(rows) > 1:
        result["dropped_boot_average_row"] = True
    return result


def parse_last_json(path_str):
    path = Path(path_str)
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def parse_top_summary(path_str):
    path = Path(path_str)
    result = {"path": str(path)}
    if not path.exists():
        result["error"] = "missing"
        return result
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        if line.startswith("top -"):
            result["top_line"] = line
            break
    for line in lines:
        if "load average" in line:
            result["load_average_line"] = line.strip()
            break
    for line in lines:
        if "%Cpu" in line or "Cpu(s)" in line:
            result["cpu_line"] = line.strip()
            break
    return result


tool_probe = parse_key_value_lines(tool_probe_path)
free_pre = parse_free(free_pre_m_path)
free_post = parse_free(free_post_m_path)
top_pre = parse_top_summary(top_pre_path)
top_post = parse_top_summary(top_post_path)
vmstat = parse_vmstat(vmstat_path)
target_last_json = parse_last_json(target_log_path)

memory_available_delta = None
if "available" in free_pre and "available" in free_post:
    memory_available_delta = free_post["available"] - free_pre["available"]

summary = {
    "run_id": run_id,
    "command_mode": command_mode,
    "trusted_variant": trusted_variant,
    "run_label": run_label,
    "env_file": env_file,
    "remote_host": remote_host,
    "remote_port": int(remote_port),
    "vmstat_interval_seconds": int(vmstat_interval),
    "command_started_at": command_started_at,
    "command_ended_at": command_ended_at,
    "wall_time_seconds": int(wall_seconds),
    "target_exit_code": int(target_exit_code),
    "target_description": target_description,
    "raw_dir": raw_dir,
    "wrapper_log_file": wrapper_log_path,
    "wrapper_log_bytes": file_size(wrapper_log_path),
    "target_log_file": target_log_path,
    "target_log_bytes": file_size(target_log_path),
    "tool_probe": tool_probe,
    "vmstat_file": vmstat_path,
    "free_pre_h_file": free_pre_h_path,
    "free_post_h_file": free_post_h_path,
    "top_pre_file": top_pre_path,
    "top_post_file": top_post_path,
    "memory_pre_mib": free_pre,
    "memory_post_mib": free_post,
    "memory_available_delta_mib": memory_available_delta,
    "top_pre_summary": top_pre,
    "top_post_summary": top_post,
    "vmstat_summary": vmstat,
    "target_last_json": target_last_json,
    "limitations": [
        "Resource evidence is based on free, top, vmstat, and shell wall time only.",
        "vmstat is system-wide sampling, not per-process attribution.",
        "Board-level power still requires an external meter.",
    ],
}

Path(summary_json_path).write_text(
    json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

tool_lines = []
for key in ("vmstat", "free", "top", "pidstat", "mpstat", "perf", "sar", "/usr/bin/time"):
    if key in tool_probe:
        tool_lines.append(f"- {key}: {tool_probe[key]}")

memory_lines = []
if "total" in free_pre:
    memory_lines.append(
        f"- pre free -m: total={free_pre['total']} used={free_pre['used']} free={free_pre['free']} available={free_pre['available']} MiB"
    )
if "total" in free_post:
    memory_lines.append(
        f"- post free -m: total={free_post['total']} used={free_post['used']} free={free_post['free']} available={free_post['available']} MiB"
    )
if memory_available_delta is not None:
    memory_lines.append(f"- delta available memory: {memory_available_delta} MiB")
if not memory_lines:
    memory_lines.append("- free -m parsing: unavailable")

vmstat_lines = []
if vmstat.get("sample_count", 0) > 0:
    cpu_line = (
        f"- avg cpu user/system/idle/wait: {vmstat['avg_cpu_user_pct']} / "
        f"{vmstat['avg_cpu_system_pct']} / {vmstat['avg_cpu_idle_pct']} / "
        f"{vmstat['avg_cpu_wait_pct']} %"
    )
    if "avg_cpu_guest_pct" in vmstat:
        cpu_line += f" (guest {vmstat['avg_cpu_guest_pct']} %)"
    vmstat_lines.extend(
        [
            f"- vmstat interval samples: {vmstat['sample_count']}",
            cpu_line,
            f"- avg/max runnable tasks: {vmstat['avg_runnable']} / {vmstat['max_runnable']}",
            f"- avg/max blocked tasks: {vmstat['avg_blocked']} / {vmstat['max_blocked']}",
            f"- min free memory seen by vmstat: {vmstat['min_free_kb']} KB",
        ]
    )
else:
    vmstat_lines.append(f"- vmstat parsing: {vmstat.get('error', 'unavailable')}")

top_lines = []
if "top_line" in top_pre:
    top_lines.append(f"- pre top header: {top_pre['top_line']}")
if "cpu_line" in top_pre:
    top_lines.append(f"- pre top cpu line: {top_pre['cpu_line']}")
if "top_line" in top_post:
    top_lines.append(f"- post top header: {top_post['top_line']}")
if "cpu_line" in top_post:
    top_lines.append(f"- post top cpu line: {top_post['cpu_line']}")

target_json_lines = []
if isinstance(target_last_json, dict):
    for key in (
        "status",
        "run_median_ms",
        "run_mean_ms",
        "run_count",
        "artifact_sha256_match",
        "output_shape",
    ):
        if key in target_last_json:
            target_json_lines.append(f"- {key}: {target_last_json[key]}")

artifact_lines = [
    f"- raw_dir: {raw_dir}",
    f"- wrapper log: {wrapper_log_path}",
    f"- target log: {target_log_path}",
    f"- vmstat log: {vmstat_path}",
    f"- free pre/post: {free_pre_h_path}, {free_post_h_path}",
    f"- top pre/post: {top_pre_path}, {top_post_path}",
    f"- tool probe: {tool_probe_path}",
]

md_lines = [
    "# Remote resource profile",
    "",
    "## Run",
    f"- run_id: {run_id}",
    f"- command_mode: {command_mode}",
    f"- trusted_variant: {trusted_variant}",
    f"- env_file: {env_file}",
    f"- remote_host: {remote_host}:{remote_port}",
    f"- vmstat_interval_seconds: {vmstat_interval}",
    f"- target_exit_code: {target_exit_code}",
    f"- command_started_at: {command_started_at}",
    f"- command_ended_at: {command_ended_at}",
    f"- wall_time_seconds: {wall_seconds}",
    f"- target_description: `{target_description}`",
    "",
    "## Tool Probe",
    *tool_lines,
    "",
    "## Resource Summary",
    *memory_lines,
    *vmstat_lines,
]

if top_lines:
    md_lines.extend(["", "## Top Snapshots", *top_lines])

if target_json_lines:
    md_lines.extend(["", "## Target JSON Summary", *target_json_lines])

md_lines.extend(
    [
        "",
        "## Artifacts",
        *artifact_lines,
        "",
        "## Limitations",
        "- Resource evidence is based on free, top, vmstat, and shell wall time only.",
        "- vmstat is system-wide and does not provide per-process RSS or per-core attribution.",
        "- Power still needs an external board-level meter if the paper requires watt data.",
    ]
)

Path(summary_md_path).write_text("\n".join(md_lines) + "\n", encoding="utf-8")
PY

log "summary_json=$SUMMARY_JSON"
log "summary_md=$SUMMARY_MD"
log "resource profile complete"

exit "$TARGET_EXIT_CODE"
