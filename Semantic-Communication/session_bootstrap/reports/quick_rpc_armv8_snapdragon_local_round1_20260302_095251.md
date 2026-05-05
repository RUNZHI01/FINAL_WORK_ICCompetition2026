# Quick Report

- execution_id: quick_rpc_armv8_snapdragon_local_round1_20260302_095251
- mode: quick
- status: success
- timestamp: 2026-03-02T10:03:14+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.snapdragon_local.2026-03-01.run_20260302_095251.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_snapdragon_local_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 1
- baseline_median_ms: 310320.827
- baseline_mean_ms: 310320.827
- baseline_variance_ms2: 0.000000
- baseline_exit_code: 0
- current_count: 1
- current_median_ms: 310658.588
- current_mean_ms: 310658.588
- current_variance_ms2: 0.000000
- current_exit_code: 0
- delta_ms_current_minus_baseline: 337.761
- improvement_pct: -0.11

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_armv8_snapdragon_local_round1_20260302_095251.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_armv8_snapdragon_local_round1_20260302_095251_raw.csv
