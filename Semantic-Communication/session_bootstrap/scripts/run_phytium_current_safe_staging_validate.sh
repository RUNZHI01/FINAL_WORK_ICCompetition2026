#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PARENT_SCRIPT="$SCRIPT_DIR/run_phytium_baseline_seeded_warm_start_current_incremental.sh"
DEFAULT_REBUILD_ENV="$SESSION_DIR/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
DEFAULT_INFERENCE_ENV="$SESSION_DIR/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
DEFAULT_STAGING_REMOTE_ARCHIVE="/home/user/Downloads/jscc-test/jscc_staging"

usage() {
  cat <<EOF
Usage:
  bash ./session_bootstrap/scripts/run_phytium_current_safe_staging_validate.sh [options]

Purpose:
  Run a current-safe incremental tuning round against an isolated remote staging archive,
  so new artifacts can be validated before they overwrite the trusted current archive.

Defaults:
  rebuild env          : $DEFAULT_REBUILD_ENV
  inference env        : $DEFAULT_INFERENCE_ENV
  staging remote archive: $DEFAULT_STAGING_REMOTE_ARCHIVE
  report prefix        : phytium_current_safe_staging_validate_<timestamp>

Options:
  --rebuild-env <path>         Override rebuild env.
  --inference-env <path>       Override inference env.
  --remote-archive-dir <dir>   Override the remote staging archive path.
  All other arguments are forwarded to run_phytium_baseline_seeded_warm_start_current_incremental.sh.

Notes:
  - This wrapper is intentionally conservative: it validates in staging first.
  - Promotion to /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
    should happen only after payload/runtime checks pass.
EOF
}

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: ${label} not found: $path" >&2
    exit 1
  fi
}

REBUILD_ENV="$DEFAULT_REBUILD_ENV"
INFERENCE_ENV="$DEFAULT_INFERENCE_ENV"
REMOTE_ARCHIVE_DIR="$DEFAULT_STAGING_REMOTE_ARCHIVE"
FORWARD_ARGS=()

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
    --remote-archive-dir)
      REMOTE_ARCHIVE_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      FORWARD_ARGS+=("$1")
      shift
      ;;
  esac
done

require_file "$PARENT_SCRIPT" "baseline-seeded incremental wrapper"
require_file "$REBUILD_ENV" "rebuild env"
require_file "$INFERENCE_ENV" "inference env"

DEFAULT_REPORT_ID="phytium_current_safe_staging_validate_$(date +%Y%m%d_%H%M%S)"

exec bash "$PARENT_SCRIPT" \
  --rebuild-env "$REBUILD_ENV" \
  --inference-env "$INFERENCE_ENV" \
  --remote-archive-dir "$REMOTE_ARCHIVE_DIR" \
  --report-id "$DEFAULT_REPORT_ID" \
  "${FORWARD_ARGS[@]}"
