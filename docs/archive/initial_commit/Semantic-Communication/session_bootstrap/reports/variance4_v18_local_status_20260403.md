# `fused_variance4_add13_tir_sqrt4` v18 Local Status

Date: `2026-04-03`

## Starting Point

- start from the exact checked-in `variance4 v17` state
- `v17` is now the current best checked-in board-proven handwritten result for
  this lane with remote median `158.478 ms`
- keep the follow-up tight and stay on the reuse/handoff direction that helped
  `v17`; do not reopen the `v16` local-scope-stacking direction

## Chosen Edit

- keep the full `v17` storage chain intact:
  local-scoped `lv335_red`, tiny `lv335_mean_local`, default-storage
  `T_multiply_red`, the handle-free `.data`-volatile one-element
  `T_multiply_local` round-trip, both reductions, and the output signature
- add one more tiny handoff:
  `T_subtract_local = T.alloc_buffer((1,), "float32", scope="local")`
- materialize `lv335 - lv335_mean_local` once per element into
  `T_subtract_local[0]`
- feed `T_subtract_local[0]` into the existing `T_multiply_local` square so the
  centered value is reused instead of re-subtracted inside the square

Rationale: `v17` already showed that staging the normalized mean once and then
reusing it could move the board result in the right direction, while `v16`
showed that simply piling on more explicit local scopes was not a safe next
step. Before freezing the checked-in `v18` surface, a tighter in-place
`lv335_red` handoff draft was locally exported and collapsed to the exact same
artifact SHA as `v17`, so it was not worth promoting. The final checked-in
`v18` therefore keeps the successful `v17` mean handoff intact and tests the
next similarly narrow reuse point: stage the centered value once, then reuse it
for the square.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v18_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v18_local_status_20260403.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v18_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v18
```

## Local Status

- focused variance4 unit tests: `82 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from `v17`, `v16`, and `v15`:
  - `v15` artifact SHA256:
    `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
  - `v16` artifact SHA256:
    `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
  - `v17` artifact SHA256:
    `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
  - `v18` artifact SHA256:
    `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
  - `v15` artifact size: `1674560`
  - `v16` artifact size: `1674632`
  - `v17` artifact size: `1674664`
  - `v18` artifact size: `1674624`
  - size delta vs `v17`: `-40 bytes`
  - size delta vs `v16`: `-8 bytes`
  - size delta vs `v15`: `+64 bytes`
- this makes `v18` a new exact-preserving, schedule-swappable, exported-
  artifact-distinct follow-up on top of the board-proven `v17` base without
  reverting to the `v16` scope-only direction

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v18/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v18/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
- build artifact size bytes:
  `1674624`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v18_correctness_check.json`

## Board Boundary

This `v18` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from the current board-proven `v17` baseline and the older
  `v16` / `v15` branches

However, the dedicated board attempt in this same session hit the current exec
sandbox socket boundary before remote upload began. That blocked attempt is
recorded separately in:

- `./session_bootstrap/reports/variance4_v18_remote_benchmark_blocked_20260403_0228.md`

Practical consequence:

- `v18` is now the next board-worthy local candidate for this lane
- `v17` remains the current best checked-in **board-proven** variance4
  candidate until `v18` is benchmarked remotely
