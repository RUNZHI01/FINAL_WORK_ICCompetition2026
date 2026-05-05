#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUALITY_SCRIPT_SOURCE="$SCRIPT_DIR/compute_image_quality_metrics.py"
SHAPE_UTILS_SOURCE="$SCRIPT_DIR/output_shape_utils.py"

usage() {
  cat <<'EOF'
Usage:
  run_remote_quality_metrics.sh --ref-dir <path> --test-dir <path> --report-prefix <path> [options]

Options:
  --ref-dir <path>           Reference directory on the execution target.
  --test-dir <path>          Test directory on the execution target.
  --report-prefix <path>     Report prefix on the execution target.
  --comparison-label <str>   Optional comparison label.
  --max-images <n>           Maximum matched PNGs. Default: 300.
  --size-mismatch <mode>     crop|crop-top-left|crop-center|error.
  --lpips <mode>             auto|force|off.
  -h, --help                 Show this message.

Env:
  REMOTE_MODE=ssh|local
  REMOTE_QUALITY_PYTHON or REMOTE_MNN_PYTHON
  REMOTE_HOST / REMOTE_USER / REMOTE_PASS when REMOTE_MODE=ssh
EOF
}

REF_DIR=""
TEST_DIR=""
REPORT_PREFIX=""
COMPARISON_LABEL=""
MAX_IMAGES="300"
SIZE_MISMATCH="crop-top-left"
LPIPS_MODE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref-dir)
      REF_DIR="${2:-}"
      shift 2
      ;;
    --test-dir)
      TEST_DIR="${2:-}"
      shift 2
      ;;
    --report-prefix)
      REPORT_PREFIX="${2:-}"
      shift 2
      ;;
    --comparison-label)
      COMPARISON_LABEL="${2:-}"
      shift 2
      ;;
    --max-images)
      MAX_IMAGES="${2:-}"
      shift 2
      ;;
    --size-mismatch)
      SIZE_MISMATCH="${2:-}"
      shift 2
      ;;
    --lpips)
      LPIPS_MODE="${2:-}"
      shift 2
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

if [[ -z "$REF_DIR" || -z "$TEST_DIR" || -z "$REPORT_PREFIX" ]]; then
  echo "ERROR: --ref-dir/--test-dir/--report-prefix are required." >&2
  exit 1
fi
if [[ ! -f "$QUALITY_SCRIPT_SOURCE" || ! -f "$SHAPE_UTILS_SOURCE" ]]; then
  echo "ERROR: quality script sources are missing." >&2
  exit 1
fi

REMOTE_MODE_RAW="${REMOTE_MODE:-ssh}"
REMOTE_MODE="$(printf '%s' "$REMOTE_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
if [[ "$REMOTE_MODE" != "ssh" && "$REMOTE_MODE" != "local" ]]; then
  echo "ERROR: REMOTE_MODE must be ssh or local (got: $REMOTE_MODE_RAW)" >&2
  exit 1
fi

REMOTE_QUALITY_PYTHON="${REMOTE_QUALITY_PYTHON:-${REMOTE_MNN_PYTHON:-}}"
if [[ -z "$REMOTE_QUALITY_PYTHON" ]]; then
  echo "ERROR: REMOTE_QUALITY_PYTHON or REMOTE_MNN_PYTHON is required." >&2
  exit 1
fi
if [[ "$REMOTE_MODE" == "ssh" ]]; then
  for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
    if [[ -z "${!req:-}" ]]; then
      echo "ERROR: Missing required variable: $req" >&2
      exit 1
    fi
  done
fi

run_remote_quality() {
  local runner_script
  local rc=0
  runner_script="$(mktemp)"
  {
    cat <<'SH'
#!/usr/bin/env bash
set -euo pipefail
SH
    declare -p REMOTE_QUALITY_PYTHON REF_DIR TEST_DIR REPORT_PREFIX COMPARISON_LABEL MAX_IMAGES SIZE_MISMATCH LPIPS_MODE
    cat <<'SH'
remote_python="$REMOTE_QUALITY_PYTHON"
runner_dir="$(mktemp -d)"
trap 'rm -rf "$runner_dir"' EXIT
mkdir -p "$(dirname "$REPORT_PREFIX")"

cat >"$runner_dir/output_shape_utils.py" <<'PY'
SH
    cat "$SHAPE_UTILS_SOURCE"
    cat <<'SH'
PY

cat >"$runner_dir/compute_image_quality_metrics.py" <<'PY'
SH
    cat "$QUALITY_SCRIPT_SOURCE"
    cat <<'SH'
PY

cmd="$remote_python $(printf '%q' "$runner_dir/compute_image_quality_metrics.py") --ref-dir $(printf '%q' "$REF_DIR") --test-dir $(printf '%q' "$TEST_DIR") --report-prefix $(printf '%q' "$REPORT_PREFIX") --max-images $(printf '%q' "$MAX_IMAGES") --size-mismatch $(printf '%q' "$SIZE_MISMATCH") --lpips $(printf '%q' "$LPIPS_MODE")"
if [[ -n "$COMPARISON_LABEL" ]]; then
  cmd+=" --comparison-label $(printf '%q' "$COMPARISON_LABEL")"
fi
bash -c "$cmd"
"$remote_python" - <<'PY' "${REPORT_PREFIX}.json"
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as infile:
    payload = json.load(infile)
print(json.dumps(payload, ensure_ascii=False))
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

run_remote_quality
