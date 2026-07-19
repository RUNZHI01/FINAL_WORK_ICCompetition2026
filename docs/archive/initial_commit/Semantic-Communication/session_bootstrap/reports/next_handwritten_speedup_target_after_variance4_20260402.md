# Next Handwritten Speedup Target After Variance4 Validation

- generated_at: `2026-04-02`
- scope: repo-local rerank after `variance4` remote path validation
- decision: `choose fused_conv2d_transpose2_add12 as the next live handwritten speedup target`

## Current evidence snapshot

- `variance4` is now remotely benchmarkable, but the validated `v13` artifact does not improve runtime:
  `session_bootstrap/reports/variance4_v13_remote_benchmark_20260402_162140.md`
- current runtime hotspot order from the accepted current artifact is still headed by:
  `fused_conv2d_transpose2_add12`, `fused_conv2d_transpose1_add9`,
  `fused_conv2d_transpose_add6`, `fused_conv2d3_add15`, `fused_variance4_add13_tir_sqrt4`
  per `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`

## Re-ranked remaining handwritten opportunities

1. `fused_conv2d_transpose2_add12`
   - still the largest remaining runtime hotspot in the current accepted profile
   - already has a stable local/remote handwritten baseline (`v1 = 161.416 ms`)
   - the clearly losing branches are now known and narrow:
     `P2`, `P4`, and `P1-style v2` all regressed or showed no gain
   - unlike `transpose1`, this lane has not yet consumed a fundamentally different scheduled-form seam under the accepted path

2. `fused_conv2d_transpose_add6`
   - real accepted win exists (`v1 = 159.503 ms`, slightly better than reference staging)
   - runtime share is meaningful, but lower than `transpose2`
   - both immediate follow-ups (`P2`, `P4`) already regressed, so the next reopen would need a new seam similar to `transpose2` but with less upside

3. `fused_conv2d3_add15`
   - still a real hotspot, but smaller than the deconv lanes
   - multiple distinct branches are now exhausted on board:
     `P2`, `P4`, and `v2 kernel repack`
   - this lane has already burned both micro-tune and memory-layout branches without a win, so it falls behind `transpose2`

4. `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
   - a clean handwritten lane exists, but the current profile share is much smaller than the deconv/conv lanes
   - no real speedup attempt has been run yet, but even a successful edit has limited integrated upside relative to the top deconv hotspot

## Explicitly deprioritized branches

- `fused_conv2d_transpose1_add9`
  - do not reopen under the current seam without a fundamentally different loop/schedule strategy
  - repo evidence already covers:
    raw `v0` catastrophic regression,
    accepted `P2+P4` baseline,
    `P1 v2` no-gain,
    `P3 v3` catastrophic regression

- `fused_variance4_add13_tir_sqrt4`
  - do not spend more time on the current syntax/lowering cleanup family
  - the lane is now proven remotely benchmarkable, but `v13` delivered no speed win and the recent chain has explicit diminishing-return evidence

## Chosen next target

Choose `fused_conv2d_transpose2_add12`.

Why this is the best ROI now:

- it still owns the largest remaining runtime share in the accepted profile
- the lane already has a trustworthy local/remote baseline and a stable comparison protocol
- the losing branches are now clearly bounded (`P1`, `P2`, `P4`), which means the next edit can avoid them instead of repeating low-yield variants
- relative to `conv2d3` and `transpose_add6`, the remaining upside is larger and less obviously exhausted

## Prepared next engineering move

This commit establishes an isolated `transpose2 v3` scaffold:

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v3_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`

Important scope note:

- the checked-in `v3` scaffold intentionally still matches the accepted `v1` operator body
- this is lane establishment, not a new performance candidate
- the purpose is to give the next edit a clean surface for a `kernel_transform`-side locality experiment without mutating the accepted `v1` baseline or reopening the already-dropped `P1/P2/P4` branches

## Exact next local action

Apply the first real `v3` edit inside:

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py`

Then validate it locally with:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3
```
