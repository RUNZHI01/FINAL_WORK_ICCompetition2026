# Quick Report

- execution_id: quick_rpc_armv8_lenovo_round1
- mode: quick
- status: success
- timestamp: 2026-03-01T14:44:59+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_144456.env
- model_name: replace_with_model_name
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 2
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 2
- baseline_median_ms: 812.024
- baseline_mean_ms: 812.024
- baseline_variance_ms2: 0.091204
- baseline_exit_code: 0
- current_count: 2
- current_median_ms: 412.241
- current_mean_ms: 412.241
- current_variance_ms2: 0.152490
- current_exit_code: 0
- delta_ms_current_minus_baseline: -399.783
- improvement_pct: 49.23

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_lenovo_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_lenovo_round1_raw.csv
