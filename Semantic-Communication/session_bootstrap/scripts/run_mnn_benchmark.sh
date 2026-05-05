#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"
REPORT_BUILDER="$SCRIPT_DIR/mnn_benchmark_report.py"
DEFAULT_ENV_FILE="$SESSION_DIR/config/local.env"

usage() {
  cat <<'EOF'
Usage:
  run_mnn_benchmark.sh [--env <path>] [--run-id <id>] [--allow-overwrite] [--dry-run]

Required env:
  LOG_DIR
  REPORT_DIR
  REMOTE_MODE=ssh|local
  REMOTE_MNN_PYTHON
  REMOTE_INPUT_DIR
  REMOTE_OUTPUT_BASE
  REMOTE_SNR_CURRENT
  At least one of:
    MNN_FP32_MODEL
    MNN_FP16_MODEL
    MNN_INT8_MODEL

Matrix env:
  MNN_INTERPRETER_COUNTS=1,2
  MNN_THREAD_COUNTS=1,2,4
  MNN_PRECISIONS=normal,low
  MNN_SHAPE_MODES=dynamic
  MNN_BUCKET_SHAPES=
  MNN_WARMUP_INPUTS=1
  MNN_AUTO_BACKEND=0|1
  MNN_TUNE_NUM=20
  MNN_MAX_INPUTS=300
  MNN_SEED=0
  MNN_QUALITY_MODE=off|low_precision_only|all
  MNN_QUALITY_REF_DIR=<remote path>
  MNN_QUALITY_MAX_IMAGES=300
  MNN_QUALITY_LPIPS=auto|force|off
  MNN_OUTPUT_PREFIX=mnn_benchmark
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
for raw_line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
    line = raw_line.strip()
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

ENV_FILE="$DEFAULT_ENV_FILE"
ENV_FILE_SPECIFIED=0
RUN_ID_OVERRIDE=""
ALLOW_OVERWRITE=0
FORCE_DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:-}"
      ENV_FILE_SPECIFIED=1
      shift 2
      ;;
    --run-id)
      RUN_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --allow-overwrite)
      ALLOW_OVERWRITE=1
      shift
      ;;
    --dry-run)
      FORCE_DRY_RUN=1
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

if [[ "$ENV_FILE_SPECIFIED" == "1" && ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ "$ENV_FILE_SPECIFIED" == "0" && ! -f "$ENV_FILE" ]]; then
  ENV_FILE=""
fi

