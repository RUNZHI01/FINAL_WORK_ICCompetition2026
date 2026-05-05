# MetaSchedule Hotspot Tasks

- generated_at: 2026-03-12T15:42:00+0800
- onnx_path: /home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- input_shape: 1,32,32,32
- task_stage_used_for_recommendation: legalized_fused_tir
- tuned_stage_pipeline: LegalizeOps -> AnnotateTIROpPattern -> FuseOps -> FuseTIR
- tuned_stage_total_tasks: 33
- raw_import_total_tasks: 3
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu

## Recommended Tuned Stage

- stage_name: legalized_fused_tir
- total_tasks: 33
- pipeline: LegalizeOps -> AnnotateTIROpPattern -> FuseOps -> FuseTIR
- recommended_FULL_HOTSPOT_TASKS: reshape2,fused_variance1_add3_tir_sqrt1,reshape1,fused_mean1_subtract1_divide1_multiply1_add4,fused_conv2d1_add2,fused_conv2d2_add2,mirror_pad1,fused_mean1_subtract1_divide1_multiply1_add4_relu

| rank | task_name | weight | dispatched_count | prim_funcs |
|---|---|---:|---:|---|
| 1 | reshape2 | 42 | 1 | main |
| 2 | fused_variance1_add3_tir_sqrt1 | 21 | 1 | main |
| 3 | reshape1 | 21 | 1 | main |
| 4 | fused_mean1_subtract1_divide1_multiply1_add4 | 11 | 1 | main |
| 5 | fused_conv2d1_add2 | 10 | 1 | main |
| 6 | fused_conv2d2_add2 | 10 | 1 | main |
| 7 | mirror_pad1 | 10 | 1 | main |
| 8 | fused_mean1_subtract1_divide1_multiply1_add4_relu | 5 | 1 | main |

## Raw Import Stage

- stage_name: raw_import
- total_tasks: 3
- recommended_FULL_HOTSPOT_TASKS: mirror_pad1,mirror_pad,mirror_pad2

| rank | task_name | weight | dispatched_count | prim_funcs |
|---|---|---:|---:|---|
| 1 | mirror_pad1 | 10 | 1 | main |
| 2 | mirror_pad | 1 | 1 | main |
| 3 | mirror_pad2 | 1 | 1 | main |

