#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
PYTHON_RUNNER_SOURCE="$SCRIPT_DIR/big_little_pipeline.py"

usage() {
  cat <<'EOF'
Usage:
  run_big_little_pipeline.sh --variant <baseline|current> [options]

Options:
  --env <path>                    Optional env file to source before running.
  --variant <baseline|current>    Artifact/runtime variant to execute.
  --execution-mode <pipeline|serial>
                                  `pipeline` runs the heterogeneous workers.
                                  `serial` is a local/mock dry-run baseline.
  --max-inputs <n>                Optional cap on the number of latent inputs.
  --seed <int>                    Optional AWGN seed.
  --run-id <id>                   Override the local report/log run_id.
  --dry-run                       Force mock inference mode.
  --big-cores <csv>               Override BIG_LITTLE_BIG_CORES.
  --little-cores <csv>            Override BIG_LITTLE_LITTLE_CORES.
  --allow-overwrite               Allow overwriting an existing local run_id.
  -h, --help                      Show this message.

Env:
  Reuses the trusted real-reconstruction env conventions:
    REMOTE_MODE=ssh|local
    REMOTE_TVM_PYTHON
    REMOTE_INPUT_DIR
    REMOTE_OUTPUT_BASE
    REMOTE_SNR_BASELINE / REMOTE_SNR_CURRENT
    REMOTE_BATCH_BASELINE / REMOTE_BATCH_CURRENT
    REMOTE_BASELINE_ARTIFACT / REMOTE_CURRENT_ARTIFACT
    or INFERENCE_BASELINE_ARCHIVE / INFERENCE_CURRENT_ARCHIVE

  big.LITTLE-specific knobs:
    REMOTE_LOCAL_PYTHON_CANDIDATES=<cmd1>:<cmd2>:...
    BIG_LITTLE_BIG_CORES=0,1
    BIG_LITTLE_LITTLE_CORES=2,3
    BIG_LITTLE_BACKEND=processes|threads
    BIG_LITTLE_ALLOW_MISSING_AFFINITY=0|1
    BIG_LITTLE_INPUT_QUEUE_SIZE=4
    BIG_LITTLE_OUTPUT_QUEUE_SIZE=4
    BIG_LITTLE_DRY_RUN=0|1
    BIG_LITTLE_EXECUTION_MODE=pipeline|serial
    BIG_LITTLE_MOCK_INFER_MS=15
    BIG_LITTLE_MAX_INPUTS=300
    BIG_LITTLE_SEED=123
    BIG_LITTLE_OUTPUT_PREFIX=big_little_pipeline
    BIG_LITTLE_REPORT_PREFIX=big_little_pipeline
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

require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "ERROR: Missing required variable: $var_name" >&2
    exit 1
  fi
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

resolve_artifact_path() {
  local explicit_path="$1"
  local archive_dir="$2"
  if [[ -n "$explicit_path" ]]; then
    printf '%s\n' "$explicit_path"
    return 0
  fi
  if [[ -n "$archive_dir" ]]; then
    printf '%s/tvm_tune_logs/optimized_model.so\n' "$archive_dir"
    return 0
  fi
  return 1
}

append_candidate() {
  local candidate="$1"
  [[ -z "$candidate" ]] && return 0
  LOCAL_PYTHON_CANDIDATES_EFFECTIVE+=("$candidate")
}

python_command_supports_modules() {
  local candidate="$1"
  shift
  [[ -z "$candidate" ]] && return 1
  local probe_script
  local cmd
  local module
  local rc=0
  probe_script="$(mktemp)"
  cat >"$probe_script" <<'PY'
import importlib
import sys

for name in sys.argv[1:]:
    importlib.import_module(name)
PY
  cmd="$candidate $(printf '%q' "$probe_script")"
  for module in "$@"; do
    cmd+=" $(printf '%q' "$module")"
  done
  set +e
  bash -lc "$cmd" >/dev/null 2>&1
  rc=$?
  set -e
  rm -f "$probe_script"
  return "$rc"
}

resolve_local_python_command() {
  local modules=("$@")
  local candidate
  local extra_candidate
  LOCAL_PYTHON_CANDIDATES_EFFECTIVE=()
  append_candidate "${REMOTE_TVM_PYTHON:-}"
  if [[ -n "${REMOTE_LOCAL_PYTHON_CANDIDATES:-}" ]]; then
    IFS=':' read -r -a LOCAL_PYTHON_EXTRA_CANDIDATES <<<"${REMOTE_LOCAL_PYTHON_CANDIDATES}"
    for extra_candidate in "${LOCAL_PYTHON_EXTRA_CANDIDATES[@]}"; do
      append_candidate "$extra_candidate"
    done
  fi
  append_candidate "$HOME/.venvs/tvm-ms/bin/python"
  append_candidate "$PROJECT_DIR/.venv/bin/python"
  append_candidate "$PROJECT_DIR/venv/bin/python"
  append_candidate "python3"
  append_candidate "/usr/bin/python3"

  for candidate in "${LOCAL_PYTHON_CANDIDATES_EFFECTIVE[@]}"; do
    if python_command_supports_modules "$candidate" "${modules[@]}"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf 'ERROR: failed to resolve a local Python command with required modules: %s\n' "${modules[*]}" >&2
  printf 'Candidates tried:\n' >&2
  printf '  %s\n' "${LOCAL_PYTHON_CANDIDATES_EFFECTIVE[@]}" >&2
  return 1
}

render_wrapper_report() {
  local pipeline_json_file="$1"
  local report_json="$2"
  local report_md="$3"
  local run_id="$4"
  local env_file="$5"
  local variant="$6"
  local remote_mode="$7"
  local log_file="$8"
  python3 - "$pipeline_json_file" "$report_json" "$report_md" "$run_id" "$env_file" "$variant" "$remote_mode" "$log_file" <<'PY'
import json
import sys
from pathlib import Path

pipeline = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
report_json = Path(sys.argv[2])
report_md = Path(sys.argv[3])
run_id = sys.argv[4]
env_file = sys.argv[5] or None
variant = sys.argv[6]
remote_mode = sys.argv[7]
log_file = sys.argv[8]

payload = {
    "status": "ok" if pipeline.get("status") == "ok" else "error",
    "run_id": run_id,
    "runner": "run_big_little_pipeline.sh",
    "env_file": env_file,
    "variant": variant,
    "remote_mode": remote_mode,
    "log_file": log_file,
    "pipeline": pipeline,
}

lines = [
    "# big.LITTLE Wrapper Report",
    "",
    f"- status: {payload['status']}",
    f"- run_id: {run_id}",
    f"- variant: {variant}",
    f"- execution_mode: {pipeline.get('execution_mode')}",
    f"- remote_mode: {remote_mode}",
    f"- env_file: {env_file}",
    f"- processed_count: {pipeline.get('processed_count')}",
    f"- total_wall_ms: {pipeline.get('total_wall_ms')}",
    f"- images_per_sec: {pipeline.get('images_per_sec')}",
    f"- dry_run: {pipeline.get('dry_run')}",
    f"- big_cores: {pipeline.get('big_cores')}",
    f"- little_cores: {pipeline.get('little_cores')}",
    f"- output_dir: {pipeline.get('output_dir')}",
    "",
    "## Affinity",
    "",
    f"- preloader: {pipeline.get('affinity', {}).get('preloader')}",
    f"- inferencer: {pipeline.get('affinity', {}).get('inferencer')}",
    f"- postprocessor: {pipeline.get('affinity', {}).get('postprocessor')}",
]
if pipeline.get("errors"):
    lines.extend(["", "## Errors", ""])
    for error in pipeline["errors"]:
        lines.append(f"- {error}")

report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False))
PY
}

