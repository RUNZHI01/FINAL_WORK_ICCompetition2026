# Quick Report

- execution_id: quick_rpc_tune_recheck_20260308_162420
- mode: quick
- status: failed_current
- timestamp: 2026-03-08T17:26:00+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/recheck_envs/quick_rpc_tune_recheck_20260308_162420.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 3
- baseline_median_ms: 329030.068
- baseline_mean_ms: 329509.089
- baseline_variance_ms2: 1480987.563965
- baseline_exit_code: 0
- current_count: 0
- current_median_ms: NA
- current_mean_ms: NA
- current_variance_ms2: NA
- current_exit_code: 124
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_tune_recheck_20260308_162420.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_recheck_20260308_162420_raw.csv
