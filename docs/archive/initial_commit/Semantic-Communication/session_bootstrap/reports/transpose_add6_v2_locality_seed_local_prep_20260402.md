# Transpose_Add6 v2 Locality Seed Local Prep

- generated_at: `2026-04-02T19:38:22+08:00`
- operator: `fused_conv2d_transpose_add6`
- stage: `v2 locality seed cloned from accepted v1`
- status: `local prep complete; no remote benchmark run`

## Accepted Baseline Identified

Current accepted handwritten baseline for this operator remains:

- candidate line: `scheduled-form v1 bias fusion`
- accepted remote report:
  `session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`
- accepted status: `accepted`
- accepted remote median: `159.503 ms`
- accepted local manifest status: `v1_bias_fusion_applied`

This new local-only candidate intentionally does **not** mutate that accepted
baseline. It lives in a separate `v2` working-copy path.

## What Changed

New repo files for this candidate:

- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v2_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy.py`
- `session_bootstrap/tests/test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`

Concrete state of the checked-in `v2` seed:

- no operator-side TIR change is landed yet
- the `v2` body intentionally matches the accepted `v1` bias-fused state
- purpose: isolate the next transpose1-style locality edit so the accepted
  `v1` files stay frozen
- preserved:
  - bias-fused `compute_init` / `compute_update`
  - materialized `data_dilate`
  - materialized `data_pad`
  - materialized `kernel_transform`
  - scheduled tiling
  - reduction split `dc_0 x dc_1 = 6 x 16`
  - `pragma_auto_unroll_max_step = 32`

## Local Build

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402
```

Observed result:

- `candidate_version = v2_working_copy`
- `candidate_status = v2_locality_seed_cloned_from_v1_ready`
- `query_tuning_record_hit = true`
- `query_ir_module_hit = true`
- `query_schedule_hit = true`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`

Artifact:

- output dir:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402`
- artifact:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402/fused_conv2d_transpose_add6_post_db_swap.so`
- artifact sha256:
  `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`
- artifact size bytes: `1678560`
- adjacent JSON:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402/fused_conv2d_transpose_add6_post_db_swap_report.json`

Interpretation:

The exported artifact SHA matches the accepted `v1` artifact SHA, which is the
expected result for a seed branch that has not yet changed operator behavior.

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose_add6_v2_locality_seed_correctness_check_20260402.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256:
  `258bfcb5bb2dd77e8efd76f1781aa9ff477b9d0bdd9fa19edbfd4e0e4c8c4a5b`
- candidate working-copy sha256:
  `5516271c178b870400c7c32ec8239263e9e9ca6f521f7b2dcf1ecd5027a8d918`
- `exact_equal = false`
- `allclose_atol0_rtol0 = false`
- `allclose_atol1e-6_rtol1e-6 = false`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 1.33514404296875e-05`
- `mean_abs_diff = 6.718498752888991e-07`
- `nonzero_diff_count = 165289`
- JSON evidence:
  `./session_bootstrap/tmp/transpose_add6_v2_locality_seed_correctness_check_20260402.json`

## Focused Tests

Command:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1 \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2
```

Result:

- `8` tests ran
- status: `OK`

## Readiness Judgment

This `v2` candidate is now:

- checked in as a distinct edit surface
- locally buildable
- mechanically swappable on the post-db scheduled seam
- numerically within the existing `allclose(atol=1e-5, rtol=1e-5)` gate
- still local-only / diagnostic-only

The next useful coding step is **not** a board benchmark yet. It is the first
real operator-side locality edit inside:

- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`

Specifically:

1. keep accepted `v1` frozen
2. reduce repeated `data_dilate` / `data_pad` staging in `v2`
3. rerun the same local build and correctness commands above
4. only then decide whether the candidate is worth board validation

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v1 \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose_add6_scheduled_form_candidate_v2

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed_20260402

/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose_add6 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose_add6_v2_locality_seed_correctness_check_20260402.json
```

## Notes

- No SSH, SCP, or remote board command was run.
- No performance claim is made here. This report is local scaffold/build proof
  only.