emit_shell_assignment() {
  local name="$1"
  local value="${!name-}"
  printf '%s=%q\n' "$name" "$value"
}

ENV_FILE=""
VARIANT=""
EXECUTION_MODE=""
MAX_INPUTS=""
SEED=""
RUN_ID_OVERRIDE=""
DRY_RUN_OVERRIDE=""
BIG_CORES_OVERRIDE=""
LITTLE_CORES_OVERRIDE=""
ALLOW_OVERWRITE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --variant)
      VARIANT="${2:-}"
      shift 2
      ;;
    --execution-mode)
      EXECUTION_MODE="${2:-}"
      shift 2
      ;;
    --max-inputs)
      MAX_INPUTS="${2:-}"
      shift 2
      ;;
    --seed)
      SEED="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN_OVERRIDE="1"
      shift
      ;;
    --big-cores)
      BIG_CORES_OVERRIDE="${2:-}"
      shift 2
      ;;
    --little-cores)
      LITTLE_CORES_OVERRIDE="${2:-}"
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

if [[ "$VARIANT" != "baseline" && "$VARIANT" != "current" ]]; then
  echo "ERROR: --variant must be baseline or current." >&2
  exit 1
fi

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

if [[ ! -f "$PYTHON_RUNNER_SOURCE" ]]; then
  echo "ERROR: runner source not found: $PYTHON_RUNNER_SOURCE" >&2
  exit 1
