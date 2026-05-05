# Transpose_Add6 P2 Local Prep

- generated_at: `2026-03-31T21:14:21+08:00`
- operator: `fused_conv2d_transpose_add6`
- stage: `P2`
- baseline commit: `6b5e98f`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py` on top of the accepted transpose_add6 scheduled-form v1 bias-fused working copy.
- Kept semantics unchanged and kept `data_dilate`, `data_pad`, `kernel_transform`, the bias-fused `compute_init` / `compute_update` path, the scheduled h/w tiling, the reduction split, and `pragma_auto_unroll_max_step=32` unchanged.
- Applied one conservative P2 inner output-channel tiling retune aimed at increasing reuse inside the existing 16-channel `c_1` group without changing outer tile coverage:
  - `c_2 x c_3`: `4 x 4` -> `2 x 8`
  - outer `c_1`: unchanged at `3`
  - per-`c_1` channel coverage: unchanged at `16`
  - `h_2 x h_3`: unchanged at `2 x 2`
  - `w_2 x w_3_fused`: unchanged at `2 x 4`
  - `dc_0 x dc_1`: unchanged at `6 x 16`
  - `pragma_auto_unroll_max_step`: unchanged at `32`
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p2_cortex_a72_inner_output_channel_tile_tuning_applied`
  - `working_copy_tir_sha256`: `421ec6aca3360d2511aacbf5526a7f3577604f81c10aec06a4a7f2f3b50dc813`
- Updated focused transpose_add6 tests to assert the checked-in P2 state:
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114
```

Result:

- `swap_succeeded`: `true`
- `structural_equal_post_swap_vs_candidate`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114`
- artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114/fused_conv2d_transpose_add6_post_db_swap.so`
- artifact sha256: `eb2100f6736d008c716966a215b4f1296f44169a4152220793105eb8b64a15f0`
- artifact size bytes: `1678560`
- adjacent JSON: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114/fused_conv2d_transpose_add6_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --output-json ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114/fused_conv2d_transpose_add6_p2_correctness_compare.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256: `258bfcb5bb2dd77e8efd76f1781aa9ff477b9d0bdd9fa19edbfd4e0e4c8c4a5b`
- candidate working-copy sha256: `421ec6aca3360d2511aacbf5526a7f3577604f81c10aec06a4a7f2f3b50dc813`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `1.33514404296875e-05`
- `mean_abs_diff`: `6.718498752888991e-07`
- `nonzero_diff_count`: `165289`
- JSON evidence: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114/fused_conv2d_transpose_add6_p2_correctness_compare.json`

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
- The transpose_add6 P2 local candidate is ready for a remote benchmark on top of the accepted transpose_add6 v1 baseline.
