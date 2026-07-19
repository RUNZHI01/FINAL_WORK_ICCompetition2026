# Transpose2 P2 Remote Benchmark

- generated_at: `2026-03-31T20:26:02+08:00`
- stage: `P2`
- operator: `fused_conv2d_transpose2_add12`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p2_20260331_201742/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256: `c97a6c67892ff1b37d79658fe1e0c2220229e8843bf5f6386c720d31a8d45b67`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `c97a6c67892ff1b37d79658fe1e0c2220229e8843bf5f6386c720d31a8d45b67`
- local/remote sha match: `true`

## Tiling Change

- accepted v1 state: inner width tiling `w_2 x w_3 = 4 x 8`
- P2 candidate: inner width tiling `w_2 x w_3 = 8 x 4`
- unchanged: outer `w_0` sweep=`8`, `h_1 x h_2 x h_3 = 4 x 2 x 1`, `dc_0 x dc_1 = 4 x 6`, `pragma_auto_unroll_max_step = 32`, bias-fused path

## Payload Result

- load_ms: `3.751`
- vm_init_ms: `0.451`
- run_median_ms: `162.641`
- run_mean_ms: `162.771`
- run_min_ms: `162.393`
- run_max_ms: `163.635`
- run_variance_ms2: `0.142928`

## Comparison

- accepted transpose2 v1 median: `161.416 ms`
- P2 delta vs transpose2 v1: `+1.225 ms` (`+0.76%`)
- reference staging median: `159.943 ms`
- P2 delta vs reference staging: `+2.698 ms` (`+1.69%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `4.76837158203125e-06`
- note: numerically acceptable locally, but slightly slower on the real target path

## Conclusion

This conservative transpose2 P2 inner-width retune regresses on the Phytium Pi and should be dropped. The next sensible step is to roll back to the accepted transpose2 v1 baseline and explore a narrower P4-style micro-optimization instead.

## Logs

- transport log: `./session_bootstrap/logs/transpose2_p2_remote_payload_20260331_202602.log`
- payload log: `./session_bootstrap/logs/transpose2_p2_remote_payload_20260331_202602_payload.log`
