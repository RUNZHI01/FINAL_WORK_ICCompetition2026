# `fused_variance4_add13_tir_sqrt4` v16 Local Status

Date: `2026-04-03`

## Starting Point

- start from the exact checked-in `variance4 v15` state
- `v15` is now the current best checked-in board-proven handwritten result for
  this lane with remote median `158.549 ms`
- keep the follow-up tight and stay on the same storage-placement direction;
  no broad rewrite and no math rewrite

## Chosen Edit

- keep the full `v15` storage chain intact:
  local-scoped `lv335_red`, the handle-free `.data`-volatile one-element local
  round-trip, the folded arithmetic, both reductions, and the output signature
- make only `T_multiply_red` explicit:
  `T.alloc_buffer((1, 12, 1, 1), "float32", scope="local")`

Rationale: after `v15` showed that explicitly local-scoping the first tiny
reduction buffer could produce a small real board-side win, the next narrow
plausible follow-up is to keep that exact storage placement intact and local-
scope the second tiny per-channel reduction buffer as well, without reopening
the already-proven exactness-critical arithmetic boundary.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v16_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v16_local_status_20260403.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v16_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v16
python3 - <<'PY'
# compare v14/v15/v16 exported artifact sha256 and size from the local build outputs
PY
```

## Local Status

- focused variance4 unit tests: `74 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from both `v15` and `v14`:
  - `v14` artifact SHA256:
    `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
  - `v15` artifact SHA256:
    `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
  - `v16` artifact SHA256:
    `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
  - `v14` artifact size: `1674488`
  - `v15` artifact size: `1674560`
  - `v16` artifact size: `1674632`
  - size delta vs `v15`: `+72 bytes`
  - size delta vs `v14`: `+144 bytes`
- this makes `v16` a new exact-preserving, schedule-swappable, exported-
  artifact-distinct follow-up on top of the already board-proven `v15` base

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v16/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v16/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
- build artifact size bytes:
  `1674632`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v16_correctness_check.json`

## Board Boundary

This `v16` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from the current board-proven `v15` baseline

However, the dedicated board attempt in this same session hit the current exec
sandbox socket boundary before remote upload or benchmark execution. That
blocked attempt is recorded separately in:

- `./session_bootstrap/reports/variance4_v16_remote_benchmark_blocked_20260403_0134.md`

Practical consequence:

- `v16` is now the next board-worthy local candidate for this lane
- `v15` remains the current best checked-in **board-proven** variance4
  candidate until `v16` is benchmarked remotely
