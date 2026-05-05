#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

TRACKER_PID_FILE="/tmp/tvm_rpc_tracker.pid"
RUNNER_PID_FILE="/tmp/tvm_rpc_runner_remote.pid"

usage() {
  cat <<'EOF'
Usage:
  manage_rpc_services.sh --env <path> <command>

Commands:
  start-tracker         Start RPC tracker on local machine (background)
  start-remote-tracker  Start RPC tracker on remote device via SSH (background)
  start-runner          Start RPC server on remote device via SSH (background)
  start-all             Start tracker + runner according to RPC_TRACKER_MODE
  stop-tracker          Stop local tracker
  stop-remote-tracker   Stop remote tracker
  stop-runner           Stop remote runner
  stop-all              Stop tracker + runner according to RPC_TRACKER_MODE
  status           Check if tracker and runner are alive
  prepare          SCP model files from remote device to local machine

Notes:
  - Tracker runs on the laptop (builder/orchestrator).
  - Runner runs on the remote ARMv8 device (measurement only).
  - The env file must define RPC_TRACKER_*, REMOTE_*, TVM_PYTHON fields.
EOF
}

ENV_FILE=""
COMMAND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env requires a file path." >&2
        exit 1
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -z "$COMMAND" ]]; then
        COMMAND="$1"
      else
        echo "ERROR: Unexpected argument: $1" >&2
        usage >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "$ENV_FILE" || -z "$COMMAND" ]]; then
  echo "ERROR: --env and a command are required." >&2
  usage >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a
source "$ENV_FILE"
set +a

LOCAL_TVM_PYTHON="${LOCAL_TVM_PYTHON:-${TVM_PYTHON:-python3}}"
TRACKER_MODE="${RPC_TRACKER_MODE:-local}"
TRACKER_HOST="${RPC_TRACKER_HOST:-127.0.0.1}"
TRACKER_BIND="${RPC_TRACKER_BIND_HOST:-0.0.0.0}"
TRACKER_PORT="${RPC_TRACKER_PORT:-9190}"
DEVICE_KEY="${DEVICE_KEY:-armv8}"
SERVER_HOST="${RPC_SERVER_HOST:-0.0.0.0}"
SERVER_PORT="${RPC_SERVER_PORT:-9090}"
SERVER_PORT_END="${RPC_SERVER_PORT_END:-9099}"
RUNNER_TRACKER_HOST="${RPC_RUNNER_TRACKER_HOST:-$TRACKER_HOST}"
SERVER_CUSTOM_ADDR="${RPC_SERVER_CUSTOM_ADDR:-}"
REMOTE_HOST_VAL="${REMOTE_HOST:-}"
REMOTE_USER_VAL="${REMOTE_USER:-}"
REMOTE_PASS_VAL="${REMOTE_PASS:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_TVM_PYTHON_VAL="${REMOTE_TVM_PYTHON:-python3}"

check_local_port() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep -q ":${port} " && return 0
  elif command -v netstat >/dev/null 2>&1; then
    netstat -tlnp 2>/dev/null | grep -q ":${port} " && return 0
  fi
  return 1
}

ssh_remote() {
  if [[ -z "$REMOTE_HOST_VAL" || -z "$REMOTE_USER_VAL" || -z "$REMOTE_PASS_VAL" ]]; then
    echo "ERROR: REMOTE_HOST/USER/PASS not configured." >&2
    return 1
  fi
  bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$REMOTE_HOST_VAL" \
    --user "$REMOTE_USER_VAL" \
    --pass "$REMOTE_PASS_VAL" \
    --port "$REMOTE_SSH_PORT" \
    -- "$@"
}

kill_remote_python_by_pattern() {
  local pattern="$1"
  ssh_remote "python3 - <<'PY'
import os, signal, subprocess
pattern = ${pattern@Q}
out = subprocess.check_output(['ps', '-ef'], text=True)
for line in out.splitlines():
    if pattern in line and 'python' in line:
        parts = line.split()
        pid = int(parts[1])
        if pid != os.getpid():
            try:
                os.kill(pid, signal.SIGTERM)
                print(f'KILLED {pid}')
            except ProcessLookupError:
                pass
PY"
}

scp_from_remote() {
  local remote_path="$1"
  local local_path="$2"
  if [[ -z "$REMOTE_HOST_VAL" || -z "$REMOTE_USER_VAL" || -z "$REMOTE_PASS_VAL" ]]; then
    echo "ERROR: REMOTE_HOST/USER/PASS not configured." >&2
    return 1
  fi

  local askpass_file
  askpass_file="$(mktemp /tmp/scp_askpass_XXXXXX.sh)"
  cat >"$askpass_file" <<'ASKEOF'
#!/bin/sh
printf '%s\n' "${SSH_ASKPASS_PASSWORD:-}"
ASKEOF
  chmod 700 "$askpass_file"

  mkdir -p "$(dirname "$local_path")"
  SSH_ASKPASS_PASSWORD="$REMOTE_PASS_VAL" \
  DISPLAY="${DISPLAY:-:0}" \
  SSH_ASKPASS="$askpass_file" \
  SSH_ASKPASS_REQUIRE=force \
  setsid -w \
  scp -P "$REMOTE_SSH_PORT" \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "${REMOTE_USER_VAL}@${REMOTE_HOST_VAL}:${remote_path}" \
    "$local_path"
  local rc=$?
  rm -f "$askpass_file"
  return "$rc"
}

