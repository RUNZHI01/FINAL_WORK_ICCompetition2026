# `fused_conv2d_transpose1_add9` v10 Local Status

Date: `2026-04-06`

## Starting Point

- start from the exact checked-in `transpose1 v7` state
- `v7` remains the current board-proven transpose1 baseline with remote median
  `156.785 ms`
- keep the failed `v8` narrower-slice branch and failed `v9` shared-`data_pad`
  seam-writeback branch as negative evidence

## Chosen Edit

- keep the winning `v7` locality family intact:
  one `h_1` stripe at a time, one `dc_0` 4-channel slice at a time, and the
  same `c_1 -> w_1` consumer order
- keep an explicit 2-row seam buffer captured after `h_1 == 0`
- for `h_1 == 1`, route the current 34 x 10 consumer stripe through a
  **disjoint current buffer** instead of rewriting shared `data_pad` rows
  in place
- feed `compute_update` from that disjoint current buffer for the second
  stripe only

Rationale: the earlier disjoint seam-buffer diagnostic proved that the
consumer-facing staged rows themselves can match `v7` exactly before
`compute_update`. `v10` exists to promote that idea into a real checked-in
scheduled-form candidate and test whether the full local proof and post-db
build path remain clean.

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v10_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v10_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v10.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v10.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v10_working_copy.py`
- `./session_bootstrap/reports/transpose1_v10_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v10 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v10_working_copy

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v10_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v10_vs_v7_correctness_20260406/check_report.json

python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v10.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v10_20260406_disjoint_current
```

## Local Status

- focused `v10` wrapper/working-copy tests: `4/4 OK`
- local correctness vs frozen `v7`:
  `exact_equal = false`,
  `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.509618759155273`,
  `nonzero_diff_count = 12288`
- despite the correctness failure, the post-db scheduled swap/build/export path
  still succeeded:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported artifact SHA256:
  `124a0b9bfa2db61745c69f90693e92992590e1f81c42e2273541d333de6462ce`
- exported artifact size bytes: `1678648`

## Interpretation

This result closes one important question:

- the disjoint second-stripe idea is **mechanically buildable** through the
  current post-db seam
- but the first full checked-in `v10` formulation is still **not exact** versus
  the winning `v7` baseline

The failure signature matches the earlier overlap-family failures rather than a
new roundoff-only mismatch, so this branch is **not** ready for board
benchmarking.

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/transpose1_v10_vs_v7_correctness_20260406/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v10_20260406_disjoint_current/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v10_20260406_disjoint_current/fused_conv2d_transpose1_add9_post_db_swap.so`

## Board Boundary

Do **not** run a board benchmark for `transpose1 v10` in its current state.

The next transpose1 step, if this family is resumed, should stay local-only and
re-examine why the full `compute_update` path still reproduces the same four-row
failure pattern even after switching the second stripe to a disjoint
consumer-facing buffer.
