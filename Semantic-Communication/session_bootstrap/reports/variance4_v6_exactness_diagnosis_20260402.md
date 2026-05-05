# `fused_variance4_add13_tir_sqrt4` v6 Exactness Diagnosis

Date: `2026-04-02`

## Outcome

- exact-preserving fix found and implemented as isolated `v6a`
- `v6` remains the first allclose-only multiply-fold experiment
- exact equality is restored locally by `v6a`

## Root-Cause Hypothesis

The `v6` source-level fold removed the full-size `T_multiply` buffer and moved
the squared centered-value expression directly into the `T_multiply_red`
reduction update.

Local LLVM/AArch64 codegen then changed from:

- `v5`: produce rounded square values first, store them into `T_multiply`, then
  sum those stored `float32` values in a later loop

to:

- `v6`: contract the square and accumulation into scalar `fmadd` instructions
  inside the variance reduction

That contraction changes the rounding boundary inside the reduction and is
enough to move three outputs by exactly one `float32` ulp after the final
`sqrt`.

Repo-local evidence:

- `v6` local correctness diff stayed limited to `3` outputs, each by
  `5.960464477539063e-08`
- `llvm-objdump -d /tmp/v6_variance4.so | rg 'fmadd|fmla'` showed scalar
  `fmadd` in the reduction path
- `llvm-objdump -d /tmp/v5_variance4.so | rg 'fmadd|fmla'` did not show those
  scalar reduction `fmadd` sites

## Exactness-Recovery Fix

`v6a` keeps the `v6` simplification of removing the standalone full-size
`T_multiply` stage, but inserts a one-element volatile local round-trip:

1. write the squared centered value into `T_multiply_local[0]`
2. read `T_multiply_local[0]`
3. add that loaded `float32` value into `T_multiply_red`

This keeps the full-size buffer removed while restoring the same local rounding
boundary that `v5` effectively relied on.

Local backend evidence:

- `llvm-objdump -d /tmp/v6a_variance4.so | rg 'fmadd|fmla'` no longer showed
  the scalar reduction `fmadd` sites seen in `v6`
- exact equality returned under the same default local `llvm` target

## Files Changed

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v6a_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v6_exactness_diagnosis_20260402.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6a
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v6a_correctness_check.json
llvm-objdump -d /tmp/v5_variance4.so | rg 'fmadd|fmla'
llvm-objdump -d /tmp/v6_variance4.so | rg 'fmadd|fmla'
llvm-objdump -d /tmp/v6a_variance4.so | rg 'fmadd|fmla'
```

No SSH, scp, or remote board commands were used.

## Local Status

- focused variance4 unit tests: `34 tests`, `OK`
- `v6` prior local correctness status: `exact_equal = false`,
  `allclose_atol1e-6_rtol1e-6 = true`, `max_abs_diff = 5.960464477539063e-08`,
  `nonzero_diff_count = 3`
- `v6a` local post-db scheduled swap build:
  `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- `v6a` local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`

## Outputs

- `v6a` build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6a/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- `v6a` build artifact SHA256:
  `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- `v6a` build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6a/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- `v6a` correctness JSON:
  `./session_bootstrap/tmp/variance4_v6a_correctness_check.json`

## Recommendation

Use `v6a` as the exact-preserving continuation point if this lane keeps the
`exact_equal` requirement.

Do not stack further simplifications on top of raw `v6`; keep `v6` recorded as
the allclose-only experiment that exposed the backend `fmadd` boundary.
