# Transpose1 P2 Local Prep

- generated_at: `2026-03-31T19:24:14+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `P2`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py` on top of the accepted scheduled-form `P0/v1` bias-fused working copy.
- Kept semantics unchanged and kept `data_dilate`, `data_pad`, `kernel_transform`, the bias-fused `compute_init` / `compute_update` path, the h/w tiling, the reduction split, and the unroll annotation unchanged.
- Applied one conservative P2 output-channel tiling retune aimed at improving reuse of the materialized input tile on Cortex-A72:
  - `c_1 x c_3`: `6 x 4` -> `3 x 8`
  - outer parallel tile count: unchanged at `32`
  - `h_2 x h_3`: unchanged at `16 x 2`
  - `dc_0 x dc_1`: unchanged at `12 x 4`
  - `pragma_auto_unroll_max_step`: unchanged at `32`
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p2_cortex_a72_output_channel_tile_tuning_applied`
  - `working_copy_tir_sha256`: `6a860799b4b7e69bd0ec0e697ab0df55f8cefc71e2d9e9fe3709f4be026b7864`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p2
```

Result:

- `swap_succeeded`: `true`
- `structural_equal_post_swap_vs_candidate`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p2`
- artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p2/fused_conv2d_transpose1_add9_post_db_swap.so`
- artifact sha256: `9f60245fdfefe9ac8716b9f5e68d001e5f42a96efdf2d07c8cd7e40656943c16`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p2/fused_conv2d_transpose1_add9_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --output-json ./session_bootstrap/tmp/transpose1_p2_correctness_check/transpose1_p2_correctness_check.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256: `fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`
- candidate working-copy sha256: `6a860799b4b7e69bd0ec0e697ab0df55f8cefc71e2d9e9fe3709f4be026b7864`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `7.62939453125e-06`
- `mean_abs_diff`: `3.7612730352520884e-07`
- `nonzero_diff_count`: `309445`
- JSON evidence: `./session_bootstrap/tmp/transpose1_p2_correctness_check/transpose1_p2_correctness_check.json`

## Focused Tests

Command:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v1
```

Result:

- `4` tests ran
- status: `OK`

## Notes

- No SSH, SCP, or remote benchmark step was run here.
- This P2 candidate is ready for a remote payload benchmark on top of the accepted `P0/v1` baseline.
