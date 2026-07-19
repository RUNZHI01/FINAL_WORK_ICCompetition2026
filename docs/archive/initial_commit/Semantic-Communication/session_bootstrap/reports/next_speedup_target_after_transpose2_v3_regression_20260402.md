# Next Speedup Target After Transpose2 v3 Regression

- generated_at: `2026-04-02`
- scope: rerank the remaining handwritten-optimization lanes after the new `transpose2 v3` board regression
- decision: `choose fused_conv2d_transpose1_add9 as the next active handwritten speedup target`

## New facts this rerank must absorb

- `transpose2 v3` is now a confirmed real-hardware regression:
  `session_bootstrap/reports/transpose2_v3_remote_benchmark_20260402_165612.md`
  - accepted `transpose2 v1`: `161.416 ms`
  - `transpose2 v3`: `162.729 ms`
  - delta vs accepted `v1`: `+1.313 ms` (`+0.81%`)
- `variance4` remote validation is now complete, but it answered only evaluability, not speed:
  `session_bootstrap/reports/variance4_v13_remote_benchmark_20260402_162140.md`
  - `variance4 v13`: `161.156 ms`
  - delta vs reference staging: `+1.213 ms` (`+0.76%`)
- prior handwritten branches already consumed:
  - `transpose1`: raw `v0` regression, accepted `P2+P4` at `159.356 ms`, `P1 v2` no gain, `P3 v3` catastrophic regression
  - `transpose_add6`: accepted `v1` at `159.503 ms`, `P2` regression, `P4` regression
  - `conv2d3_add15`: accepted `v1` at `161.000 ms`, `P2` regression, `P4` regression, `v2 kernel repack` regression

## Runtime ROI frame

From the latest accepted 3-sample runtime profile
`session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`:

1. `fused_conv2d_transpose2_add12`: `21.76%`
2. `fused_conv2d_transpose1_add9`: `20.26%`
3. `fused_conv2d_transpose_add6`: `14.35%`
4. `fused_conv2d3_add15`: `10.15%`
5. `fused_variance4_add13_tir_sqrt4`: `5.05%`

The hotspot order still matters, but branch exhaustion now matters more than raw share.

## Re-ranked remaining opportunities

### 1) `fused_conv2d_transpose1_add9`

Why it moves to the top:

- it is still the largest **remaining** hotspot once `transpose2` is removed from the active queue
- this lane has already shown that schedule-preserving handwritten edits can move real hardware in the right direction:
  - `v1`: `162.954 ms`
  - accepted `P2+P4`: `159.356 ms`
  - gain vs `v1`: `-3.598 ms`
- the losing branches are informative rather than totally disqualifying:
  - raw `v0` proved the old pre-compile seam is not performance-comparable
  - `P1 v2` says do not chase dilate+pad fusion on this family
  - `P3 v3` says do not chase direct guarded reads on this scheduled form
- that leaves one honest remaining path: a **fundamentally different** transpose1 locality/schedule idea on top of the accepted `P2+P4` state

### 2) `fused_conv2d_transpose_add6`

Why it stays close but second:

- real accepted win exists: `159.503 ms`, slightly better than reference staging
- runtime share is still large at `14.35%`
- however the lane has less demonstrated upside than `transpose1`, and its most obvious follow-ups are already weakened by cross-lane evidence:
  - its own `P2` and `P4` both regressed
  - the analogous `P1` and `P3` style moves already failed on the larger transpose lanes

### 3) `fused_conv2d3_add15`

Why it falls further back:

- smaller hotspot than the deconv lanes
- every board-tested follow-up after `v1` lost:
  - `P2`
  - `P4`
  - `v2 kernel repack`
- after the new `transpose2 v3` result, another kernel-pack-style reopen looks even less attractive here

### 4) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

Why it remains only a reserve option:

- a repo-local handwritten lane exists, but the latest accepted runtime profile no longer puts it in the top active shortlist
- integrated upside is smaller than the deconv lanes
- its validation surface is also less mature than `transpose1`, `transpose_add6`, and `conv2d3`

## Explicitly deprioritized

### `fused_conv2d_transpose2_add12`

Deprioritize for now, even though it is still the single largest hotspot:

- accepted baseline exists: `161.416 ms`
- failed follow-ups now cover multiple distinct directions:
  - `P2` width retune regressed
  - `P4` unroll change showed no gain
  - `P1-style v2` dilate+pad fusion regressed
  - `v3` kernel_transform output-channel-inner repack regressed
- after today’s `v3` result, continuing to push `transpose2` without a qualitatively new seam would be blind iteration

### `fused_variance4_add13_tir_sqrt4`

Deprioritize because:

- the remote path question is answered
- the current exact-preserving cleanup family does not generate a faster artifact
- recent work should be treated as evaluability closure, not an active speedup lane

## Chosen next target

Choose `fused_conv2d_transpose1_add9`.

Why this is the best expected ROI now:

- it combines very high runtime share with the strongest evidence that handwritten scheduled-form edits can still create real board gains
- it already has an accepted benchmarked state (`P2+P4`) that is the current fastest handwritten result in-repo
- unlike `transpose2`, its recent failures are specific enough to bound what not to try next, rather than indicating that the whole lane is exhausted

## Prepared next move

This commit adds an isolated `transpose1 v4` scaffold:

- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v4_working_copy_manifest.json`

Important scope note:

- the checked-in `v4` working copy intentionally still matches the accepted `transpose1 P2+P4` state
- this is **not** a new performance candidate
- the point is to freeze the accepted baseline and give the next real transpose1 idea a clean edit surface

## Exact next action

Apply the first genuinely different transpose1 edit inside:

- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py`

Then sanity-check it locally with:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4
```
