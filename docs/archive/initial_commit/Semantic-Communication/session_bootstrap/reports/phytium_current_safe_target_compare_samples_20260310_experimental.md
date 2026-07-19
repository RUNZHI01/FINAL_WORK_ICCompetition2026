# Phytium Pi baseline-seeded current-safe one-shot summary

- mode: baseline-seeded warm-start current rebuild-only + safe runtime
- generated_at: 2026-03-10T03:50:56+08:00
- report_id: phytium_current_safe_target_compare_samples_20260310_experimental
- rebuild_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- inference_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
- historical_seed_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs
- total_trials: 0
- runner: local
- search_mode: baseline_seeded_rebuild_only
- interpretation: baseline-seeded warm-start current rebuild-only evidence only; not an independent fresh current line

## Build

- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}
- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- local_tvm_version: 0.24.dev0
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- existing_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs
- output_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_current_safe_target_compare_samples_20260310/experimental
- tune_report: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_current_safe_target_compare_samples_20260310/experimental/tune_report.json
- optimized_model_so: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_current_safe_target_compare_samples_20260310/experimental/optimized_model.so
- optimized_model_sha256: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- optimized_model_size_bytes: 2060848
- rebuild_elapsed_sec: 3.5

## Remote

- remote_host: 100.121.87.73
- remote_archive_dir: /home/user/Downloads/jscc-test/jscc
- remote_so: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- remote_so_sha256: 2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449
- remote_so_size_bytes: 2060848
- artifact_hash_match: yes

## Safe Runtime Inference

- runtime: TVM 0.24.dev0 safe path only
- remote_tvm_python: env TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages /home/user/anaconda3/envs/tvm310_safe/bin/python
- remote_tvm_version: 0.24.dev0
- input_shape: 1,32,32,32
- input_dtype: float32
- entry: main
- warmup_runs: 2
- repeat: 10
- device: cpu
- load_ms: 4.258
- vm_init_ms: 0.514
- run_count: 10
- run_median_ms: 2478.651
- run_mean_ms: 2478.329
- run_min_ms: 2477.343
- run_max_ms: 2479.036
- run_variance_ms2: 0.464439
- output_shape: [1, 3, 256, 256]
- output_dtype: float32

## Logs

- orchestrator_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_current_safe_target_compare_samples_20260310_experimental.log
- remote_payload_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_current_safe_target_compare_samples_20260310_experimental_remote_payload.log
- summary_json: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_current_safe_target_compare_samples_20260310_experimental.json
