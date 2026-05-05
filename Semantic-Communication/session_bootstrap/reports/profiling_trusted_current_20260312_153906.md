# Operator Hotspot Analysis

- run_id: trusted_current_20260312_153906
- mode: stage_weight_hotspot_analysis
- generated_at: 2026-03-12T15:39:08+0800
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- onnx_path: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- input_shape: 1,32,32,32
- trusted_target_line: Phytium Pi current-safe / cortex-a72 + neon

## Runtime Profiling Status

- status: not_productized
- note: The repo has stage-weight hotspot extraction and the TVM VM profile API exists locally, but there is no validated trusted remote per-op profiling wrapper yet. This 5.1 artifact promotes the current stage-weight hotspot path to first-class status.
- local_vm_profile_api_available: True
- local_tvm_version: 0.24.dev0
- local_profiling_report_methods: calls,configuration,csv,device_metrics,from_json,json,same_as,table

## Trusted Current Resource Evidence

- resource_profile_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/resource_profile_trusted_current_20260312_001.json
- resource_profile_run_id: resource_profile_trusted_current_20260312_001
- cpu_summary_pct: user=67.266 system=11.83 idle=20.16 wait=0.83
- runnable_tasks_avg_max: 3.755 / 8
- min_free_kb: 115408
- trusted_current_runtime_ms: median=264.912 mean=268.442 count=300
- artifact_sha256_match: True (1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644)

## Quality Guard

- quality_report_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/quality_metrics_20260312_tvm_baseline_vs_tvm_current.json
- quality_run_id: quality_metrics_20260312_tvm_baseline_vs_tvm_current
- matched_png_count: 300
- psnr_mean_median_db: 34.529852149146066 / 34.60044266656402
- ssim_mean_median: 0.9704320174669012 / 0.9704312518412365

## Stage-Weight Hotspots

- task_stage_used_for_recommendation: legalized_fused_tir
- total_tasks: 33
- total_stage_weight: 162
- top_k: 8
- top_k_weight_share_pct: 80.247
- FULL_HOTSPOT_TASKS_candidate: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu

| rank | task_name | family | weight | share % | cumulative % | prim_funcs |
|---|---|---|---:|---:|---:|---|
| 1 | reshape2 | reshape | 42 | 25.926 | 25.926 | main |
| 2 | fused_variance1_add3_tir_sqrt1 | norm_stats | 21 | 12.963 | 38.889 | main |
| 3 | reshape1 | reshape | 21 | 12.963 | 51.852 | main |
| 4 | fused_mean1_subtract1_divide1_multiply1_add4 | norm_stats | 11 | 6.79 | 58.642 | main |
| 5 | fused_conv2d1_add2 | conv2d | 10 | 6.173 | 64.815 | main |
| 6 | fused_conv2d2_add2 | conv2d | 10 | 6.173 | 70.988 | main |
| 7 | mirror_pad1 | pad | 10 | 6.173 | 77.16 | main |
| 8 | fused_mean1_subtract1_divide1_multiply1_add4_relu | norm_stats | 5 | 3.086 | 80.247 | main |

## Family Summary

| family | total weight | share % | top tasks |
|---|---:|---:|---|
| reshape | 75 | 46.296 | reshape2,reshape1,reshape |
| norm_stats | 50 | 30.864 | fused_variance1_add3_tir_sqrt1,fused_mean1_subtract1_divide1_multiply1_add4,fused_mean1_subtract1_divide1_multiply1_add4_relu |
| conv2d | 25 | 15.432 | fused_conv2d1_add2,fused_conv2d2_add2,fused_conv2d3_add15 |
| pad | 12 | 7.407 | mirror_pad1,mirror_pad,mirror_pad2 |

## Reference Check

- reference_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/hotspot_tasks_20260311_0008.json
- same_top_k_as_reference: True
- added_vs_reference: none
- removed_vs_reference: none

## Artifacts

- stage_hotspot_markdown: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.md
- stage_hotspot_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.json
- profiling_markdown: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_153906.md
- profiling_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_trusted_current_20260312_153906.json

## Next 4.2 Command

```bash
TUNE_OP_NAMES=reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu \
bash ./session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh \
  --rebuild-env /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env \
  --inference-env ./session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env \
  --total-trials 2000 \
  --report-id "phytium_baseline_seeded_warm_start_current_incremental_hotspot_$(date +%Y%m%d_%H%M%S)" \
  --repeat 10 \
  --warmup-runs 2
```

## Limitations

- This report uses tuned-stage MetaSchedule weight as a hotspot proxy, not true remote per-op wall time.
- Trusted resource evidence says the current path is compute-heavy, but it does not attribute latency to individual operators.
- Do not lock 7.1 manual TIR targets from reshape-heavy stage weights alone; get runtime or focused micro-benchmark evidence first.
