# Inference Benchmark Report

- execution_id: inference_legacy_parse_ok_20260308_1807
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-08T18:03:29+08:00
- env_file: /tmp/infer_legacy_parse_ok2_nuycVB.env
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
- current_load_ms: 4.0
- current_vm_init_ms: 1.0
- current_run_median_ms: 115.0
- current_run_mean_ms: 116.0
- current_run_min_ms: 114.0
- current_run_max_ms: 119.0
- current_run_variance_ms2: 4.0
- current_run_count: 3
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- delta_ms_current_minus_baseline: 0.600
- improvement_pct: -0.52

## Commands

- baseline_cmd: bash /tmp/infer_legacy_base_syvZhL.sh
- current_cmd: bash /tmp/infer_legacy_cur_qQmHH7.sh

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_legacy_parse_ok_20260308_1807.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_legacy_parse_ok_20260308_1807_raw.csv
