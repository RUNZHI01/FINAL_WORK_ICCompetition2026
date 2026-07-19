# `fused_variance4_add13_tir_sqrt4` v7 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v6a` volatile one-element local round-trip that restored exact equality
- remove the redundant explicit `T.Cast("float32", ...)` around the squared centered-value local write

Rationale: this is a narrow exactness-aware follow-up after `v6a`, because the
local `float32` store/load boundary appears to be the part that blocks the
backend contraction seen in `v6`, while the explicit cast on the local write
looks redundant when the squared expression is already `float32`.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v7_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v7_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v7
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v7_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `38 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- no SSH, scp, or remote board commands were used

## Outputs

- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v7/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v7/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v7_correctness_check.json`

## Next Step

Use `v7` as the new exact-preserving continuation point and evaluate a `v8`
candidate that keeps the cast-free volatile scalar round-trip intact while
testing whether the local storage declaration can be simplified without losing
the explicit `float32` store/load boundary that recovered exact equality in
`v6a`/`v7`.
