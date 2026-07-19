# `fused_conv2d_transpose1_add9` v6 Local Prep

Date: `2026-04-02T18:02:08+08:00`

## Chosen Move

- baseline to beat: checked-in `transpose1 v4`
  (`./session_bootstrap/reports/transpose1_v4_remote_benchmark_20260402_172812.md`)
- new follow-up: keep the `v4` materialized `data_dilate` / `data_pad` /
  `kernel_transform` strategy, but narrow the staged data region from the full
  `66 x 10` tile to the `34 x 10` stripe needed by one `h_1` region at a time
- consumer order for the new stripe stays `h_1 -> c_1 -> w_1`, so the new lane
  still reuses each staged stripe across all three `c_1` groups and both `w_1`
  positions without reopening the dropped `v5` `h_1/w_1 -> c_1` direction

Rationale: this is the most direct remaining follow-up in the same
staging/reuse/locality family that produced the current leading `v4` result.
It keeps the proven materialized-buffer strategy intact, keeps reuse across the
three output-channel groups, and shrinks the live staged data footprint in the
dimension where the tile is still wide enough to meaningfully reduce staged
rows (`66 -> 34`) without changing the reduction math.

## Alternatives Explicitly Deprioritized

- `v5` full-tile `h_1/w_1 -> c_1` consumer-order follow-up:
  already proven worse than `v4`, so it is not the next branch
- `w_1`-stripe staging follow-up:
  deprioritized behind `h_1`-stripe staging because the current tile is already
  only `10` padded columns wide, so the live-set reduction is smaller and the
  loop shape leans back toward the same consumer-order family that just lost
- kernel-side or other non-data-staging locality follow-ups:
  deprioritized because the only fresh winning evidence in this lane came from
  changing when the data tile is staged and reused, not from moving
  `kernel_transform` or reopening a different family
- older losing families remain closed:
  raw pre-compile `v0`, `P1` dilate+pad fusion, and `P3` direct guarded read

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v6_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v6.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy.py`
- `./session_bootstrap/reports/transpose1_v6_local_prep_20260402.md`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v6 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v6_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v6_vs_v4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v6_vs_v1_p2_p4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v6_20260402_h1_stripe
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- scheduled reference vs `v6`:
  `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`,
  `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- leading `v4` vs `v6`:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- accepted `v1/P2/P4` vs `v6`:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap build:
  `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- no SSH, scp, or remote board commands were used

## Outputs

- scheduled reference vs `v6` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v6_correctness_20260402/check_report.json`
- `v4` vs `v6` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v6_vs_v4_correctness_20260402/check_report.json`
- accepted `v1/P2/P4` vs `v6` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v6_vs_v1_p2_p4_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v6_20260402_h1_stripe/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v6_20260402_h1_stripe/fused_conv2d_transpose1_add9_post_db_swap.so`
- build artifact SHA256:
  `9371c8d3287d24ffc02a3db0c63d56dcebc14329722350f59324dfe49361bb42`

## Exact Next Board-side Step

Benchmark this exact local artifact on the board without mutating the frozen
`v4` path:

- candidate entrypoint:
  `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6.py`
- swapped artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v6_20260402_h1_stripe/fused_conv2d_transpose1_add9_post_db_swap.so`
- compare against the existing `v4` board baseline report:
  `./session_bootstrap/reports/transpose1_v4_remote_benchmark_20260402_172812.md`

Use the same standard board payload benchmark protocol you used for `v4` and
`v5`.
