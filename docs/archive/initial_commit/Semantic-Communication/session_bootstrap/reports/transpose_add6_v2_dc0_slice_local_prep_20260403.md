# `fused_conv2d_transpose_add6` v2 Local Prep

- generated_at: `2026-04-03T00:01:21+08:00`
- operator: `fused_conv2d_transpose_add6`
- stage: `v2 dc_0-slice data_pad reuse`
- status: `local proof complete; no remote benchmark run`

## Baseline To Beat

- active next-target decision:
  `session_bootstrap/reports/next_speedup_target_after_transpose1_overlap_closure_20260402.md`
- rerank rationale:
  `session_bootstrap/reports/project_speedup_rerank_after_transpose1_closure_20260402.md`
- accepted handwritten board baseline for this operator:
  `session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`
- accepted remote median: `159.503 ms`

## Chosen Move

Spend the first real `transpose_add6 v2` branch on the same locality family
that won on `transpose1`, but adapted to this operator's existing reduction
split:

- keep the accepted `v1` bias-fused `compute_init` / `compute_update` path
- keep `data_dilate` materialized once for the full operator call
- keep `kernel_transform`, tiling, reduction order, and
  `pragma_auto_unroll_max_step = 32`
- change only the tile-local staging order so `data_pad` is prepared one
  `dc_0` slice (`16` input channels) at a time, then immediately reused across
  all three `c_1` groups before the next slice is staged

Rationale:

- the old `v1` shape staged the same `6 x 10` padded patch three times, once
  for each `c_1` group, even though the staged data does not depend on `c_1`
- this move reduces repeated tile-local staging without reopening the already
  losing `P2` / `P4` micro-tune family
- it also keeps the accepted `v1` arithmetic path intact, so exact local
  comparison against `v1` is possible

## Files Changed

- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v2_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/README.md`
- `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy.py`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1 \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose_add6_v2_correctness_vs_reference_20260402.json

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose_add6_v2_correctness_vs_v1_20260402.json

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_20260402_dc0_slice
```

## Local Status

- focused transpose_add6 tests: `8 tests`, `OK`
- current v2 working-copy sha256:
  `15e3369a1bcdd100176aec60eeb53ce94548cd5f77da01ad845e589555bf1049`

Against the frozen scheduled reference seed:

- `exact_equal = false`
- `allclose(atol=1e-5, rtol=1e-5) = true`
- `max_abs_diff = 1.33514404296875e-05`
- `mean_abs_diff = 6.718498752888991e-07`
- `nonzero_diff_count = 165289`
- JSON:
  `./session_bootstrap/tmp/transpose_add6_v2_correctness_vs_reference_20260402.json`

Against the accepted `transpose_add6 v1` working copy:

- `exact_equal = true`
- `allclose(atol=0, rtol=0) = true`
- `max_abs_diff = 0.0`
- `nonzero_diff_count = 0`
- matching output checksum:
  `1a2ef83c1ebf7c637f6f3aeb7e090b78f81044204d47d9bd4d5ef3b01523c67f`
- JSON:
  `./session_bootstrap/tmp/transpose_add6_v2_correctness_vs_v1_20260402.json`

Post-db scheduled swap build/export:

- `candidate_status = v2_dc0_slice_data_pad_reuse_applied`
- `query_tuning_record_hit = true`
- `query_ir_module_hit = true`
- `query_schedule_hit = true`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`
- local artifact:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_20260402_dc0_slice/fused_conv2d_transpose_add6_post_db_swap.so`
- local artifact sha256:
  `383443d0001cdf67d353c1abee2c5c01b52e07c65e32366aac188ae43e2a07c7`
- local artifact size bytes: `1678560`
- adjacent build report:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_20260402_dc0_slice/fused_conv2d_transpose_add6_post_db_swap_report.json`

## Interpretation

This is a credible next handwritten candidate, but only in the local-evidence
sense:

- it is a real operator-side change, not just another empty seed clone
- it preserves the accepted `v1` behavior exactly under local proof checks
- it survives the actual post-db scheduled swap/build/export seam and produces a
  new artifact SHA
- it is still **not** a speed claim

## Board-side Status

No remote benchmark was run in this turn.

Reason:

- this lane has a clean local-first runbook and a payload benchmark runner, but
  it does not yet have a checked-in transpose_add6-specific upload/sync helper
  comparable to the transpose1 path
- I did not improvise direct SSH or ad-hoc copy commands outside existing
  handwritten-lane helpers

## Exact Next Step

If the project wants board proof for this candidate next, add or reuse a
documented repo helper that stages:

- local artifact:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_20260402_dc0_slice/fused_conv2d_transpose_add6_post_db_swap.so`
- into a dedicated remote archive:
  `<archive>/tvm_tune_logs/optimized_model.so`

Then benchmark it through the existing payload runner:

```bash
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

Until that staging step is scripted, keep this result classified as
`local-only / exact-vs-v1 / build-validated`.
