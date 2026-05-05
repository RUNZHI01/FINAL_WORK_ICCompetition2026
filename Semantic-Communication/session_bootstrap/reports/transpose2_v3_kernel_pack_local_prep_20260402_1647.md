# Transpose2 v3 Kernel-Pack Local Prep

- generated_at: `2026-04-02T16:47:51+0800`
- operator: `fused_conv2d_transpose2_add12`
- stage: `v3 first real kernel_transform-side locality candidate`
- status: `local prep complete; ready for board benchmark`

## Chosen Edit

- Edited only the checked-in `v3` working-copy lane on top of the accepted `v1` baseline.
- Kept `data_dilate` and `data_pad` materialized so this lane does not revisit the dropped `v2` `data_dilate + data_pad -> data_dilate_pad` fusion idea.
- Repacked the materialized `kernel_transform` buffer from `[output_channel, input_channel, kh, kw]` to `[input_channel, kh, kw, output_channel]`.
- Updated `compute_update` to read `kernel_transform[v_dc, v_dh, v_dw, v_c]`, so the unchanged inner `c_3` output-channel sweep walks contiguous weights.
- Kept the accepted `v1` bias-fused `compute_init` / `compute_update` path, scheduled h/w tiling, reduction split `dc_0 x dc_1 = 4 x 6`, outer `w_0` sweep `= 8`, and `pragma_auto_unroll_max_step = 32` unchanged.

Rationale:

- This is a narrow kernel-transform-side locality edit aimed at the actual inner `c_3` access pattern on the A72-targeted scheduled loop nest.
- It changes only the kernel packing/layout and the corresponding read site, which keeps the rest of the accepted transpose2 schedule surface stable.

## Files Changed

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v3_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy.py`
- `session_bootstrap/reports/transpose2_v3_kernel_pack_local_prep_20260402_1647.md`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3 \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_v3_kernel_pack_correctness_compare.json
```

## Local Status

- Focused unit tests: `4 tests`, `OK`
- Local post-db scheduled swap:
  - `candidate_status = v3_kernel_transform_oc_inner_pack_applied`
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- Exported artifact:
  - `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_post_db_swap.so`
  - SHA256: `25cdc5a8e402f6859f4e2418f5fe45d3b25f72a54e12bf96a77deb1dc2551fd9`
  - size bytes: `1678752`
- Local correctness compare against the frozen scheduled reference seed:
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 4.76837158203125e-06`
  - `mean_abs_diff = 2.3944838289935433e-07`
  - `nonzero_diff_count = 607527`
- No SSH, SCP, or remote board commands were used.

## Evidence

- Local build report:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_post_db_swap_report.json`
- Local correctness JSON:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_v3_kernel_pack_correctness_compare.json`

## Exact Board-Side Next Step

Upload and benchmark this exact artifact on the board:

- `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_post_db_swap.so`

Use the same remote payload protocol already used for `session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`, and compare the resulting measurements directly against the accepted `v1` transpose2 baseline (`161.416 ms` median).
