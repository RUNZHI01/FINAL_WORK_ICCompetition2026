#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ONE_SHOT_SCRIPT="${PHYTIUM_BASELINE_STYLE_ONE_SHOT_SCRIPT:-$SCRIPT_DIR/run_phytium_current_safe_one_shot.sh}"
DEFAULT_REBUILD_ENV="$SESSION_DIR/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
DEFAULT_INFERENCE_ENV="$SESSION_DIR/config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env"
DEFAULT_REPORT_PREFIX="phytium_baseline_style_current_rebuild"
EXPECTED_BASELINE_CMD="run_remote_tvm_inference_payload.sh --variant baseline"
EXPECTED_CURRENT_CMD="run_remote_tvm_inference_payload.sh --variant current"

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_phytium_baseline_style_current_rebuild.sh [options]

Purpose:
  Rebuild and validate the current artifact through the fairer baseline-style payload path:
    1) rebuild current locally from the existing tuning DB
    2) upload optimized_model.so into the remote current archive
    3) run the same payload-style current inference path used by Scheme A fair compare
    4) save a concise summary with explicit payload-symmetric semantics

Defaults:
  rebuild env   : $DEFAULT_REBUILD_ENV
  inference env : $DEFAULT_INFERENCE_ENV

Options:
  --rebuild-env <path>        Override rebuild env file.
  --inference-env <path>      Override fair payload inference env file.
  --target <json>             Override the current target JSON.
  --output-dir <path>         Override local output dir for rebuilt artifact.
  --remote-archive-dir <dir>  Override remote current archive dir.
  --report-id <id>            Override report/log prefix.
  --repeat <n>                Override inference repeat count.
  --warmup-runs <n>           Override inference warmup count.
  --entry <name>              Override Relax VM entry name.
  --upload-db                 Also upload the resulting tuning_logs DB into the remote current archive.
  --help                      Show this message.

Notes:
  - This entrypoint is rebuild-only by design; it refuses rebuild envs with TUNE_TOTAL_TRIALS != 0.
  - It validates that the inference env is payload-symmetric and does not point at legacy compat wrappers.
  - For the legacy/current mixed safe-runtime path, use run_phytium_current_safe_one_shot.sh explicitly instead.
EOF
}

REBUILD_ENV="$DEFAULT_REBUILD_ENV"
INFERENCE_ENV="$DEFAULT_INFERENCE_ENV"
TARGET_OVERRIDE=""
OUTPUT_DIR_OVERRIDE=""
REMOTE_ARCHIVE_DIR_OVERRIDE=""
REPORT_ID_OVERRIDE=""
REPEAT_OVERRIDE=""
WARMUP_OVERRIDE=""
ENTRY_OVERRIDE=""
UPLOAD_DB_FLAG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild-env)
      REBUILD_ENV="${2:-}"
      shift 2
      ;;
    --inference-env)
      INFERENCE_ENV="${2:-}"
      shift 2
      ;;
    --target)
      TARGET_OVERRIDE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --remote-archive-dir)
      REMOTE_ARCHIVE_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --report-id)
      REPORT_ID_OVERRIDE="${2:-}"
      shift 2
      ;;
    --repeat)
      REPEAT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --warmup-runs)
      WARMUP_OVERRIDE="${2:-}"
      shift 2
      ;;
    --entry)
      ENTRY_OVERRIDE="${2:-}"
      shift 2
      ;;
    --upload-db)
      UPLOAD_DB_FLAG=1
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

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

append_optional_arg() {
  local option="$1"
  local value="$2"
  if [[ -n "$value" ]]; then
    RUN_CMD+=("$option" "$value")
  fi
}

validate_payload_cmd() {
  local value="$1"
  local expected="$2"
  local label="$3"

  if [[ -z "$value" ]]; then
    echo "ERROR: Missing ${label} in inference env; this fair wrapper expects explicit payload-symmetric commands." >&2
    exit 1
  fi
  if [[ "$value" == *"run_remote_legacy_tvm_compat.sh"* ]]; then
    echo "ERROR: ${label} points at legacy compat flow: $value" >&2
    exit 1
  fi
  if [[ "$value" != *"$expected"* ]]; then
    echo "ERROR: ${label} must contain '$expected' for the fair baseline-style path." >&2
    echo "       actual: $value" >&2
    exit 1
  fi
}

