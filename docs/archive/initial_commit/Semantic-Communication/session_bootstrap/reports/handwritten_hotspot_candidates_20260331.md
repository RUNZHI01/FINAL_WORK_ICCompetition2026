# Handwritten Hotspot Candidates

- generated_at: 2026-03-31T01:46:56+0800
- current_profile_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.json
- reference_profile_json: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_fixed_20260330_2305.json
- best_candidate_freeze_md: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/reports/current_best_staging_candidate_20260331.md
- current_best_staging_artifact_sha256: 5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d
- current_best_staging_reprobe_median_ms: 329.928
- reference_staging_reprobe_median_ms: 389.017
- suggested_staging_archive: /home/user/Downloads/jscc-test/jscc_staging_handwritten

## Current Curated Runtime Top Ops

| rank | name | family | duration us | percent |
| --- | --- | --- | ---: | ---: |
| 1 | fused_conv2d_transpose1_add9 | deconv | 24275.26 | 14.60 |
| 2 | fused_conv2d_transpose2_add12 | deconv | 20234.68 | 12.17 |
| 3 | fused_conv2d_transpose_add6 | deconv | 17385.33 | 10.46 |
| 4 | fused_conv2d3_add15 | conv | 11800.99 | 7.10 |
| 5 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | norm_stats | 11065.87 | 6.66 |
| 6 | fused_variance4_add13_tir_sqrt4 | norm_stats | 7099.57 | 4.27 |
| 7 | fused_mean3_subtract3_divide3_multiply3_add11_relu2 | norm_stats | 5825.71 | 3.50 |
| 8 | fused_variance3_add10_tir_sqrt3 | norm_stats | 3575.03 | 2.15 |

## Wave 1: Conv and Deconv

| priority | name | family | current us | current % | reference % | current raw rank | shapes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | fused_conv2d_transpose1_add9 | deconv | 24275.26 | 14.60 | 8.30 | 1 | float32[1, 48, 64, 64], float32[48, 24, 3, 3], float32[1, 24, 1, 1], float32[1, 24, 128, 128] |
| 2 | fused_conv2d_transpose2_add12 | deconv | 20234.68 | 12.17 | 10.20 | 2 | float32[1, 24, 128, 128], float32[24, 12, 3, 3], float32[1, 12, 1, 1], float32[1, 12, 256, 256] |
| 3 | fused_conv2d_transpose_add6 | deconv | 17385.33 | 10.46 | 8.01 | 3 | float32[1, 96, 32, 32], float32[96, 48, 3, 3], float32[1, 48, 1, 1], float32[1, 48, 64, 64] |
| 4 | fused_conv2d3_add15 | conv | 11800.99 | 7.10 | 6.91 | 5 | float32[1, 12, 262, 262], float32[3, 12, 7, 7], float32[1, 3, 1, 1], float32[1, 3, 256, 256] |

1. `fused_conv2d_transpose1_add9`: Still a top compute kernel in the best staging candidate (24275.26 us, 14.60%). Joint-top5 reference was 8.30%, so this kernel survived multiple targeted rounds. Manual NEON/TIR is the next conservative lever. Wave 1: handwritten TIR plus NEON for spatial tile and vector store.
2. `fused_conv2d_transpose2_add12`: Still a top compute kernel in the best staging candidate (20234.68 us, 12.17%). Joint-top5 reference was 10.20%, so this kernel survived multiple targeted rounds. Manual NEON/TIR is the next conservative lever. Wave 1: handwritten TIR plus NEON for spatial tile and vector store.
3. `fused_conv2d_transpose_add6`: Still a top compute kernel in the best staging candidate (17385.33 us, 10.46%). Joint-top5 reference was 8.01%, so this kernel survived multiple targeted rounds. Manual NEON/TIR is the next conservative lever. Wave 1: handwritten TIR plus NEON for spatial tile and vector store.
4. `fused_conv2d3_add15`: Still a top compute kernel in the best staging candidate (11800.99 us, 7.10%). Joint-top5 reference was 6.91%, so this kernel survived multiple targeted rounds. Manual NEON/TIR is the next conservative lever. Wave 1: handwritten TIR plus NEON for kernel tile and epilogue.

## Wave 2: Norm and Reduction

