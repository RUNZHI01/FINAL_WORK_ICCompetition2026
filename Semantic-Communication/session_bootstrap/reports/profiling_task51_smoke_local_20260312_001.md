# Task 5.1 Operator Profiling

- generated_at: 2026-03-12T15:42:01+0800
- run_id: profiling_task51_smoke_local_20260312_001
- overall_status: stage_level_hotspot_only
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_task51_smoke_local_20260312_001.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_task51_smoke_local_20260312_001

## Task-stage hotspot extraction

- status: extracted
- requested_mode: auto
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_task51_smoke_local_20260312_001/hotspot_tasks.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_task51_smoke_local_20260312_001/hotspot_tasks.md
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

- status: skipped
- requested_mode: skip
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
- trusted_variant: current
- remote_host: N/A
- target: N/A
- command: `N/A`
- command_log: N/A
- expected_artifact_sha256: N/A

## Outcome

- overall_status: stage_level_hotspot_only
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: N/A
