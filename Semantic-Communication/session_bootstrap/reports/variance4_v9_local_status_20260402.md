# `fused_variance4_add13_tir_sqrt4` v9 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v8` one-element local store/load round-trip intact
- remove only `T.attr(T_multiply_local_data, "volatile_scope", 1)` from the
  local allocation

Rationale: this is the narrowest direct follow-up suggested by the `v8`
report. The explicit float32 local allocation, declared one-element local
buffer, local write block, and local read block all remain in place, so `v9`
isolates whether the `volatile_scope` attribute itself is still required for
exact equality.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v9_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v9_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v9
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v9_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `46 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = false`, `allclose_atol1e-6_rtol1e-6 = true`,
  `max_abs_diff = 5.960464477539063e-08`, `mean_abs_diff = 1.4901161193847656e-08`,
  `nonzero_diff_count = 3`
- the exactness regression shape matches the earlier local `v6` regression
  pattern even though the explicit one-element local store/load round-trip is
  still present
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v9/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `325738c6c07cbd4232534bbd238c475dc0e926b921963875645de9203f72a8b4`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v9/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v9_correctness_check.json`

## Next Step

Keep `v8` as the exact-preserving baseline and treat `v9` as an allclose-only
experiment showing that removing `volatile_scope` is not exact-safe locally.
If this lane continues, test one changed-but-still-explicit volatility encoding
from `v8` rather than removing the volatility marker entirely.
