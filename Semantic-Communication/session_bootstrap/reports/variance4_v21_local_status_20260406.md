# `fused_variance4_add13_tir_sqrt4` v21 Local Status

Date: `2026-04-06`

## Starting Point

- start from the exact checked-in `variance4 v18` state
- `v18` remains the current best checked-in board-proven handwritten result for
  this lane with remote median `158.347 ms`
- keep `v19` as negative evidence against changing the mean handoff and
  reduction storage at the same time
- keep the checked-in `v20` Welford draft intact as a separate algorithmic
  branch rather than folding it into the current reuse/handoff line

## Chosen Edit

- keep the full `v18` reuse/handoff chain intact:
  local-scoped `lv335_red`, one-element `T_subtract_local`, explicit local
  `T_multiply_red`, and the handle-free `.data`-volatile one-element
  `T_multiply_local` round-trip
- retry only the `v19` idea that was still worth isolating:
  tighten `lv335_mean_local` from a `(1, 12, 1, 1)` local buffer to a
  one-element local scalar loaded once per channel
- keep the hot `k2/k3` loop nested underneath that scalar mean handoff and feed
  the scalar handoff into the existing centered-value `T_subtract_local` stage
- unlike `v19`, explicitly keep `T_multiply_red` in `scope="local"` so this
  branch measures the scalar mean handoff without reintroducing a reduction
  storage confound

Rationale: `v19` regressed slightly relative to `v18`, but it changed two
things at once from the board-proven `v18` baseline: the mean handoff shape and
the `T_multiply_red` storage placement. `v21` exists to isolate that question
cleanly. If `v21` later beats `v18` on board, the improvement can be attributed
to the scalar mean handoff itself rather than to a mixed structural change.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v21_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21_working_copy.py`
- `./session_bootstrap/reports/variance4_v21_local_status_20260406.md`

## Commands Run

```bash
python3 -m unittest -q \
  ./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21.py \
  ./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21_working_copy.py

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v21_correctness_check.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v21
```

## Local Status

- focused `v21` wrapper/working-copy unit tests: `4 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from both `v18` and `v19`:
  - `v18` artifact SHA256:
    `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
  - `v19` artifact SHA256:
    `a6e38b879d01993b98e6cc50b43bc772e3d7b2fbdf52f9fcc830365111e7646a`
  - `v21` artifact SHA256:
    `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
  - `v18` artifact size: `1674624`
  - `v19` artifact size: `1674616`
  - `v21` artifact size: `1674688`
  - size delta vs `v18`: `+64 bytes`
  - size delta vs `v19`: `+72 bytes`

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v21/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v21/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- build artifact size bytes:
  `1674688`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v21_correctness_check.json`

## Board Boundary

This `v21` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from the current board-proven `v18` baseline and the older
  `v19` branch

However, the attempted board run in this same session hit a network-level
timeout before upload began. That blocked attempt is recorded separately in:

- `./session_bootstrap/reports/variance4_v21_remote_benchmark_blocked_20260406.md`

Practical consequence:

- `v21` is now the next board-worthy local candidate for this lane
- `v18` remains the current best checked-in **board-proven** variance4
  candidate until `v21` is benchmarked remotely
