# Inference Benchmark Report

- execution_id: inference_safe_smoke_20260308_1750
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-08T17:54:09+08:00
- env_file: /tmp/infer_smoke_vuTyCC.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 180
- baseline_load_ms: 4.022
- baseline_vm_init_ms: 3.371
- baseline_run_median_ms: 2555.383
- baseline_run_mean_ms: 2555.383
- baseline_run_min_ms: 2555.383
- baseline_run_max_ms: 2555.383
- baseline_run_variance_ms2: 0.0
- baseline_run_count: 1
- baseline_exit_code: 0
- baseline_output_shape: [1, 3, 256, 256]
- baseline_output_dtype: float32
- current_load_ms: 4.184
- current_vm_init_ms: 0.526
- current_run_median_ms: 2511.961
- current_run_mean_ms: 2511.961
- current_run_min_ms: 2511.961
- current_run_max_ms: 2511.961
- current_run_variance_ms2: 0.0
- current_run_count: 1
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- delta_ms_current_minus_baseline: -43.422
- improvement_pct: 1.70

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_safe_smoke_20260308_1750.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_safe_smoke_20260308_1750_raw.csv
