# Transpose_Add6 V1 Local Prep

- generated_at: `2026-03-31T20:53:12+08:00`
- operator: `fused_conv2d_transpose_add6`
- candidate: `scheduled-form v1 bias fusion`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py` on top of the checked-in transpose_add6 scheduled reference seed.
- Folded bias `lv306` into the scheduled `compute_init` / `compute_update` path so accumulation now writes directly to `T_add_intermediate`.
- Removed the full-size `compute_intermediate` allocation and removed the trailing scheduled `T_add` pass.
- Kept `data_dilate`, `data_pad`, `kernel_transform`, the scheduled h/w tiling, the reduction split, and `pragma_auto_unroll_max_step=32` unchanged.
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `v1_bias_fusion_applied`
  - `working_copy_tir_sha256`: `56eb1970c0c5f75955696c9c0d4d2333b0c12a4fb32fc83bd723685ffeb959e6`
- Extended `session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py` so the existing compare helper can be reused for transpose_add6 through `--operator-name fused_conv2d_transpose_add6`.
- Added focused transpose_add6 tests:
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230
```

Result:

- `swap_succeeded`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230`
- artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230/fused_conv2d_transpose_add6_post_db_swap.so`
- artifact sha256: `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`
- artifact size bytes: `1678560`
- adjacent JSON: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230/fused_conv2d_transpose_add6_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --output-json ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230/fused_conv2d_transpose_add6_v1_correctness_compare.json
```

Result against frozen scheduled reference seed:

- reference seed sha256: `258bfcb5bb2dd77e8efd76f1781aa9ff477b9d0bdd9fa19edbfd4e0e4c8c4a5b`
- candidate working-copy sha256: `56eb1970c0c5f75955696c9c0d4d2333b0c12a4fb32fc83bd723685ffeb959e6`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `1.33514404296875e-05`
- `mean_abs_diff`: `6.718498752888991e-07`
- `nonzero_diff_count`: `165289`
- JSON evidence: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230/fused_conv2d_transpose_add6_v1_correctness_compare.json`

## Focused Tests

Command:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1
```

Result:

- `4` tests ran
- status: `OK`

## Notes

- No SSH, SCP, or remote benchmark step was run here.
- No commit was created here.
- The transpose_add6 scheduled-form v1 candidate is locally buildable and matches the frozen scheduled reference within the established `allclose(atol=1e-5, rtol=1e-5)` tolerance gate, so local prep is ready for remote benchmarking.
