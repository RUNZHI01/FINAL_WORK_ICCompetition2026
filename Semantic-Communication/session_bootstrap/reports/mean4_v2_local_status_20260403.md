# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` v2 Local Status

Date: `2026-04-03`

## Starting Point

- the checked-in `mean4` lane previously had only the seed-clone `v1` working
  copy and a local post-db swap/build proof
- current best-staging still keeps `mean4` in the task summary, but there is no
  direct DB `query_schedule` / `query_ir_module` hit for this operator
- after `transpose2 v4` and `transpose_add6 v2` both regressed on the board,
  the next high-value lane moved to `mean4`

## Chosen Edit

Keep the reduction and output signature intact, but make the first real
operator-side handwritten change on top of the checked-in `v1` seed clone:

- keep `lv335_red` as the reduction buffer
- stage the normalized per-channel mean once into:
  `lv335_mean_local = T.alloc_buffer((1, 12, 1, 1), "float32", scope="local")`
- replace the four full-frame epilogue intermediates with one-element local
  handoff buffers:
  - `T_subtract_local`
  - `T_divide_local`
  - `T_multiply_local`
  - `T_add_local`
- compute the subtract/divide/multiply/add/relu chain inside the final
  elementwise loop instead of materializing full `1 x 12 x 256 x 256`
  intermediates

Rationale:

- this is the smallest mean4 edit that attacks obvious memory traffic without
  inventing a new schedule family
- it also mirrors the fresh repo evidence from `variance4`, where tiny
  reuse/handoff edits were the only ones that produced board-side gains

## Files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v2_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py`
- `./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py`
- `./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py`
- `./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/README.md`
- `./session_bootstrap/runbooks/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_runbook_2026-03-31.md`
- `./session_bootstrap/reports/mean4_v2_local_status_20260403.md`

## Commands Run

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_mean4_subtract4_divide4_multiply4_add14_relu3 \
  --candidate-tir ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/mean4_v2_correctness_check_20260403.json

/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue
```

## Local Status

- correctness vs the frozen scheduled reference:
  - `exact_equal = false`
  - `allclose_atol1e-6_rtol1e-6 = true`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 9.5367431640625e-07`
  - `mean_abs_diff = 1.744936106717887e-08`
  - `nonzero_diff_count = 118176`
- DB lookup maturity is unchanged:
  - `query_tuning_record_hit = false`
  - `query_ir_module_hit = false`
  - `query_schedule_hit = false`
- post-db swap/build/export:
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- exported artifact is distinct from the earlier `v1` proof build:
  - `v1` artifact SHA256:
    `de429fe2d2be48696c740aa4b279a9da6337fc469d2d05d6061f874e6702bbc9`
  - `v2` artifact SHA256:
    `4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2`
  - `v1` artifact size: `1678704`
  - `v2` artifact size: `1674256`
  - size delta vs `v1`: `-4448 bytes`

Interpretation:

- `v2` is a real handwritten branch, not just another empty working copy
- it is **not** exact-preserving, so it should be treated as an allclose-gated
  exploratory candidate rather than a numerically identical rewrite
- the max diff stays under `1e-6`, which is clean enough to justify a first
  board attempt for this previously unevaluated lane

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/mean4_v2_correctness_check_20260403.json`
- build report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`

## Board Boundary

This round also added the missing dedicated `mean4` board helper path:

- `./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py`
- `./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`

The first board attempt through that helper path was launched in this same
round, but the current exec sandbox blocked SSH sockets before upload
completed. That blocked attempt is recorded separately in:

- `./session_bootstrap/reports/mean4_v2_remote_benchmark_blocked_20260403.md`

Practical consequence:

- `mean4 v2` is now the first board-worthy local candidate for this lane
- the helper/evaluability gap is closed inside the repo
- there is still **no** board performance claim yet for `mean4`
