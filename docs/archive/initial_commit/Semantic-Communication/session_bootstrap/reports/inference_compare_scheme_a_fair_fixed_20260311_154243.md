# Inference Benchmark Report

- execution_id: inference_compare_scheme_a_fair_fixed_20260311_154243
- mode: inference_benchmark
- status: success
- timestamp: 2026-03-11T15:44:01+08:00
- env_file: ./session_bootstrap/tmp/inference_compare_scheme_a_fair_run_fixed_20260311_154243.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 10
- inference_warmup_runs: 2
- inference_timeout_sec: 5400
- baseline_expected_sha256_configured: 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849
- current_expected_sha256_configured: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- baseline_load_ms: 3.736
- baseline_vm_init_ms: 0.916
- baseline_run_median_ms: 1829.28
- baseline_run_mean_ms: 1829.958
- baseline_run_min_ms: 1827.509
- baseline_run_max_ms: 1832.405
- baseline_run_variance_ms2: 2.848837
- baseline_run_count: 10
- baseline_exit_code: 0
- baseline_output_shape: [1, 3, 249, 249]
- baseline_output_dtype: float32
- baseline_artifact_path: /home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so
- baseline_artifact_sha256: 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849
- baseline_artifact_sha256_expected: 85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849
- baseline_artifact_sha256_match: True
- current_load_ms: 3.738
- current_vm_init_ms: 3.006
- current_run_median_ms: 152.846
- current_run_mean_ms: 153.033
- current_run_min_ms: 152.668
- current_run_max_ms: 154.568
- current_run_variance_ms2: 0.279139
- current_run_count: 10
- current_exit_code: 0
- current_output_shape: [1, 3, 256, 256]
- current_output_dtype: float32
- current_artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- current_artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_expected: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- current_artifact_sha256_match: True
- delta_ms_current_minus_baseline: -1676.434
- improvement_pct: 91.64

## Commands

- baseline_cmd: REMOTE_TVM_PYTHON=/home/user/venv/bin/tvm_compat_python.sh bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline
- current_cmd: bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_compare_scheme_a_fair_fixed_20260311_154243.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_compare_scheme_a_fair_fixed_20260311_154243_raw.csv
