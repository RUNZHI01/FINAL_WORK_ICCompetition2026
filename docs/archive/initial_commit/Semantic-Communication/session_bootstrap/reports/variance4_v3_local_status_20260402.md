# `fused_variance4_add13_tir_sqrt4` v3 Local Status

Date: `2026-04-02`

## Chosen Edit

- remove the standalone `T_divide_intermediate` stage from the `v3` working copy
- fold the `/65536.0` directly into the final `sqrt` consumer

Rationale: this is the next narrow local-only follow-up after `v2`, because the
epsilon add was already fused into the final consumer and the remaining
1x12x1x1 divide stage was redundant.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v3_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3.py`
- `./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v3
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v3_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `18 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v3/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `001a1dd591a53c8bcaf0e4b98e7966633f690f11e86ea5f14d4819f826f2abf3`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v3_correctness_check.json`

## Commit Status

- attempted selective `git add` for the variance4 `v3` files and directly-related helper/test/doc/report updates
- blocked by the environment because `.git/index.lock` could not be created: `Read-only file system`

## Next Step

Keep the lane local-only and evaluate the next narrow schedule-form
simplification candidate, most likely folding the remaining `T_divide` mean
stage directly into the `T_subtract` consumer while preserving the rest of the
scheduled structure.
