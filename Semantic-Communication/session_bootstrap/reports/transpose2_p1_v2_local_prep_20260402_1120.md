# Transpose2 P1 v2 Local Prep

- generated_at: `2026-04-02T11:20:02+08:00`
- operator: `fused_conv2d_transpose2_add12`
- stage: `P1-style dilate+pad fusion on top of accepted v1`
- status: `local prep complete; no remote benchmark run`

## Accepted Baseline Identified

Current accepted handwritten baseline for this operator remains:

- candidate line: `scheduled-form v1 bias fusion`
- accepted remote report: `session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`
- accepted status: `accepted_baseline`
- accepted remote median: `161.416 ms`
- accepted local working-copy manifest status: `v1_bias_fusion_applied`

This new local-only candidate intentionally does **not** mutate that accepted baseline.
It lives in a separate `v2` working-copy path.

## What Changed

New files added for this candidate:

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v2_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py`

Concrete operator-side change on top of accepted v1:

- replaced the separate materialized `data_dilate` `(1,24,255,255)` plus `data_pad` `(1,24,258,258)` path
- with one materialized `data_dilate_pad` `(1,24,258,258)` buffer
- `data_dilate_pad` now directly emits padded+dilated values from `lv332`
- preserved:
  - accepted `v1` bias-fused `compute_init` / `compute_update`
  - materialized `kernel_transform`
  - scheduled h/w tiling
  - reduction split `dc_0 x dc_1 = 4 x 6`
  - outer `w_0` sweep `= 8`
  - `pragma_auto_unroll_max_step = 32`

Interpretation:

- this is the `transpose2` analog of the `transpose1` P1-style structural move
- but landed as a new `v2` candidate so the accepted `v1` files stay frozen

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402
```

Observed result:

- `candidate_version = v2_working_copy`
- `candidate_status = p1_dilate_pad_fusion_on_top_of_v1_applied`
- `query_tuning_record_hit = true`
- `query_ir_module_hit = true`
- `query_schedule_hit = true`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`

Artifact:

- output dir: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402`
- artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402/fused_conv2d_transpose2_add12_post_db_swap.so`
- artifact sha256: `6ce0647a3e6ad762474bd3d5ff29e831c1aa4f705eb3260d67673cc96052292d`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402/fused_conv2d_transpose2_add12_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose2_p1_v2_correctness_check/transpose2_p1_v2_correctness_check.json
```

Result against frozen scheduled reference seed:

- reference seed sha256: `9b4c4c0fdb7c515a52ad343a5b8130e8acdf92ee08725b83acb4bc042da3dc37`
- candidate working-copy sha256: `078c823cb5387da0d21ef26343ad0be091ca107c059a3375294ed5355af96661`
- `exact_equal = false`
- `allclose_atol0_rtol0 = false`
- `allclose_atol1e-6_rtol1e-6 = false`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 4.76837158203125e-06`
- `mean_abs_diff = 2.3944838289935433e-07`
- `nonzero_diff_count = 607527`
- JSON evidence: `./session_bootstrap/tmp/transpose2_p1_v2_correctness_check/transpose2_p1_v2_correctness_check.json`

## Focused Tests

Command:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v2
```

Result:

- `4` tests ran
- status: `OK`

## Readiness Judgment

This `v2` candidate is:

- locally buildable
- mechanically swappable on the post-db scheduled seam
- numerically within the existing `allclose(atol=1e-5, rtol=1e-5)` gate
- still local-only / diagnostic-only until a real board benchmark happens

So the honest next step is:

1. upload `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402/fused_conv2d_transpose2_add12_post_db_swap.so`
2. benchmark it with the same remote payload protocol used for `session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`
3. compare directly against the accepted `v1` median `161.416 ms`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v2

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose2_add12 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose2_p1_v2_correctness_check/transpose2_p1_v2_correctness_check.json
```
