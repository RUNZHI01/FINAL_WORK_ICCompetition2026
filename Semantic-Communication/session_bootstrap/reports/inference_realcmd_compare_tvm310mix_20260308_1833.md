# Inference Benchmark Report

- execution_id: inference_realcmd_compare_tvm310mix_20260308_1833
- mode: inference_benchmark
- status: failed_baseline
- timestamp: 2026-03-08T18:47:58+08:00
- env_file: /tmp/infer_realcmd_compare_tvm310mix2_0T1l01.env
- model_name: jscc
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- input_shape: 1,32,32,32
- input_dtype: float32
- inference_repeat: 1
- inference_warmup_runs: 0
- inference_timeout_sec: 1800
- baseline_load_ms: NA
- baseline_vm_init_ms: NA
- baseline_run_median_ms: NA
- baseline_run_mean_ms: NA
- baseline_run_min_ms: NA
- baseline_run_max_ms: NA
- baseline_run_variance_ms2: NA
- baseline_run_count: 0
- baseline_exit_code: 1
- baseline_output_shape: NA
- baseline_output_dtype: NA
- current_load_ms: NA
- current_vm_init_ms: NA
- current_run_median_ms: NA
- current_run_mean_ms: NA
- current_run_min_ms: NA
- current_run_max_ms: NA
- current_run_variance_ms2: NA
- current_run_count: 0
- current_exit_code: NA
- current_output_shape: NA
- current_output_dtype: NA
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Commands

- baseline_cmd: bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" --port "${REMOTE_SSH_PORT:-22}" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/inference_benchmark_baseline\" && PYTHONPATH=\"$REMOTE_TORCH_PYTHONPATH\" \"$REMOTE_TVM310_PYTHON\" tvm_002.py --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/inference_benchmark_baseline\" --snr \"$REMOTE_SNR_BASELINE\" --batch_size \"$REMOTE_BATCH_BASELINE\""
- current_cmd: bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" --port "${REMOTE_SSH_PORT:-22}" -- "set -euo pipefail && cd \"$REMOTE_JSCC_DIR\" && mkdir -p \"$REMOTE_OUTPUT_BASE/inference_benchmark_current\" && PYTHONPATH=\"$REMOTE_TORCH_PYTHONPATH\" \"$REMOTE_TVM310_PYTHON\" tvm_002.py --input_dir \"$REMOTE_INPUT_DIR\" --output_dir \"$REMOTE_OUTPUT_BASE/inference_benchmark_current\" --snr \"$REMOTE_SNR_CURRENT\" --batch_size \"$REMOTE_BATCH_CURRENT\""

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/inference_realcmd_compare_tvm310mix_20260308_1833.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/inference_realcmd_compare_tvm310mix_20260308_1833_raw.csv
