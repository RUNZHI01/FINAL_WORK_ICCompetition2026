# Inference Benchmark Report

- execution_id: inference_real_reconstruction_compare_run_20260311_212301
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T21:34:34+08:00
- env_file: ./session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
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
- baseline_run_median_ms: 1830.3
- baseline_run_mean_ms: 1831.471
- baseline_run_min_ms: 1826.3
- baseline_run_max_ms: 1862.8
- baseline_run_variance_ms2: 26.853192
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 2.65
- current_vm_init_ms: 0.464
- current_run_median_ms: 255.931
- current_run_mean_ms: 255.882
- current_run_min_ms: 214.649
- current_run_max_ms: 612.877
- current_run_variance_ms2: 677.402119
- current_run_count: 300
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_expected: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1574.369
- improvement_pct: 86.02

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_real_reconstruction_compare_run_20260311_212301.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301_raw.csv
