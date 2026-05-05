# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T20:51:25+0800
- run_id: profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055/hotspot_tasks_reused.md
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
- trusted_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/profile_new_artifact_20260330_205110.env
- trusted_variant: current
- remote_host: 100.121.87.73
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- command: `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055/runtime_command.log
- expected_artifact_sha256: 2eb2f8777dd72b46747ebb82738eba5659b5c284983e6c20c349eb4f464d2ca5
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 2eb2f8777dd72b46747ebb82738eba5659b5c284983e6c20c349eb4f464d2ca5
- processed_count: 1
- input_count: 1
- run_median_ms: 1659.636
- run_mean_ms: 1659.636
- load_ms: 2.414
- vm_init_ms: 0.486
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime top ops

| rank | name | mean_duration_us | mean_percent | samples | devices |
| --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose_add6 | 497266.467 | 32.59226245907302 | 1 | cpu0 |
| 2 | fused_conv2d3_add15 | 281567.81 | 18.45475730328384 | 1 | cpu0 |
| 3 | fused_conv2d_add2 | 61336.122 | 4.020144367477975 | 1 | cpu0 |
| 4 | fused_conv2d2_add2 | 56760.613 | 3.720252458193349 | 1 | cpu0 |
| 5 | fused_conv2d2_add2 | 56691.275 | 3.7157078479202674 | 1 | cpu0 |
| 6 | fused_conv2d2_add2 | 56683.315 | 3.715186126818221 | 1 | cpu0 |
| 7 | fused_conv2d2_add2 | 56664.036 | 3.713922526174205 | 1 | cpu0 |
| 8 | fused_conv2d2_add2 | 56662.556 | 3.713825522753221 | 1 | cpu0 |

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: fused_conv2d_transpose_add6,fused_conv2d3_add15
