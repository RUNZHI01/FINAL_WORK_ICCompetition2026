# Quick Report

- execution_id: quick_rpc_armv8_snapdragon_local_round1_20260302_015535
- mode: quick
- status: failed_baseline
- timestamp: 2026-03-02T01:55:36+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/agent_loops/msloop_prep_local_short_snapdragon_working.run_20260302_015535.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_snapdragon_local_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 0
- baseline_median_ms: NA
- baseline_mean_ms: NA
- baseline_variance_ms2: NA
- baseline_exit_code: 127
- current_count: 0
- current_median_ms: NA
- current_mean_ms: NA
- current_variance_ms2: NA
- current_exit_code: NA
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_snapdragon_local_round1_20260302_015535.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_015535_raw.csv
