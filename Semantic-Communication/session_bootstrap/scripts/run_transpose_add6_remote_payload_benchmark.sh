#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  run_transpose_add6_remote_payload_benchmark.sh \
    --inference-env <env_file> \
    --local-artifact <path/to/fused_conv2d_transpose_add6_post_db_swap.so> \
    [--database-dir <tuning_logs_dir>] \
    [--remote-archive-dir <remote archive>] \
    [--report-id <id>] \
    [--upload-only]

This helper stays narrow and operator-specific:
- it stages a local transpose_add6 handwritten artifact into a dedicated remote archive
- it optionally mirrors the frozen DB JSON files into that archive
- it then runs the existing run_remote_tvm_inference_payload.sh current-path benchmark
- all remote actions go through the repository ssh_with_password.sh helper
EOF
}

INFERENCE_ENV=""
LOCAL_ARTIFACT=""
DATABASE_DIR=""
REMOTE_ARCHIVE_DIR="/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6"
REPORT_ID="transpose_add6_remote_payload_$(date +%Y%m%d_%H%M%S)"
UPLOAD_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --inference-env)
      INFERENCE_ENV="${2:-}"
      shift 2
      ;;
    --local-artifact)
      LOCAL_ARTIFACT="${2:-}"
      shift 2
      ;;
    --database-dir)
      DATABASE_DIR="${2:-}"
      shift 2
      ;;
    --remote-archive-dir)
      REMOTE_ARCHIVE_DIR="${2:-}"
      shift 2
      ;;
    --report-id)
      REPORT_ID="${2:-}"
      shift 2
      ;;
    --upload-only)
      UPLOAD_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$INFERENCE_ENV" || -z "$LOCAL_ARTIFACT" ]]; then
  echo "ERROR: --inference-env and --local-artifact are required." >&2
  usage >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a
source "$INFERENCE_ENV"
set +a

for req in REMOTE_HOST REMOTE_USER REMOTE_PASS; do
  if [[ -z "${!req:-}" ]]; then
    echo "ERROR: missing required variable from env: $req" >&2
    exit 1
  fi
done

if [[ ! -f "$LOCAL_ARTIFACT" ]]; then
  echo "ERROR: local artifact not found: $LOCAL_ARTIFACT" >&2
  exit 1
fi

SSH_SCRIPT="${SSH_SCRIPT:-$SCRIPT_DIR/ssh_with_password.sh}"
REMOTE_PORT="${REMOTE_SSH_PORT:-22}"

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

remote_exec() {
  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "$REMOTE_PORT" \
    -- "$1"
}

local_file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

local_file_size_bytes() {
  stat -c '%s' "$1"
}

remote_file_meta() {
  local remote_path="$1"
  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "$REMOTE_PORT" \
    -- \
    python3 -c 'import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"ERROR: missing remote file: {path}")
digest = hashlib.sha256()
with path.open("rb") as infile:
    for chunk in iter(lambda: infile.read(1024 * 1024), b""):
        digest.update(chunk)
print(f"sha256={digest.hexdigest()}")
print(f"size_bytes={path.stat().st_size}")' \
    "$remote_path"
}

meta_field() {
  local meta_text="$1"
  local field_name="$2"
  printf '%s\n' "$meta_text" | awk -F= -v key="$field_name" '$1 == key {print $2}' | tr -d '\r\n'
}

copy_remote_file_byte_stable() {
  local src="$1"
  local dst="$2"
  remote_exec "mkdir -p $(shell_quote "$(dirname "$dst")")"
  base64 "$src" | bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "$REMOTE_PORT" \
    -- \
    python3 -c 'import base64, pathlib, sys
payload = base64.b64decode(sys.stdin.buffer.read())
path = pathlib.Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(payload)' \
    "$dst"
}

copy_and_verify_remote_file() {
  local src="$1"
  local dst="$2"
  local label="$3"
  local local_sha local_size remote_meta remote_sha remote_size

  copy_remote_file_byte_stable "$src" "$dst"
  local_sha="$(local_file_sha256 "$src")"
  local_size="$(local_file_size_bytes "$src")"
  remote_meta="$(remote_file_meta "$dst")"
  remote_sha="$(meta_field "$remote_meta" sha256)"
  remote_size="$(meta_field "$remote_meta" size_bytes)"

  if [[ -z "$remote_sha" || -z "$remote_size" ]]; then
    echo "ERROR: failed to collect remote metadata for $label path=$dst" >&2
    printf '%s\n' "$remote_meta" >&2
    exit 1
  fi

  if [[ "$local_sha" != "$remote_sha" || "$local_size" != "$remote_size" ]]; then
    echo "ERROR: local/remote sha mismatch: label=$label path=$dst local_sha=$local_sha remote_sha=$remote_sha local_size=$local_size remote_size=$remote_size" >&2
    exit 1
  fi
}

REMOTE_SO="$REMOTE_ARCHIVE_DIR/tvm_tune_logs/optimized_model.so"
copy_and_verify_remote_file "$LOCAL_ARTIFACT" "$REMOTE_SO" "optimized_model.so"

if [[ -n "$DATABASE_DIR" ]]; then
  if [[ ! -f "$DATABASE_DIR/database_workload.json" || ! -f "$DATABASE_DIR/database_tuning_record.json" ]]; then
    echo "ERROR: database dir missing required JSON files: $DATABASE_DIR" >&2
    exit 1
  fi
  copy_and_verify_remote_file "$DATABASE_DIR/database_workload.json" "$REMOTE_ARCHIVE_DIR/tuning_logs/database_workload.json" "database_workload.json"
  copy_and_verify_remote_file "$DATABASE_DIR/database_tuning_record.json" "$REMOTE_ARCHIVE_DIR/tuning_logs/database_tuning_record.json" "database_tuning_record.json"
fi

LOCAL_SHA="$(local_file_sha256 "$LOCAL_ARTIFACT")"
LOCAL_SIZE="$(local_file_size_bytes "$LOCAL_ARTIFACT")"
REMOTE_META="$(remote_file_meta "$REMOTE_SO")"
REMOTE_SHA="$(meta_field "$REMOTE_META" sha256)"
REMOTE_SIZE="$(meta_field "$REMOTE_META" size_bytes)"

if [[ -z "$REMOTE_SHA" || -z "$REMOTE_SIZE" ]]; then
  echo "ERROR: failed to read remote artifact metadata: path=$REMOTE_SO" >&2
  printf '%s\n' "$REMOTE_META" >&2
  exit 1
fi

if [[ "$UPLOAD_ONLY" -eq 1 ]]; then
  printf '{"status":"upload_verified","remote_artifact":"%s","local_sha256":"%s","remote_sha256":"%s","local_size_bytes":%s,"remote_size_bytes":%s}\n' \
    "$REMOTE_SO" "$LOCAL_SHA" "$REMOTE_SHA" "$LOCAL_SIZE" "$REMOTE_SIZE"
  exit 0
fi

export INFERENCE_CURRENT_ARCHIVE="$REMOTE_ARCHIVE_DIR"
export REMOTE_TVM_JSCC_BASE_DIR="$REMOTE_ARCHIVE_DIR"
export INFERENCE_CURRENT_EXPECTED_SHA256="$REMOTE_SHA"
export INFERENCE_EXECUTION_ID="$REPORT_ID"

BENCH_JSON="$(bash "$SCRIPT_DIR/run_remote_tvm_inference_payload.sh" --variant current)"

printf '%s\n' "$BENCH_JSON"
