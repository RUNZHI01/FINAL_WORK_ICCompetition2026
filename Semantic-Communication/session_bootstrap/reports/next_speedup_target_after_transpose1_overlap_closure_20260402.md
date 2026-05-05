# Next Speedup Target After Transpose1 Overlap Closure

- generated_at: `2026-04-02T19:48:41+08:00`
- decision_source: `session_bootstrap/reports/project_speedup_rerank_after_transpose1_closure_20260402.md`
- chosen target: `fused_conv2d_transpose_add6`
- prep status: `repo-local v2 locality seed verified; no remote benchmark run`

## Decision

Use `fused_conv2d_transpose_add6` as the next active project-wide speedup
target after transpose1 overlap/carry closure.

This file does not re-rank anything. It records the already-chosen target from
`session_bootstrap/reports/project_speedup_rerank_after_transpose1_closure_20260402.md`
and the current local prep status for that target.

## Repo-Local Prep In Scope

The active local prep surface is the isolated `v2` locality seed:

- candidate entrypoint:
  `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`
- editable working copy:
  `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`
- manifest:
  `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v2_working_copy_manifest.json`
- detailed prep note:
  `session_bootstrap/reports/transpose_add6_v2_locality_seed_local_prep_20260402.md`

Current intent of this seed:

- keep the accepted `transpose_add6 v1` baseline frozen
- keep the checked-in `v2` body equal to the accepted `v1` operator state for now
- open a clean edit surface for the first transpose1-style locality follow-up

## Local Validation

Focused tests:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1 \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2
```

- result: `8 tests`, `OK`

Local post-db swap build:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402_codex
```

- `candidate_version = v2_working_copy`
- `candidate_status = v2_locality_seed_cloned_from_v1_ready`
- `query_tuning_record_hit = true`
- `query_ir_module_hit = true`
- `query_schedule_hit = true`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`
- artifact sha256:
  `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`

Correctness probe:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose_add6_v2_locality_seed_correctness_check_20260402_codex.json
```

- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 1.33514404296875e-05`
- `mean_abs_diff = 6.718498752888991e-07`
- `nonzero_diff_count = 165289`

## Exact Next Action

Apply the first real `v2` operator-side locality edit inside:

- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`

Specifically reduce repeated `data_dilate` / `data_pad` staging while keeping
the accepted `v1` baseline untouched, then rerun the same local build and
correctness commands above.
