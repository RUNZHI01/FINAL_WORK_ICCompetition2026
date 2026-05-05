# Quick Report

- execution_id: quick_rpc_smoke_first_round_20260302_001644
- mode: quick
- status: success
- timestamp: 2026-03-02T00:16:48+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/offline_prep_snapdragon_working.run_20260302_001644.env
- model_name: smoke_rpc_model
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_smoke_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 3
- baseline_median_ms: 816.228
- baseline_mean_ms: 816.410
- baseline_variance_ms2: 0.557102
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 417.288
- current_mean_ms: 417.815
- current_variance_ms2: 0.865664
- current_exit_code: 0
- delta_ms_current_minus_baseline: -398.940
- improvement_pct: 48.88

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_smoke_first_round_20260302_001644.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_smoke_first_round_20260302_001644_raw.csv
