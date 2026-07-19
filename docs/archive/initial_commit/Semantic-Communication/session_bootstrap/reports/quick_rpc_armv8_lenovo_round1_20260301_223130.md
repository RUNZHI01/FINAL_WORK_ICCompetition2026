# Quick Report

- execution_id: quick_rpc_armv8_lenovo_round1_20260301_223130
- mode: quick
- status: success
- timestamp: 2026-03-01T22:31:33+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/aligncheck_snapdragon_working.run_20260301_223130.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 2
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db
- baseline_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "baseline $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.8`
- current_cmd: `mkdir -p "$TUNING_DB_DIR/quick" && echo "current $(date -Iseconds)" >> "$TUNING_DB_DIR/quick/history.log" && sleep 0.4`
- baseline_count: 2
- baseline_median_ms: 817.322
- baseline_mean_ms: 817.322
- baseline_variance_ms2: 0.345744
- baseline_exit_code: 0
- current_count: 2
- current_median_ms: 415.695
- current_mean_ms: 415.695
- current_variance_ms2: 1.136356
- current_exit_code: 0
- delta_ms_current_minus_baseline: -401.627
- improvement_pct: 49.14

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_lenovo_round1_20260301_223130.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_lenovo_round1_20260301_223130_raw.csv
