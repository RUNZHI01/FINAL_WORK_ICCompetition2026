# `fused_conv2d_transpose1_add9` Post-Overlap Closure Decision

- generated_at: `2026-04-02`
- scope: local-only decision after the transpose1 overlap/carry family was closed
- chosen_path: `PATH 2`
- decision: `treat transpose1 as near-exhausted under the current v7 seam and rerank the next project-wide target as fused_conv2d_transpose_add6`

## Baseline Still In Force

- current best board-validated transpose1 candidate:
  `session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- current best remote median: `156.785 ms`

## Why PATH 2

The remaining nearby transpose1 follow-ups no longer clear the bar for a real
checked-in branch:

1. The overlap/carry family is closed.
   - boundary diagnostic:
     `session_bootstrap/reports/transpose1_overlap_boundary_diagnostic_20260402.md`
   - follow-up closure:
     `session_bootstrap/reports/transpose1_v9_follow_up_decision_20260402.md`
   - the explicit-carry and disjoint-buffer scratch proofs kept failing on the
     same boundary rows `32/33` and `96/97`, so another overlap variant would
     just reopen a blocked lane.

2. The consumer-order reopen is already a loser.
   - `transpose1 v5` changed only the consumer order and regressed versus the
     then-leading `v4`:
     `158.972 ms` vs `158.621 ms`
   - report:
     `session_bootstrap/reports/transpose1_v5_remote_benchmark_20260402_175309.md`

3. The narrower-than-`v7` slice direction is already closed.
   - `transpose1 v8` reduced the staged reduction slice from one `dc_0`
     4-channel slice to one input channel and regressed badly:
     `174.005 ms` vs `156.785 ms`
   - report:
     `session_bootstrap/reports/transpose1_v8_remote_benchmark_20260402_185518.md`

4. The width-side follow-up is not a real reduction from the current `v7`
   structure.
   - `v7` already stages one `34 x 10` padded stripe once and reuses it across
     both `w_1` positions.
   - splitting that into two `w_1` windows would require two `34 x 6` padded
     windows, so staged width work grows from `10` columns to `12`.
   - local count:
     per-buffer staged writes grow from `1,044,480` to `1,253,376`
     (`+20%`), so this is a duplication seam, not a reduction seam.

5. The kernel-side seam is too weak relative to the still-dominant data staging.
   - in checked-in `v7`, `kernel_transform` writes only
     `24 * 48 * 3 * 3 = 10,368` elements once per operator call.
   - the `v7` `data_dilate + data_pad` staging writes
     `2,088,960` elements across spatial tiles / stripes / `dc_0` slices.
   - ratio: staged data writes are about `201.48x` larger than the one-time
     kernel transform write volume.
   - recent kernel-pack style probes also regressed on nearby lanes:
     `transpose2 v3` and `conv2d3_add15 v2`.

## Concrete Decision

No credible non-overlap transpose1 follow-up seam remains near `v7` under the
current local evidence.

Keep `transpose1 v7` as the active promoted transpose1 result and stop creating
new transpose1 branches until a materially different seam exists.

## Re-ranked Next Project-wide Target

### 1) `fused_conv2d_transpose_add6`

Choose this as the next active speedup target.

Why it moves to the top now:

- runtime share is still large:
  `14.35%` in
  `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- a real accepted board gain already exists:
  `159.503 ms` in
  `session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`
- only bias fusion plus two micro-tune branches have been consumed so far:
  `P2` regressed and `P4` regressed
- the checked-in scheduled-form TIR still has the same materialized
  `data_dilate`, `data_pad`, and `kernel_transform` structure as the winning
  transpose1 lane, so the transpose1-style data-locality family is still
  available here and has not been spent yet

### 2) `fused_conv2d_transpose2_add12`

Keep it second, not first.

- it is still the largest runtime hotspot at `21.76%`
- but current repo evidence already covers multiple losing follow-ups on the
  accepted seam:
  `P1`-style fusion, `P2`, `P4`, and `v3` kernel repack
- after that spread of losses, there is no equally concrete next seam today
  comparable to the transpose1-to-transpose_add6 locality transfer

### 3) `fused_conv2d3_add15`

- runtime share is smaller at `10.15%`
- post-`v1` follow-ups already lost:
  `P2`, `P4`, and `v2` kernel repack

### 4) `fused_variance4_add13_tir_sqrt4`

- reserve lane only
- recent work closed evaluability, not speed
- the latest remote result still did not beat reference staging

## Why No New Scaffold Was Added Here

`transpose_add6` already has a stable checked-in handwritten lane, accepted
`v1` baseline, focused tests, and a working local post-db build path.

The next meaningful move is the first real locality edit on top of that lane,
not another empty transpose1-style placeholder clone.

## Exact Next Action

Work on `fused_conv2d_transpose_add6` next.

Specifically:

1. freeze the accepted `v1` files as the baseline to beat
2. create the first isolated follow-up edit surface for transpose_add6
3. spend the first real branch on the transpose1-style data-locality family:
   stage once and reuse more aggressively before touching kernel layout or more
   micro-tuning
4. validate locally first with the existing transpose_add6 post-db swap build
   path, then decide whether the result is mature enough for a board benchmark
