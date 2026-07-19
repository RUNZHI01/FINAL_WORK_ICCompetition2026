# Inference Benchmark Report

- execution_id: inference_compare_currentsafe_split_topup15_validate_20260313_0002
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-13T00:13:44+08:00
- env_file: session_bootstrap/tmp/inference_compare_currentsafe_split_topup15_validate_20260313_0002.env
- model_name: jscc
- target: {kind:llvm,mtriple:aarch64-linux-gnu,mcpu:cortex-a72,mattr:[+neon],num-cores:4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 10
- inference_warmup_runs: 2
- inference_timeout_sec: 5400
- baseline_expected_sha256_configured: NA
- current_expected_sha256_configured: 65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: 1853.7
- baseline_run_mean_ms: 1854.857
- baseline_run_min_ms: 1849.4
- baseline_run_max_ms: 1932.4
- baseline_run_variance_ms2: 45.200589
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: NA
- baseline_artifact_sha256: NA
- baseline_artifact_sha256_expected: NA
- baseline_artifact_sha256_match: NA
- current_load_ms: 3.867
- current_vm_init_ms: 2.106
- current_run_median_ms: 131.343
- current_run_mean_ms: 131.576
- current_run_min_ms: 130.683
- current_run_max_ms: 133.783
- current_run_variance_ms2: 0.773951
- current_run_count: 10
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377
- current_artifact_sha256_expected: 65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1722.357
- improvement_pct: 92.91

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_compare_currentsafe_split_topup15_validate_20260313_0002.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002_raw.csv