do_start_tracker() {
  if check_local_port "$TRACKER_PORT"; then
    echo "[rpc] tracker already listening on :${TRACKER_PORT}"
    return 0
  fi

  echo "[rpc] starting tracker on ${TRACKER_BIND}:${TRACKER_PORT} ..."
  nohup "$LOCAL_TVM_PYTHON" -m tvm.exec.rpc_tracker \
    --host "$TRACKER_BIND" \
    --port "$TRACKER_PORT" \
    >/tmp/tvm_rpc_tracker.log 2>&1 &
  local pid=$!
  echo "$pid" >"$TRACKER_PID_FILE"

  sleep 2
  if kill -0 "$pid" 2>/dev/null; then
    echo "[rpc] tracker started (pid=$pid, port=$TRACKER_PORT)"
  else
    echo "ERROR: tracker failed to start. Check /tmp/tvm_rpc_tracker.log" >&2
    return 1
  fi
}

do_start_remote_tracker() {
  if [[ -z "$REMOTE_HOST_VAL" ]]; then
    echo "ERROR: REMOTE_HOST not set, cannot start remote tracker." >&2
    return 1
  fi

  echo "[rpc] starting remote tracker on ${REMOTE_HOST_VAL}:${TRACKER_PORT} ..."
  ssh_remote "nohup ${REMOTE_TVM_PYTHON_VAL} -m tvm.exec.rpc_tracker --host 0.0.0.0 --port ${TRACKER_PORT} >/tmp/tvm_rpc_tracker_remote.log 2>&1 & echo started"
}

do_start_runner() {
  if [[ -z "$REMOTE_HOST_VAL" ]]; then
    echo "ERROR: REMOTE_HOST not set, cannot start remote runner." >&2
    return 1
  fi

  local tracker_ip="$RUNNER_TRACKER_HOST"
  if [[ "$TRACKER_MODE" != "remote" && ( "$tracker_ip" == "127.0.0.1" || "$tracker_ip" == "localhost" ) ]]; then
    echo "WARN: runner tracker host is localhost in local-tracker mode; the remote device needs to reach your laptop IP."
    echo "      Set RPC_RUNNER_TRACKER_HOST / RPC_TRACKER_HOST to your laptop's reachable IP."
  fi

  local custom_addr_arg=""
  if [[ -n "$SERVER_CUSTOM_ADDR" ]]; then
    custom_addr_arg="--custom-addr ${SERVER_CUSTOM_ADDR}"
  fi

  echo "[rpc] starting rpc_server on ${REMOTE_HOST_VAL} -> tracker ${tracker_ip}:${TRACKER_PORT} key=${DEVICE_KEY} ..."

  ssh_remote "nohup ${REMOTE_TVM_PYTHON_VAL} -m tvm.exec.rpc_server \
    --tracker ${tracker_ip}:${TRACKER_PORT} \
    ${custom_addr_arg} \
    --key ${DEVICE_KEY} \
    --host ${SERVER_HOST} \
    --port ${SERVER_PORT} \
    --port-end ${SERVER_PORT_END} \
    >/tmp/tvm_rpc_server.log 2>&1 & echo \$!" >"$RUNNER_PID_FILE" 2>/dev/null || true

  local remote_pid
  remote_pid="$(cat "$RUNNER_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
  if [[ -n "$remote_pid" && "$remote_pid" =~ ^[0-9]+$ ]]; then
    echo "[rpc] remote rpc_server started (remote_pid=$remote_pid)"
  else
    echo "WARN: could not capture remote PID. Check /tmp/tvm_rpc_server.log on the device."
  fi
}

do_stop_tracker() {
  if [[ -f "$TRACKER_PID_FILE" ]]; then
    local pid
    pid="$(cat "$TRACKER_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "[rpc] tracker stopped (pid=$pid)"
    else
      echo "[rpc] tracker process not running"
    fi
    rm -f "$TRACKER_PID_FILE"
  else
    echo "[rpc] no tracker PID file found"
  fi
}

do_stop_remote_tracker() {
  if [[ -z "$REMOTE_HOST_VAL" ]]; then
    echo "[rpc] REMOTE_HOST not set, skip remote tracker stop"
    return 0
  fi

  echo "[rpc] stopping remote tracker on ${REMOTE_HOST_VAL} ..."
  kill_remote_python_by_pattern "tvm.exec.rpc_tracker" 2>/dev/null || true
  echo "[rpc] remote tracker stop signal sent"
}

