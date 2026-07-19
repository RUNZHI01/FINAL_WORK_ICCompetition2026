# Transpose2 V1 Local Prep

- generated_at: `2026-03-31T20:08:27+08:00`
- operator: `fused_conv2d_transpose2_add12`
- candidate: `scheduled-form v1 bias fusion`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py` on top of the checked-in transpose2 scheduled reference seed.
- Folded bias `lv334` into the scheduled `compute_init` / `compute_update` path so accumulation now writes directly to `T_add_intermediate`.
- Removed the full-size `compute_intermediate` allocation and removed the trailing scheduled `T_add` pass.
- Kept `data_dilate`, `data_pad`, `kernel_transform`, the scheduled h/w tiling, the reduction split, the `w_0` sweep, and `pragma_auto_unroll_max_step=32` unchanged.
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `v1_bias_fusion_applied`
  - `working_copy_tir_sha256`: `df890bb0d5f22197efff690dc0b1b6968bc6a0b7fe0ebbaf473bb1bd20077968`
- Extended `session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py` so the existing compare helper can be reused for transpose2 through `--operator-name fused_conv2d_transpose2_add12`.
- Added focused transpose2 tests:
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744
```

Result:

- `swap_succeeded`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744`
- artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744/fused_conv2d_transpose2_add12_post_db_swap.so`
- artifact sha256: `bae5c138c3c21fda694bd21db4bbd19144263ec3bab3d7de30ab3942551dd561`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744/fused_conv2d_transpose2_add12_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --output-json ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744/fused_conv2d_transpose2_add12_v1_correctness_compare.json
```

Result against frozen scheduled reference seed:

- reference seed sha256: `9b4c4c0fdb7c515a52ad343a5b8130e8acdf92ee08725b83acb4bc042da3dc37`
- candidate working-copy sha256: `df890bb0d5f22197efff690dc0b1b6968bc6a0b7fe0ebbaf473bb1bd20077968`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `4.76837158203125e-06`
- `mean_abs_diff`: `2.3944838289935433e-07`
- `nonzero_diff_count`: `607527`
- JSON evidence: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744/fused_conv2d_transpose2_add12_v1_correctness_compare.json`

## Focused Tests

Command:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1
```

Result:

- `4` tests ran
- status: `OK`

## Notes

- No SSH, SCP, or remote benchmark step was run here.
- No commit was created here.
- The transpose2 scheduled-form v1 candidate is locally buildable and matches the frozen scheduled reference within the established `allclose(atol=1e-5, rtol=1e-5)` tolerance, so local prep is ready for remote benchmarking.