fi

REMOTE_MODE_RAW="${REMOTE_MODE:-ssh}"
REMOTE_MODE="$(printf '%s' "$REMOTE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$REMOTE_MODE" != "ssh" && "$REMOTE_MODE" != "local" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh or local (got: $REMOTE_MODE_RAW)" >&2
  exit 1
fi

require_var REMOTE_INPUT_DIR
require_var REMOTE_OUTPUT_BASE

if [[ "$REMOTE_MODE" == "ssh" ]]; then
  require_var REMOTE_TVM_PYTHON
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    require_var "$req"
  done
fi

if [[ "$VARIANT" == "baseline" ]]; then
  require_var REMOTE_SNR_BASELINE
  require_var REMOTE_BATCH_BASELINE
  REAL_SNR="$REMOTE_SNR_BASELINE"
  REAL_BATCH="$REMOTE_BATCH_BASELINE"
  REAL_ARTIFACT_PATH="$(resolve_artifact_path "${REMOTE_BASELINE_ARTIFACT:-}" "${INFERENCE_BASELINE_ARCHIVE:-${REMOTE_TVM_PRIMARY_DIR:-}}")" || {
    echo "ERROR: Missing baseline artifact path. Set REMOTE_BASELINE_ARTIFACT or INFERENCE_BASELINE_ARCHIVE/REMOTE_TVM_PRIMARY_DIR." >&2
    exit 1
  }
  REAL_EXPECTED_SHA256="${INFERENCE_BASELINE_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
else
  require_var REMOTE_SNR_CURRENT
  require_var REMOTE_BATCH_CURRENT
  REAL_SNR="$REMOTE_SNR_CURRENT"
  REAL_BATCH="$REMOTE_BATCH_CURRENT"
  REAL_ARTIFACT_PATH="$(resolve_artifact_path "${REMOTE_CURRENT_ARTIFACT:-}" "${INFERENCE_CURRENT_ARCHIVE:-${REMOTE_TVM_JSCC_BASE_DIR:-}}")" || {
    echo "ERROR: Missing current artifact path. Set REMOTE_CURRENT_ARTIFACT or INFERENCE_CURRENT_ARCHIVE/REMOTE_TVM_JSCC_BASE_DIR." >&2
    exit 1
  }
  REAL_EXPECTED_SHA256="${INFERENCE_CURRENT_EXPECTED_SHA256:-${INFERENCE_EXPECTED_SHA256:-}}"
fi

if ! [[ "$REAL_BATCH" =~ ^[0-9]+$ ]]; then
  echo "ERROR: batch_size must be a non-negative integer (got: $REAL_BATCH)." >&2
  exit 1
