# Full Report

- execution_id: full_rpc_armv8_phytium_realcmd_round1
- mode: full
- status: success
- timestamp: 2026-03-01T20:30:57+08:00
- env_file: ./session_bootstrap/config/rpc_armv8.phytium_pi.2026-03-01.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- full_timeout_sec: 5400
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_phytium_pi_db
- baseline_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/full\" && \"$REMOTE_TVM_PYTHON\" "tvm_002.py" --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/full\" --snr \"$REMOTE_SNR_BASELINE\" --batch_size \"$REMOTE_BATCH_BASELINE\""`
- current_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/full\" && \"$REMOTE_TVM_PYTHON\" "tvm_002.py" --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/full\" --snr \"$REMOTE_SNR_CURRENT\" --batch_size \"$REMOTE_BATCH_CURRENT\""`
- baseline_elapsed_ms: 129928.662
- baseline_exit_code: 0
- baseline_count: 1
- current_elapsed_ms: 163140.347
- current_exit_code: 0
- current_count: 1
- delta_ms_current_minus_baseline: 33211.685
- improvement_pct: -25.56
- full_notes: real TVM inference via tvm_002.py; single-variable experiment keeps batch fixed at 1 and changes only SNR

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_rpc_armv8_phytium_realcmd_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_realcmd_round1_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
