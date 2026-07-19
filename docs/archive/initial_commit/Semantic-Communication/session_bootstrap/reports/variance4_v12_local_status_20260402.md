# `fused_variance4_add13_tir_sqrt4` v12 Local Status

Date: `2026-04-02`

## Chosen Edit

- keep the `v11` explicit `.data`-level volatile one-element local round-trip
  intact
- remove only the separate raw local `T.allocate(...)` handle and declare the
  one-element local buffer directly via
  `T.decl_buffer((1,), "float32", scope="local")`

Rationale: the requested next step was to test whether the explicit raw
allocation handle could be simplified away without losing the explicit
`.data`-level volatility encoding that `v11` established as buildable and
exact-preserving. A narrower handle-removal form than `T.alloc_buffer(...)`
exists here: keep `T.decl_buffer(...)`, make the storage scope explicit on that
buffer declaration, and keep the volatility marker on `T_multiply_local.data`.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v12_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v12_local_status_20260402.md`

## Commands Run

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# scratch probe: test handle-free variants that keep
# T.attr(T_multiply_local.data, "volatile_scope", 1)
# 1) T.decl_buffer((1,), "float32", scope="local")
# 2) T.alloc_buffer((T.int64(1),), scope="local")
PY
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v12
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v12_correctness_check.json
```

## Local Status

- scratch probe result: both handle-free source forms were locally importable,
  buildable, and `exact_equal = true`; `v12` checks in the narrower
  `T.decl_buffer(..., scope="local")` form
- focused variance4 unit tests: `58 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- local correctness compare against the frozen scheduled reference: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v12/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v12/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v12_correctness_check.json`

## Next Step

If `v12` stays exact-preserving through the full checked-in local proof path,
the next exactness-aware step should be to compare its exported artifact and
codegen-visible volatile load/store shape against `v11`, to determine whether
the raw allocation handle is not just removable in TVMScript but also locally
equivalent at the artifact level.
