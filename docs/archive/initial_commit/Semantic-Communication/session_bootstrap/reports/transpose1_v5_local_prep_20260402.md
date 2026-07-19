# `fused_conv2d_transpose1_add9` v5 Local Prep

Date: `2026-04-02`

## Chosen Edit

- baseline to beat: checked-in `transpose1 v4` (`158.621 ms` remote median from `./session_bootstrap/reports/transpose1_v4_remote_benchmark_20260402_172812.md`)
- new follow-up: keep v4's stage-once `data_dilate` / `data_pad` reuse outside `c_1`, but flip the compute consumer order from `c_1 -> h_1/w_1` to `h_1/w_1 -> c_1`

Rationale: this stays in the same winning staging/reuse family as v4 and does not reopen the already-losing raw pre-compile `v0`, `P1` dilate+pad fusion, or `P3` direct guarded-read branches. The only operator-side change is to consume each staged spatial subtile across all three output-channel groups before advancing to the next subtile.

## Files

- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v5_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v5.py`
- `./session_bootstrap/tests/test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy.py`
- `./session_bootstrap/reports/transpose1_v5_local_prep_20260402.md`

## Commands Run

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v5 \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v5_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v5_vs_v4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --operator-name fused_conv2d_transpose1_add9 \
  --reference-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_v5_vs_v1_p2_p4_correctness_20260402/check_report.json
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v5_20260402
```

## Local Status

- focused transpose1 unit tests: `4 tests`, `OK`
- scheduled reference vs v5: `exact_equal = false`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- accepted `v1/P2/P4` vs v5: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- leading v4 vs v5: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local post-db scheduled swap build: `swap_succeeded = true`, `build_status = built`, `export_status = exported`
- no SSH, scp, or remote board commands were used

## Outputs

- scheduled reference vs v5 correctness JSON:
  `./session_bootstrap/tmp/transpose1_v5_correctness_20260402/check_report.json`
- accepted `v1/P2/P4` vs v5 correctness JSON:
  `./session_bootstrap/tmp/transpose1_v5_vs_v1_p2_p4_correctness_20260402/check_report.json`
- v4 vs v5 correctness JSON:
  `./session_bootstrap/tmp/transpose1_v5_vs_v4_correctness_20260402/check_report.json`
- build report:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v5_20260402/fused_conv2d_transpose1_add9_post_db_swap_report.json`
- build artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v5_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- build artifact SHA256:
  `e8ad20741e13b18cf4476cb4b7e798d379a0a6bec89a5c6c16bdda2b7805eb9f`

## Board-side Next Step

Benchmark this exact local artifact on the board:

- candidate entrypoint:
  `./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v5.py`
- swapped artifact:
  `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v5_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- comparison baseline:
  `transpose1 v4` remote report `./session_bootstrap/reports/transpose1_v4_remote_benchmark_20260402_172812.md` (`158.621 ms` median)

Use the same standard board payload benchmark protocol you used for v4. Do not mutate the checked-in v4 or older accepted transpose1 files during that board run.
