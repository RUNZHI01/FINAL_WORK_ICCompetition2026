# `fused_variance4_add13_tir_sqrt4` v22 Local Status

Date: `2026-04-06`

## Starting Point

- start from the exact checked-in `variance4 v18` state
- keep the successful `v18` handoff family intact:
  normalized-mean handoff, centered-value `T_subtract_local`, and local
  `T_multiply_red`
- isolate only one structural idea: retime the second phase so each per-channel
  mean is produced and then consumed through the full `k2/k3` reduction before
  moving to the next channel

## Chosen Edit

- keep `lv335_mean_local` at the original `(1, 12, 1, 1)` local shape from `v18`
- keep `T_subtract_local` and `T_multiply_local` as one-element locals
- keep `T_multiply_red` explicit `scope="local"`
- change only the second-phase loop timing:
  materialize `lv335_mean_local[...]`, then immediately run the nested
  `256 x 256` centered-value and square reduction for that same channel

Rationale: after `v21` isolated the scalar-mean branch, the next smallest
question was whether loop retiming alone was enough to create a distinct
codegen-visible improvement while preserving the original `v18` mean-handoff
shape.

## Commands Run

```bash
python3 -m unittest -q \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22.py \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22_working_copy_tir.py \
  --output-json session_bootstrap/tmp/variance4_v22_correctness_check.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22.py \
  --output-dir session_bootstrap/tmp/variance4_post_db_swap_local_build_v22
```

## Local Status

- focused variance4 unit tests: `4 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`

## Key Result

The working-copy source is genuinely new:

- `v22` working-copy TIR SHA256:
  `e604407820d376b2837394b4a260cc9eb16756a321553a8b73fab74faa6ceafa`

But the exported full-module artifact collapses to the same bytes as the
already checked-in `v21` branch:

- `v21` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v22` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v21` artifact size:
  `1674688`
- `v22` artifact size:
  `1674688`

This means the current post-db build path canonicalizes the `v22`
per-channel-retimed branch back to the same compiled artifact as `v21`.

## Interpretation

This is useful negative evidence:

- the `v22` loop-retiming-only change is exact-preserving and mechanically
  swappable
- but it does **not** produce a new compiled artifact under the current build
  path
- therefore `v22` should be kept as methodology evidence, not promoted as a new
  board queue candidate

Practical consequence:

- keep `v21` as the distinct local candidate from the scalar-mean branch
- keep `v22` as proof that loop retiming alone collapses back to the `v21`
  artifact in this lane
- keep `v18 = 158.347 ms` as the current board-proven best until a distinct
  later branch is benchmarked remotely

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/variance4_v22_correctness_check.json`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v22/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v22/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
