# `fused_variance4_add13_tir_sqrt4` v8 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v7` volatile one-element local round-trip that restored exact equality
- remove only the redundant explicit `scope="local"` from `T.decl_buffer(...)`

Rationale: this is the narrow next exactness-aware simplification suggested by
the `v7` report. The local allocation already uses `T.allocate(..., "local")`
and still carries the `volatile_scope` attribute, so the extra scope annotation
on the declared one-element buffer is the smallest remaining declaration-level
redundancy to test without intentionally removing the float32 local store/load
boundary that recovered exact equality.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v8_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v8_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v8
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v8_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `42 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v8/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v8/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v8_correctness_check.json`

## Next Step

Use `v8` as the new exact-preserving continuation point and test one more narrow
declaration-level simplification: whether the `volatile_scope` attribute can be
changed or removed without losing the explicit float32 local store/load
boundary that still preserves exact equality.
