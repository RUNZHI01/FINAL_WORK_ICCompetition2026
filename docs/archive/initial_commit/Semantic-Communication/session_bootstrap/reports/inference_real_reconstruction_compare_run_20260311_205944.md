# Inference Benchmark Report

- execution_id: inference_real_reconstruction_compare_run_20260311_205944
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T21:11:20+08:00
- env_file: ./session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_205944.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 7200
- baseline_expected_sha256_configured: NA
- current_expected_sha256_configured: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 1833.5
- baseline_run_mean_ms: 1835.175
- baseline_run_min_ms: 1830.2
- baseline_run_max_ms: 1886.4
- baseline_run_variance_ms2: 42.846625
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 3.968
- current_vm_init_ms: 2.943
- current_run_median_ms: NA
- current_run_mean_ms: NA
- current_run_min_ms: NA
- current_run_max_ms: NA
- current_run_variance_ms2: 0.0
- current_run_count: 0
- current_exit_code: 0
- current_output_shape: NA
- current_output_dtype: NA
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_expected: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1833.500
- improvement_pct: 100.00

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_real_reconstruction_compare_run_20260311_205944.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_205944_raw.csv
