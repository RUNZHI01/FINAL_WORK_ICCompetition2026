# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` v5 Local Status

Date: `2026-04-06`

## Starting Point

- `mean4 v4` had already been proven to be the baked-in baseline for the
  repo's current handwritten final route, so simply re-integrating `v4` could
  not create a new handwritten-line artifact
- the next useful branch therefore had to be **beyond v4**, while staying
  inside the same post-db scheduled-form seam
- the target constraint still comes from the same board facts: Phytium Pi is
  treated as `cortex-a72 + neon`, and `mean4` is dominated by hot epilogue
  traffic on `1 x 12 x 256 x 256`

## Chosen Edit

`v5` keeps the `v4` direction but compresses the channel-wise epilogue
parameters one step further:

- keep the mean reduction intact
- keep the one-pass spatial epilogue
- precompute an affine pair once per channel:
  - `scale = weight / std`
  - `shift = bias - mean * scale`
- rewrite the hot loop into:
  - `x * scale + shift`
  - then `relu`

This keeps the schedule-preserving/post-db path intact while removing one more
layer of repeated per-element epilogue work from the inner loop.

## Files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v5_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy.py`
- `./session_bootstrap/reports/mean4_v5_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_mean4_subtract4_divide4_multiply4_add14_relu3 \
  --candidate-tir ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/mean4_v5_correctness_check_20260406.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v5_20260406_affine_precompute

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406
```

## Local Status

- focused tests: `4 / 4 OK`
- correctness vs frozen scheduled reference:
  - `exact_equal = false`
  - `allclose_atol1e-6_rtol1e-6 = true`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 9.5367431640625e-07`
  - `mean_abs_diff = 2.8699618681571337e-08`
  - `nonzero_diff_count = 195747`
- post-db swap/build/export:
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- exported operator-level artifact:
  - artifact SHA256:
    `02224b16b398cbe62d0c7c419051a5833c982072445639330486524cce082b1d`
  - artifact size: `1673976`
- integrated handwritten-line artifact:
  - preset: `opus_final_v3_mean4`
  - candidate override:
    `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v5 working copy`
  - artifact SHA256:
    `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
  - artifact size: `1674024`
- current handwritten final baseline for comparison:
  - artifact SHA256:
    `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
  - artifact size: `1674120`

## Interpretation

- `v5` is a real new branch beyond the baked-in `v4` baseline
- it stays inside the same accepted numerical tolerance envelope as `v4`
- unlike `v4`, this branch does **not** collapse back to the repo's current
  handwritten final artifact when integrated through the real handwritten
  preset

That makes `v5` a board-worthy handwritten-line candidate instead of another
identity-only local ablation.

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/mean4_v5_correctness_check_20260406.json`
- build report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v5_20260406_affine_precompute/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- operator-level artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v5_20260406_affine_precompute/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- handwritten-line integration report:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/integration_report.json`
- handwritten-line artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so`

## Board Follow-up

The board result for the handwritten-line `v5` artifact is recorded separately
in:

- `./session_bootstrap/reports/handwritten_mean4_v5_line_remote_benchmark_20260406_1537.md`
