# Transpose2 P4 Local Prep

- generated_at: `2026-03-31T20:31:03+08:00`
- operator: `fused_conv2d_transpose2_add12`
- stage: `P4`
- baseline commit: `6477ec2`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py` on top of the accepted transpose2 scheduled-form v1 state.
- Kept semantics unchanged and kept the accepted v1 bias-fused `compute_init` / `compute_update` path, `data_dilate`, `data_pad`, `kernel_transform`, the scheduled h/w tiling, the reduction split, the outer `w_0` sweep, and the `w_3_fused` / `w_3_fused_init` vectorized inner-width lanes unchanged.
- Applied one conservative P4-style inner-loop-adjacent micro-tune analogous to the accepted transpose1 P4 change:
  - outer parallel-loop annotation `pragma_auto_unroll_max_step`: `32` -> `64`
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p4_auto_unroll64_applied`
  - `working_copy_tir_sha256`: `6b86c065ce678eb10739cc54a9fc45ba17b7368872a81e592fd3f45683ca96bb`
- Updated focused transpose2 tests to assert the checked-in P4 state:
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942
```

Result:

- `swap_succeeded`: `true`
- `structural_equal_post_swap_vs_candidate`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942`
- artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942/fused_conv2d_transpose2_add12_post_db_swap.so`
- artifact sha256: `0d818524c63b94ede51aad1335165160107f9bf35da52a4fcc08f8384ec4aaef`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942/fused_conv2d_transpose2_add12_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --output-json ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942/fused_conv2d_transpose2_add12_p4_correctness_compare.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256: `9b4c4c0fdb7c515a52ad343a5b8130e8acdf92ee08725b83acb4bc042da3dc37`
- candidate working-copy sha256: `6b86c065ce678eb10739cc54a9fc45ba17b7368872a81e592fd3f45683ca96bb`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `4.76837158203125e-06`
- `mean_abs_diff`: `2.3944838289935433e-07`
- `nonzero_diff_count`: `607527`
- JSON evidence: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942/fused_conv2d_transpose2_add12_p4_correctness_compare.json`

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
- The transpose2 P4 working copy is locally buildable and matches the frozen scheduled reference within the established `allclose(atol=1e-5, rtol=1e-5)` tolerance gate, so local prep is ready for remote benchmarking.