if [[ -n "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a
  source "$ENV_FILE"
  set +a
fi

require_var LOG_DIR
require_var REPORT_DIR
require_var REMOTE_MODE
require_var REMOTE_MNN_PYTHON
require_var REMOTE_INPUT_DIR
require_var REMOTE_OUTPUT_BASE
require_var REMOTE_SNR_CURRENT

LOG_DIR_RESOLVED="$(resolve_path "$LOG_DIR")"
REPORT_DIR_RESOLVED="$(resolve_path "$REPORT_DIR")"
mkdir -p "$LOG_DIR_RESOLVED" "$REPORT_DIR_RESOLVED"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ID="${RUN_ID_OVERRIDE:-${MNN_RUN_ID:-mnn_deep_opt_${STAMP}}}"
LOG_FILE="$LOG_DIR_RESOLVED/${RUN_ID}.log"
RESULTS_JSONL="$REPORT_DIR_RESOLVED/${RUN_ID}_raw.jsonl"
REPORT_JSON="$REPORT_DIR_RESOLVED/${RUN_ID}.json"
REPORT_MD="$REPORT_DIR_RESOLVED/${RUN_ID}.md"

if [[ "$ALLOW_OVERWRITE" != "1" ]]; then
  existing_outputs=()
  [[ -e "$LOG_FILE" ]] && existing_outputs+=("$LOG_FILE")
  [[ -e "$RESULTS_JSONL" ]] && existing_outputs+=("$RESULTS_JSONL")
  [[ -e "$REPORT_JSON" ]] && existing_outputs+=("$REPORT_JSON")
  [[ -e "$REPORT_MD" ]] && existing_outputs+=("$REPORT_MD")
  if [[ "${#existing_outputs[@]}" -gt 0 ]]; then
    printf 'ERROR: run artifacts already exist for RUN_ID=%s\n' "$RUN_ID" >&2
    printf '  %s\n' "${existing_outputs[@]}" >&2
    exit 1
  fi
fi

: >"$LOG_FILE"
: >"$RESULTS_JSONL"

MNN_INTERPRETER_COUNTS="${MNN_INTERPRETER_COUNTS:-1,2}"
MNN_THREAD_COUNTS="${MNN_THREAD_COUNTS:-1,2,4}"
MNN_PRECISIONS="${MNN_PRECISIONS:-normal,low}"
MNN_SHAPE_MODES="${MNN_SHAPE_MODES:-dynamic}"
MNN_BUCKET_SHAPES="${MNN_BUCKET_SHAPES:-}"
MNN_WARMUP_INPUTS="${MNN_WARMUP_INPUTS:-1}"
MNN_AUTO_BACKEND="${MNN_AUTO_BACKEND:-0}"
MNN_TUNE_NUM="${MNN_TUNE_NUM:-20}"
MNN_MAX_INPUTS="${MNN_MAX_INPUTS:-300}"
MNN_SEED="${MNN_SEED:-0}"
MNN_OUTPUT_PREFIX="${MNN_OUTPUT_PREFIX:-mnn_benchmark}"
MNN_QUALITY_MODE="${MNN_QUALITY_MODE:-off}"
MNN_QUALITY_MAX_IMAGES="${MNN_QUALITY_MAX_IMAGES:-300}"
MNN_QUALITY_LPIPS="${MNN_QUALITY_LPIPS:-auto}"
MNN_MOCK_INFER_MS="${MNN_MOCK_INFER_MS:-15}"

has_model=0
for model_var in MNN_FP32_MODEL MNN_FP16_MODEL MNN_INT8_MODEL; do
  if [[ -n "${!model_var:-}" ]]; then
    has_model=1
    break
  fi
done
if [[ "$has_model" != "1" ]]; then
  echo "ERROR: at least one of MNN_FP32_MODEL/MNN_FP16_MODEL/MNN_INT8_MODEL must be set." >&2
  exit 1
fi

should_run_quality() {
  local model_variant="$1"
  case "$MNN_QUALITY_MODE" in
    off)
      return 1
      ;;
    all)
      [[ -n "${MNN_QUALITY_REF_DIR:-}" ]]
      return
      ;;
    low_precision_only)
      [[ -n "${MNN_QUALITY_REF_DIR:-}" && ( "$model_variant" == "fp16" || "$model_variant" == "int8" ) ]]
      return
      ;;
    *)
      echo "ERROR: unsupported MNN_QUALITY_MODE=$MNN_QUALITY_MODE" >&2
      exit 1
      ;;
  esac
}

append_result_record() {
  local record_json="$1"
  printf '%s\n' "$record_json" >>"$RESULTS_JSONL"
}

