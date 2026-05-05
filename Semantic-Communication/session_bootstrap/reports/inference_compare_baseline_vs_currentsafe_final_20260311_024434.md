# Inference Benchmark Report

- execution_id: inference_compare_baseline_vs_currentsafe_final_20260311_024434
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T07:15:56+08:00
- env_file: ./session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_final_20260311_024434.env
- model_name: jscc
- target: {kind:llvm,mtriple:aarch64-linux-gnu,mcpu:cortex-a72,mattr:[+neon],num-cores:4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 10
- inference_warmup_runs: 2
- inference_timeout_sec: 5400
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 1832.1
- baseline_run_mean_ms: 1833.184
- baseline_run_min_ms: 1829.6
- baseline_run_max_ms: 1868.1
- baseline_run_variance_ms2: 22.308233
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- current_load_ms: 4.035
- current_vm_init_ms: 3.782
- current_run_median_ms: 2480.189
- current_run_mean_ms: 2480.056
- current_run_min_ms: 2478.958
- current_run_max_ms: 2481.397
- current_run_variance_ms2: 0.472978
- current_run_count: 10
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- delta_ms_current_minus_baseline: 648.089
- improvement_pct: -35.37

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_compare_baseline_vs_currentsafe_final_20260311_024434.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_final_20260311_024434_raw.csv
