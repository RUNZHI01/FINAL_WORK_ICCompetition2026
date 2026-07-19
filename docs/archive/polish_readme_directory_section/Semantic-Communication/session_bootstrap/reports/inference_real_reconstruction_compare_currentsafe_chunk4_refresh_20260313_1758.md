# Inference Benchmark Report

- execution_id: inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-13T18:22:47+08:00
- env_file: ./session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
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
- current_expected_sha256_configured: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 1850.0
- baseline_run_mean_ms: 1850.857
- baseline_run_min_ms: 1846.2
- baseline_run_max_ms: 1892.1
- baseline_run_variance_ms2: 23.074646
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 2.629
- current_vm_init_ms: 0.461
- current_run_median_ms: 230.339
- current_run_mean_ms: 230.719
- current_run_min_ms: 189.687
- current_run_max_ms: 637.698
- current_run_variance_ms2: 752.430274
- current_run_count: 300
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- current_artifact_sha256_expected: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1619.661
- improvement_pct: 87.55

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758_raw.csv
