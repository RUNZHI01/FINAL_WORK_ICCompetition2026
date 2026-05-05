# `fused_conv2d_transpose1_add9` v9 Local Prep

Date: `2026-04-02T19:18:56+0800`

## Chosen Move

- exact/current performance baseline kept in force: checked-in `transpose1 v7`
  (`./session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`,
  remote median `156.785 ms`)
- dropped lane kept closed: `transpose1 v8` single-input-channel slice
- checked-in `v9` local-proof candidate: keep `v7`'s one-`h_1`-at-a-time `34 x 10`
  stripe, one `dc_0` `4`-channel staged slice, and `c_1 -> w_1` consumer order,
  then add an explicit tile-indexed `2`-row `data_pad` seam carry

Rationale: the overlap-boundary diagnostic proved that the seam row values are
exact on both producer and consumer sides, but the old overlap probe failed
because it depended on skipped writes and stale state. This `v9` candidate makes
the carry explicit while keeping the winning `v7` structure otherwise intact.

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v9_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy.py`
- `./session_bootstrap/reports/transpose1_v9_local_prep_20260402.md`

## Commands Run

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy.py
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v9_vs_v7_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v9_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v9.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v9_20260402_explicit_carry
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- scheduled reference vs `v9`:
  `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.509618759155273`, `nonzero_diff_count = 312051`
- `v7` vs `v9`:
  `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.509618759155273`, `nonzero_diff_count = 12288`
- seam-failure shape from the local row check:
  output diffs remain on rows `32`, `33`, `96`, `97`
- local post-db scheduled swap build:
  `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local artifact SHA256:
  `ddcbb0fa38540232e683143ca41b8f32f4b2c99f11c2228bfba4dcf94ae88365`
- no SSH, scp, or remote board commands were used

## Exact Local Proof Verdict

Result: **`v7` exactness was not preserved**

The explicit `2`-row seam-carry proof candidate is mechanically swappable and
buildable locally, but it still fails exact local correctness against the
frozen `v7` baseline. This means the current explicit-carry formulation is not
ready for board benchmarking.

## Outputs

- scheduled reference vs `v9` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v9_correctness_20260402/check_report.json`
- `v7` vs `v9` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v9_vs_v7_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v9_20260402_explicit_carry/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v9_20260402_explicit_carry/fused_conv2d_transpose1_add9_post_db_swap.so`

## Exact Board-side Step

No board-side step is recommended for this `v9` artifact.

Because local `v7` exactness failed, do **not** run the board benchmark for
`transpose1 v9`. The next operator step should remain local-only: redesign the
explicit seam carry and prove exact equality vs `v7` before any remote run.

## Operator Control

Git commit was intentionally left untouched for manual operator control.
