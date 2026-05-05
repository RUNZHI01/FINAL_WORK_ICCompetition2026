# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T18:47:11+0800
- run_id: profiling_judge_multi_20260330_184658
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_multi_20260330_184658.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_multi_20260330_184658

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_multi_20260330_184658/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_multi_20260330_184658/hotspot_tasks_reused.md
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
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 3 --seed 0 --profile-ops --profile-samples 3`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_multi_20260330_184658/runtime_command.log
- expected_artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- processed_count: 3
- input_count: 3
- run_median_ms: 246.697
- run_mean_ms: 257.31
- load_ms: 2.396
- vm_init_ms: 0.477
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime top ops

| rank | name | mean_duration_us | mean_percent | samples | devices |
| --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose2_add12 | 29819.038 | 21.755516877671226 | 1 | cpu0 |
| 2 | fused_conv2d_transpose1_add9 | 27772.727 | 20.2625594758441 | 1 | cpu0 |
| 3 | fused_conv2d_transpose_add6 | 19662.084 | 14.345157624206031 | 1 | cpu0 |
| 4 | fused_conv2d3_add15 | 13917.403 | 10.153925685323992 | 1 | cpu0 |
| 5 | fused_variance4_add13_tir_sqrt4 | 6927.412 | 5.054134499060036 | 1 | cpu0 |
| 6 | fused_variance3_add10_tir_sqrt3 | 3521.155 | 2.5689811667095506 | 1 | cpu0 |
| 7 | fused_conv2d_add2 | 2662.255 | 1.942340781924776 | 1 | cpu0 |
| 8 | fused_conv2d2_add2 | 1654.32 | 1.2069667264607618 | 1 | cpu0 |

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: fused_conv2d_transpose2_add12,fused_conv2d_transpose1_add9