fi
if [[ -n "$MAX_INPUTS" ]] && ! [[ "$MAX_INPUTS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-inputs must be a non-negative integer (got: $MAX_INPUTS)." >&2
  exit 1
fi
if [[ -n "$SEED" ]] && ! [[ "$SEED" =~ ^-?[0-9]+$ ]]; then
  echo "ERROR: --seed must be an integer (got: $SEED)." >&2
  exit 1
fi

BIG_CORES="${BIG_CORES_OVERRIDE:-${BIG_LITTLE_BIG_CORES:-}}"
LITTLE_CORES="${LITTLE_CORES_OVERRIDE:-${BIG_LITTLE_LITTLE_CORES:-}}"
ALLOW_MISSING_AFFINITY="${BIG_LITTLE_ALLOW_MISSING_AFFINITY:-0}"
INPUT_QUEUE_SIZE="${BIG_LITTLE_INPUT_QUEUE_SIZE:-4}"
OUTPUT_QUEUE_SIZE="${BIG_LITTLE_OUTPUT_QUEUE_SIZE:-4}"
DRY_RUN="${DRY_RUN_OVERRIDE:-${BIG_LITTLE_DRY_RUN:-0}}"
EXECUTION_MODE_EFFECTIVE="${EXECUTION_MODE:-${BIG_LITTLE_EXECUTION_MODE:-pipeline}}"
MOCK_INFER_MS="${BIG_LITTLE_MOCK_INFER_MS:-15}"
MAX_INPUTS_EFFECTIVE="${MAX_INPUTS:-${BIG_LITTLE_MAX_INPUTS:-}}"
SEED_EFFECTIVE="${SEED:-${BIG_LITTLE_SEED:-}}"
OUTPUT_PREFIX="${BIG_LITTLE_OUTPUT_PREFIX:-big_little_pipeline}"
REPORT_PREFIX="${BIG_LITTLE_REPORT_PREFIX:-big_little_pipeline}"
BACKEND="${BIG_LITTLE_BACKEND:-processes}"
: "${TVM_RUNTIME_PRELOAD_PY:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_SO:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_FUNC:=}"
: "${TVM_TRANSPOSE_ADD6_PROXY_REG:=}"

if [[ "$EXECUTION_MODE_EFFECTIVE" != "pipeline" && "$EXECUTION_MODE_EFFECTIVE" != "serial" ]]; then
  echo "ERROR: execution mode must be pipeline or serial (got: $EXECUTION_MODE_EFFECTIVE)." >&2
  exit 1
fi

if [[ "$REMOTE_MODE" == "local" ]]; then
  if [[ "$DRY_RUN" == "1" ]]; then
    REMOTE_TVM_PYTHON="$(resolve_local_python_command numpy)"
  else
    REMOTE_TVM_PYTHON="$(resolve_local_python_command numpy tvm)"
  fi
fi

LOG_DIR_RESOLVED="$(resolve_path "${LOG_DIR:-./session_bootstrap/logs}")"
REPORT_DIR_RESOLVED="$(resolve_path "${REPORT_DIR:-./session_bootstrap/reports}")"
mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${RUN_ID_OVERRIDE:-${REPORT_PREFIX}_${VARIANT}_${STAMP}}"
LOG_FILE="$LOG_DIR_RESOLVED/${RUN_ID}.log"
REPORT_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.json"
REPORT_MD="$REPORT_DIR_RESOLVED/${RUN_ID}.md"
RAW_OUTPUT_FILE="$REPORT_DIR_RESOLVED/${RUN_ID}.raw.log"

if [[ "$ALLOW_OVERWRITE" != "1" ]]; then
  existing_outputs=()
  [[ -e "$LOG_FILE" ]] && existing_outputs+=("$LOG_FILE")
  [[ -e "$REPORT_JSON" ]] && existing_outputs+=("$REPORT_JSON")
  [[ -e "$REPORT_MD" ]] && existing_outputs+=("$REPORT_MD")
  [[ -e "$RAW_OUTPUT_FILE" ]] && existing_outputs+=("$RAW_OUTPUT_FILE")
  if [[ "${#existing_outputs[@]}" -gt 0 ]]; then
    printf 'ERROR: run artifacts already exist for RUN_ID=%s\n' "$RUN_ID" >&2
    printf 'Refusing to overwrite:\n' >&2
    printf '  %s\n' "${existing_outputs[@]}" >&2
    echo "Hint: use --run-id with a fresh value or pass --allow-overwrite." >&2
    exit 1
  fi
fi

REAL_OUTPUT_DIR="$REMOTE_OUTPUT_BASE/${OUTPUT_PREFIX}_${VARIANT}"
REAL_EXTRA_PYTHONPATH="${REMOTE_REAL_EXTRA_PYTHONPATH:-${REMOTE_TORCH_PYTHONPATH:-}}"

{
  echo "[$(date -Iseconds)] big.LITTLE wrapper started"
  echo "run_id=$RUN_ID"
  echo "variant=$VARIANT"
  echo "env_file=${ENV_FILE:-NA}"
  echo "remote_mode=$REMOTE_MODE"
  echo "artifact_path=$REAL_ARTIFACT_PATH"
  echo "input_dir=$REMOTE_INPUT_DIR"
  echo "output_dir=$REAL_OUTPUT_DIR"
  echo "snr=$REAL_SNR"
  echo "batch_size=$REAL_BATCH"
  echo "execution_mode=$EXECUTION_MODE_EFFECTIVE"
  echo "resolved_remote_tvm_python=$REMOTE_TVM_PYTHON"
  echo "big_cores=$BIG_CORES"
  echo "little_cores=$LITTLE_CORES"
  echo "backend=$BACKEND"
  echo "dry_run=$DRY_RUN"
  echo "max_inputs=${MAX_INPUTS_EFFECTIVE:-NA}"
  echo "seed=${SEED_EFFECTIVE:-NA}"
} >"$LOG_FILE"

run_pipeline_remote() {
  local runner_script
  local rc=0
  runner_script="$(mktemp)"
  {
    cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
    for var_name in \
      REMOTE_TVM_PYTHON REMOTE_INPUT_DIR REAL_OUTPUT_DIR REAL_SNR REAL_BATCH VARIANT \
      REAL_ARTIFACT_PATH REAL_EXPECTED_SHA256 REAL_EXTRA_PYTHONPATH BIG_CORES LITTLE_CORES \
      BACKEND ALLOW_MISSING_AFFINITY INPUT_QUEUE_SIZE OUTPUT_QUEUE_SIZE DRY_RUN MOCK_INFER_MS \
      MAX_INPUTS_EFFECTIVE SEED_EFFECTIVE EXECUTION_MODE_EFFECTIVE \
      TVM_RUNTIME_PRELOAD_PY TVM_TRANSPOSE_ADD6_PROXY_SO TVM_TRANSPOSE_ADD6_PROXY_FUNC \
      TVM_TRANSPOSE_ADD6_PROXY_REG; do
      emit_shell_assignment "$var_name"
    done
    cat <<'SH'

remote_python="$REMOTE_TVM_PYTHON"
input_dir="$REMOTE_INPUT_DIR"
output_dir="$REAL_OUTPUT_DIR"
snr="$REAL_SNR"
batch_size="$REAL_BATCH"
variant="$VARIANT"
artifact_path="$REAL_ARTIFACT_PATH"
expected_sha256="$REAL_EXPECTED_SHA256"
extra_pythonpath="$REAL_EXTRA_PYTHONPATH"
big_cores="$BIG_CORES"
little_cores="$LITTLE_CORES"
backend="$BACKEND"
allow_missing_affinity="$ALLOW_MISSING_AFFINITY"
input_queue_size="$INPUT_QUEUE_SIZE"
output_queue_size="$OUTPUT_QUEUE_SIZE"
dry_run="$DRY_RUN"
mock_infer_ms="$MOCK_INFER_MS"
max_inputs="$MAX_INPUTS_EFFECTIVE"
seed="$SEED_EFFECTIVE"
execution_mode="$EXECUTION_MODE_EFFECTIVE"
preload_py="${TVM_RUNTIME_PRELOAD_PY:-}"
proxy_so="${TVM_TRANSPOSE_ADD6_PROXY_SO:-}"
proxy_func="${TVM_TRANSPOSE_ADD6_PROXY_FUNC:-}"
proxy_reg="${TVM_TRANSPOSE_ADD6_PROXY_REG:-}"

mkdir -p "$output_dir"
rm -rf "$output_dir/reconstructions"

if [[ -n "$extra_pythonpath" ]]; then
  export PYTHONPATH="$extra_pythonpath${PYTHONPATH:+:$PYTHONPATH}"
  export REMOTE_REAL_EXTRA_PYTHONPATH="$extra_pythonpath"
  export DEMO_EXTRA_PYTHONPATH="$extra_pythonpath"
  export REMOTE_TORCH_PYTHONPATH="${REMOTE_TORCH_PYTHONPATH:-$extra_pythonpath}"
fi
export PYTHONNOUSERSITE=1
if [[ -n "$preload_py" ]]; then
  export TVM_RUNTIME_PRELOAD_PY="$preload_py"
fi
if [[ -n "$proxy_so" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_SO="$proxy_so"
fi
if [[ -n "$proxy_func" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_FUNC="$proxy_func"
fi
if [[ -n "$proxy_reg" ]]; then
  export TVM_TRANSPOSE_ADD6_PROXY_REG="$proxy_reg"
fi

run_remote_python() {
  local stdin_payload cmd arg rc=0
  stdin_payload="$(mktemp)"
  cat >"$stdin_payload"
  cmd="$remote_python"
  for arg in "$@"; do
    cmd+=" $(printf '%q' "$arg")"
  done
  set +e
  bash -c "$cmd" <"$stdin_payload"
  rc=$?
  set -e
  rm -f "$stdin_payload"
  return "$rc"
}

echo "[big-little] variant=$variant artifact=$artifact_path output_dir=$output_dir snr=$snr batch_size=$batch_size python=$remote_python"

extra_args=()
if [[ -n "$max_inputs" ]]; then
  extra_args+=(--max-inputs "$max_inputs")
fi
if [[ -n "$seed" ]]; then
  extra_args+=(--seed "$seed")
fi
if [[ -n "$big_cores" ]]; then
  extra_args+=(--big-cores "$big_cores")
fi
if [[ -n "$little_cores" ]]; then
  extra_args+=(--little-cores "$little_cores")
fi
if [[ "$allow_missing_affinity" == "1" ]]; then
  extra_args+=(--allow-missing-affinity)
fi
if [[ "$dry_run" == "1" ]]; then
  extra_args+=(--dry-run)
fi
if [[ -n "$mock_infer_ms" ]]; then
  extra_args+=(--mock-infer-ms "$mock_infer_ms")
fi

run_remote_python - \
  --artifact-path "$artifact_path" \
  --input-dir "$input_dir" \
  --output-dir "$output_dir" \
  --snr "$snr" \
  --batch-size "$batch_size" \
  --variant "$variant" \
  --execution-mode "$execution_mode" \
  --expected-sha256 "$expected_sha256" \
  --input-queue-size "$input_queue_size" \
  --output-queue-size "$output_queue_size" \
  --backend "$backend" \
  "${extra_args[@]}" <<'PY'
SH
    cat "$PYTHON_RUNNER_SOURCE"
    cat <<'SH'
PY
SH
  } >"$runner_script"
  chmod 700 "$runner_script"

  if [[ "$REMOTE_MODE" == "ssh" ]]; then
    set +e
    bash "$SCRIPT_DIR/ssh_with_password.sh" \
      --host "$REMOTE_HOST" \
      --user "$REMOTE_USER" \
      --pass "$REMOTE_PASS" \
      --port "${REMOTE_SSH_PORT:-22}" \
      -- \
      bash -s \
      <"$runner_script"
    rc=$?
    set -e
    rm -f "$runner_script"
    return "$rc"
  fi

  set +e
  bash "$runner_script"
  rc=$?
  set -e
  rm -f "$runner_script"
  return "$rc"
}

TMP_OUTPUT="$(mktemp)"
PIPELINE_JSON_FILE="$(mktemp)"
set +e
run_pipeline_remote 2>&1 | tee "$TMP_OUTPUT" >(cat >>"$RAW_OUTPUT_FILE") >(cat >>"$LOG_FILE")
RUN_RC=${PIPESTATUS[0]}
set -e

if parse_last_json_line "$TMP_OUTPUT" >"$PIPELINE_JSON_FILE"; then
  WRAPPER_STDOUT="$(render_wrapper_report "$PIPELINE_JSON_FILE" "$REPORT_JSON" "$REPORT_MD" "$RUN_ID" "${ENV_FILE:-}" "$VARIANT" "$REMOTE_MODE" "$LOG_FILE")"
  printf '%s\n' "$WRAPPER_STDOUT"
  PIPELINE_STATUS="$(python3 - "$PIPELINE_JSON_FILE" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(payload.get('status', 'error'))
PY
)"
  if [[ "$RUN_RC" -ne 0 || "$PIPELINE_STATUS" != "ok" ]]; then
    exit 1
  fi
  exit 0
fi

echo "ERROR: failed to parse pipeline JSON output. See $LOG_FILE and $RAW_OUTPUT_FILE" >&2
exit "${RUN_RC:-1}"
