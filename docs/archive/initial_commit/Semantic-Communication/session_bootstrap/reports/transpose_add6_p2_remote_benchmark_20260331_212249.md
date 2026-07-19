# Transpose_Add6 P2 Remote Benchmark

- generated_at: `2026-03-31T21:22:49+08:00`
- stage: `P2`
- operator: `fused_conv2d_transpose_add6`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_p2_20260331_2114/fused_conv2d_transpose_add6_post_db_swap.so`
- local sha256: `eb2100f6736d008c716966a215b4f1296f44169a4152220793105eb8b64a15f0`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `eb2100f6736d008c716966a215b4f1296f44169a4152220793105eb8b64a15f0`
- local/remote sha match: `true`

## Tiling Change

- accepted v1 state: inner output-channel tiling `c_2 x c_3 = 4 x 4`
- P2 candidate: inner output-channel tiling `c_2 x c_3 = 2 x 8`
- unchanged: outer `c_1 = 3`, per-`c_1` channel coverage `16`, `h_2 x h_3 = 2 x 2`, `w_2 x w_3_fused = 2 x 4`, `dc_0 x dc_1 = 6 x 16`, `pragma_auto_unroll_max_step = 32`, bias-fused path

## Payload Result

- load_ms: `3.763`
- vm_init_ms: `0.466`
- run_median_ms: `161.122`
- run_mean_ms: `161.094`
- run_min_ms: `160.624`
- run_max_ms: `161.618`
- run_variance_ms2: `0.14217`

## Comparison

- accepted transpose_add6 v1 median: `159.503 ms`
- P2 delta vs transpose_add6 v1: `+1.619 ms` (`+1.01%`)
- reference staging median: `159.943 ms`
- P2 delta vs reference staging: `+1.179 ms` (`+0.74%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.33514404296875e-05`
- note: numerically acceptable locally, but slightly slower on the real target path

## Conclusion

This transpose_add6 P2 inner output-channel tiling retune regresses on the Phytium Pi and should be dropped. Keep transpose_add6 v1 as the accepted baseline and continue with a narrower P4-style micro-optimization instead.

## Logs

- transport log: `./session_bootstrap/logs/transpose_add6_p2_remote_payload_20260331_212249.log`
- payload log: `./session_bootstrap/logs/transpose_add6_p2_remote_payload_20260331_212249_payload.log`
