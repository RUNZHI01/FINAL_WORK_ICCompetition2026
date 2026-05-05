# Transpose1 v4 First Locality Local Prep

- generated_at: `2026-04-02T17:25:00+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v4 data-staging hoist outside c_1`
- status: `local_ready_for_remote_benchmark`

## Chosen Edit

On top of the accepted transpose1 `P2+P4` scheduled-form state, this `v4` candidate keeps all three materialized staging buffers (`data_dilate`, `data_pad`, `kernel_transform`) and the accepted tiling/unroll structure intact, but hoists the per-spatial-tile `data_dilate` / `data_pad` fill outside the `c_1` loop so the staged tile is built once and then reused across all three output-channel groups.

## Why this edit

This is intentionally different from the already-dropped transpose1 branches:

- not raw pre-compile `v0`
- not `P1`-style dilate+pad fusion
- not `P3` direct guarded-read

The goal is to keep the accepted materialized-buffer strategy while removing repeated tile staging work across `c_1` groups.

## Commands Run

```bash
python3 -m unittest   session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4   session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py   --operator-name fused_conv2d_transpose1_add9   --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py   --output-json ./session_bootstrap/tmp/transpose1_v4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py   --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py   --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402_first_locality_candidate
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- local correctness compare: `exact_equal = false`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- no SSH, scp, or remote board commands were used in this prep stage

## Outputs

- correctness JSON:
  `./session_bootstrap/tmp/transpose1_v4_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402_first_locality_candidate/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402_first_locality_candidate/fused_conv2d_transpose1_add9_post_db_swap.so`
- build artifact SHA256:
  `42b17ee6b458f1440fd6cd40f70ea88ace4d9b547f5960854c911ab1f94a4f95`

## Board-side Next Step

Upload this exact `.so` to a dedicated handwritten transpose1-v4 staging archive and run the standard remote payload benchmark protocol with `2` warmups and `10` repeats. Compare against:

- accepted transpose1 `P2+P4`: `159.356 ms`
- reference staging: `159.943 ms`
