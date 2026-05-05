# Quick Report

- execution_id: quick_rpc_tune_safe_recheck_20260308_165534
- mode: quick
- status: success
- timestamp: 2026-03-08T17:26:06+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/recheck_envs/quick_rpc_tune_safe_recheck_20260308_165534.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- quick_repeat: 3
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_db
- baseline_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant baseline`
- current_cmd: `bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current`
- baseline_count: 3
- baseline_median_ms: 305742.841
- baseline_mean_ms: 305393.190
- baseline_variance_ms2: 451651.830460
- baseline_exit_code: 0
- current_count: 3
- current_median_ms: 304745.971
- current_mean_ms: 304721.957
- current_variance_ms2: 28748.029144
- current_exit_code: 0
- delta_ms_current_minus_baseline: -996.870
- improvement_pct: 0.33

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_rpc_tune_safe_recheck_20260308_165534.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_rpc_tune_safe_recheck_20260308_165534_raw.csv
