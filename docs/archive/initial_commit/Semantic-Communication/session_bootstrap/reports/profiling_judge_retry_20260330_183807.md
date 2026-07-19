# Task 5.1 Operator Profiling

- generated_at: 2026-03-30T18:38:19+0800
- run_id: profiling_judge_retry_20260330_183807
- overall_status: runtime_operator_profile
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_20260330_183807.json
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_20260330_183807

## Task-stage hotspot extraction

- status: reused
- requested_mode: reuse
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_20260330_183807/hotspot_tasks_reused.json
- report_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_20260330_183807/hotspot_tasks_reused.md
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
- command_log: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_judge_retry_20260330_183807/runtime_command.log
- expected_artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- artifact_path: /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
- artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- processed_count: 1
- input_count: 1
- run_median_ms: 298.858
- run_mean_ms: 298.858
- load_ms: 2.384
- vm_init_ms: 0.458
- runtime_profile_status: profiled_raw
- runtime_profile_supported: True

### Runtime raw report preview

```text
Name                                                    Duration (us)  Percent  Device  Count                                                                                                                                             Argument Shapes  
fused_conv2d_transpose1_add9                                29,258.49    21.54    cpu0      1                                                               float32[1, 48, 64, 64], float32[48, 24, 3, 3], float32[1, 24, 1, 1], float32[1, 24, 128, 128]  
fused_conv2d_transpose2_add12                               27,157.04    19.99    cpu0      1                                                             float32[1, 24, 128, 128], float32[24, 12, 3, 3], float32[1, 12, 1, 1], float32[1, 12, 256, 256]  
fused_conv2d_transpose_add6                                 19,619.35    14.44    cpu0      1                                                                 float32[1, 96, 32, 32], float32[96, 48, 3, 3], float32[1, 48, 1, 1], float32[1, 48, 64, 64]  
fused_conv2d2_add2                                          15,572.05    11.46    cpu0     10                                                                 float32[1, 96, 32, 32], float32[96, 96, 1, 1], float32[1, 96, 1, 1], float32[1, 96, 32, 32]  
fused_conv2d3_add15                                         14,242.97    10.48    cpu0      1                                                                float32[1, 12, 262, 262], float32[3, 12, 7, 7], float32[1, 3, 1, 1], float32[1, 3, 256, 256]  
fused_variance4_add13_tir_sqrt4                              6,915.31     5.09    cpu0      1                                                                                                              float32[1, 12, 256, 256], float32[1, 12, 1, 1]  
fused_variance3_add10_tir_sqrt3                              3,551.11     2.61    cpu0      1                                                                                                              float32[1, 24, 128, 128], float32[1, 24, 1, 1]  
fused_conv2d_add2                                            2,661.47     1.96    cpu0      1                                                                 float32[1, 32, 34, 34], float32[96, 32, 3, 3], float32[1, 96, 1, 1], float32[1, 96, 32, 32]  
fused_variance1_add3_tir_sqrt1                               2,182.46     1.61    cpu0     21                                                                                                                float32[1, 96, 32, 32], float32[1, 96, 1, 1]  
fused_mean1_subtract1_divide1_multiply1_add4                 1,927.11     1.42    cpu0     11                                                  float32[1, 96, 32, 32], float32[1, 96, 1, 1], float32[96, 1, 1], float32[96, 1, 1], float32[1, 96, 32, 32]  
fused_conv2d1_add2                                           1,829.22     1.35    cpu0     10                                                                  float32[1, 96, 34, 34], float32[96, 1, 3, 3], float32[1, 96, 1, 1], float32[1, 96, 32, 32]  
fused_mean4_subtract4_divide4_multiply4_add14_relu3          1,796.10     1.32    cpu0      1                                              float32[1, 12, 256, 256], float32[1, 12, 1, 1], float32[12, 1, 1], float32[12, 1, 1], float32[1, 12, 256, 256]  
mirror_pad2                                                    970.70     0.71    cpu0      1                                                                                                          float32[1, 12, 256, 256], float32[1, 12, 262, 262]  
fused_mean3_subtract3_divide3_multiply3_add11_relu2            951.34     0.70    cpu0      1                                              float32[1, 24, 128, 128], float32[1, 24, 1, 1], float32[24, 1, 1], float32[24, 1, 1], float32[1, 24, 128, 128]  
fused_mean1_subtract1_divide1_multiply1_add4_relu              909.52     0.67    cpu0      5                                                  float32[1, 96, 32, 32], float32[1, 96, 1, 1], float32[96, 1, 1], float32[96, 1, 1], float32[1, 96, 32, 32]  
mirror_pad1                                                    754.86     0.56    cpu0     10                                                                                                              float32[1, 96, 32, 32], float32[1, 96, 34, 34]  
fused_mean1_subtract1_divide1_multiply1_add4_add5              744.00     0.55    cpu0      4                          float32[1, 96, 32, 32], float32[1, 96, 1, 1], float32[96, 1, 1], float32[96, 1, 1], float32[1, 96, 32, 32], float32[1, 96, 32, 32]  
fused_mean2_subtract2_divide2_multiply2_add8_relu1             410.95     0.30    cpu0      1                                                  float32[1, 48, 64, 64], float32[1, 48, 1, 1], float32[48, 1, 1], float32[48, 1, 1], float32[1, 48, 64, 64]  
fused_variance2_add7_tir_sqrt2                                 346.47     0.26    cpu0      1                                                                                                                float32[1, 48, 64, 64], float32[1, 48, 1, 1]  
fused_mean1_subtract1_divide1_multiply1_add4_add5_add5         264.73     0.19    cpu0      1  float32[1, 96, 32, 32], float32[1, 96, 1, 1], float32[96, 1, 1], float32[96, 1, 1], float32[1, 96, 32, 32], float32[1, 96, 32, 32], float32[1, 96, 32, 32]  
fused_variance_add_tir_sqrt                                    224.03     0.16    cpu0      1                                                                                                                float32[1, 32, 32, 32], float32[1, 32, 1, 1]  
vm.builtin.reshape                                             134.38     0.10    cpu0     63                                                                                                                                                 float32[96]  
fused_mean_subtract_divide_multiply_add1                        89.16     0.07    cpu0      1                                                  float32[1, 32, 32, 32], float32[1, 32, 1, 1], float32[32, 1, 1], float32[32, 1, 1], float32[1, 32, 32, 32]  
mirror_pad                                                      49.28     0.04    cpu0      1                                                                                                              float32[1, 32, 32, 32], float32[1, 32, 34, 34]  
vm.builtin.reshape                                              13.36     0.01    cpu0      3                                                                                                                                                 float32[12]  
vm.builtin.reshape                                              13.04     0.01    cpu0      3                                                                                                                                                 float32[24]  
vm.builtin.reshape                                              10.16     0.01    cpu0      3                                                                                                                                                 float32[48]  
vm.builtin.check_tensor_info                                     8.80     0.01    cpu0      1                                                                                                                                      float32[1, 32, 32, 32]  
vm.builtin.reshape                                               6.68     0.00    cpu0      1                                                                                                                                                  float32[3]  
vm.builtin.reshape                                               6.28     0.00    cpu0      2                                                                                                                                                 float32[32]  
vm.builtin.match_shape                                           4.56     0.00    cpu0      1                                                                                                                                      float32[1, 32, 32, 32]  
----------                                                                                                                                                                                                                                                 
Sum                                                        132,624.99    97.62            164                                                                                                                                                              
Total                                                      135,856.36             cpu0      1                                                                                                                                                              

Configuration
-------------
Number of threads: 2
Executor: VM

```

## Outcome

- overall_status: runtime_operator_profile
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu
- runtime_hotspot_candidates: N/A
