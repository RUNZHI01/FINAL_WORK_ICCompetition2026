# `fused_variance4_add13_tir_sqrt4` v15 Local Status

Date: `2026-04-03`

## Starting Point

- start from the exact checked-in `variance4 v14` state
- `v14` is already board-proven with remote median `159.655 ms`
- `v14` remains the current best checked-in board-proven candidate for the
  variance4 lane unless a later follow-up is also benchmarked on board

## Chosen Edit

- keep the full `v14` handle-free `.data`-volatile one-element local round-trip
  intact
- make only `lv335_red` explicit:
  `T.alloc_buffer((1, 12, 1, 1), "float32", scope="local")`
- leave `T_multiply_red`, `T_multiply_local`, both reductions, and the output
  signature otherwise unchanged

Rationale: `lv335_red` is a tiny per-channel reduction buffer that is reread
through the hot second reduction. Making only that buffer explicitly `local` is
the smallest plausible storage-placement follow-up on top of `v14` that can
change the exported artifact without reopening the already-settled exactness
boundary around the volatile one-element round-trip.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v15_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v15_local_status_20260403.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v15_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15
python3 - <<'PY'
# compare v14/v15 exported artifact sha256 and size from the two local build reports
PY
```

## Local Status

- focused variance4 unit tests: `70 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from `v14`:
  - `v14` artifact SHA256:
    `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
  - `v15` artifact SHA256:
    `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
  - `v14` artifact size: `1674488`
  - `v15` artifact size: `1674560`
  - size delta vs `v14`: `+72 bytes`
- this makes `v15` a new exact-preserving, schedule-swappable, exported-artifact-
  distinct follow-up on top of the already board-proven `v14` base

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
- build artifact size bytes:
  `1674560`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v15_correctness_check.json`

## Board Boundary

This `v15` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from the board-proven `v14` baseline

However, the dedicated board attempt in this same session hit the current exec
sandbox socket boundary before upload or benchmark execution. That blocked
attempt is recorded separately in:

- `./session_bootstrap/reports/variance4_v15_remote_benchmark_blocked_20260403_0105.md`

Practical consequence:

- `v15` is now the next board-worthy local candidate for this lane
- `v14` remains the current best checked-in **board-proven** variance4
  candidate until `v15` is benchmarked remotely
