# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T18:40:37+0800
- run_id: profiling_judge_retry_parse_20260330_184026
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026/hotspot_tasks_reused.md
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
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026/runtime_command.log
- expected_artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- processed_count: 1
- input_count: 1
- run_median_ms: 277.733
- run_mean_ms: 277.733
- load_ms: 2.454
- vm_init_ms: 0.475
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime top ops

| rank | name | mean_duration_us | mean_percent | samples | devices |
| --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose1_add9 | 27805.575 | 20.930366370789947 | 1 | cpu0 |
| 2 | fused_conv2d_transpose2_add12 | 25140.421 | 18.924198555358103 | 1 | cpu0 |
| 3 | fused_conv2d_transpose_add6 | 19714.715 | 14.840053041366996 | 1 | cpu0 |
| 4 | fused_conv2d3_add15 | 14205.41 | 10.692979222594145 | 1 | cpu0 |
| 5 | fused_variance4_add13_tir_sqrt4 | 6940.069 | 5.224067001260065 | 1 | cpu0 |
| 6 | fused_variance3_add10_tir_sqrt3 | 3536.353 | 2.661954083180878 | 1 | cpu0 |
| 7 | fused_conv2d_add2 | 2674.754 | 2.013394118687921 | 1 | cpu0 |
| 8 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | 1651.319 | 1.2430137360959623 | 1 | cpu0 |

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: fused_conv2d_transpose1_add9,fused_conv2d_transpose2_add12
