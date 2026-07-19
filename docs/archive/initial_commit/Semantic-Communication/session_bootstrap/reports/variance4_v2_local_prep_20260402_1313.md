# Variance4 v2 Local Prep

- generated_at: `2026-04-02T13:13:26+0800`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v2 first handwritten scheduled-form edit on top of frozen v1`
- status: `local prep complete; no remote work run`

## Baseline

The fresh local-only handwritten lane established in `a7dcad0` remains intact:

- frozen baseline candidate: `scheduled-form v1 working copy`
- baseline status: `seed_synced_unedited`
- baseline status report:
  `session_bootstrap/reports/variance4_handwritten_lane_status_20260402.md`

This new step does not mutate that `v1` path. The first real edit lives in a
separate `v2` working-copy path.

## Chosen First Edit

Chosen edit:

- remove the standalone `T_add_intermediate` stage
- fold the epsilon add directly into the final `compute -> sqrt` consumer

Rationale:

- it is the narrowest obvious local simplification in the recovered scheduled
  form
- it only touches the tiny `1x12x1x1` epilogue and leaves both reductions,
  `T_divide`, `T_subtract`, and `T_multiply` staging untouched
- it preserves the existing local proof seam because the operator signature,
  block names around the seam, and the overall post-db swap mechanism remain
  unchanged

## Files Changed

- `session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v2_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py`
- `session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy.py`
- `session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py`
- `session_bootstrap/tests/test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`

Checked-in `v2` metadata:

- candidate status:
  `v2_epsilon_add_fused_into_sqrt_on_top_of_v1_seed_applied`
- candidate working-copy sha256:
  `2931f9360fa761278a89bd705148cfb59af3274e018b90ff935ac63613a4e846`

## Local Build / Probe

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v2_20260402
```

Observed result:

- `candidate_version = v2_working_copy`
- `candidate_status = v2_epsilon_add_fused_into_sqrt_on_top_of_v1_seed_applied`
- `query_tuning_record_hit = false`
- `query_ir_module_hit = false`
- `query_schedule_hit = false`
- `swap_succeeded = true`
- `structural_equal_post_swap_vs_candidate = true`
- `build_status = built`
- `export_status = exported`

Artifact:

- output dir:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v2_20260402`
- artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v2_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- artifact sha256:
  `5719231c5cd93468bab74761627330b7c16afd826d20b00810f937d69a03abaf`
- artifact size bytes: `1678600`
- adjacent JSON:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v2_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`

## Correctness

Command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v2_correctness_check_20260402.json
```

Result against the frozen scheduled reference seed:

- reference seed sha256:
  `ebe53f7f503cd5c0db9e8f7df77f30fae6295e0c448153bc482837e6a73c2ebf`
- candidate working-copy sha256:
  `2931f9360fa761278a89bd705148cfb59af3274e018b90ff935ac63613a4e846`
- `exact_equal = true`
- `allclose_atol0_rtol0 = true`
- `allclose_atol1e-6_rtol1e-6 = true`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 0.0`
- `mean_abs_diff = 0.0`
- `nonzero_diff_count = 0`
- JSON evidence:
  `./session_bootstrap/tmp/variance4_v2_correctness_check_20260402.json`

## Focused Tests

Commands:

```bash
python3 -m py_compile \
  session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py \
  session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy.py \
  session_bootstrap/tests/test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py

python3 -m unittest \
  session_bootstrap.tests.test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy \
  session_bootstrap.tests.test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1 \
  session_bootstrap.tests.test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy \
  session_bootstrap.tests.test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2 \
  session_bootstrap.tests.test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy
```

Result:

- `9` tests ran
- status: `OK`

## What This Candidate Proves

- the first real handwritten edit for `fused_variance4_add13_tir_sqrt4` now
  exists in a versioned repo-native `v2` path while the fresh `v1` baseline
  stays frozen
- the existing local post-db swap seam can consume that edited `v2` candidate
  and still export a local artifact successfully
- this specific epilogue fusion is locally correctness-preserving against the
  frozen scheduled reference on the fixed seed
- this step still does not prove a direct DB-scheduled record exists and does
  not make any runtime or performance claim

## Exact Next Step

Take one more narrow local-only variance4 iteration: remove the now-redundant
`T_divide_intermediate` buffer/stage by folding the `/ 65536.0` directly into
the final `sqrt` consumer, then rerun the same `v2`-style local build and
correctness proof before considering any broader rewrite.
