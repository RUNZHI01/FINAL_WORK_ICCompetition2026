# Transpose_Add6 P4 Remote Benchmark

- generated_at: `2026-03-31T21:36:28+08:00`
- stage: `P4`
- operator: `fused_conv2d_transpose_add6`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p4_20260331_212704/fused_conv2d_transpose_add6_post_db_swap.so`
- local sha256: `74721e82c37a32b788102ade34b8f2eed23b6d912b66a56d3915c4b611c72dd6`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `74721e82c37a32b788102ade34b8f2eed23b6d912b66a56d3915c4b611c72dd6`
- local/remote sha match: `true`

## Micro-Change

- accepted transpose_add6 v1 state kept intact
- P4 change: `pragma_auto_unroll_max_step` raised from `32` to `64`
- unchanged: bias-fused path, output-channel tiling `c_1 x c_2 x c_3 = 3 x 4 x 4`, `h_2 x h_3 = 2 x 2`, `w_2 x w_3_fused = 2 x 4`, `dc_0 x dc_1 = 6 x 16`, 4-lane vectorized inner loops

## Payload Result

- load_ms: `3.768`
- vm_init_ms: `0.466`
- run_median_ms: `160.805`
- run_mean_ms: `160.969`
- run_min_ms: `159.825`
- run_max_ms: `162.999`
- run_variance_ms2: `1.035643`

## Comparison

- accepted transpose_add6 v1 median: `159.503 ms`
- P4 delta vs transpose_add6 v1: `+1.302 ms` (`+0.82%`)
- reference staging median: `159.943 ms`
- P4 delta vs reference staging: `+0.862 ms` (`+0.54%`)
- current best transpose1 state: `159.356 ms`
- P4 delta vs transpose1 best: `+1.449 ms` (`+0.91%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.33514404296875e-05`
- note: numerically acceptable locally, but slower on the real target path

## Conclusion

This transpose_add6 P4 auto-unroll micro-tune regresses on the Phytium Pi and should be dropped. Keep transpose_add6 v1 as the accepted baseline.

## Logs

- transport log: `./session_bootstrap/logs/transpose_add6_p4_remote_payload_20260331_213628.log`
- payload log: `./session_bootstrap/logs/transpose_add6_p4_remote_payload_20260331_213628_payload.log`
