# `fused_variance4_add13_tir_sqrt4` v23 Local Status

Date: `2026-04-06`

## Starting Point

- start from the exact checked-in `variance4 v18` state
- keep the winning `v18` handoff family intact:
  normalized-mean handoff, centered-value `T_subtract_local`, local
  `T_multiply_red`, and the one-element volatile `T_multiply_local` round-trip
- avoid reopening the already non-productive `v22` loop-retiming direction

## Chosen Edit

- keep the same arithmetic and reduction order as `v18`
- keep the same two reductions and final `sqrt` output signature
- change only the tiny per-channel buffer shapes:
  - `lv335_red`: `(1, 12, 1, 1)` -> `(12,)`
  - `lv335_mean_local`: `(1, 12, 1, 1)` -> `(12,)`
  - `T_multiply_red`: `(1, 12, 1, 1)` -> `(12,)`
- update the corresponding local reads/writes from four-index unit-shape access
  to direct `v_ax1` / `v_i1` channel indexing

Rationale: after `v22` showed that loop retiming alone collapses back to the
`v21` artifact, the next narrow branch should target something more
codegen-visible while still staying inside the same successful handoff family.
Flattening the tiny 12-channel internal buffers does exactly that.

## Commands Run

```bash
python3 -m unittest -q \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23.py \
  session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23_working_copy_tir.py \
  --output-json session_bootstrap/tmp/variance4_v23_correctness_check.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23.py \
  --output-dir session_bootstrap/tmp/variance4_post_db_swap_local_build_v23
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

## Distinctness

This branch produces a genuinely new exported full-module artifact:

- `v18` artifact SHA256:
  `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
- `v21` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v22` artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- `v23` artifact SHA256:
  `2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720`
- `v18` artifact size:
  `1674624`
- `v21` artifact size:
  `1674688`
- `v22` artifact size:
  `1674688`
- `v23` artifact size:
  `1674696`
- size delta vs `v21/v22`:
  `+8 bytes`
- size delta vs `v18`:
  `+72 bytes`

## Interpretation

This makes `v23` the new useful local follow-up on this lane:

- it is exact-preserving against the frozen scheduled reference
- it is mechanically swappable through the existing post-db seam
- it exports a genuinely distinct artifact instead of collapsing back to `v21`

Practical consequence:

- `v23` is now the next board-worthy local candidate for the variance4 lane
- `v22` should stay classified as artifact-identical negative evidence
- `v18 = 158.347 ms` remains the current board-proven best until `v23` is
  benchmarked remotely

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/variance4_v23_correctness_check.json`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
