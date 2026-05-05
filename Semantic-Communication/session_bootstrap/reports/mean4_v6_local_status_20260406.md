# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` v6 Local Status

Date: `2026-04-06`

## Starting Point

- `mean4 v5` had already become the first post-`v4` handwritten-line candidate
  that beat the current handwritten final on same-day payload median
- the next worthwhile question was therefore no longer "can mean4 beat v4 at
  all", but whether the handwritten code still had a **larger structural**
  inefficiency left inside the operator itself
- the concrete hypothesis for `v6` was:
  keep `v5`'s affine epilogue math unchanged, but reorder the channel phases
  from `reduce all channels -> epilogue all channels` into
  `reduce channel c -> affine precompute c -> epilogue c`

## Chosen Edit

`v6` is a pure phase-ordering branch on top of `v5`:

- keep the reduction formula intact
- keep the affine pair intact
  - `scale = weight / std`
  - `shift = bias - mean * scale`
- keep the hot loop formula intact
  - `out = max(x * scale + shift, 0)`
- only change the channel-level loop nesting so each `256 x 256` channel plane
  can be reduced and consumed immediately before the next channel begins

The intent was to test whether channel-local temporal reuse is worth more on
Phytium Pi than the already-accepted `v5` math simplification alone.

## Files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v6_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py`
- `./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy.py`
- `./session_bootstrap/reports/mean4_v6_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py \
  ./session_bootstrap/tests/test_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_mean4_subtract4_divide4_multiply4_add14_relu3 \
  --candidate-tir ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/mean4_v6_correctness_check_20260406.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v6_20260406_channelwise_phase_order

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406
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
    `3bcdc181e3fe3c2e2284b8fdf3fc4e06797ccfdbbe2d52beb32c5c855d3c7a61`
  - artifact size: `1671952`
- integrated handwritten-line artifact:
  - preset: `opus_final_v3_mean4`
  - candidate override:
    `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v6 working copy`
  - artifact SHA256:
    `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`
  - artifact size: `1672000`
- current handwritten final baseline for comparison:
  - artifact SHA256:
    `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
  - artifact size: `1674120`
- current beyond-`v4` positive candidate for comparison:
  - handwritten-line artifact SHA256:
    `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
  - artifact size: `1674024`

## Interpretation

- `v6` is a real new branch:
  it does not collapse back to the baked-in handwritten final artifact
- it also does not collapse back to the existing `v5` handwritten-line branch
- numerically it stays inside the same accepted tolerance envelope as `v4/v5`
- therefore `v6` is a board-worthy structural candidate, not a local-only
  identity ablation

That is enough to justify a real handwritten-line payload check, but not enough
to claim a speedup yet.

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/mean4_v6_correctness_check_20260406.json`
- build report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v6_20260406_channelwise_phase_order/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- operator-level artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v6_20260406_channelwise_phase_order/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- handwritten-line integration report:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/integration_report.json`
- handwritten-line artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so`

## Board Follow-up

The board result for the handwritten-line `v6` artifact is recorded separately
in:

- `./session_bootstrap/reports/handwritten_mean4_v6_line_remote_benchmark_20260406_1804.md`
