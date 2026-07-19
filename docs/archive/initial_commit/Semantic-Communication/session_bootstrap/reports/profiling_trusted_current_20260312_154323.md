# Task 5.1 Operator Profiling

- generated_at: 2026-03-12T15:43:35+0800
- run_id: profiling_trusted_current_20260312_154323
- overall_status: stage_level_hotspot_only
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323

## Task-stage hotspot extraction

- status: extracted
- requested_mode: auto
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323/hotspot_tasks.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323/hotspot_tasks.md
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu

### Hotspot preview

| rank | task_name | weight | dispatched_count | prim_funcs |
| --- | --- | --- | --- | --- |
| 1 | reshape2 | 42 | 1 | main |
| 2 | fused_variance1_add3_tir_sqrt1 | 21 | 1 | main |
| 3 | reshape1 | 21 | 1 | main |
| 4 | fused_mean1_subtract1_divide1_multiply1_add4 | 11 | 1 | main |
| 5 | fused_conv2d1_add2 | 10 | 1 | main |
| 6 | fused_conv2d2_add2 | 10 | 1 | main |
| 7 | mirror_pad1 | 10 | 1 | main |
| 8 | fused_mean1_subtract1_divide1_multiply1_add4_relu | 5 | 1 | main |

## Runtime/operator profiling attempt

- status: fallback_only
- requested_mode: auto
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_154323/runtime_command.log
- expected_artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- fallback_reason: AttributeError: Module has no function 'profile'
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
- processed_count: 1
- input_count: 1
- run_median_ms: 317.123
- run_mean_ms: 317.123
- load_ms: 2.407
- vm_init_ms: 0.474
- runtime_profile_status: unsupported
- runtime_profile_supported: False

## Outcome

- overall_status: stage_level_hotspot_only
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: N/A
