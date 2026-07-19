# Phytium Pi baseline-style current rebuild summary

- mode: baseline-style current rebuild-only + payload-symmetric runtime
- generated_at: 2026-03-20T16:28:21+08:00
- report_id: phytium_baseline_style_current_rebuild_20260320_162720
- rebuild_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- inference_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env

## Build

- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- local_tvm_version: 0.24.dev0
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- existing_db: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs
- output_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_style_current_rebuild_20260320_162720
- tune_report: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_style_current_rebuild_20260320_162720/tune_report.json
- tuning_logs_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_style_current_rebuild_20260320_162720/tuning_logs
- task_summary_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/phytium_baseline_style_current_rebuild_20260320_162720/task_summary.json
- total_trials: 0
- runner: local
- search_mode: baseline_seeded_rebuild_only
- optimized_model_so: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/phytium_baseline_style_current_rebuild_20260320_162720/optimized_model.so
- optimized_model_sha256: 75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080
- optimized_model_size_bytes: 1675320
- rebuild_elapsed_sec: 4.7

## Remote

- remote_host: 100.121.87.73
- remote_archive_dir: /home/user/Downloads/jscc-test/jscc
- remote_so: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- remote_so_sha256: 75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080
- remote_so_size_bytes: 1675320
- artifact_hash_match: yes
- tuning_logs_uploaded: no
- remote_tuning_logs_dir: NA
- remote_database_workload_json: NA
- remote_database_tuning_record_json: NA

## Payload-Symmetric Inference

- runtime: payload-symmetric runtime path: load_module() once -> VM init once -> warmup -> repeated main()
- remote_tvm_python: env TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages /home/user/anaconda3/envs/tvm310_safe/bin/python
- remote_tvm_version: 0.24.dev0
- input_shape: 1,32,32,32
- input_dtype: float32
- entry: main
- warmup_runs: 2
- repeat: 10
- device: cpu
- load_ms: 3.747
- vm_init_ms: 0.479
- run_count: 10
- run_median_ms: 2463.239
- run_mean_ms: 2463.315
- run_min_ms: 2462.356
- run_max_ms: 2464.276
- run_variance_ms2: 0.34533
- output_shape: [1, 3, 256, 256]
- output_dtype: float32

## Logs

- orchestrator_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_style_current_rebuild_20260320_162720.log
- remote_payload_log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_baseline_style_current_rebuild_20260320_162720_remote_payload.log
- summary_json: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_baseline_style_current_rebuild_20260320_162720.json
