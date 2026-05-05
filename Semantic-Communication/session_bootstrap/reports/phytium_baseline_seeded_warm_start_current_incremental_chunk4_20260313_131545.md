# Phytium Pi baseline-seeded current-safe one-shot summary

- mode: baseline-seeded warm-start current incremental tuning + safe runtime
- generated_at: 2026-03-13T13:54:49+08:00
- report_id: phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545
- rebuild_env: session_bootstrap/tmp/chunked_incremental_1000_20260313_012433/resume_from_chunk2_20260313_131545/chunk4.env
- inference_env: session_bootstrap/tmp/chunked_incremental_1000_20260313_012433/resume_from_chunk2_20260313_131545/inference_tvm310_safe_chunk2_b944dce3.env

## Build

- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- local_tvm_version: 0.24.dev0
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- existing_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk3_20260313_131545/tuning_logs
- output_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545
- tune_report: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/tune_report.json
- tuning_logs_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/tuning_logs
- task_summary_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/task_summary.json
- total_trials: 250
- runner: rpc
- search_mode: baseline_seeded_warm_start_incremental
- optimized_model_so: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so
- optimized_model_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- optimized_model_size_bytes: 1651136
- rebuild_elapsed_sec: 1338.2

## Remote

- remote_host: 100.121.87.73
- remote_archive_dir: /home/user/Downloads/jscc-test/jscc
- remote_so: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- remote_so_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- remote_so_size_bytes: 1651136
- artifact_hash_match: yes
- tuning_logs_uploaded: yes
- remote_tuning_logs_dir: /home/user/Downloads/jscc-test/jscc/tuning_logs
- remote_database_workload_json: /home/user/Downloads/jscc-test/jscc/tuning_logs/database_workload.json
- remote_database_tuning_record_json: /home/user/Downloads/jscc-test/jscc/tuning_logs/database_tuning_record.json

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
- load_ms: 3.766
- vm_init_ms: 1.138
- run_count: 10
- run_median_ms: 127.322
- run_mean_ms: 127.48
- run_min_ms: 126.786
- run_max_ms: 128.824
- run_variance_ms2: 0.384093
- output_shape: [1, 3, 256, 256]
- output_dtype: float32

## Logs

- orchestrator_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.log
- remote_payload_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545_remote_payload.log
- summary_json: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.json
