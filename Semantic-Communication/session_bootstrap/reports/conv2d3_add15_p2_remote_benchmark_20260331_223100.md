# Conv2d3_Add15 P2 Remote Benchmark

- generated_at: `2026-03-31T22:31:00+08:00`
- stage: `P2`
- operator: `fused_conv2d3_add15`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_p2_20260331_222242/fused_conv2d3_add15_post_db_swap.so`
- local sha256: `10387870bbffdd74802c5a2e887eb639ffc0c70c05e22c7f5407912f8e17da7c`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `10387870bbffdd74802c5a2e887eb639ffc0c70c05e22c7f5407912f8e17da7c`
- local/remote sha match: `true`

## Tiling Change

- accepted v1 state: reduction-channel tiling `rc_0 x rc_1 = 6 x 2`
- P2 candidate: reduction-channel tiling `rc_0 x rc_1 = 3 x 4`
- unchanged: direct `lv347/param_0` conv access pattern, outer parallel tile count `64`, output tile coverage `16 x 64`, `ry_0 x ry_1 = 1 x 7`, `rx_0 x rx_1 = 1 x 7`, `pragma_auto_unroll_max_step = 256`

## Payload Result

- load_ms: `3.851`
- vm_init_ms: `0.468`
- run_median_ms: `163.238`
- run_mean_ms: `163.515`
- run_min_ms: `162.678`
- run_max_ms: `164.503`
- run_variance_ms2: `0.363497`

## Comparison

- accepted conv2d3_add15 v1 median: `161.000 ms`
- P2 delta vs conv2d3_add15 v1: `+2.238 ms` (`+1.39%`)
- reference staging median: `159.943 ms`
- P2 delta vs reference staging: `+3.295 ms` (`+2.06%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.9073486328125e-05`
- note: numerically acceptable locally, but slower on the real target path

## Conclusion

This conv2d3_add15 P2 reduction-channel tiling retune regresses on the Phytium Pi and should be dropped. Keep conv2d3_add15 v1 as the accepted baseline and continue with a narrower P4-style micro-optimization instead.

## Logs

- transport log: `./session_bootstrap/logs/conv2d3_add15_p2_remote_payload_20260331_223100.log`
- payload log: `./session_bootstrap/logs/conv2d3_add15_p2_remote_payload_20260331_223100_payload.log`