require_command bash
require_file "$ONE_SHOT_SCRIPT" "shared one-shot wrapper"
require_file "$REBUILD_ENV" "rebuild env"
require_file "$INFERENCE_ENV" "inference env"

set -a
# shellcheck source=/dev/null
source "$REBUILD_ENV"
set +a

TUNE_TOTAL_TRIALS_VALUE="${TUNE_TOTAL_TRIALS:-}"
if [[ -z "$TUNE_TOTAL_TRIALS_VALUE" ]]; then
  echo "ERROR: Missing TUNE_TOTAL_TRIALS in rebuild env." >&2
  exit 1
fi
if ! [[ "$TUNE_TOTAL_TRIALS_VALUE" =~ ^[0-9]+$ ]]; then
  echo "ERROR: TUNE_TOTAL_TRIALS must be a non-negative integer (got: $TUNE_TOTAL_TRIALS_VALUE)." >&2
  exit 1
fi
if [[ "$TUNE_TOTAL_TRIALS_VALUE" -ne 0 ]]; then
  echo "ERROR: This baseline-style rebuild wrapper only supports rebuild-only envs (TUNE_TOTAL_TRIALS=0)." >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$INFERENCE_ENV"
set +a

validate_payload_cmd "${INFERENCE_BASELINE_CMD:-}" "$EXPECTED_BASELINE_CMD" "INFERENCE_BASELINE_CMD"
validate_payload_cmd "${INFERENCE_CURRENT_CMD:-}" "$EXPECTED_CURRENT_CMD" "INFERENCE_CURRENT_CMD"

if [[ "${REMOTE_MODE:-ssh}" != "ssh" ]]; then
  echo "ERROR: This baseline-style current rebuild path is for the Phytium Pi over SSH only (REMOTE_MODE=ssh expected)." >&2
  exit 1
fi

export PHYTIUM_ONE_SHOT_REPORT_PREFIX="$DEFAULT_REPORT_PREFIX"
export PHYTIUM_ONE_SHOT_REPORT_TITLE="Phytium Pi baseline-style current rebuild summary"
export PHYTIUM_ONE_SHOT_START_LABEL="Phytium baseline-style current rebuild started"
export PHYTIUM_ONE_SHOT_COMPLETE_LABEL="Phytium baseline-style current rebuild complete."
export PHYTIUM_ONE_SHOT_MODE_LOG_DESCRIPTION="baseline-style current rebuild-only + payload-symmetric runtime"
export PHYTIUM_ONE_SHOT_MODE_REBUILD_DESCRIPTION="baseline-style current rebuild-only + payload-symmetric runtime"
export PHYTIUM_ONE_SHOT_MODE_INCREMENTAL_DESCRIPTION="baseline-style current warm-start incremental tuning + payload-symmetric runtime"
export PHYTIUM_ONE_SHOT_INFERENCE_SECTION_TITLE="Payload-Symmetric Inference"
export PHYTIUM_ONE_SHOT_INFERENCE_RUNTIME_LABEL="payload-symmetric runtime path: load_module() once -> VM init once -> warmup -> repeated main()"

RUN_CMD=(
  bash "$ONE_SHOT_SCRIPT"
  --rebuild-env "$REBUILD_ENV"
  --inference-env "$INFERENCE_ENV"
)
append_optional_arg --target "$TARGET_OVERRIDE"
append_optional_arg --output-dir "$OUTPUT_DIR_OVERRIDE"
append_optional_arg --remote-archive-dir "$REMOTE_ARCHIVE_DIR_OVERRIDE"
append_optional_arg --report-id "$REPORT_ID_OVERRIDE"
append_optional_arg --repeat "$REPEAT_OVERRIDE"
append_optional_arg --warmup-runs "$WARMUP_OVERRIDE"
append_optional_arg --entry "$ENTRY_OVERRIDE"
if [[ "$UPLOAD_DB_FLAG" -eq 1 ]]; then
  RUN_CMD+=(--upload-db)
fi

exec "${RUN_CMD[@]}"
