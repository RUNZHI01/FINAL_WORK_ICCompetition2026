#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT=/home/tianxing/tvm_metaschedule_execution_project
SSH_SCRIPT=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/ssh_with_password.sh
PAYLOAD_RUNNER=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_tvm_inference_payload.sh
LOCAL_ARCHIVE_ROOT=session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/baseline_candidate_archive
REMOTE_ARCHIVE_DIR=/home/user/Downloads/baseline_current_safe_bridge/baseline_export_bridge_local_smoke_20260320_1
REMOTE_HOST=100.121.87.73
REMOTE_USER=user
REMOTE_PASS=user
REMOTE_PORT=22
REMOTE_TVM_PYTHON='env LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages /home/user/anaconda3/envs/tvm310_safe/bin/python'
INPUT_SHAPE=1,32,32,32
INPUT_DTYPE=float32
ENTRY_NAME=main
WARMUP_RUNS=0
REPEAT_COUNT=1
DEVICE_NAME=cpu
EXPECTED_SHA256=75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

upload_file() {
  local src_path="$1"
  local dst_path="$2"
  bash "$SSH_SCRIPT" \
    --host "$REMOTE_HOST" \
    --user "$REMOTE_USER" \
    --pass "$REMOTE_PASS" \
    --port "$REMOTE_PORT" \
    -- "mkdir -p $(shell_quote "$(dirname "$dst_path")") && cat > $(shell_quote "$dst_path")" \
    <"$src_path"
}

upload_file "$LOCAL_ARCHIVE_ROOT/tvm_tune_logs/optimized_model.so" "$REMOTE_ARCHIVE_DIR/tvm_tune_logs/optimized_model.so"
upload_file "$LOCAL_ARCHIVE_ROOT/tuning_logs/database_workload.json" "$REMOTE_ARCHIVE_DIR/tuning_logs/database_workload.json"
upload_file "$LOCAL_ARCHIVE_ROOT/tuning_logs/database_tuning_record.json" "$REMOTE_ARCHIVE_DIR/tuning_logs/database_tuning_record.json"

export REMOTE_MODE=ssh
export REMOTE_HOST
export REMOTE_USER
export REMOTE_PASS
export REMOTE_SSH_PORT="$REMOTE_PORT"
export REMOTE_TVM_PYTHON
export INFERENCE_BASELINE_ARCHIVE="$REMOTE_ARCHIVE_DIR"
export INFERENCE_BASELINE_EXPECTED_SHA256="$EXPECTED_SHA256"
export TUNE_INPUT_SHAPE="$INPUT_SHAPE"
export TUNE_INPUT_DTYPE="$INPUT_DTYPE"
export INFERENCE_ENTRY="$ENTRY_NAME"
export INFERENCE_WARMUP_RUNS="$WARMUP_RUNS"
export INFERENCE_REPEAT="$REPEAT_COUNT"
export INFERENCE_DEVICE="$DEVICE_NAME"

bash "$PAYLOAD_RUNNER" --variant baseline

echo
echo "If the baseline candidate reports [1,3,256,256], rerun the fair compare with this archive as baseline."
