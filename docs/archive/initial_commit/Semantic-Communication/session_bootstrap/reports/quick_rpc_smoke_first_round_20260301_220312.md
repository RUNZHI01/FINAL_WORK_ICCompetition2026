# Quick Report

- execution_id: quick_rpc_smoke_first_round_20260301_220312
- mode: quick
- status: success
- timestamp: 2026-03-01T22:03:16+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/verifyloop3_snapdragon_working.run_20260301_220312.env
- model_name: smoke_rpc_model
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_smoke_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 3
- baseline_median_ms: 813.472
- baseline_mean_ms: 813.711
- baseline_variance_ms2: 0.711244
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 413.725
- current_mean_ms: 413.807
- current_variance_ms2: 0.935539
- current_exit_code: 0
- delta_ms_current_minus_baseline: -399.747
- improvement_pct: 49.14

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round_20260301_220312.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260301_220312_raw.csv
