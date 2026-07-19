# `fused_conv2d_transpose1_add9` v8 Local Prep

Date: `2026-04-02T18:53:00+08:00`

## Chosen Move

- baseline to beat: checked-in `transpose1 v7`
  (`./session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`)
- rejected first direction: both the broader `h_1` overlap-carry probe and the
  narrower producer-only overlap-carry probe failed local correctness at the
  `h_1` stripe boundary, so that lane was not kept as the checked-in `v8`
- checked-in `v8` follow-up: keep `v7`'s one-`h_1`-at-a-time `34 x 10` stripe,
  keep the winning `c_1 -> w_1` reuse order, and narrow the staged reduction
  slice from one `4`-channel `dc_0` slice to one input channel at a time

Rationale: after the overlap lane failed twice, the nearest conservative
follow-up in the same winning staging/reuse/locality family was to reduce the
live staged reduction-channel footprint without reopening the known-losing
`v5` consumer-order branch or reintroducing the broken `h_1` boundary carry.
This keeps the `v7` data-locality shape intact while making the staged slice
strictly narrower.

## Alternatives Explicitly Deprioritized

- both `h_1` overlap-carry variants:
  closed by local correctness failure, so they are not the checked-in `v8`
- `w_1`-window / rolling-width follow-up:
  still deprioritized because it pushes back toward the already-losing
  consumer-order direction
- kernel-side slice staging:
  still deprioritized behind data-side narrowing because the fresh winning
  evidence in transpose1 came from staged-data locality changes

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v8_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy.py`
- `./session_bootstrap/reports/transpose1_v8_local_prep_20260402.md`

## Commands Run

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py \
  session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy.py
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v8_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v8_vs_v7_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v8_20260402_single_channel_slice
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- scheduled reference vs `v8`:
  `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`,
  `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- `v7` vs `v8`:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap build:
  `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local artifact SHA256:
  `2968e548b40d1cc0942daa87947afc13962134a7d66bfab63042390ab9f4b3a5`
- no SSH, scp, or remote board commands were used

## Outputs

- scheduled reference vs `v8` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v8_correctness_20260402/check_report.json`
- `v7` vs `v8` correctness JSON:
  `./session_bootstrap/tmp/transpose1_v8_vs_v7_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v8_20260402_single_channel_slice/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v8_20260402_single_channel_slice/fused_conv2d_transpose1_add9_post_db_swap.so`

## Exact Next Board-side Step

Benchmark this exact local artifact on the board without mutating the frozen
`v7` path:

- candidate entrypoint:
  `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8.py`
- swapped artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v8_20260402_single_channel_slice/fused_conv2d_transpose1_add9_post_db_swap.so`
- compare against the existing `v7` board baseline report:
  `./session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`

Use the same standard board payload benchmark protocol you used for `v7`.

## Operator Control

Git commit was intentionally left untouched for manual operator control.
