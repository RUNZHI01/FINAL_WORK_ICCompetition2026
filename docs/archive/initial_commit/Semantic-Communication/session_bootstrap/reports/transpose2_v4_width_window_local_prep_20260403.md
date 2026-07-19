# Transpose2 v4 Width-Window Local Prep

- generated_at: `2026-04-03T03:31:26+08:00`
- operator: `fused_conv2d_transpose2_add12`
- stage: `v4 w0-local 10x34 data staging on top of accepted v1`
- status: `local prep complete; exact-vs-v1; ready for board benchmark`

## Chosen Edit

On top of the accepted `transpose2 v1` bias-fused baseline, this `v4`
candidate:

- keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized
- keeps the accepted bias-fused `compute_init` / `compute_update` path
- keeps the scheduled h/w tiling, reduction split `dc_0 x dc_1 = 4 x 6`,
  outer height-tile sweep, and `pragma_auto_unroll_max_step = 32`
- changes only the data-staging scope:
  - before: stage the full `10 x 258` padded strip, then reuse it across all
    eight `w_0` tiles
  - now: move staging inside `w_0` and prepare only the current `10 x 34`
    window before reusing it across the four `h_1` rows for that tile

## Why This Edit

This is deliberately different from the already-dropped `transpose2` branches:

- not `P2` width retuning
- not `P4` unroll tuning
- not `v2` `data_dilate + data_pad -> data_dilate_pad` fusion
- not `v3` kernel-transform repack

The accepted `v1` loop nest still pays for a very wide staged strip
(`258` padded columns) even though each `w_0` tile only consumes a `34`-column
window. This `v4` branch spends that width-locality seam without changing the
accepted arithmetic or kernel layout.

## Files Changed

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v4_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/README.md`

## Commands Run

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py \
  session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py \
  session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy.py

python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4 \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose2_v4_correctness_20260403_codex/check_report.json

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose2_v4_vs_v1_correctness_20260403_codex/check_report.json

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex
```

## Local Status

- focused unit tests: `4 tests`, `OK`
- scheduled reference vs `v4`:
  - `exact_equal = false`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 4.76837158203125e-06`
  - `mean_abs_diff = 2.3944838289935433e-07`
  - `nonzero_diff_count = 607527`
- accepted `v1` vs `v4`:
  - `exact_equal = true`
  - `max_abs_diff = 0.0`
  - `nonzero_diff_count = 0`
- local post-db scheduled swap:
  - `candidate_status = v4_w0_window_data_stage_applied`
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`

## Exported Artifact

- local artifact:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256:
  `e8d66616b53064aa9af730dd8649dedbf399eb8afca5cbed8c1bf7a96a359a8f`
- accepted `v1` local sha256:
  `bae5c138c3c21fda694bd21db4bbd19144263ec3bab3d7de30ab3942551dd561`

Interpretation:

This branch is now:

- exact-equal to the accepted `v1` operator path under the local checker
- mechanically swappable on the existing post-db seam
- exportable as a distinct full-module artifact

That is enough maturity to justify a real board payload benchmark when a
socket-capable session is available.

## Evidence

- scheduled reference vs `v4` correctness JSON:
  `./session_bootstrap/tmp/transpose2_v4_correctness_20260403_codex/check_report.json`
- accepted `v1` vs `v4` correctness JSON:
  `./session_bootstrap/tmp/transpose2_v4_vs_v1_correctness_20260403_codex/check_report.json`
- local build report:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap_report.json`

## Exact Next Step

Upload this exact `.so` to a dedicated handwritten `transpose2 v4` staging
archive and benchmark it against the accepted `transpose2 v1` board baseline.
