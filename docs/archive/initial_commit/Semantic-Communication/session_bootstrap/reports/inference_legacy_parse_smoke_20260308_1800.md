# Inference Benchmark Report

- execution_id: inference_legacy_parse_smoke_20260308_1800
- mode: inference_benchmark
- status: failed_current
- timestamp: 2026-03-08T18:02:35+08:00
- env_file: /tmp/infer_legacy_parse_nNOx32.env
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
- baseline_run_median_ms: 114.4
- baseline_run_mean_ms: 115.967
- baseline_run_min_ms: 114.1
- baseline_run_max_ms: 119.4
- baseline_run_variance_ms2: 5.908889
- baseline_run_count: 3
- baseline_exit_code: 0
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
- current_exit_code: 1
- current_output_shape: NA
- current_output_dtype: NA
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Commands

- baseline_cmd: printf 2026-03-01\ 20:26:15,743\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1194\ 秒\\n2026-03-01\ 20:26:16,014\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1141\ 秒\\n2026-03-01\ 20:26:16,249\ -\ INFO\ -\ 批量推理时间（1\ 个样本）:\ 0.1144\ 秒\\n
- current_cmd: printf {"load_ms":4.0,"vm_init_ms":1.0,"run_median_ms":115.0,"run_mean_ms":116.0,"run_min_ms":114.0,"run_max_ms":119.0,"run_variance_ms2":4.0,"run_count":3,"output_shape":[1,3,256,256],"output_dtype":"float32"}\\n

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_legacy_parse_smoke_20260308_1800.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_legacy_parse_smoke_20260308_1800_raw.csv
