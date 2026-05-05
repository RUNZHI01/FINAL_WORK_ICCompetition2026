# Phytium Pi baseline-seeded current-safe one-shot summary

- mode: baseline-seeded warm-start current incremental tuning + safe runtime
- generated_at: 2026-03-11T00:25:12+08:00
- report_id: phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix
- rebuild_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- inference_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env

## Build

- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- local_tvm_version: 0.24.dev0
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- existing_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs
- output_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix
- tune_report: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix/tune_report.json
- tuning_logs_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix/tuning_logs
- task_summary_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix/task_summary.json
- total_trials: 160
- runner: rpc
- search_mode: baseline_seeded_warm_start_incremental
- optimized_model_so: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix/optimized_model.so
- optimized_model_sha256: d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6
- optimized_model_size_bytes: 1684408
- rebuild_elapsed_sec: 984.6

## Remote

- remote_host: 100.121.87.73
- remote_archive_dir: /home/user/Downloads/jscc-test/jscc
- remote_so: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- remote_so_sha256: d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6
- remote_so_size_bytes: 1684408
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
- load_ms: 4.121
- vm_init_ms: 2.891
- run_count: 10
- run_median_ms: 2476.478
- run_mean_ms: 2477.091
- run_min_ms: 2475.502
- run_max_ms: 2482.568
- run_variance_ms2: 3.737573
- output_shape: [1, 3, 256, 256]
- output_dtype: float32

## Logs

- orchestrator_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix.log
- remote_payload_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix_remote_payload.log
- summary_json: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_round2_20260311_hotfix.json
