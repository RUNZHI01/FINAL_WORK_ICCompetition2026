# Mean4 v2 Remote Benchmark

- generated_at: `2026-04-03T16:27:00+08:00`
- operator: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- candidate: `v2 scalar epilogue handoff`
- status: `board proof completed; regression vs frozen staging`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- local sha256:
  `4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2`
- local/remote sha match: `true`

## Upload Verification

First ran `--upload-only` mode to verify upload integrity:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

Result:
- `status = upload_verified`
- `local_sha256 = remote_sha256 = 4486eef6...02bd2`
- `local_size_bytes = remote_size_bytes = 1674256`

## Payload Result

After upload verification, ran full payload benchmark:

- load_ms: `6.374`
- vm_init_ms: `0.881`
- run_median_ms: `340.201`
- run_mean_ms: `340.201`
- run_min_ms: `340.201`
- run_max_ms: `340.201`
- run_variance_ms2: `0.0`
- run_count: `1`
- output_shape: `[1, 3, 256, 256]`

## Comparison

Reference point from frozen staging artifact:
- frozen staging median: `329.928 ms`

This `mean4 v2` run compares as:
- vs frozen staging: `+10.273 ms` (`+3.11% slower`)

## Interpretation

The positive result here is **evaluability**:
- the hardened helper path worked correctly
- upload integrity was verified with the new `--upload-only` mode
- SHA and size matched exactly between local and remote
- the board successfully loaded and ran the intended artifact

However, the performance result is negative:
- this first `mean4 v2` scalar epilogue handoff candidate regresses payload latency
- the scalarized handoff buffers that worked well for `variance4` do not translate to a win on `mean4`
- this is the first real explored branch for `mean4`, so it serves as an important negative evidence point

## Decision

- helper/deploy status: `keep` (the hardened upload/benchmark path is now reusable)
- candidate status: `drop for speedup purposes`
- the lane should remain live for a materially different edit idea, but this exact scalar epilogue handoff family is now closed

## Next Steps

Given the recent pattern of negative results:
- `transpose_add6 v2`: +8.36% slower
- `transpose2 v4`: +2.29% slower
- `mean4 v2`: +3.11% slower

The project should:
1. reassess whether the current optimization family (data-staging locality / epilogue handoff) is approaching diminishing returns
2. consider returning to already-successful lanes (`transpose1 v7`, `variance4 v18`) for deeper analysis
3. or explore a fundamentally different optimization direction

## Commands

Upload verification:

```bash
set -a
source ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env
set +a
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- upload verification log: available via `run_mean4_remote_payload_benchmark.sh`
- payload log: available via `run_remote_tvm_inference_payload.sh`
