# Transpose_Add6 P4 Local Prep

- generated_at: `2026-03-31T21:28:07+08:00`
- operator: `fused_conv2d_transpose_add6`
- stage: `P4`
- baseline commit: `6b5e98f`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py` on top of the accepted transpose_add6 v1 bias-fused working copy.
- Kept semantics unchanged and kept the dropped P2 tiling retune out of the working copy.
- Applied one conservative P4-style micro-change analogous to the successful transpose1 P4:
  - outer scheduled-region `pragma_auto_unroll_max_step`: `32` -> `64`
- Unchanged:
  - bias-fused `compute_init` / `compute_update` path
  - output-channel tiling `c_1 x c_2 x c_3 = 3 x 4 x 4`
  - `h_2 x h_3 = 2 x 2`
  - `w_2 x w_3_fused = 2 x 4`
  - `dc_0 x dc_1 = 6 x 16`
  - existing 4-lane vectorized inner stores / updates
  - materialized `data_dilate`, `data_pad`, and `kernel_transform`
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p4_cortex_a72_auto_unroll64_on_v1_applied`
  - `working_copy_tir_sha256`: `fceaab838c3d0dea835fd8758e01645e3ff55e544990d2bedae5d408e7ce0a0b`
- Updated focused transpose_add6 tests to assert the checked-in P4 state:
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py`

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

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704
```

Result:

- `swap_succeeded`: `true`
- `structural_equal_post_swap_vs_candidate`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704`
- artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704/fused_conv2d_transpose_add6_post_db_swap.so`
- artifact sha256: `74721e82c37a32b788102ade34b8f2eed23b6d912b66a56d3915c4b611c72dd6`
- artifact size bytes: `1678560`
- adjacent JSON: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704/fused_conv2d_transpose_add6_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --output-json ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704/fused_conv2d_transpose_add6_p4_correctness_compare.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256: `258bfcb5bb2dd77e8efd76f1781aa9ff477b9d0bdd9fa19edbfd4e0e4c8c4a5b`
- candidate working-copy sha256: `fceaab838c3d0dea835fd8758e01645e3ff55e544990d2bedae5d408e7ce0a0b`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `1.33514404296875e-05`
- `mean_abs_diff`: `6.718498752888991e-07`
- `nonzero_diff_count`: `165289`
- JSON evidence: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704/fused_conv2d_transpose_add6_p4_correctness_compare.json`

## Notes

- No SSH, SCP, or remote benchmark step was run here.
- No commit was created here.
- The transpose_add6 P4 local candidate is ready for a remote benchmark on top of the accepted transpose_add6 v1 baseline.