| priority | name | family | current us | current % | reference % | current raw rank | shapes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | norm_stats | 11065.87 | 6.66 | 5.21 | 7 | float32[1, 12, 256, 256], float32[1, 12, 1, 1], float32[12, 1, 1], float32[12, 1, 1], float32[1, 12, 256, 256] |
| 2 | fused_variance4_add13_tir_sqrt4 | norm_stats | 7099.57 | 4.27 | 3.28 | 9 | float32[1, 12, 256, 256], float32[1, 12, 1, 1] |
| 3 | fused_mean3_subtract3_divide3_multiply3_add11_relu2 | norm_stats | 5825.71 | 3.50 | 2.53 | 11 | float32[1, 24, 128, 128], float32[1, 24, 1, 1], float32[24, 1, 1], float32[24, 1, 1], float32[1, 24, 128, 128] |
| 4 | fused_variance3_add10_tir_sqrt3 | norm_stats | 3575.03 | 2.15 | 1.54 | 14 | float32[1, 24, 128, 128], float32[1, 24, 1, 1] |

1. `fused_mean4_subtract4_divide4_multiply4_add14_relu3`: Now visible after the joint-top6 conv/deconv protection set (11065.87 us, 6.66%). Joint-top5 reference was 5.21%, so this is a real residual rather than a one-off spike. This is a reduction/vector epilogue candidate for handwritten TIR. Wave 2: handwritten TIR for reduction, vector math, and fused epilogue.
2. `fused_variance4_add13_tir_sqrt4`: Now visible after the joint-top6 conv/deconv protection set (7099.57 us, 4.27%). Joint-top5 reference was 3.28%, so this is a real residual rather than a one-off spike. This is a reduction/vector epilogue candidate for handwritten TIR. Wave 2: handwritten TIR for reduction, vector math, and fused epilogue.
3. `fused_mean3_subtract3_divide3_multiply3_add11_relu2`: Now visible after the joint-top6 conv/deconv protection set (5825.71 us, 3.50%). Joint-top5 reference was 2.53%, so this is a real residual rather than a one-off spike. This is a reduction/vector epilogue candidate for handwritten TIR. Wave 2: handwritten TIR for reduction, vector math, and fused epilogue.
4. `fused_variance3_add10_tir_sqrt3`: Now visible after the joint-top6 conv/deconv protection set (3575.03 us, 2.15%). Joint-top5 reference was 1.54%, so this is a real residual rather than a one-off spike. This is a reduction/vector epilogue candidate for handwritten TIR. Wave 2: handwritten TIR for reduction, vector math, and fused epilogue.

## Monitor Only

| name | family | current % | reference % | current raw rank |
| --- | --- | ---: | ---: | ---: |
| fused_variance1_add3_tir_sqrt1 | norm_stats | 8.85 | 6.16 | 4 |
| fused_conv2d2_add2 | conv | 7.00 | 4.96 | 6 |
| fused_mean1_subtract1_divide1_multiply1_add4 | norm_stats | 5.10 | 3.76 | 8 |
| fused_conv2d_add2 | conv | 1.62 | 26.48 | 15 |

- `fused_variance1_add3_tir_sqrt1`: Visible in raw aggregated calls but not promoted into the diagnosis shortlist. Use a focused reprobe or micro-benchmark before spending handwritten effort here.
- `fused_conv2d2_add2`: Still visible in raw aggregated calls, but the diagnosis no longer promotes it as a curated top hotspot. Reconfirm with a focused reprobe before manual TIR.
- `fused_mean1_subtract1_divide1_multiply1_add4`: Visible in raw aggregated calls but not promoted into the diagnosis shortlist. Use a focused reprobe or micro-benchmark before spending handwritten effort here.
- `fused_conv2d_add2`: Triggered the jump from joint-top5 to joint-top6 (26.48% -> 1.62%). Keep it as a control, not the first handwritten kernel.

## Guardrails

- Do not overwrite the trusted current archive.
- Use the current best staging candidate as the fixed comparison point.
- Work one handwritten kernel at a time and re-profile after each candidate.
- If a candidate creates a new dominant hotspot or regresses payload, keep it in staging only.

## Suggested Commands

```bash
python3 ./session_bootstrap/scripts/prepare_handwritten_hotspot_candidates.py
```

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top6_refine_staging_search.sh
```

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_staging_validate.sh \
  --rebuild-env <manual_overlay.env> \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten \
  --report-id phytium_handwritten_<op>_$(date +%Y%m%d_%H%M%S)
```

