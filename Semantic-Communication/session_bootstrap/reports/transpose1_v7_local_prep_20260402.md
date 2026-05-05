# `fused_conv2d_transpose1_add9` v7 Local Prep

Date: `2026-04-02T18:18:00+08:00`

## Chosen Move

- baseline to beat: checked-in `transpose1 v6`
  (`./session_bootstrap/reports/transpose1_v6_remote_benchmark_20260402_180831.md`)
- new follow-up: keep `v6`'s materialized `data_dilate` / `data_pad` /
  `kernel_transform` strategy and the winning `h_1` stripe shape, but move
  data staging inside `dc_0` so only one `4`-channel by `34 x 10` slice is
  prepared at a time before immediate reuse across all three `c_1` groups and
  both `w_1` positions

Rationale: this stays in the same winning staging/reuse/locality family as
`v4` and `v6`, preserves the successful `c_1`-before-`w_1` consumer family,
and reduces how much staged input-channel state must stay hot before compute
consumes it. Unlike a `w_1`-window follow-up, it does not duplicate width-halo
staging, and unlike the dropped `v5` lane it does not switch to
`h_1`/`w_1`-before-`c_1`.

## Alternatives Explicitly Deprioritized

- `w_1`-window staging:
  deprioritized because splitting the current `10`-column stripe into two
  `6`-column windows would duplicate shared halo columns and push the loop
  structure back toward the already-regressed `v5` consumer-order direction
- finer `h_2` or `w_2` micro-stripes:
  deprioritized because they would multiply staging frequency and duplicate
  halo rows/columns much more aggressively than the current `h_1` stripe
- kernel-side locality changes:
  deprioritized because the only fresh winning evidence in this lane came from
  changing when staged data is prepared and reused, not from moving
  `kernel_transform`
- closed losing families stay closed:
  raw pre-compile `v0`, `P1` dilate+pad fusion, `P3` direct guarded read, and
  the `v5` `h_1/w_1 -> c_1` consumer-order branch

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v7_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy.py`
- `./session_bootstrap/reports/transpose1_v7_local_prep_20260402.md`

## Commands Run

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy.py
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v7_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v7_vs_v6_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v7_vs_v1_p2_p4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v7_20260402_dc0_slice
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- scheduled reference vs `v7`:
  `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`,
  `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- leading `v6` vs `v7`:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- accepted `v1/P2/P4` vs `v7`:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap build:
  `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local artifact SHA256:
  `6ebc1377fbbc9cab36a81d586acb2f2b4a8b9e7cce01d1241022835245718131`
- no SSH, scp, or remote board commands were used

## Outputs

- scheduled reference vs `v7` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v7_correctness_20260402/check_report.json`
- `v6` vs `v7` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v7_vs_v6_correctness_20260402/check_report.json`
- accepted `v1/P2/P4` vs `v7` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v7_vs_v1_p2_p4_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v7_20260402_dc0_slice/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v7_20260402_dc0_slice/fused_conv2d_transpose1_add9_post_db_swap.so`

## Exact Next Board-side Step

Benchmark this exact local artifact on the board without mutating the frozen
`v6` path:

- candidate entrypoint:
  `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7.py`
- swapped artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v7_20260402_dc0_slice/fused_conv2d_transpose1_add9_post_db_swap.so`
- compare against the existing `v6` board baseline report:
  `./session_bootstrap/reports/transpose1_v6_remote_benchmark_20260402_180831.md`

Use the same standard board payload benchmark protocol you used for `v6`.

## Operator Control

Git commit was intentionally left untouched for manual operator control.
