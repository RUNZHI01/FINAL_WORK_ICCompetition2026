# `fused_variance4_add13_tir_sqrt4` v19 Local Status

Date: `2026-04-03`

## Starting Point

- start from the exact checked-in `variance4 v18` state
- `v18` is now the current best checked-in board-proven handwritten result for
  this lane with remote median `158.347 ms`
- stay on the reuse/handoff direction that helped `v17` and `v18`; do not
  reopen the `v16` local-scope-stacking direction and do not promote
  artifact-identical rewrites

## Chosen Edit

- keep the full `v18` storage chain intact:
  local-scoped `lv335_red`, one-element `T_subtract_local`, default-storage
  `T_multiply_red`, the handle-free `.data`-volatile one-element
  `T_multiply_local` round-trip, both reductions, and the output signature
- tighten the normalized-mean handoff itself:
  change `lv335_mean_local` from a `(1, 12, 1, 1)` local buffer to a
  one-element local buffer
- materialize `lv335_red[...] / 65536.0` once per channel into
  `lv335_mean_local[0]`
- nest the hot `k2/k3` reduction loops under that per-channel handoff and feed
  `lv335_mean_local[0]` into the existing `T_subtract_local` centered-value
  stage

Rationale: `v17` and `v18` both moved in the right direction by staging one
small arithmetic handoff and then reusing it in the hot loop. The next equally
narrow follow-up is therefore not another explicit scope placement, but a
tighter mean handoff: keep the centered-value reuse from `v18`, but scalarize
the normalized mean handoff itself so the hot loop no longer reindexes the
12-element local mean buffer.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v19_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v19_local_status_20260403.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v19_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v19
```

## Local Status

- focused variance4 unit tests: `86 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from `v18`, `v17`, `v16`, and `v15`:
  - `v15` artifact SHA256:
    `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
  - `v16` artifact SHA256:
    `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
  - `v17` artifact SHA256:
    `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
  - `v18` artifact SHA256:
    `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
  - `v19` artifact SHA256:
    `a6e38b879d01993b98e6cc50b43bc772e3d7b2fbdf52f9fcc830365111e7646a`
  - `v15` artifact size: `1674560`
  - `v16` artifact size: `1674632`
  - `v17` artifact size: `1674664`
  - `v18` artifact size: `1674624`
  - `v19` artifact size: `1674616`
  - size delta vs `v18`: `-8 bytes`
  - size delta vs `v17`: `-48 bytes`
  - size delta vs `v16`: `-16 bytes`
  - size delta vs `v15`: `+56 bytes`
- this makes `v19` a new exact-preserving, schedule-swappable, exported-
  artifact-distinct follow-up on top of the board-proven `v18` base without
  reopening the disproven `v16` scope-stacking direction

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v19/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v19/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `a6e38b879d01993b98e6cc50b43bc772e3d7b2fbdf52f9fcc830365111e7646a`
- build artifact size bytes:
  `1674616`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v19_correctness_check.json`

## Board Boundary

This `v19` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from the current board-proven `v18` baseline and the older
  `v17` / `v16` / `v15` branches

However, the dedicated board attempt in this same session hit the current exec
sandbox socket boundary before remote upload began. That blocked attempt is
recorded separately in:

- `./session_bootstrap/reports/variance4_v19_remote_benchmark_blocked_20260403_0254.md`

Practical consequence:

- `v19` is now the next board-worthy local candidate for this lane
- `v18` remains the current best checked-in **board-proven** variance4
  candidate until `v19` is benchmarked remotely
