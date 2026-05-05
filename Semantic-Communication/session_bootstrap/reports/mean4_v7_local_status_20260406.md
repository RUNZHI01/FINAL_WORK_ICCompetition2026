# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` v7 Local Status

Date: `2026-04-06`

## Starting Point

- `v5` had already proven that affine precompute on top of the fused epilogue
  can beat the current handwritten final on same-day board payload
- `v6` then tested the phase-ordering hypothesis and came back as real but near
  parity board evidence
- after the `v5/v6` codegen inspection, the strongest remaining operator-local
  seam became clear:
  the epilogue was already NEON-vectorized, but the reduction was still a
  scalar dependency chain

## Chosen Edit

`v7` is a reduction-only follow-up on top of `v5`:

- keep the two-phase structure from `v5`
- keep the affine epilogue math unchanged
  - `scale = weight / std`
  - `shift = bias - mean * scale`
  - `out = max(x * scale + shift, 0)`
- replace the scalar reduction chain with a four-lane local partial sum
  structure
- split width as `64 x 4`, mark the inner lane `T.vectorized(4)`, and reduce
  the four partial sums horizontally after the channel plane is consumed

This is intentionally narrower than `v6`: the goal is to isolate
reduction-side codegen as the variable under test.

## Files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v7_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy.py`
- `./session_bootstrap/reports/mean4_v7_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_mean4_subtract4_divide4_multiply4_add14_relu3 \
  --candidate-tir ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/mean4_v7_correctness_check_20260406.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v7_20260406_partial_sum_reduction

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406
```

## Local Status

- focused tests: `4 / 4 OK`
- correctness vs frozen scheduled reference:
  - `exact_equal = false`
  - `allclose_atol1e-6_rtol1e-6 = true`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 1.430511474609375e-06`
  - `mean_abs_diff = 3.1926216337296864e-08`
  - `nonzero_diff_count = 205200`
- post-db swap/build/export:
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- exported operator-level artifact:
  - artifact SHA256:
    `98df71cc08e5f93c0f8dbc8e709694660acbd8e3b0afbc517adf31d7d5194a2b`
  - artifact size: `1672048`
- integrated handwritten-line artifact:
  - preset: `opus_final_v3_mean4`
  - candidate override:
    `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v7 working copy`
  - artifact SHA256:
    `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`
  - artifact size: `1672096`
- current handwritten final baseline for comparison:
  - artifact SHA256:
    `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
  - artifact size: `1674120`
- earlier beyond-`v4` branch for comparison:
  - `v5` handwritten-line artifact SHA256:
    `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
  - `v5` handwritten-line artifact size: `1674024`

## Codegen Sanity Check

The local build was followed by direct symbol inspection on the integrated
handwritten-line artifact. The key result is that `v7` does hit the intended
seam:

- reduction now contains vector instructions such as
  `fadd v0.4s, v0.4s, v1.4s` and `faddp s1, v0.2s`
- epilogue still contains the expected NEON path
  `dup + fmla + fmaxnm`
- compute symbol size on the integrated artifact is `0x288` (`648` bytes)

That is enough to say that `v7` is not just structurally distinct; it also
changes reduction code generation in the intended direction.

## Interpretation

- `v7` is a real new branch:
  it does not collapse back to the baked-in handwritten final artifact
- unlike `v6`, it also changes the codegen at exactly the remaining hot seam
  identified after the `v5/v6` inspection
- numerically it stays inside the accepted local envelope
  `allclose(1e-6, 1e-6) = true`
- this makes `v7` a board-worthy handwritten-line candidate with a much
  stronger hypothesis behind it than `v6`

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/mean4_v7_correctness_check_20260406.json`
- build report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v7_20260406_partial_sum_reduction/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- operator-level artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v7_20260406_partial_sum_reduction/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- handwritten-line integration report:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/integration_report.json`
- handwritten-line artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so`

## Board Follow-up

The board result for the handwritten-line `v7` artifact is recorded separately
in:

- `./session_bootstrap/reports/handwritten_mean4_v7_line_remote_benchmark_20260406_1835.md`
- `./session_bootstrap/reports/mean4_v7_codegen_confirmation_20260406.md`
