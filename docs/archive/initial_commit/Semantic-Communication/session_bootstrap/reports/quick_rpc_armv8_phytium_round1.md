# Quick Report

- execution_id: quick_rpc_armv8_phytium_round1
- mode: quick
- status: success
- timestamp: 2026-03-01T16:50:42+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_165035.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_phytium_pi_db
- baseline_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "test -f \"$REMOTE_TVM_PRIMARY_SO\" && test -f \"$REMOTE_TVM_PRIMARY_DB_RECORD\" && test -f \"$REMOTE_TVM_PRIMARY_DB_WORKLOAD\" && \"$REMOTE_TVM_PYTHON\" -c \"import tvm; print(tvm.__version__)\""`
- current_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "test -d \"$REMOTE_TVM_ALT_DIR\" && test -f \"$REMOTE_TVM_ALT_SO\" && ls -lh \"$REMOTE_TVM_ALT_SO\""`
- baseline_count: 1
- baseline_median_ms: 6494.468
- baseline_mean_ms: 6494.468
- baseline_variance_ms2: 0.000000
- baseline_exit_code: 0
- current_count: 1
- current_median_ms: 1046.129
- current_mean_ms: 1046.129
- current_variance_ms2: 0.000000
- current_exit_code: 0
- delta_ms_current_minus_baseline: -5448.339
- improvement_pct: 83.89

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_phytium_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_phytium_round1_raw.csv
