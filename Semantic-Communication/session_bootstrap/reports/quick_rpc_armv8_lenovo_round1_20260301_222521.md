# Quick Report

- execution_id: quick_rpc_armv8_lenovo_round1_20260301_222521
- mode: quick
- status: success
- timestamp: 2026-03-01T22:25:25+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/msloop_prep_snapdragon_working.run_20260301_222521.env
- model_name: replace_with_model_name
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 3
- baseline_median_ms: 814.126
- baseline_mean_ms: 814.328
- baseline_variance_ms2: 1.237203
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 412.592
- current_mean_ms: 413.422
- current_variance_ms2: 2.443960
- current_exit_code: 0
- delta_ms_current_minus_baseline: -401.534
- improvement_pct: 49.32

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_lenovo_round1_20260301_222521.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_lenovo_round1_20260301_222521_raw.csv
