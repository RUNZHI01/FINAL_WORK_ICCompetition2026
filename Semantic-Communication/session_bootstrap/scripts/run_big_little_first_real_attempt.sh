#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$SESSION_DIR/.." && pwd)"

SOURCE_ENV_FILE="${1:-$PROJECT_DIR/session_bootstrap/config/big_little_pipeline.current.2026-03-18.phytium_pi.env}"

if [[ ! -f "$SOURCE_ENV_FILE" ]]; then
  echo "ERROR: env file not found: $SOURCE_ENV_FILE" >&2
  exit 1
fi

cd "$PROJECT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
RUNTIME_ENV="./session_bootstrap/config/big_little_pipeline.current.runtime_${STAMP}.env"
cp "$SOURCE_ENV_FILE" "$RUNTIME_ENV"

echo "Using runtime env copy: $RUNTIME_ENV"

REMOTE_MODE_EFFECTIVE="$(bash -lc 'set -a; source "$1" >/dev/null 2>&1; printf "%s" "${REMOTE_MODE:-ssh}"' bash "$RUNTIME_ENV")"
REMOTE_MODE_EFFECTIVE="$(printf '%s' "$REMOTE_MODE_EFFECTIVE" | tr '[:upper:]' '[:lower:]')"

SUGGESTION_JSON="./session_bootstrap/reports/big_little_topology_suggestion_latest.json"
CAPTURE_TXT="./session_bootstrap/reports/big_little_topology_capture_latest.txt"

if [[ "$REMOTE_MODE_EFFECTIVE" == "local" ]]; then
  echo "=== [1/2] local/mock mode detected: skip remote topology probe ==="
  echo "remote_mode=local"
  echo
  echo "=== [2/2] current big.LITTLE pipeline run ==="
  bash ./session_bootstrap/scripts/run_big_little_pipeline.sh \
    --env "$RUNTIME_ENV" \
    --variant current

  echo
  echo "=== local/mock compare ==="
  bash ./session_bootstrap/scripts/run_big_little_compare.sh \
    --env "$RUNTIME_ENV"
else
  echo "=== [1/4] read-only topology probe ==="
  python3 ./session_bootstrap/scripts/big_little_topology_probe.py ssh \
    --env "$RUNTIME_ENV" \
    --timeout-sec 180 \
    --write-raw "$CAPTURE_TXT" \
    > "$SUGGESTION_JSON"
  cat "$SUGGESTION_JSON"

  echo
  echo "=== [2/4] apply topology suggestion to runtime env ==="
  python3 ./session_bootstrap/scripts/apply_big_little_topology_suggestion.py \
    --env "$RUNTIME_ENV" \
    --suggestion "$SUGGESTION_JSON"

  echo
  echo "=== [3/4] current big.LITTLE pipeline run ==="
  bash ./session_bootstrap/scripts/run_big_little_pipeline.sh \
    --env "$RUNTIME_ENV" \
    --variant current

  echo
  echo "=== [4/4] serial vs pipeline compare ==="
  bash ./session_bootstrap/scripts/run_big_little_compare.sh \
    --env "$RUNTIME_ENV"
fi

echo
echo "Done. Runtime env copy: $RUNTIME_ENV"
echo "Check session_bootstrap/reports/big_little_pipeline_* and big_little_compare_*"
