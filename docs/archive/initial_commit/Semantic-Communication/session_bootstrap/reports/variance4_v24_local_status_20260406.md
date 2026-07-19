# `fused_variance4_add13_tir_sqrt4` v24 Local Status

Date: `2026-04-06`

## Starting Point

- start from the exact checked-in `variance4 v21` state
- keep the scalar normalized-mean handoff from `v21`
- keep the same nested per-channel consume-now loop shape from `v21`
- test only one extra micro-move: whether the tighter 12-channel reduction
  indexing introduced by `v23` still matters once the mean handoff is already
  scalarized

## Chosen Edit

- keep `lv335_mean_local` as a one-element local scalar loaded once per channel
- keep `T_subtract_local` and `T_multiply_local` as one-element locals
- keep `T_multiply_red` explicit `scope="local"`
- flatten only the tiny reduction buffers:
  - `lv335_red`: `(1, 12, 1, 1)` -> `(12,)`
  - `T_multiply_red`: `(1, 12, 1, 1)` -> `(12,)`

Rationale: `v23` proved that flattening the 12-channel tiny buffers is
codegen-visible on the original `v18` mean-handoff branch. The next isolated
question was whether the same indexing change would still survive after the
mean handoff itself had already been tightened to the `v21` scalar form.

## Commands Run

```bash
python3 -m unittest -q \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24.py \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24_working_copy_tir.py \
  --output-json session_bootstrap/tmp/variance4_v24_correctness_check.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24.py \
  --output-dir session_bootstrap/tmp/variance4_post_db_swap_local_build_v24
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

The working-copy source is new:

- `v24` working-copy TIR SHA256:
  `f2a2afa5132911c0979c0605800d9dad7c96237cd905d5954a5a3260c663184b`

But the exported full-module artifact collapses back to the same bytes as the
checked-in `v21` branch:

- `v21` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v24` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v21` artifact size:
  `1674688`
- `v24` artifact size:
  `1674688`

Reference point for the still-distinct sibling branch:

- `v23` artifact SHA256:
  `2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720`

## Interpretation

This is another useful negative result:

- `v24` is exact-preserving and mechanically swappable
- but on the scalar-mean branch, flattening `lv335_red` and `T_multiply_red`
  does **not** survive as a new compiled artifact
- in practice, the current post-db build path canonicalizes this branch back to
  the same compiled artifact as `v21`

Practical consequence:

- keep `v21` as the compiled representative of the scalar-mean branch
- keep `v22` and `v24` as two different negative proofs that neighboring
  micro-moves can collapse back to existing artifacts
- keep `v23` as the current next board-worthy distinct local candidate
- keep `v18 = 158.347 ms` as the current board-proven best until `v23` can be
  benchmarked remotely

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/variance4_v24_correctness_check.json`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v24/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v24/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
