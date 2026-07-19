# Quick Report

- execution_id: quick_rpc_smoke_first_round
- mode: quick
- status: success
- timestamp: 2026-03-01T13:18:09+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_131806.env
- model_name: smoke_rpc_model
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224
- threads: 4
- quick_repeat: 2
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_smoke_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 2
- baseline_median_ms: 813.226
- baseline_mean_ms: 813.226
- baseline_variance_ms2: 0.251502
- baseline_exit_code: 0
- current_count: 2
- current_median_ms: 413.209
- current_mean_ms: 413.209
- current_variance_ms2: 0.289444
- current_exit_code: 0
- delta_ms_current_minus_baseline: -400.017
- improvement_pct: 49.19

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_raw.csv
