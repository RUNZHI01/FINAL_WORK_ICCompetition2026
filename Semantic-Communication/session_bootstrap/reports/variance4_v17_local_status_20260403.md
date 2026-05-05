# `fused_variance4_add13_tir_sqrt4` v17 Local Status

Date: `2026-04-03`

## Starting Point

- start from the exact checked-in `variance4 v15` state
- `v15` remains the current best checked-in board-proven handwritten result for
  this lane with remote median `158.549 ms`
- treat `v16` only as negative evidence against blindly stacking more explicit
  local-scope placements on top of `v15`

## Chosen Edit

- keep the full `v15` storage chain intact:
  local-scoped `lv335_red`, default-storage `T_multiply_red`, the handle-free
  `.data`-volatile one-element local round-trip on `T_multiply_local`, both
  reductions, and the output signature
- add a tiny normalized-mean handoff buffer:
  `lv335_mean_local = T.alloc_buffer((1, 12, 1, 1), "float32", scope="local")`
- materialize `lv335_red / 65536.0` once per channel between the two existing
  reductions
- feed `lv335_mean_local[...]` into the hot `T_multiply_local` loop instead of
  re-dividing `lv335_red[...]` inside each squared subtract

Rationale: after the real `v16` board result showed that simply adding another
explicit local scope could move the median in the wrong direction, the next
useful narrow dimension was a storage/reuse handoff detail instead: normalize
the tiny per-channel mean once, then reuse that staged value in the hot second
reduction while leaving the already exactness-critical volatile product
round-trip untouched.

## Files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v17_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17.py`
- `./session_bootstrap/tests/test_fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17_working_copy.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/README.md`
- `./session_bootstrap/reports/variance4_v17_local_status_20260403.md`

## Commands Run

```bash
python3 -m unittest discover -s ./session_bootstrap/tests -p 'test_*variance4*py'
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v17_correctness_check.json
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17
python3 - <<'PY'
# compare v15/v16/v17 exported artifact sha256 and size from the local build reports
PY
```

## Local Status

- focused variance4 unit tests: `78 tests`, `OK`
- local correctness compare against the frozen scheduled reference:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- exported local artifact is distinct from both `v15` and `v16`:
  - `v15` artifact SHA256:
    `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
  - `v16` artifact SHA256:
    `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
  - `v17` artifact SHA256:
    `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
  - `v15` artifact size: `1674560`
  - `v16` artifact size: `1674632`
  - `v17` artifact size: `1674664`
  - size delta vs `v15`: `+104 bytes`
  - size delta vs `v16`: `+32 bytes`
- this makes `v17` a new exact-preserving, schedule-swappable, exported-
  artifact-distinct follow-up on top of the board-proven `v15` base without
  repeating the `v16` local-scope stacking move

## Outputs

- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- build artifact SHA256:
  `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
- build artifact size bytes:
  `1674664`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v17_correctness_check.json`

## Board Boundary

This `v17` candidate is mature enough for the existing variance4 board-side
payload path because it is:

- exact-preserving against the frozen scheduled reference
- successfully consumed by the existing post-db scheduled swap seam
- successfully built and exported through the full-module path
- artifact-distinct from both the current board-proven `v15` baseline and the
  regressing `v16` branch

However, the dedicated board attempt in this same session hit the current exec
sandbox socket boundary before remote upload began. That blocked attempt is
recorded separately in:

- `./session_bootstrap/reports/variance4_v17_remote_benchmark_blocked_20260403_0205.md`

Practical consequence:

- `v17` is now the next exact-preserving, artifact-distinct local follow-up on
  the `variance4` lane
- `v15` remains the current best checked-in **board-proven** variance4
  candidate until `v17` is benchmarked remotely
