# Project Speedup Rerank After Variance4 Freeze

- generated_at: `2026-04-03T03:31:26+08:00`
- scope: `repo-local rerank after freezing variance4 at v18`
- frozen variance4 result in force:
  `session_bootstrap/reports/variance4_v18_remote_benchmark_20260403_0239.md`
- variance4 follow-up closure:
  `session_bootstrap/reports/variance4_v19_remote_benchmark_20260403_0307.md`
- chosen next target: `fused_conv2d_transpose2_add12`

## Decision

Freeze `fused_variance4_add13_tir_sqrt4` at `v18` as the current best
board-proven result for that lane, and move the next active handwritten speedup
attempt to `fused_conv2d_transpose2_add12`.

This is a rerank, not a claim that `transpose2` is already winning. The point
is ROI: after the new `variance4` evidence and the latest `transpose_add6`
negative result, `transpose2` again has the best remaining combination of
hotspot size, lane maturity, and still-unspent structural upside.

## Current Evidence Snapshot

- `variance4` is now explicitly frozen:
  - `v18` board median `158.347 ms`
  - `v19` board median `158.556 ms`
  - conclusion: `v19` is a real explored branch, but `v18` stays best
- `transpose_add6` already spent the exact locality family that justified its
  last promotion:
  - accepted `v1` board median `159.503 ms`
  - first real `v2` `dc_0`-slice `data_pad` reuse candidate:
    `172.836 ms`
  - report:
    `session_bootstrap/reports/transpose_add6_v2_dc0_slice_remote_benchmark_20260403_0030.md`
- `transpose2` remains the largest unresolved deconv hotspot in the accepted
  profile family and still has a schedule-backed local/remote baseline:
  - accepted `v1` board median `161.416 ms`
  - report:
    `session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`

## Re-ranked Opportunities

### 1) `fused_conv2d_transpose2_add12`

Best remaining headline potential.

Why it moves back to the top:

- it is still the largest remaining deconv hotspot in the accepted reprobe
  evidence
- the lane is mature:
  - direct DB/query hits exist
  - accepted `v1` has already been built and board-benchmarked
  - remote payload comparison protocol is already known to work
- the rejected branches are now clearly bounded:
  - `P2` width retune
  - `P4` unroll micro-tune
  - `v2` `data_dilate + data_pad -> data_dilate_pad` fusion
  - `v3` kernel-transform repack
- unlike the exhausted branches above, accepted `v1` still stages a full
  `10 x 258` padded strip for every outer height tile, which leaves a distinct
  width-window data-staging seam unspent

### 2) `fused_conv2d_transpose_add6`

Still valuable, but no longer first.

Why it falls behind `transpose2`:

- the lane does have a real accepted win:
  - `v1` board median `159.503 ms`
- helper/deploy mechanics are now in place, so future board proof is easy
- but the very reason it was promoted after transpose1 closure was the
  unspent transpose1-style locality family, and the first real spend on that
  family (`v2 dc_0-slice data_pad reuse`) was a strong regression on board

Interpretation:

`transpose_add6` should stay live, but not as the first spend until it has a
materially different seam than the already-losing `v2` shape.

### 3) `fused_conv2d3_add15`

Lower expected ROI than the two deconv lanes.

Why:

- accepted `v1` never beat the stronger handwritten deconv states
- `P2`, `P4`, and `v2` kernel repack all regressed on board
- the remaining next seam is less obvious than the new width-window staging
  seam now available in `transpose2`

### 4) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

Reserve underexplored lane, but not the best immediate spend.

Why:

- it remains underexplored
- but it still lacks direct best-staging DB schedule hits
- there is still no board-proof path for a real handwritten mean4 candidate
- integrated upside is smaller than the active deconv hotspots

### 5) `fused_variance4_add13_tir_sqrt4`

Frozen reserve lane only.

Why:

- `v18` is a real board-proven positive result and should be preserved
- `v19` already shows the current family is in diminishing-return territory
- the user-visible mission now is explicitly to stop grinding this lane for
  tiny follow-ups

## Chosen Next Move

Use `fused_conv2d_transpose2_add12` as the next active handwritten lane.

The smallest honest continuation is:

1. keep accepted `v1` frozen
2. open a separate `v4` branch for the width-window data-staging seam
3. stage only the current `w_0`-local `10 x 34` window instead of the full
   `10 x 258` padded strip
4. rerun the standard local proof path before any board claim
