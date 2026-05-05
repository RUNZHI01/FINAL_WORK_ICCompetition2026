# Next Speedup Target After Variance4 Validation

Date: `2026-04-02`

## Decision

The next handwritten-optimization target should be:

- `fused_conv2d_transpose2_add12`

## Why this target now

Current repo evidence says:

- `variance4` has now been taken all the way through remote path validation, and the answer is useful but negative for speed:
  - remote path is valid
  - current `v13` median = `161.156 ms`
  - delta vs reference staging = `+1.213 ms` (`+0.76%`)
  - continuing syntax-only variance4 edits is now low ROI
- `transpose2` still represents one of the largest remaining runtime hotspots, and unlike variance4 it still has a concrete next operator-side seam worth isolating
- the accepted `transpose2 v1` baseline is real, buildable, and remotely benchmarked:
  - accepted `v1` median = `161.416 ms`
- the dropped `transpose2 v2` branch answered only one thing:
  - the `P1`-style `data_dilate + data_pad -> data_dilate_pad` fusion is a regression
  - it did **not** exhaust all possible transpose2 follow-up edits

The repo-local next best use of engineering time is therefore to keep the accepted `transpose2 v1` baseline frozen and open a fresh, isolated `v3` lane aimed at a different seam.

## Explicitly deprioritized alternatives

### 1) `fused_variance4_add13_tir_sqrt4`

Deprioritized because:

- remote path is now validated already
- current exact-preserving syntax-cleanup line exports the same artifact across `v11` / `v12` / `v13`
- the board run for `v13` showed no speed gain
- more syntax cleanup is unlikely to create a new performance result without a genuinely different artifact-producing edit

### 2) `fused_conv2d_transpose1_add9`

Deprioritized because:

- it already had multiple deeper iterations than most lanes
- `P2+P4` remains the current best state
- later structural follow-ups (`v3` / direct-read path) regressed badly on real hardware
- this branch currently looks more exhausted than transpose2

### 3) `fused_conv2d3_add15`

Deprioritized because:

- the latest real-board kernel-repack follow-up (`v2`) regressed
- no equally concrete higher-ROI next seam is presently staged in-repo
- its current evidence does not beat transpose2 on expected near-term payoff

### 4) `fused_conv2d_transpose_add6`

Deprioritized because:

- `v1` is acceptable, but its known `P2` / `P4` follow-ups regressed
- current repo evidence gives no cleaner next move than the new transpose2 v3 isolation lane

## Chosen next engineering move

Create an isolated `transpose2 v3` scaffold that:

- keeps accepted `v1` frozen
- intentionally leaves the operator body unchanged for now
- records that the next real edit should target a **kernel_transform-side locality seam**, not the already-dropped `P1` branch
- is locally runnable through the existing post-db scheduled swap path

## Recommended next action

Use the new `transpose2 v3` scaffold as the edit surface for the next real handwritten pass. The next coding move should be a concrete kernel-transform-side locality experiment, followed by local proof and then a real board benchmark.
