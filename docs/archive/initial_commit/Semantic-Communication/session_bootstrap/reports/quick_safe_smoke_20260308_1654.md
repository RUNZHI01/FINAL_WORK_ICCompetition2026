# Quick Report

- execution_id: quick_safe_smoke_20260308_1654
- mode: quick
- status: success
- timestamp: 2026-03-08T16:54:34+08:00
- env_file: /tmp/quick_safe_smoke_s3S7pI.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 1
- baseline_median_ms: 10387.873
- baseline_mean_ms: 10387.873
- baseline_variance_ms2: 0.000000
- baseline_exit_code: 0
- current_count: 1
- current_median_ms: 10550.650
- current_mean_ms: 10550.650
- current_variance_ms2: 0.000000
- current_exit_code: 0
- delta_ms_current_minus_baseline: 162.777
- improvement_pct: -1.57

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_safe_smoke_20260308_1654.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_safe_smoke_20260308_1654_raw.csv
