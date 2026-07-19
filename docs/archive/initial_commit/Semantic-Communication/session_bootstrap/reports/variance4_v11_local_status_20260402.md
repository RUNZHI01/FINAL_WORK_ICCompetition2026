# `fused_variance4_add13_tir_sqrt4` v11 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v8` one-element local store/load round-trip intact
- move only the explicit `volatile_scope` marker from the raw local allocation
  handle to the declared one-element local buffer data handle via
  `T.attr(T_multiply_local.data, "volatile_scope", 1)`

Rationale: `v9` showed that removing volatility entirely is not exact-safe, and
`v10` showed that attaching `volatile_scope` to the declared buffer object is
build-blocked in local LLVM/AArch64 codegen. The next narrow follow-up was
therefore to keep the same explicit one-element local allocation, the same
declared local buffer, and the same float32 store/load boundary as `v8`, while
testing the remaining explicit volatility encoding on `T_multiply_local.data`.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v11_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v11_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v11
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v11_correctness_check.json
```

## Local Status

- focused variance4 unit tests: `54 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`,
  `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- the `.data`-targeted explicit volatility encoding is therefore both locally
  buildable and exact-preserving under the established local `llvm` compare
  path
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v11/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v11/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v11_correctness_check.json`

## Next Step

Keep `v8` as the exact-preserving baseline and treat `v11` as a locally
buildable exact-preserving alternative encoding. The next exactness-aware step
should be to inspect whether `T.attr(T_multiply_local.data, "volatile_scope",
1)` lowers to the same codegen-visible `AttrStmt` form as the raw-handle `v8`
encoding; if it does, use that evidence to choose the next narrow simplification
from the same exact-preserving round-trip shape.
