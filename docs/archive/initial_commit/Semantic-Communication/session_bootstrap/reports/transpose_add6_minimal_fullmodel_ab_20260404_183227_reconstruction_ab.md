# Inference Benchmark Report

- execution_id: transpose_add6_minimal_fullmodel_ab_20260404_183227_reconstruction_ab
- mode: inference_benchmark
- status: failed_current
- timestamp: 2026-04-04T18:55:57+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/transpose_add6_minimal_fullmodel_ab_20260404_183227/reconstruction_compare.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 7200
- output_shape_compare_policy: warn
- output_shape_compare_status: not_checked
- output_shape_compare_reason: not_checked
- output_shape_compare_relation: unknown
- output_shape_compare_common_shape: NA
- output_shape_delta_current_minus_baseline: NA
- output_shape_normalization_hint_center: NA
- output_shape_normalization_hint_top_left: NA
- output_shape_compare_message: Output shape comparison has not run yet.
- baseline_expected_sha256_configured: NA
- current_expected_sha256_configured: 599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542
- baseline_load_ms: 0.0
- baseline_vm_init_ms: 0.0
- baseline_run_median_ms: 1837.25
- baseline_run_mean_ms: 2064.856
- baseline_run_min_ms: 1832.6
- baseline_run_max_ms: 3798.4
- baseline_run_variance_ms2: 300828.088527
- baseline_run_count: 300
- baseline_exit_code: 0
- baseline_output_shape: NA
- baseline_output_dtype: NA
- baseline_artifact_path: /home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so
- baseline_artifact_sha256: 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849
- baseline_artifact_sha256_expected: 0
- baseline_artifact_sha256_match: False
- current_load_ms: NA
- current_vm_init_ms: NA
- current_run_median_ms: NA
- current_run_mean_ms: NA
- current_run_min_ms: NA
- current_run_max_ms: NA
- current_run_variance_ms2: NA
- current_run_count: 0
- current_exit_code: 135
- current_output_shape: NA
- current_output_dtype: NA
- current_artifact_path: NA
- current_artifact_sha256: NA
- current_artifact_sha256_expected: NA
- current_artifact_sha256_match: NA
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/transpose_add6_minimal_fullmodel_ab_20260404_183227_reconstruction_ab.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/transpose_add6_minimal_fullmodel_ab_20260404_183227_reconstruction_ab_raw.csv
