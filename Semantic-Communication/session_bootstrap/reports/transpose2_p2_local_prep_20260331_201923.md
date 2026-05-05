# Transpose2 P2 Local Prep

- generated_at: `2026-03-31T20:19:23+08:00`
- operator: `fused_conv2d_transpose2_add12`
- stage: `P2`
- baseline commit: `6477ec2`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py` on top of the accepted transpose2 scheduled-form v1 bias-fused working copy.
- Kept semantics unchanged and kept `data_dilate`, `data_pad`, `kernel_transform`, the bias-fused `compute_init` / `compute_update` path, the reduction split, the outer `w_0` sweep, and `pragma_auto_unroll_max_step=32` unchanged.
- Applied one conservative P2 inner-width tiling retune aimed at matching 4-lane width vectors on Cortex-A72 while preserving the same 32-column outer width tile:
  - `w_2 x w_3`: `4 x 8` -> `8 x 4`
  - outer `w_0` sweep: unchanged at `8`
  - `h_1 x h_2 x h_3`: unchanged at `4 x 2 x 1`
  - `dc_0 x dc_1`: unchanged at `4 x 6`
  - `pragma_auto_unroll_max_step`: unchanged at `32`
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p2_cortex_a72_inner_width_tile_tuning_applied`
  - `working_copy_tir_sha256`: `13ce7b4489acd19eac7afc0924b7bcfdb6bdefeb546a4ff122b9ea7bf43b4d12`
- Updated focused transpose2 tests to assert the checked-in P2 width-tiling state:
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy.py`
  - `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742
```

Result:

- `swap_succeeded`: `true`
- `structural_equal_post_swap_vs_candidate`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742`
- artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742/fused_conv2d_transpose2_add12_post_db_swap.so`
- artifact sha256: `c97a6c67892ff1b37d79658fe1e0c2220229e8843bf5f6386c720d31a8d45b67`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742/fused_conv2d_transpose2_add12_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --output-json ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742/fused_conv2d_transpose2_add12_p2_correctness_compare.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256: `9b4c4c0fdb7c515a52ad343a5b8130e8acdf92ee08725b83acb4bc042da3dc37`
- candidate working-copy sha256: `13ce7b4489acd19eac7afc0924b7bcfdb6bdefeb546a4ff122b9ea7bf43b4d12`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `4.76837158203125e-06`
- `mean_abs_diff`: `2.3944838289935433e-07`
- `nonzero_diff_count`: `607527`
- JSON evidence: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742/fused_conv2d_transpose2_add12_p2_correctness_compare.json`

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
- The transpose2 P2 local candidate is ready for a remote benchmark on top of the accepted transpose2 v1 baseline.
