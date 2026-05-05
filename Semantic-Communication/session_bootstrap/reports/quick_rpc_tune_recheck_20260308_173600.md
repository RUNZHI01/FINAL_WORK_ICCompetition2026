# Quick Report

- execution_id: quick_rpc_tune_recheck_20260308_173600
- mode: quick
- status: success
- timestamp: 2026-03-08T18:06:27+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/recheck_envs/quick_rpc_tune_recheck_20260308_173600.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 3
- baseline_median_ms: 304061.589
- baseline_mean_ms: 304037.593
- baseline_variance_ms2: 13850.115250
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 303992.103
- current_mean_ms: 304533.287
- current_variance_ms2: 688455.117310
- current_exit_code: 0
- delta_ms_current_minus_baseline: -69.486
- improvement_pct: 0.02

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_tune_recheck_20260308_173600.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_recheck_20260308_173600_raw.csv
