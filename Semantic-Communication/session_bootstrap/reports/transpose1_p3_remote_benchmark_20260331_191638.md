# Transpose1 P3 Remote Benchmark

- generated_at: `2026-03-31T19:16:38+08:00`
- stage: `P3 Path A`
- operator: `fused_conv2d_transpose1_add9`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_path_a/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `d5891aaecca9e43d9b1aace2ed2dc583d66ba7d280e92cd8520303e05de04e3f`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `d5891aaecca9e43d9b1aace2ed2dc583d66ba7d280e92cd8520303e05de04e3f`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.89`
- vm_init_ms: `0.468`
- run_median_ms: `202.524`
- run_mean_ms: `202.734`
- run_min_ms: `202.387`
- run_max_ms: `203.981`
- run_variance_ms2: `0.217141`

## Comparison

- accepted P0/v1 median: `162.954 ms`
- P3 delta vs P0/v1: `+39.570 ms` (`+24.28%`)
- reference staging median: `159.943 ms`
- P3 delta vs reference staging: `+42.581 ms` (`+26.62%`)

## Local Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `7.62939453125e-06`
- note: numerically close locally, but runtime regresses badly on the actual target path

## Conclusion

P3 Path A is a clear regression on the Phytium Pi and should be dropped in its current form. The most reasonable next step is to roll back to the accepted P0/v1 state and continue with `P2` tile tuning on top of that accepted baseline instead of committing this P3 branch.

## Logs

- transport log: `./session_bootstrap/logs/transpose1_p3_remote_payload_20260331_191638.log`
- payload log: `./session_bootstrap/logs/transpose1_p3_remote_payload_20260331_191638_payload.log`