run_one_config() {
  local model_variant="$1"
  local model_path="$2"
  local interpreter_count="$3"
  local session_threads="$4"
  local precision="$5"
  local shape_mode="$6"
  local config_id output_prefix runner_tmp rc runner_payload quality_payload quality_prefix record_json

  config_id="${model_variant}_i${interpreter_count}_t${session_threads}_${precision}_${shape_mode}"
  output_prefix="${MNN_OUTPUT_PREFIX}_${RUN_ID}_${config_id}"
  runner_tmp="$(mktemp)"

  {
    echo "[$(date -Iseconds)] config_start=$config_id model=$model_path"
    echo "variant=current"
    echo "output_prefix=$output_prefix"
  } >>"$LOG_FILE"

  set +e
  bash "$SCRIPT_DIR/run_remote_mnn_reconstruction.sh" \
    --variant current \
    --model-path "$model_path" \
    --output-prefix "$output_prefix" \
    --max-inputs "$MNN_MAX_INPUTS" \
    --seed "$MNN_SEED" \
    --interpreter-count "$interpreter_count" \
    --session-threads "$session_threads" \
    --precision "$precision" \
    --shape-mode "$shape_mode" \
    --bucket-shapes "$MNN_BUCKET_SHAPES" \
    --warmup-inputs "$MNN_WARMUP_INPUTS" \
    $( [[ "$MNN_AUTO_BACKEND" == "1" ]] && printf '%s' "--auto-backend --tune-num $MNN_TUNE_NUM" ) \
    $( [[ "$FORCE_DRY_RUN" == "1" || "${MNN_DRY_RUN:-0}" == "1" ]] && printf '%s' "--dry-run --mock-infer-ms $MNN_MOCK_INFER_MS" ) \
    >"$runner_tmp" 2>&1
  rc=$?
  set -e

  cat "$runner_tmp" >>"$LOG_FILE"
  if runner_payload="$(parse_last_json_line "$runner_tmp" 2>/dev/null)"; then
    :
  else
    runner_payload='{}'
  fi

  quality_payload="{}"
  if [[ "$rc" -eq 0 ]] && should_run_quality "$model_variant"; then
    quality_prefix="${REMOTE_OUTPUT_BASE%/}/quality_reports/${RUN_ID}_${config_id}_quality"
    quality_tmp="$(mktemp)"
    set +e
    bash "$SCRIPT_DIR/run_remote_quality_metrics.sh" \
      --ref-dir "$MNN_QUALITY_REF_DIR" \
      --test-dir "$(python3 -c 'import json,sys; payload=json.loads(sys.argv[1]); print(payload.get("reconstruction_dir",""))' "$runner_payload")" \
      --report-prefix "$quality_prefix" \
      --comparison-label "mnn_${config_id}" \
      --max-images "$MNN_QUALITY_MAX_IMAGES" \
      --lpips "$MNN_QUALITY_LPIPS" \
      >"$quality_tmp" 2>&1
    quality_rc=$?
    set -e
    cat "$quality_tmp" >>"$LOG_FILE"
    if [[ "$quality_rc" -eq 0 ]]; then
      if quality_payload="$(parse_last_json_line "$quality_tmp" 2>/dev/null)"; then
        :
      else
        quality_payload='{}'
      fi
    fi
    rm -f "$quality_tmp"
  fi

  record_json="$(python3 - "$model_variant" "$model_path" "$interpreter_count" "$session_threads" "$precision" "$shape_mode" "$config_id" "$MNN_AUTO_BACKEND" "$runner_payload" "$quality_payload" "$rc" <<'PY'
import json
import sys

model_variant, model_path, interpreter_count, session_threads, precision, shape_mode, config_id, auto_backend, runner_raw, quality_raw, rc_raw = sys.argv[1:12]
runner_payload = json.loads(runner_raw or "{}")
quality_payload = json.loads(quality_raw or "{}")
quality_summary = {}
if isinstance(quality_payload, dict):
    aggregate = quality_payload.get("aggregate") or {}
    quality_summary = {
        "psnr_db": (aggregate.get("psnr_db") or {}).get("mean"),
        "ssim": (aggregate.get("ssim") or {}).get("mean"),
        "lpips": (aggregate.get("lpips") or {}).get("mean"),
        "status": quality_payload.get("status"),
        "run_id": quality_payload.get("run_id"),
        "report_json": quality_payload.get("json_report"),
        "report_markdown": quality_payload.get("markdown_report"),
    }
record = {
    "status": "ok" if rc_raw == "0" and runner_payload.get("status") == "ok" else "error",
    "config_id": config_id,
    "model_variant": model_variant,
    "model_path": model_path,
    "interpreter_count": int(interpreter_count),
    "session_threads": int(session_threads),
    "precision": precision,
    "shape_mode": shape_mode,
    "auto_backend": auto_backend == "1",
    "runner_payload": runner_payload,
    "quality_summary": quality_summary,
}
print(json.dumps(record, ensure_ascii=False))
PY
)"
  append_result_record "$record_json"
  rm -f "$runner_tmp"
}

IFS=',' read -r -a interpreter_counts <<<"$MNN_INTERPRETER_COUNTS"
IFS=',' read -r -a thread_counts <<<"$MNN_THREAD_COUNTS"
IFS=',' read -r -a precisions <<<"$MNN_PRECISIONS"
IFS=',' read -r -a shape_modes <<<"$MNN_SHAPE_MODES"

for model_variant in fp32 fp16 int8; do
  case "$model_variant" in
    fp32) model_path="${MNN_FP32_MODEL:-}" ;;
    fp16) model_path="${MNN_FP16_MODEL:-}" ;;
    int8) model_path="${MNN_INT8_MODEL:-}" ;;
  esac
  if [[ -z "$model_path" ]]; then
    continue
  fi
  for interpreter_count in "${interpreter_counts[@]}"; do
    for session_threads in "${thread_counts[@]}"; do
      for precision in "${precisions[@]}"; do
        for shape_mode in "${shape_modes[@]}"; do
          run_one_config "$model_variant" "$model_path" "$interpreter_count" "$session_threads" "$precision" "$shape_mode"
        done
      done
    done
  done
done

python3 "$REPORT_BUILDER" \
  --results-jsonl "$RESULTS_JSONL" \
  --report-json "$REPORT_JSON" \
  --report-md "$REPORT_MD" \
  --run-id "$RUN_ID" \
  --title "MNN Benchmark Report"
