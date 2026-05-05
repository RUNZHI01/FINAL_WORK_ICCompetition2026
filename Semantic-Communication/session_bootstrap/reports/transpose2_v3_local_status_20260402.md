# `fused_conv2d_transpose2_add12` v3 Local Status

Date: `2026-04-02`

## Chosen Edit

- no operator-side TIR edit yet
- this commit only establishes an isolated `v3` scaffold on top of the accepted `v1` baseline

Rationale: the repo evidence already killed the `P1`-style dilate+pad fusion branch for transpose2, but transpose2 still has enough runtime weight to justify another try. The right next move is therefore not to mutate `v1`, but to create a clean `v3` edit surface for a different seam: a kernel_transform-side locality pass.

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v3_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy.py`
- `./session_bootstrap/reports/transpose2_v3_local_status_20260402.md`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3 \
  session_bootstrap.tests.test_fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_20260402
```

## Local Status

- focused transpose2 unit tests: `4 tests`, `OK`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- this is intentionally a scaffold-only lane, so no new correctness delta or performance claim is introduced yet
- no SSH, scp, or remote board commands were used

## Outputs

- build report:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_20260402/fused_conv2d_transpose2_add12_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_20260402/fused_conv2d_transpose2_add12_post_db_swap.so`
- build artifact SHA256:
  `bae5c138c3c21fda694bd21db4bbd19144263ec3bab3d7de30ab3942551dd561`

## Next Step

Apply the first real `transpose2 v3` handwritten edit against a kernel_transform-side locality seam, rerun this same local proof path, and only then take the changed artifact to the board for a real payload benchmark.
