# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` v4 Local Status

Date: `2026-04-06`

## Starting Point

- the repo's hardware notes already constrain this lane to a very specific
  optimization direction: Phytium Pi is treated as `cortex-a72 + neon`, and
  the key cache fact is `L1d = 32 KB`
- for `mean4`, the hot tensor is `1 x 12 x 256 x 256`, so repeatedly
  materializing full-frame elementwise intermediates is the wrong fit for the
  board
- the earlier `mean4 v2` board regression closed the "copy variance4's scalar
  one-element handoff family onto mean4" path as the wrong family for this
  operator

## Chosen Edit

`v4` keeps the reduction and arithmetic order intact, but changes where the
epilogue traffic lives:

- keep the existing reduction:
  `lv335_red -> T_divide_intermediate`
- stage the per-channel values once into one-element local buffers:
  - `mean_local`
  - `std_local`
  - `weight_local`
  - `bias_local`
- fuse the hot epilogue into one inner pass:
  `subtract -> divide -> multiply -> add -> relu`
- keep the final block purely spatial:
  `T.axis.remap("SSSSSS", ...)`

This is deliberately operator-specific. The point is not to scalarize every
step; the point is to stop writing four extra `1 x 12 x 256 x 256`
intermediates when `mean4` already has channel-invariant parameters that can
be hoisted and reused across the full `256 x 256` frame.

## Files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v4_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy.py`
- `./session_bootstrap/reports/mean4_v4_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_mean4_subtract4_divide4_multiply4_add14_relu3 \
  --candidate-tir ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/mean4_v4_correctness_check_20260406.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4_20260406_channel_fused
```

## Local Status

- focused tests: `4 / 4 OK`
- correctness vs frozen scheduled reference:
  - `exact_equal = false`
  - `allclose_atol1e-6_rtol1e-6 = true`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 9.5367431640625e-07`
  - `mean_abs_diff = 1.744936106717887e-08`
  - `nonzero_diff_count = 118176`
- post-db swap/build/export:
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- exported artifact:
  - `v4` artifact SHA256:
    `cb38d01fbc59c7a4acf42a95074f16757d61911628236ef890e70637b37315cd`
  - `v4` artifact size: `1674072`
- artifact distinctness:
  - earlier `mean4 v2` artifact SHA256:
    `4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2`
  - frozen staging artifact SHA256:
    `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`

## Interpretation

- `v4` is a real new branch, not a collapse back to `v2` or frozen staging
- this branch is still not exact-preserving, so it remains an allclose-gated
  handwritten candidate rather than a numerically identical rewrite
- the error stays inside the existing accepted tolerance envelope, while the
  structural change finally matches the operator's actual bottleneck:
  per-channel parameter reuse and fewer full-frame writes

That is enough to justify a real board payload attempt.

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/mean4_v4_correctness_check_20260406.json`
- build report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4_20260406_channel_fused/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4_20260406_channel_fused/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`

## Board Follow-up

The board result for this local candidate is recorded separately in:

- `./session_bootstrap/reports/mean4_v4_remote_benchmark_20260406_1425.md`
