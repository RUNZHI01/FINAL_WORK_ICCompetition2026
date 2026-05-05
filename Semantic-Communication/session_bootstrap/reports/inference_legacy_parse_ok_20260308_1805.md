# Inference Benchmark Report

- execution_id: inference_legacy_parse_ok_20260308_1805
- mode: inference_benchmark
- status: failed_baseline
- timestamp: 2026-03-08T18:03:11+08:00
- env_file: /tmp/infer_legacy_parse_ok_wD79Pn.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 30
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: NA
- baseline_run_mean_ms: NA
- baseline_run_min_ms: NA
- baseline_run_max_ms: NA
- baseline_run_variance_ms2: NA
- baseline_run_count: 0
- baseline_exit_code: 2
- baseline_output_shape: NA
- baseline_output_dtype: NA
- current_load_ms: NA
- current_vm_init_ms: NA
- current_run_median_ms: NA
- current_run_mean_ms: NA
- current_run_min_ms: NA
- current_run_max_ms: NA
- current_run_variance_ms2: NA
- current_run_count: 0
- current_exit_code: NA
- current_output_shape: NA
- current_output_dtype: NA
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Commands

- baseline_cmd: python3 -c print('2026-03-01\ 20:26:15,743\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1194\ 秒');print('2026-03-01\ 20:26:16,014\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1141\ 秒');print('2026-03-01\ 20:26:16,249\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1144\ 秒')
- current_cmd: python3 -c print('{\"load_ms\":4.0,\"vm_init_ms\":1.0,\"run_median_ms\":115.0,\"run_mean_ms\":116.0,\"run_min_ms\":114.0,\"run_max_ms\":119.0,\"run_variance_ms2\":4.0,\"run_count\":3,\"output_shape\":[1,3,256,256],\"output_dtype\":\"float32\"}')

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_legacy_parse_ok_20260308_1805.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_legacy_parse_ok_20260308_1805_raw.csv
