# Baseline export bridge summary

- report_id: baseline_export_bridge_local_smoke_20260320_1
- rebuild_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- source_db: session_bootstrap/tmp/rpc_tune_output_20260306_195752/tuning_logs
- source_archive: None
- source_db_sha256_workload: d677de5fed68b37d02c6818c8c5b203bd4045ea3a78569ee37c3b6f20c053623
- source_db_sha256_tuning_record: 5d50a197741204c1d11db0e03d449d29fa1bfc23e8937c928fd6307deea8e173

## Local build

- local_builder_python: /home/tianxing/.venvs/tvm-ms/bin/python
- onnx_model: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- optimized_model_so: session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/build_output/optimized_model.so
- optimized_model_sha256: 75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080
- optimized_model_size_bytes: 1675320
- tune_report: session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/build_output/tune_report.json
- task_summary_json: session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/build_output/task_summary.json

## Candidate archive

- archive_root: session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/baseline_candidate_archive
- artifact_path: session_bootstrap/tmp/baseline_export_bridge_local_smoke_20260320_1/baseline_candidate_archive/tvm_tune_logs/optimized_model.so
- artifact_sha256: 75f480ab8d272fc7cb9174ed55afef8a86ed17d67bffe8168d5ca4afbae31080
- artifact_size_bytes: 1675320

## Local current-safe probe

- payload_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/logs/baseline_export_bridge_local_smoke_20260320_1.local_probe.log
- status: current_safe_probe_succeeded
- output_shape: [1, 3, 256, 256]
- output_dtype: float32
- expected_output_shape: [1, 3, 256, 256]
- output_contract_match: True

## Board stage

- remote_archive_dir: /home/user/Downloads/baseline_current_safe_bridge/baseline_export_bridge_local_smoke_20260320_1
- board_stage_script: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/baseline_export_bridge_local_smoke_20260320_1_board_stage.sh

## Next step

- Run the generated board-stage script to upload this candidate archive to /home/user/Downloads/baseline_current_safe_bridge/baseline_export_bridge_local_smoke_20260320_1 and probe it under the current-safe runtime on the Pi. If that probe still returns [1, 3, 256, 256], rerun the fair compare with this archive as baseline.
