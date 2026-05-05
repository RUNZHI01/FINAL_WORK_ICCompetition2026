# Project Speedup Rerank After Transpose2 v4 Regression

- generated_at: `2026-04-03T03:56:56+08:00`
- scope: rerank the remaining handwritten speedup lanes after `transpose2 v4`
  and `transpose_add6 v2` were both board-proven negative and `variance4` was
  frozen at `v18`
- decision: `choose fused_mean4_subtract4_divide4_multiply4_add14_relu3 as the next active handwritten lane`

## Facts This Rerank Must Absorb

- `variance4` is frozen at its current best board-proven result:
  `session_bootstrap/reports/variance4_v18_remote_benchmark_20260403_0239.md`
  - `variance4 v18 = 158.347 ms`
  - `variance4 v19 = 158.556 ms`
  - conclusion: keep `v18`, treat `v19` as a small regressing follow-up
- `transpose2 v4` is now a board-proven negative:
  `session_bootstrap/reports/transpose2_v4_remote_benchmark_20260403_0343.md`
  - accepted `transpose2 v1 = 161.416 ms`
  - `transpose2 v4 = 165.113 ms`
  - delta vs accepted `v1`: `+3.697 ms` (`+2.29%`)
  - conclusion: the width-window `w_0` data-staging family is materially spent
- `transpose_add6 v2` is also board-proven negative:
  `session_bootstrap/reports/transpose_add6_v2_dc0_slice_remote_benchmark_20260403_0030.md`
  - accepted `transpose_add6 v1 = 159.503 ms`
  - `transpose_add6 v2 = 172.836 ms`
  - delta vs accepted `v1`: `+13.333 ms` (`+8.36%`)
  - conclusion: the obvious transpose1-style locality transfer is no longer a
    live first spend for this lane
- `transpose1` remains a strong promoted result, but not a good next lane:
  `session_bootstrap/reports/transpose1_post_overlap_closure_decision_20260402.md`
  - current best board result: `transpose1 v7 = 156.785 ms`
  - closure conclusion: near-exhausted under the current `v7` seam; do not
    reopen without a materially different idea
- `conv2d3_add15` already spent its nearby schedule-preserving branches:
  - accepted baseline:
    `session_bootstrap/reports/conv2d3_add15_v1_remote_benchmark_20260331_221417.md`
    -> `161.000 ms`
  - negative follow-ups:
    `P2 = 163.238 ms`,
    `P4 = 162.029 ms`,
    `v2 kernel repack = 161.999 ms`

## Runtime ROI Frame

From the current handwritten-hotspot archive
`session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`:

- `fused_conv2d3_add15`: `11800.99 us`, `7.10%`
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3`: `11065.87 us`, `6.66%`
- `fused_variance4_add13_tir_sqrt4`: `7099.57 us`, `4.27%`

The remaining non-deconv ROI is now concentrated in `conv2d3_add15` and
`mean4`, and their hotspot gap is small enough that branch exhaustion matters
more than raw share.

## Re-ranked Remaining Opportunities

### 1) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

Why it moves to the top now:

- it is still a visible runtime hotspot at `6.66%`, only slightly behind
  `conv2d3_add15` at `7.10%`
- unlike `conv2d3_add15`, it has not already burned through several
  board-tested follow-up branches
- the latest `variance4` work materially changes the prior for this family:
  tiny reduction/epilogue handoff edits in the sibling norm-stats lane
  produced a real board gain up to `-1.00%` vs frozen staging, so this is not
  just theoretical pattern-matching
- `mean4` still lacked both a real handwritten edit and a checked-in board
  helper path, so even closing that evaluability gap is high-value repo work

### 2) `fused_conv2d3_add15`

Why it stays second:

- hotspot share is still real at `7.10%`
- the lane already has a complete board path and an accepted baseline
- however every board-tested follow-up after `v1` regressed:
  `P2`, `P4`, and `v2 kernel repack`
- that makes another nearby schedule-preserving reopen lower expected value
  than a first real `mean4` move

### 3) `fused_conv2d_transpose2_add12`

Why it falls behind despite being large:

- it is still a large hotspot, but the recently active locality seam is now
  explicitly spent by `v4`
- the lane already carries multiple distinct negative follow-ups:
  `P2`, `P4`, `P1/v2`, `v3`, and now `v4`
- it should stay live only for a materially different idea, not as the next
  default spend

### 4) `fused_conv2d_transpose_add6`

Why it stays behind `transpose2`:

- a good board baseline still exists at `159.503 ms`
- but the exact reason it was recently promoted has now been disproven by the
  `v2` board regression
- helper maturity is no longer the issue here; expected upside from the obvious
  next seam is
  materially worse than spending the first real mean4 branch

### 5) `fused_variance4_add13_tir_sqrt4`

Keep it frozen:

- `v18` is the current best board-proven result
- `v19` already answered the “one more tiny follow-up” question with a slight
  regression
- the lane should be preserved, not actively reopened right now

## Explicitly Deprioritized

### `fused_conv2d_transpose1_add9`

Do not reopen this lane for the current round:

- `transpose1 v7 = 156.785 ms` remains an excellent promoted result
- but the checked-in closure report already argues that the nearby non-overlap
  seams are spent
- spending another turn here would be broad wandering unless a genuinely new
  idea appears

## Chosen Next Target

Choose `fused_mean4_subtract4_divide4_multiply4_add14_relu3`.

Why this is the best next spend:

- it is the highest-value remaining lane that is both underexplored and still
  close to the hotspot front
- current repo evidence now supports reuse/handoff-style micro-edits on this
  norm-stats family
- the lane also benefits disproportionately from a first real candidate plus a
  first board-proof helper path, because both were still missing

## Concrete Forward Move In This Round

This round advances `mean4` in two linked steps:

1. Add the first real handwritten `v2` candidate on top of the checked-in v1
   seed clone.
   - `session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2_working_copy_tir.py`
   - edit: keep the reduction shape intact, stage the per-channel normalized
     mean once into `lv335_mean_local`, and collapse the
     subtract/divide/multiply/add chain into one-element local handoff buffers
2. Add the missing repo-pattern board helper path for `mean4`.
   - `session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py`
   - `session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`

Local proof from this same round:

- correctness vs frozen scheduled seed:
  `exact_equal = false`,
  `allclose_atol1e-6_rtol1e-6 = true`,
  `allclose_atol1e-5_rtol1e-5 = true`,
  `max_abs_diff = 9.5367431640625e-07`
- post-db swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported artifact:
  `4486eef6...02bd2 / 1674256 bytes`
- prior v1 proof artifact:
  `de429fe2...2bbc9 / 1678704 bytes`

Board step outcome from this same round:

- the first dedicated `mean4` board attempt was launched through the new helper
  path
- the upload/benchmark step was blocked by the current exec sandbox socket
  boundary before any remote SHA or payload sample could be produced
- that blocker is recorded separately in:
  `session_bootstrap/reports/mean4_v2_remote_benchmark_blocked_20260403.md`

## Exact Next Action Outside This Sandbox

Reuse the assets generated in this round:

- env:
  `./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env`
- local artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- helper:
  `./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`

Then:

1. upload the artifact through the helper
2. confirm the remote SHA matches `4486eef6...02bd2`
3. run `run_remote_tvm_inference_payload.sh --variant current`
4. decide from the real board number whether `mean4 v2` is promotable or just
   the first explored branch
