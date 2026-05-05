# Inference Benchmark Report

- execution_id: inference_local_real_reconstruction_validation_20260311
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T20:53:19+08:00
- env_file: ./session_bootstrap/tmp/local_real_reconstruction_validation_20260311.env
- model_name: jscc_local_real_reconstruction_validation
- target: {kind:llvm,mtriple:x86_64-linux-gnu,mcpu:core-avx2}
- shape_buckets: 1x32x32x32
- threads: 1
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 600
- baseline_expected_sha256_configured: NA
- current_expected_sha256_configured: NA
- baseline_load_ms: 1.363
- baseline_vm_init_ms: 0.51
- baseline_run_median_ms: 734.936
- baseline_run_mean_ms: 734.936
- baseline_run_min_ms: 734.936
- baseline_run_max_ms: 734.936
- baseline_run_variance_ms2: 0.0
- baseline_run_count: 1
- baseline_exit_code: 0
- baseline_output_shape: [1, 3, 256, 256]
- baseline_output_dtype: float32
- baseline_artifact_path: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/local_legacy_wrapper_validation_20260311/baseline_archive/tvm_tune_logs/optimized_model.so
- baseline_artifact_sha256: 9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 0.841
- current_vm_init_ms: 0.111
- current_run_median_ms: 713.969
- current_run_mean_ms: 713.969
- current_run_min_ms: 713.969
- current_run_max_ms: 713.969
- current_run_variance_ms2: 0.0
- current_run_count: 1
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/local_legacy_wrapper_validation_20260311/current_archive/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- current_artifact_sha256_expected: NA
- current_artifact_sha256_match: NA
- delta_ms_current_minus_baseline: -20.967
- improvement_pct: 2.85

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_local_real_reconstruction_validation_20260311.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_local_real_reconstruction_validation_20260311_raw.csv
