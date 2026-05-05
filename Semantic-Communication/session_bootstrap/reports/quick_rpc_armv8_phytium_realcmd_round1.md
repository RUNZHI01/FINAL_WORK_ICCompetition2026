# Quick Report

- execution_id: quick_rpc_armv8_phytium_realcmd_round1
- mode: quick
- status: success
- timestamp: 2026-03-01T20:35:15+08:00
- env_file: ./session_bootstrap/config/rpc_armv8.phytium_pi.2026-03-01.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_phytium_pi_db
- baseline_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/quick_baseline\" && \"$REMOTE_TVM_PYTHON\" "tvm_001.py" --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/quick_baseline\" --snr \"$REMOTE_SNR_BASELINE\""`
- current_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/quick_current\" && \"$REMOTE_TVM_PYTHON\" "tvm_001.py" --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/quick_current\" --snr \"$REMOTE_SNR_CURRENT\""`
- baseline_count: 1
- baseline_median_ms: 173616.079
- baseline_mean_ms: 173616.079
- baseline_variance_ms2: 0.000000
- baseline_exit_code: 0
- current_count: 1
- current_median_ms: 256881.177
- current_mean_ms: 256881.177
- current_variance_ms2: 0.000000
- current_exit_code: 0
- delta_ms_current_minus_baseline: 83265.098
- improvement_pct: -47.96

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_phytium_realcmd_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_phytium_realcmd_round1_raw.csv
