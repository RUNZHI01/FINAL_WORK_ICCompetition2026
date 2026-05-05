# Transpose1 P3 v3 Local Prep

- generated_at: `2026-04-02T11:41:46+08:00`
- stage: `P3 path A direct-stride-read candidate on top of accepted P2+P4`
- operator: `fused_conv2d_transpose1_add9`
- status: `local_ready_for_remote_benchmark`

## Why this candidate exists

Recent real-board evidence ruled out the narrower P1-style `dilate+pad` fusion move on both transpose1 and transpose2. This `v3` candidate therefore pivots to the repo’s documented `P3 path A` direction instead of repeating that losing structural change.

## Structural Change

On top of the accepted transpose1 `P2+P4` state, this candidate:

- removes the materialized `data_dilate` buffer
- removes the materialized `data_pad` buffer
- keeps `kernel_transform` materialized
- keeps the accepted output-channel tiling `c_1 x c_3 = 3 x 8`
- keeps the accepted `pragma_auto_unroll_max_step = 64`
- rewrites `compute_update` to read `lv318` directly through the transposed-convolution stride/parity guards

## Local checks

Focused tests passed:

```bash
python3 -m unittest \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v3_working_copy \
  session_bootstrap.tests.test_fused_conv2d_transpose1_add9_scheduled_form_candidate_v3
```

Local post-db build passed:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_v3_20260402
```

Correctness compare passed within the existing tolerance gate:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/check_transpose1_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v3_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/transpose1_p3_v3_correctness_check/transpose1_p3_v3_correctness_check.json
```

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_v3_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `e80aa54fc3eb1eabf8e34696ab1f0c24c22a20bd362339d155e812d90bc79676`
- artifact size: `1678648 bytes`
- local build report: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_v3_20260402/fused_conv2d_transpose1_add9_post_db_swap_report.json`

## Correctness Context

- reference seed sha256: `fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`
- candidate working-copy sha256: `233558e25a6232539de189feb22fad1db71d2fb234c74533e5e1110a84aa42cd`
- `exact_equal = false`
- `allclose_atol0_rtol0 = false`
- `allclose_atol1e-6_rtol1e-6 = false`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 8.58306884765625e-06`
- `mean_abs_diff = 4.6075993509475666e-07`
- `nonzero_diff_count = 328202`
- correctness JSON: `./session_bootstrap/tmp/transpose1_p3_v3_correctness_check/transpose1_p3_v3_correctness_check.json`

## Remote next step

Upload this exact `.so` to a dedicated handwritten transpose1-v3 staging archive and run the standard remote payload benchmark protocol with `2` warmups and `10` repeats. Compare against:

- accepted transpose1 `P2+P4`: `159.356 ms`
- reference staging: `159.943 ms`
