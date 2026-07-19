# `fused_variance4_add13_tir_sqrt4` v4 Local Status

Date: `2026-04-02`

## Chosen Edit

- remove the standalone `T_divide` mean stage from the `v4` working copy
- fold the mean `/65536.0` directly into the `T_subtract` consumer

Rationale: this is the next narrow local-only follow-up after `v3`, because the
remaining 1x12x1x1 mean divide stage only fed `T_subtract` and could be inlined
without disturbing the already-checked-in `v1`/`v2`/`v3` candidates or the rest
of the scheduled structure.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v4_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4.py`
- `./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v4_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v4
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v4_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `22 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v4/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `3be7357937038b8f07ba738bb77a3acd0c5ede586559554862e04f222ed44c93`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v4_correctness_check.json`

## Next Step

Keep the lane local-only and evaluate a `v5` candidate that removes the
standalone `T_subtract` full-size stage by folding the subtraction directly
into the `T_multiply` consumer while preserving the remaining scheduled
structure.
