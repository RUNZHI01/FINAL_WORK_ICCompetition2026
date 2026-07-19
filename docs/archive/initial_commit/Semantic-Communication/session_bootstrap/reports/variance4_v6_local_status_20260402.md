# `fused_variance4_add13_tir_sqrt4` v6 Local Status

Date: `2026-04-02`

## Chosen Edit

- remove the standalone full-size `T_multiply` stage from the `v6` working copy
- fold the squared centered-value expression directly into the `T_multiply_red` consumer

Rationale: this is the next narrow local-only follow-up after `v5`, because the remaining full-size `T_multiply` stage only fed `T_multiply_red` and could be inlined without disturbing the already-checked-in `v1`/`v2`/`v3`/`v4`/`v5` candidates or the rest of the scheduled structure.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v6_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6.py`
- `./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v6_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py   --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6.py   --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6
/home/tianxing/.venvs/tvm-ms/bin/python   ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py   --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy_tir.py   --output-json ./session_bootstrap/tmp/variance4_v6_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `30 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = false`, `allclose_atol1e-6_rtol1e-6 = true`, `max_abs_diff = 5.960464477539063e-08`, `nonzero_diff_count = 3`
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `2faca52fd5db32a367ca14f87f7c0f475f67faec852865ee518f5184b96b5541`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v6_correctness_check.json`

## Interpretation

This `v6` candidate is still mechanically swappable and locally buildable, but it is the first variance4 iteration in this chain that loses exact local equivalence against the frozen scheduled reference.

Observed numerical drift:

- `exact_equal = false`
- `allclose_atol1e-6_rtol1e-6 = true`
- `max_abs_diff = 5.960464477539063e-08`
- `nonzero_diff_count = 3`

That suggests the `T_multiply -> T_multiply_red` fold changed the floating-point behavior just enough to perturb a few outputs, even though the delta is still extremely small.

## Next Step

Do **not** immediately stack a `v7` simplification on top of this result. First determine whether the `T_multiply -> T_multiply_red` fold can be made `exact_equal = true`; if not, keep `v5` as the last exact local candidate and choose a different next narrow simplification.
