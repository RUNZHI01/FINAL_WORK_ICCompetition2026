# Project Speedup Rerank After Transpose1 Closure

- generated_at: `2026-04-02T19:38:22+08:00`
- scope: `repo-local rerank after transpose1 overlap/carry closure`
- frozen transpose1 result still in force:
  `session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- current best board-validated candidate median: `156.785 ms`
- chosen next target: `fused_conv2d_transpose_add6`

## Decision

Keep `fused_conv2d_transpose_add6` as the next active project-wide speedup
target.

The earlier closure note already leaned this way, and the full repo check still
supports it after reintroducing `mean4` as the main underexplored alternative.

## Re-ranked Opportunities

### 1) `fused_conv2d_transpose_add6`

Best expected ROI for a real speed improvement.

Why it stays first:

- it is still a large residual hotspot:
  - `14.35%` in
    `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
  - `10.46%` in the curated handwritten shortlist:
    `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- it already has a real accepted board win:
  - `transpose_add6 v1` median `159.503 ms`
  - reference staging median `159.943 ms`
  - report:
    `session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`
- the lane is mature and schedule-backed locally:
  - `query_tuning_record_hit = true`
  - `query_ir_module_hit = true`
  - `query_schedule_hit = true`
  - lane summary:
    `session_bootstrap/reports/transpose_add6_local_handwritten_lane_summary_20260331.md`
- only the baseline bias-fusion plus two micro-tune branches have been spent:
  - `P2` regressed:
    `session_bootstrap/reports/transpose_add6_p2_remote_benchmark_20260331_212249.md`
  - `P4` regressed:
    `session_bootstrap/reports/transpose_add6_p4_remote_benchmark_20260331_213628.md`
- the checked-in `v1` TIR still materializes `data_dilate`, `data_pad`, and
  `kernel_transform`, so the transpose1-style locality family is still
  available here and has not yet been consumed by a real branch

### 2) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

Second, but not first.

Why it moved ahead of other non-`transpose_add6` lanes:

- it remains a meaningful residual hotspot in the curated shortlist:
  `6.66%` in
  `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- it now has a checked-in local lane, runbook, and local build wrapper:
  `session_bootstrap/reports/mean4_local_handwritten_lane_summary_20260331.md`
- unlike `transpose2`, `conv2d3_add15`, and `variance4`, it has not already
  burned several remote-tested follow-up branches with losses

Why it is still behind `transpose_add6`:

- current best-staging does **not** expose a direct `query_tuning_record`,
  `query_ir_module`, or `query_schedule` hit for mean4
- the checked-in lane proves post-db swap/build viability, not schedule-backed
  equivalence
- there is still no board evidence for any handwritten mean4 edit

### 3) `fused_conv2d_transpose2_add12`

Still important, but not the best next spend.

Why it falls behind:

- it is the largest raw hotspot at `21.76%` in
  `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- but the accepted local/remote baseline already lagged reference staging:
  `161.416 ms` vs `159.943 ms`
- multiple follow-ups have now lost on board:
  - `P2`
  - `P4`
  - `P1 v2` dilate+pad fusion
  - `v3` kernel repack
- reports:
  - `session_bootstrap/reports/transpose2_p2_remote_benchmark_20260331_202602.md`
  - `session_bootstrap/reports/transpose2_p4_remote_benchmark_20260331_203415.md`
  - `session_bootstrap/reports/transpose2_p1_v2_remote_benchmark_20260402_112915.md`
  - `session_bootstrap/reports/transpose2_v3_remote_benchmark_20260402_165612.md`

Interpretation:

The hotspot size is real, but expected ROI is now lower than `transpose_add6`
because the operator already consumed several plausible follow-ups without a
single on-board win.

### 4) `fused_conv2d3_add15`

Deprioritized for now.

Why:

- hotspot share is smaller than the deconv lanes:
  `10.15%` raw in
  `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- accepted `v1` never beat reference staging:
  `161.000 ms` vs `159.943 ms`
- `P2`, `P4`, and `v2` kernel repack all regressed on board
- reports:
  - `session_bootstrap/reports/conv2d3_add15_p2_remote_benchmark_20260331_223100.md`
  - `session_bootstrap/reports/conv2d3_add15_p4_remote_benchmark_20260331_224339.md`
  - `session_bootstrap/reports/conv2d3_add15_v2_remote_benchmark_20260402_124724.md`

Interpretation:

This lane is well scaffolded, but the next high-confidence seam is less obvious
than the unspent transpose1-style locality transfer still available in
`transpose_add6`.

### 5) `fused_variance4_add13_tir_sqrt4`

Reserve lane only.

Why it stays last among the current shortlist:

- hotspot share is modest:
  `5.05%` raw in
  `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- the main recent achievement was path validity, not speed:
  `session_bootstrap/reports/variance4_v13_remote_benchmark_20260402_162140.md`
- the lane still lacks direct best-staging DB hits:
  `session_bootstrap/reports/variance4_handwritten_lane_status_20260402.md`
- many local versions were already consumed resolving evaluability, lowering,
  and exactness rather than revealing a new speed seam

## Concrete Next Step

Use `fused_conv2d_transpose_add6` for the next active branch.

The smallest honest repo-local continuation is:

1. freeze accepted `v1` as the baseline to beat
2. open a separate `v2` locality seed so the accepted baseline stays untouched
3. spend the first real `v2` edit on reducing repeated `data_dilate` /
   `data_pad` staging while preserving the accepted bias-fused compute path
4. rerun the existing local build and correctness path before any board work
