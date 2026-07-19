# Phytium Pi baseline-seeded current-safe one-shot summary

- mode: baseline-seeded warm-start current rebuild-only + safe runtime
- generated_at: 2026-03-31T04:42:03+08:00
- report_id: phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114
- rebuild_env: ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_hook_overlay.env
- inference_env: ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_validate_inference.env

## Build

- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- local_tvm_version: 0.24.dev0
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- existing_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
- output_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114
- tune_report: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114/tune_report.json
- tuning_logs_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114/tuning_logs
- task_summary_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114/task_summary.json
- total_trials: 0
- runner: local
- search_mode: baseline_seeded_rebuild_only
- optimized_model_so: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114/optimized_model.so
- optimized_model_sha256: b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28
- optimized_model_size_bytes: 1680408
- rebuild_elapsed_sec: 14.9

## Remote

- remote_host: 100.121.87.73
- remote_archive_dir: /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9
- remote_so: /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so
- remote_so_sha256: b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28
- remote_so_size_bytes: 1680408
- artifact_hash_match: yes
- tuning_logs_uploaded: no
- remote_tuning_logs_dir: NA
- remote_database_workload_json: NA
- remote_database_tuning_record_json: NA

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
- load_ms: 3.806
- vm_init_ms: 0.432
- run_count: 10
- run_median_ms: 655.693
- run_mean_ms: 655.679
- run_min_ms: 654.227
- run_max_ms: 657.46
- run_variance_ms2: 1.233527
- output_shape: [1, 3, 256, 256]
- output_dtype: float32

## Logs

- orchestrator_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.log
- remote_payload_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114_remote_payload.log
- summary_json: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.json
