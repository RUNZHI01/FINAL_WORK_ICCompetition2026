# Inference Benchmark Report

- execution_id: inference_local_legacy_wrapper_20260311_015655
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T13:36:39+08:00
- env_file: session_bootstrap/tmp/local_legacy_wrapper_validation_20260311/inference_local_legacy_wrapper.env
- model_name: jscc_local_wrapper_validation
- target: {kind:llvm,mtriple:x86_64-linux-gnu,mcpu:core-avx2}
- shape_buckets: 1x32x32x32
- threads: 1
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 4
- inference_warmup_runs: 1
- inference_timeout_sec: 600
- baseline_expected_sha256_configured: 9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8
- current_expected_sha256_configured: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 709.385
- baseline_run_mean_ms: 709.571
- baseline_run_min_ms: 706.83
- baseline_run_max_ms: 712.683
- baseline_run_variance_ms2: 5.237429
- baseline_run_count: 4
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 0.923
- current_vm_init_ms: 0.084
- current_run_median_ms: 693.88
- current_run_mean_ms: 695.788
- current_run_min_ms: 691.081
- current_run_max_ms: 704.308
- current_run_variance_ms2: 27.25322
- current_run_count: 4
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/local_legacy_wrapper_validation_20260311/current_archive/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- current_artifact_sha256_expected: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -15.505
- improvement_pct: 2.19

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_local_legacy_wrapper_20260311_015655.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_local_legacy_wrapper_20260311_015655_raw.csv
