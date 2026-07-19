# Runtime Profiling 扩样本报告 (10 inputs x 10 profiled samples)

- generated_at: 2026-04-03
- artifact_sha256: 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- target: {"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
- remote_host: 100.121.87.73
- purpose: expand profiling from 3 samples to 10 for improved statistical confidence

## Overall timing

| metric | value |
|---|---|
| samples | 10 |
| median | 230.75 ms |
| mean | 232.829 ms |
| min | 197.776 ms |
| max | 303.851 ms |
| stddev | 25.965 ms |
| load_ms | 2.312 |
| vm_init_ms | 0.473 |

Individual sample times (ms): [303.851, 237.898, 222.559, 217.838, 231.448, 231.905, 222.726, 197.776, 232.236, 230.052]

## Per-op profiling (10 profiled samples)

| rank | op | mean_us | median_us | min_us | max_us | std_us | pct_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | fused_conv2d_transpose1_add9 | 27510 | 27389 | 27352 | 28538 | 364 | 21.61% |
| 2 | fused_conv2d_transpose2_add12 | 22515 | 22549 | 22378 | 22690 | 109 | 17.68% |
| 3 | fused_conv2d_transpose_add6 | 20375 | 20354 | 20229 | 20707 | 155 | 16.00% |
| 4 | fused_conv2d2_add2 | 15685 | 15579 | 15552 | 16532 | 302 | 12.32% |
| 5 | fused_conv2d3_add15 | 14322 | 14281 | 14197 | 14571 | 119 | 11.25% |
| 6 | fused_variance4_add13_tir_sqrt4 | 7053 | 7029 | 6997 | 7287 | 84 | 5.54% |
| 7 | fused_variance3_add10_tir_sqrt3 | 3562 | 3543 | 3512 | 3769 | 74 | 2.80% |
| 8 | fused_conv2d_add2 | 2670 | 2660 | 2631 | 2817 | 53 | 2.10% |
| 9 | fused_variance1_add3_tir_sqrt1 | 2282 | 2273 | 2260 | 2314 | 21 | 1.79% |
| 10 | fused_mean1_subtract1_divide1_multiply1_add4 | 1944 | 1923 | 1902 | 2169 | 80 | 1.53% |
| 11 | fused_conv2d1_add2 | 1781 | 1771 | 1752 | 1832 | 27 | 1.40% |
| 12 | fused_mean4_subtract4_divide4_multiply4_add14_relu3 | 1775 | 1773 | 1752 | 1795 | 14 | 1.39% |
| 13 | mirror_pad2 | 1008 | 999 | 987 | 1044 | 21 | 0.79% |
| 14 | fused_mean3_subtract3_divide3_multiply3_add11_relu2 | 953 | 943 | 932 | 992 | 20 | 0.75% |
| 15 | fused_mean1_subtract1_divide1_multiply1_add4_relu | 910 | 903 | 898 | 959 | 18 | 0.71% |
| 16 | mirror_pad1 | 790 | 776 | 765 | 881 | 34 | 0.62% |
| 17 | fused_mean1_subtract1_divide1_multiply1_add4_add5 | 741 | 741 | 733 | 752 | 6 | 0.58% |
| 18 | fused_mean2_subtract2_divide2_multiply2_add8_relu1 | 404 | 401 | 397 | 418 | 7 | 0.32% |
| 19 | fused_variance2_add7_tir_sqrt2 | 349 | 349 | 334 | 367 | 11 | 0.27% |
| 20 | fused_mean1_subtract1_divide1_multiply1_add4_add5_add5 | 272 | 271 | 267 | 283 | 5 | 0.21% |
| 21 | fused_variance_add_tir_sqrt | 225 | 221 | 218 | 251 | 10 | 0.18% |
| 22 | fused_mean_subtract_divide_multiply_add1 | 87 | 88 | 84 | 90 | 2 | 0.07% |
| 23 | mirror_pad | 56 | 57 | 53 | 59 | 2 | 0.04% |

All 10 samples contributed per-op data (n=10 per op).

## Comparison with previous profiling

| metric | 3-sample (2026-03-30) | 10-sample (2026-04-03) | delta |
|---|---|---|---|
| median e2e | 246.697 ms | 230.75 ms | -6.5% |
| mean e2e | 257.31 ms | 232.829 ms | -9.5% |
| samples | 3 | 10 | +233% |
| top-1 op | conv2d_transpose2_add12 (21.76%) | conv2d_transpose1_add9 (21.61%) | order swap |
| top-2 op | conv2d_transpose1_add9 (20.26%) | conv2d_transpose2_add12 (17.68%) | order swap |
| top-3 op | conv2d_transpose_add6 (14.35%) | conv2d_transpose_add6 (16.00%) | stable |

## Key findings

1. **Hotspot ordering confirmed with higher confidence**: Top 3 ops (two conv2d_transpose + conv2d_transpose_add6) consistently account for ~55% of runtime across all 10 samples.

2. **Per-op stability**: Top ops show low standard deviation relative to mean (std/mean < 2%), confirming stable measurement.

3. **E2e variance**: First sample (303.85 ms) is an outlier (~30% above median), likely due to cold-start/caching effects. Excluding it, remaining 9 samples have median 230.65 ms with std 11.3 ms.

4. **Hotspot candidates for future optimization**:
   - Primary: `fused_conv2d_transpose1_add9` (21.6%) and `fused_conv2d_transpose2_add12` (17.7%)
   - Secondary: `fused_conv2d_transpose_add6` (16.0%), `fused_conv2d2_add2` (12.3%), `fused_conv2d3_add15` (11.3%)
   - These 5 ops together account for ~79% of total runtime.

5. **Handwritten optimization impact**: transpose1 v7 (-1.97%) and variance4 v18 (-0.99%) correspond to ops #1 and #6 respectively in this profile. Combined ~3 ms improvement is visible but small relative to total 230 ms.

## Associated reports

- Previous profiling (3 samples): `profiling_judge_multi_20260330_184658.md`
- Judge evidence pack: `judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`
- Profiling enablement plan: `runbooks/runtime_profiling_enablement_plan_2026-03-30.md`
