# `fused_variance4_add13_tir_sqrt4` v10 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v8` one-element local store/load round-trip intact
- move only the explicit `volatile_scope` marker from the raw local allocation
  handle to the declared one-element local buffer via
  `T.attr(T_multiply_local, "volatile_scope", 1)`

Rationale: `v9` showed that removing volatility entirely is not exact-safe, so
the next narrow follow-up is to keep volatility explicit while changing only
its attachment point. This keeps the same one-element local allocation, the
same declared local buffer, and the same float32 store/load boundary as `v8`,
while testing whether the local backend treats the volatile marker the same way
when it is attached to the declared buffer rather than the raw allocation
handle.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v10_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v10_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v10
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v10_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `50 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`,
  `build_status = failed`, `export_status = skipped`,
  `build_error = "InternalError: Check failed: (v) is false: "`
- local correctness compare against the frozen scheduled reference did not reach
  numeric comparison because candidate runtime build failed with the same
  `tvm.error.InternalError` in LLVM/AArch64 codegen while lowering the
  `volatile_scope` attr on the declared local buffer
- repo-local parser/import evidence still showed the `v10` script is accepted by
  TVM and normalizes to `T.decl_buffer((1,), scope="local")` plus
  `T.attr(T_multiply_local, "volatile_scope", 1)`
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v10/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  not produced because local codegen failed before export
- correctness JSON:
  not produced because candidate runtime build failed before comparison

## Next Step

Keep `v8` as the exact-preserving baseline and treat `v10` as a build-blocked
explicit-volatility experiment. If this lane continues, inspect whether
LLVM/AArch64 codegen only accepts `volatile_scope` on the raw allocation handle
for this pattern, then test one remaining explicit variant such as
`T.attr(T_multiply_local.data, "volatile_scope", 1)` or inspect the generated
AttrStmt node kind before codegen.
