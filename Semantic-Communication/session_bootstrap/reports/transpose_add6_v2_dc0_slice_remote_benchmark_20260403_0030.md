# `fused_conv2d_transpose_add6` v2 Remote Benchmark

- generated_at: `2026-04-03T00:30:23+08:00`
- operator: `fused_conv2d_transpose_add6`
- candidate: `v2 dc_0-slice data_pad reuse`
- status: `board proof completed; current evidence says slower than accepted v1`

## What Was Added Before This Run

To avoid ad-hoc SSH and keep this lane aligned with existing repo patterns, this
turn added two minimal checked-in helpers:

- `session_bootstrap/scripts/prepare_handwritten_fused_conv2d_transpose_add6_env.py`
- `session_bootstrap/scripts/run_transpose_add6_remote_payload_benchmark.sh`

The remote helper intentionally reuses the same deployment pattern already used
elsewhere in the repo:

- remote actions go through `session_bootstrap/scripts/ssh_with_password.sh`
- artifact staging is done by `cat > remote_path` after remote `mkdir -p`
- payload timing is still executed by the existing
  `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`

## Artifact Staging

- local artifact:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_20260402_dc0_slice/fused_conv2d_transpose_add6_post_db_swap.so`
- local sha256:
  `383443d0001cdf67d353c1abee2c5c01b52e07c65e32366aac188ae43e2a07c7`
- remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `383443d0001cdf67d353c1abee2c5c01b52e07c65e32366aac188ae43e2a07c7`
- local/remote sha match: `true`

The helper also mirrored the frozen best-staging DB JSON files into:

- `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6/tuning_logs/database_workload.json`
- `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6/tuning_logs/database_tuning_record.json`

## Candidate Change Under Test

Relative to accepted `transpose_add6 v1`, this candidate keeps the arithmetic
path unchanged and changes only tile-local staging order:

- accepted `v1` bias-fused `compute_init` / `compute_update` path preserved
- `data_dilate` and `kernel_transform` remain materialized
- `data_pad` is staged one `dc_0` (`16`-channel) slice at a time
- each staged slice is reused across all three `c_1` groups before the next
  slice is prepared

Local proof before this run already showed:

- focused tests: `8/8 OK`
- exact-vs-v1: `true`
- post-db scheduled swap/build/export: `success`

## Payload Result

The first real board-side payload probe completed successfully and loaded the
expected artifact:

- `artifact_sha256_match = true`
- `load_ms = 3.79`
- `vm_init_ms = 2.907`
- `run_count = 1`
- `run_samples_ms = [172.836]`
- `run_median_ms = 172.836`
- `run_mean_ms = 172.836`
- `run_min_ms = 172.836`
- `run_max_ms = 172.836`
- `output_shape = [1, 3, 256, 256]`

## Comparison

Reference points already accepted in this repo:

- accepted `transpose_add6 v1` remote median: `159.503 ms`
- frozen staging reference median: `159.943 ms`

This first v2 board sample compares as:

- vs accepted `v1`: `+13.333 ms` (`+8.36%` slower)
- vs frozen staging reference: `+12.893 ms` (`+8.06%` slower)

## Interpretation

The important positive result here is **evaluability**:

- the lane is no longer blocked on missing upload/sync mechanics
- the checked-in helper successfully staged the v2 artifact to a dedicated
  handwritten archive on the board
- the board really ran the intended artifact and verified its SHA

But the performance result itself is currently negative:

- this first board proof does **not** support keeping `transpose_add6 v2` as a
  speed win candidate
- under the present evidence, the `dc_0`-slice `data_pad` reuse change regresses
  payload latency relative to accepted `v1`

## Decision

- deployment/helper status: `keep`
- candidate status: `drop for speedup purposes unless a later multi-sample rerun changes the conclusion`
- accepted handwritten board baseline for this operator remains:
  `transpose_add6 v1`, remote median `159.503 ms`

## Exact Next Step

Do **not** spend the next iteration on defending this exact `v2` shape.
Instead:

1. keep the new helper path as the reusable board-proof mechanism for this lane
2. revert attention to a different, narrower locality move or a different
   hotspot lane
3. if needed, rerun this candidate with multi-sample payload timing only as a
   confidence check, not as the primary optimization direction
