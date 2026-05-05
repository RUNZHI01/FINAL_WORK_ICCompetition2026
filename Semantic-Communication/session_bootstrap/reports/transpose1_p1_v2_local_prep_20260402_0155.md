# Transpose1 P1 v2 Local Prep

- generated_at: `2026-04-02T01:55:00+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `P1-style structural candidate on top of accepted P2+P4`
- status: `local prep complete; no remote benchmark run`

## Accepted Baseline Identified

Current accepted handwritten baseline for this operator remains:

- candidate line: `scheduled-form v1 working copy`
- accepted remote report: `session_bootstrap/reports/transpose1_p4_remote_benchmark_20260331_193220.md`
- accepted status: `P2 + P4 kept`
- accepted remote median: `159.356 ms`
- accepted local working-copy manifest status: `p4_cortex_a72_auto_unroll64_on_p2_applied`

This new local-only candidate intentionally does **not** mutate that accepted baseline.
It lives in a separate `v2` working-copy path.

## What Changed

New files added for this candidate:

- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v2_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2.py`

Concrete operator-side change on top of accepted P2+P4:

- replaced the separate materialized `data_dilate` `(1,48,127,127)` plus `data_pad` `(1,48,130,130)` path
- with one materialized `data_dilate_pad` `(1,48,130,130)` buffer
- `data_dilate_pad` now directly emits padded+dilated values from `lv318`
- preserved:
  - accepted P2 output-channel tiling `c_1 x c_3 = 3 x 8`
  - accepted P4 `pragma_auto_unroll_max_step = 64`
  - bias-fused `compute_init` / `compute_update`
  - materialized `kernel_transform`
  - existing h/w tiling, reduction split, and 4-lane vectorized inner loops

Interpretation:

- this is the previously planned `P1`-style structural move (fuse `dilate + pad`)
- but landed as a **new `v2` candidate** so the accepted `v1/P2/P4` files stay frozen

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402
```

Rerun after manifest SHA pin:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun
```

Observed result:

- `candidate_version = v2_working_copy`
- `candidate_status = p1_dilate_pad_fusion_on_top_of_p2_p4_applied`
- `query_tuning_record_hit = true`
- `query_ir_module_hit = true`
- `query_schedule_hit = true`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`

Artifact:

- output dir: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun`
- artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun/fused_conv2d_transpose1_add9_post_db_swap.so`
- artifact sha256: `2349df5dc2270385efd842516e6c3bdf55dd28bf9e0a3ac34febffe0aee878ca`
- artifact size bytes: `1678648`
- adjacent JSON: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun/fused_conv2d_transpose1_add9_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_p1_v2_correctness_check/transpose1_p1_v2_correctness_check.json
```

Result against frozen scheduled reference seed:

- reference seed sha256: `fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`
- candidate working-copy sha256: `0557bc5c731159c25e49080691dbea09175fce3386c71078535aa3636204b93e`
- `exact_equal = false`
- `allclose_atol0_rtol0 = false`
- `allclose_atol1e-6_rtol1e-6 = false`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 7.62939453125e-06`
- `mean_abs_diff = 3.7612730352520884e-07`
- `nonzero_diff_count = 309445`
- JSON evidence: `./session_bootstrap/tmp/transpose1_p1_v2_correctness_check/transpose1_p1_v2_correctness_check.json`

## Readiness Judgment

This `v2` candidate is:

- locally buildable
- mechanically swappable on the post-db scheduled seam
- numerically within the existing `allclose(atol=1e-5, rtol=1e-5)` gate
- still local-only / diagnostic-only until real board benchmarking happens

So the honest next step is:

1. upload this `v2` artifact to the handwritten staging archive on the board;
2. run the same remote payload benchmark path used for accepted `transpose1` candidates;
3. compare against accepted `P2+P4 = 159.356 ms`.

## Commands Run

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_p1_v2_correctness_check/transpose1_p1_v2_correctness_check.json

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun
```