do_stop_runner() {
  if [[ -z "$REMOTE_HOST_VAL" ]]; then
    echo "[rpc] REMOTE_HOST not set, skip remote stop"
    return 0
  fi

  echo "[rpc] stopping rpc_server on ${REMOTE_HOST_VAL} ..."
  kill_remote_python_by_pattern "tvm.exec.rpc_server" 2>/dev/null || true
  rm -f "$RUNNER_PID_FILE"
  echo "[rpc] remote rpc_server stop signal sent"
}

do_status() {
  echo "=== RPC Service Status ==="

  if [[ "$TRACKER_MODE" == "remote" ]]; then
    echo -n "Tracker (remote ${TRACKER_HOST}:${TRACKER_PORT}): "
    if ssh_remote "ss -tlnp 2>/dev/null | grep -q ':${TRACKER_PORT} ' || netstat -tlnp 2>/dev/null | grep -q ':${TRACKER_PORT} '" 2>/dev/null; then
      echo "LISTENING"
    else
      echo "NOT RUNNING or UNREACHABLE"
    fi
  else
    echo -n "Tracker (local :${TRACKER_PORT}): "
    if check_local_port "$TRACKER_PORT"; then
      echo "LISTENING"
    else
      echo "NOT RUNNING"
    fi
  fi

  if [[ -n "$REMOTE_HOST_VAL" ]]; then
    echo -n "Runner (${REMOTE_HOST_VAL}:${SERVER_PORT}-${SERVER_PORT_END}): "
    if ssh_remote "ss -tlnp 2>/dev/null | grep -Eq ':(${SERVER_PORT}|${SERVER_PORT_END}|909[0-9]) ' || netstat -tlnp 2>/dev/null | grep -Eq ':(${SERVER_PORT}|${SERVER_PORT_END}|909[0-9]) '" 2>/dev/null; then
      echo "LISTENING"
    else
      echo "NOT RUNNING or UNREACHABLE"
    fi
  else
    echo "Runner: REMOTE_HOST not configured"
  fi

  echo -n "Tracker query: "
  if "$LOCAL_TVM_PYTHON" -c "
from tvm.rpc import connect_tracker
t = connect_tracker('${TRACKER_HOST}', ${TRACKER_PORT})
summary = t.summary()
print('devices:', summary)
" 2>/dev/null; then
    :
  else
    echo "FAILED (tracker may not be running)"
  fi
}

do_prepare() {
  local onnx_remote="${PREPARE_ONNX_REMOTE:-${REMOTE_ONNX_PATH:-}}"
  local onnx_local="${ONNX_MODEL_PATH:-}"

  if [[ -z "$onnx_remote" ]]; then
    echo "WARN: PREPARE_ONNX_REMOTE / REMOTE_ONNX_PATH not set, skip ONNX transfer."
  elif [[ -z "$onnx_local" ]]; then
    echo "WARN: ONNX_MODEL_PATH not set, don't know where to save locally."
  elif [[ -f "$onnx_local" ]]; then
    echo "[prepare] ONNX already exists locally: $onnx_local"
  else
    echo "[prepare] SCP: ${REMOTE_HOST_VAL}:${onnx_remote} -> ${onnx_local}"
    scp_from_remote "$onnx_remote" "$onnx_local"
    echo "[prepare] ONNX transferred successfully"
  fi

  local remote_db_dir="${REMOTE_TUNING_LOGS_DIR:-}"
  local local_db_dir="${TUNE_EXISTING_DB:-}"
  if [[ -n "$remote_db_dir" && -n "$local_db_dir" && ! -d "$local_db_dir" ]]; then
    mkdir -p "$local_db_dir"
    for fname in database_workload.json database_tuning_record.json; do
      echo "[prepare] SCP: ${REMOTE_HOST_VAL}:${remote_db_dir}/${fname} -> ${local_db_dir}/${fname}"
      scp_from_remote "${remote_db_dir}/${fname}" "${local_db_dir}/${fname}" 2>/dev/null || \
        echo "WARN: could not transfer ${fname}"
    done
  fi
}

case "$COMMAND" in
  start-tracker)
    do_start_tracker
    ;;
  start-runner)
    do_start_runner
    ;;
  start-all)
    if [[ "$TRACKER_MODE" == "remote" ]]; then
      do_start_remote_tracker
    else
      do_start_tracker
    fi
    sleep 1
    do_start_runner
    ;;
  stop-tracker)
    do_stop_tracker
    ;;
  start-remote-tracker)
    do_start_remote_tracker
    ;;
  stop-remote-tracker)
    do_stop_remote_tracker
    ;;
  stop-runner)
    do_stop_runner
    ;;
  stop-all)
    do_stop_runner
    if [[ "$TRACKER_MODE" == "remote" ]]; then
      do_stop_remote_tracker
    else
      do_stop_tracker
    fi
    ;;
  status)
    do_status
    ;;
  prepare)
    do_prepare
    ;;
  *)
    echo "ERROR: Unknown command: $COMMAND" >&2
    usage >&2
    exit 1
    ;;
esac
