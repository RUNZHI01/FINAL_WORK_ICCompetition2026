# Quick Report

- execution_id: quick_rpc_smoke_first_round_20260301_222048
- mode: quick
- status: success
- timestamp: 2026-03-01T22:20:51+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/lockfix_a_snapdragon_working.run_20260301_222048.env
- model_name: smoke_rpc_model
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224
- threads: 4
- quick_repeat: 2
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_smoke_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 2
- baseline_median_ms: 812.628
- baseline_mean_ms: 812.628
- baseline_variance_ms2: 0.013456
- baseline_exit_code: 0
- current_count: 2
- current_median_ms: 412.567
- current_mean_ms: 412.567
- current_variance_ms2: 0.082656
- current_exit_code: 0
- delta_ms_current_minus_baseline: -400.061
- improvement_pct: 49.23

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round_20260301_222048.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260301_222048_raw.csv
