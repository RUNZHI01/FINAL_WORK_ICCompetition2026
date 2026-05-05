# Task 5.1 Operator Profiling

- generated_at: 2026-03-31T00:32:29+0800
- run_id: profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/hotspot_tasks_reused.md
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

- status: profiled_raw
- requested_mode: attempt
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/profile_joint_top6_staging_artifact_20260331_003213.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/runtime_command.log
- expected_artifact_sha256: 5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d
- artifact_path: /home/user/Downloads/jscc-test/jscc_staging/tvm_tune_logs/optimized_model.so
- artifact_sha256: 5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d
- processed_count: 1
- input_count: 1
- run_median_ms: 329.928
- run_mean_ms: 329.928
- load_ms: 3.312
- vm_init_ms: 0.485
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime top ops

| rank | name | mean_duration_us | mean_percent | samples | devices |
| --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose1_add9 | 24275.261 | 14.600473480896312 | 1 | cpu0 |
| 2 | fused_conv2d_transpose2_add12 | 20234.681 | 12.170247040182037 | 1 | cpu0 |
| 3 | fused_conv2d_transpose_add6 | 17385.325 | 10.456488052559504 | 1 | cpu0 |
| 4 | fused_conv2d3_add15 | 11800.99 | 7.097762678775012 | 1 | cpu0 |
| 5 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | 11065.872 | 6.655622391824871 | 1 | cpu0 |
| 6 | fused_variance4_add13_tir_sqrt4 | 7099.569 | 4.270070213057382 | 1 | cpu0 |
| 7 | fused_mean3_subtract3_divide3_multiply3_add11_relu2 | 5825.708 | 3.503900335466856 | 1 | cpu0 |
| 8 | fused_variance3_add10_tir_sqrt3 | 3575.034 | 2.150221540781896 | 1 | cpu0 |

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: fused_conv2d_transpose1_add9,fused_conv2d_transpose2_add12
