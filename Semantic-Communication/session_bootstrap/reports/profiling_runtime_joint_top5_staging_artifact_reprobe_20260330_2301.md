# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T23:01:19+0800
- run_id: profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301
- overall_status: stage_level_hotspot_only
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301/hotspot_tasks_reused.md
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

- status: failed
- requested_mode: attempt
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/profile_joint_top5_staging_artifact_20260330_230106.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301/runtime_command.log
- expected_artifact_sha256: 9979d906a7eb52772eab3c124aea58246e7e0f0e4391b76d57af6d095ddbc805
- fallback_reason: trusted runtime command failed with rc=1; see /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_20260330_2301/runtime_command.log

## Outcome

- overall_status: stage_level_hotspot_only
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: N/A
