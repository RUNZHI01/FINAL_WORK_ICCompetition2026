# Inference Benchmark Report

- execution_id: inference_compare_baseline_vs_currentsafe_rerun2_20260311_124453
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T12:55:10+08:00
- env_file: ./session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_rerun2_20260311_124453.env
- model_name: jscc
- target: {kind:llvm,mtriple:aarch64-linux-gnu,mcpu:cortex-a72,mattr:[+neon],num-cores:4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 10
- inference_warmup_runs: 2
- inference_timeout_sec: 5400
- current_expected_sha256_configured: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 1835.7
- baseline_run_mean_ms: 1844.507
- baseline_run_min_ms: 1832.0
- baseline_run_max_ms: 2061.2
- baseline_run_variance_ms2: 820.63328
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 3.72
- current_vm_init_ms: 2.844
- current_run_median_ms: 152.782
- current_run_mean_ms: 152.868
- current_run_min_ms: 152.283
- current_run_max_ms: 153.854
- current_run_variance_ms2: 0.185529
- current_run_count: 10
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_expected: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1682.918
- improvement_pct: 91.68

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_compare_baseline_vs_currentsafe_rerun2_20260311_124453.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun2_20260311_124453_raw.csv
