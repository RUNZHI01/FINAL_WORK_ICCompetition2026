# `fused_conv2d_transpose1_add9` v4 Local Status

Date: `2026-04-02`

## Chosen Edit

- no operator-side TIR edit yet
- this commit only establishes an isolated `v4` scaffold on top of the accepted `P2+P4` baseline

Rationale: `transpose1` has re-entered the top position after `transpose2 v3` regressed on the board, but the next move must not mutate the accepted `P2+P4` files or reopen already-failed branches (`v0`, `P1`, `P3`). The right first step is to create a clean `v4` edit surface for a genuinely different locality/schedule idea.

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v4_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy.py`
- `./session_bootstrap/reports/transpose1_v4_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- this is intentionally a scaffold-only lane, so no new correctness delta or performance claim is introduced yet
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- build artifact SHA256:
  `e165fb0316981ef408ffe53c07c8aefe02e9937203877ca679cf29ff6c86ce1d`

## Next Step

Apply the first genuinely different transpose1 locality/schedule edit against this `v4` scaffold, rerun the same local proof path, and only then take the changed artifact to the board for a real payload benchmark.
