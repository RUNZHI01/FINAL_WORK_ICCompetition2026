# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T21:57:33+0800
- run_id: profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200/hotspot_tasks_reused.md
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
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/profile_shifted_top3_artifact_20260330_215718.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_shifted_top3_tuned_artifact_reprobe_20260330_2200/runtime_command.log
- expected_artifact_sha256: 23beda366cefda56f4f620bac29be1ed26e23ee2f290df00429a1c417e0720b3
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 23beda366cefda56f4f620bac29be1ed26e23ee2f290df00429a1c417e0720b3
- processed_count: 1
- input_count: 1
- run_median_ms: 1391.62
- run_mean_ms: 1391.62
- load_ms: 2.287
- vm_init_ms: 0.451
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime top ops

| rank | name | mean_duration_us | mean_percent | samples | devices |
| --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose1_add9 | 522451.65 | 42.58428803284712 | 1 | cpu0 |
| 2 | fused_conv2d_transpose2_add12 | 522262.929 | 42.56890565359375 | 1 | cpu0 |
| 3 | fused_conv2d_add2 | 61507.705 | 5.0134052135913265 | 1 | cpu0 |
| 4 | fused_conv2d_transpose_add6 | 17088.022 | 1.3928202748706568 | 1 | cpu0 |
| 5 | fused_conv2d3_add15 | 12254.977 | 0.9988856775625394 | 1 | cpu0 |
| 6 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | 10994.272 | 0.8961274130524157 | 1 | cpu0 |
| 7 | fused_variance4_add13_tir_sqrt4 | 6918.84 | 0.5639447696512854 | 1 | cpu0 |
| 8 | fused_mean3_subtract3_divide3_multiply3_add11_relu2 | 5822.892 | 0.47461561297042737 | 1 | cpu0 |

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: fused_conv2d_transpose1_add9,fused_conv2d_transpose2_add12
