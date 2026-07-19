# Transpose1 P3 Local Prep

- generated_at: `2026-03-31T11:11:30+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `P3 Path A`
- status: `local prep complete; no remote benchmark run`

## What Changed

- Updated `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py` on top of the existing scheduled-form `v1` working copy.
- Removed the materialized `data_dilate` / `data_pad` buffer allocations and their scheduled sblocks.
- Kept `kernel_transform` materialized and kept the earlier bias-fusion path in `compute_init`.
- Replaced `compute_update` reads of `data_pad[...]` with guarded direct reads from `lv318[...]` using the scheduled-form P3 Path A stride mapping:
  - `dh = v_h + v_dh - 1`
  - `dw = v_w + v_dw - 1`
  - read `lv318[..., dh // 2, dw // 2]` only when `dh` / `dw` are in `[0, 127)` and even
- Updated `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`:
  - `status`: `p3_path_a_direct_lv318_indexing_applied`
  - `working_copy_tir_sha256`: `c9c07b7b128bc4a5ae1ed40535c1bf8301f550d5821273accf8ff644eaac98de`
- Added a local compare helper: `session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_path_a
```

Result:

- `swap_succeeded`: `true`
- `build_status`: `built`
- `export_status`: `exported`
- output dir: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_path_a`
- artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_path_a/fused_conv2d_transpose1_add9_post_db_swap.so`
- artifact sha256: `d5891aaecca9e43d9b1aace2ed2dc583d66ba7d280e92cd8520303e05de04e3f`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_path_a/fused_conv2d_transpose1_add9_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --output-json ./session_bootstrap/tmp/transpose1_p3_correctness_check/transpose1_p3_correctness_check.json
```

Result against frozen scheduled reference seed:

- reference seed sha256: `fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`
- candidate working-copy sha256: `c9c07b7b128bc4a5ae1ed40535c1bf8301f550d5821273accf8ff644eaac98de`
- local build target for compare: `llvm`
- frozen RNG seed: `20260331`
- `exact_equal`: `false`
- `allclose_atol0_rtol0`: `false`
- `allclose_atol1e-6_rtol1e-6`: `false`
- `allclose_atol1e-5_rtol1e-5`: `true`
- `max_abs_diff`: `7.62939453125e-06`
- `mean_abs_diff`: `3.7612730352520884e-07`
- `nonzero_diff_count`: `309445`
- JSON evidence: `./session_bootstrap/tmp/transpose1_p3_correctness_check/transpose1_p3_correctness_check.json`

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
- P3 Path A is locally buildable and numerically close to the frozen scheduled reference seed, but it is not bitwise-identical under this local `llvm` compare.
