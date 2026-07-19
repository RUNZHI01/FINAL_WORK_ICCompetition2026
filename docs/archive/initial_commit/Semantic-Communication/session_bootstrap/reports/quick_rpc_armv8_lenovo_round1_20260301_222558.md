# Quick Report

- execution_id: quick_rpc_armv8_lenovo_round1_20260301_222558
- mode: quick
- status: success
- timestamp: 2026-03-01T22:26:02+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/msloop_prep_snapdragon_working.run_20260301_222558.env
- model_name: replace_with_model_name
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 3
- baseline_median_ms: 811.809
- baseline_mean_ms: 812.278
- baseline_variance_ms2: 0.597901
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 412.270
- current_mean_ms: 412.333
- current_variance_ms2: 0.430253
- current_exit_code: 0
- delta_ms_current_minus_baseline: -399.539
- improvement_pct: 49.22

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_lenovo_round1_20260301_222558.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_lenovo_round1_20260301_222558_raw.csv
