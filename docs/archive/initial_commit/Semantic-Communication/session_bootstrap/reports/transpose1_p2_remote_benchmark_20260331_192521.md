# Transpose1 P2 Remote Benchmark

- generated_at: `2026-03-31T19:25:21+08:00`
- stage: `P2`
- operator: `fused_conv2d_transpose1_add9`
- status: `accepted`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p2/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `9f60245fdfefe9ac8716b9f5e68d001e5f42a96efdf2d07c8cd7e40656943c16`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `9f60245fdfefe9ac8716b9f5e68d001e5f42a96efdf2d07c8cd7e40656943c16`
- local/remote sha match: `true`

## Tiling Change

- accepted baseline: output-channel tiling `c_1 x c_3 = 6 x 4`
- P2 candidate: output-channel tiling `c_1 x c_3 = 3 x 8`
- unchanged: outer parallel tile count `32`, `h_2 x h_3 = 16 x 2`, `dc_0 x dc_1 = 12 x 4`, `pragma_auto_unroll_max_step = 32`

## Payload Result

- load_ms: `3.802`
- vm_init_ms: `0.463`
- run_median_ms: `159.977`
- run_mean_ms: `160.156`
- run_min_ms: `159.597`
- run_max_ms: `161.445`
- run_variance_ms2: `0.266394`

## Comparison

- accepted P0/v1 median: `162.954 ms`
- P2 delta vs P0/v1: `-2.977 ms` (`-1.83%`)
- reference staging median: `159.943 ms`
- P2 delta vs reference staging: `+0.034 ms` (`+0.02%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `7.62939453125e-06`
- note: not bitwise-equal locally, but numerically within the existing tolerance gate and remote runtime improved

## Conclusion

P2 is a valid improvement on top of the accepted P0/v1 baseline and should be kept. The next step is to commit this P2 tiling change and then decide whether any narrower P4-style micro-optimization is still worth attempting.

## Logs

- transport log: `./session_bootstrap/logs/transpose1_p2_remote_payload_20260331_192521.log`
- payload log: `./session_bootstrap/logs/transpose1_p2_remote_payload_20260331_192521_payload.log`
