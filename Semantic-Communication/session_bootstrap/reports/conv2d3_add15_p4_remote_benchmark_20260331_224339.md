# Conv2d3_Add15 P4 Remote Benchmark

- generated_at: `2026-03-31T22:43:39+08:00`
- stage: `P4`
- operator: `fused_conv2d3_add15`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_p4_20260331_224008/fused_conv2d3_add15_post_db_swap.so`
- local sha256: `79590b5152daec5c000b9a7abfe300be903e6e04a1f0076b3d9e82b5bb3b2990`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `79590b5152daec5c000b9a7abfe300be903e6e04a1f0076b3d9e82b5bb3b2990`
- local/remote sha match: `true`

## Micro-Change

- accepted conv2d3_add15 v1 state kept intact
- P4 change: outer scheduled-region `pragma_auto_unroll_max_step` raised from `256` to `512`
- unchanged: bias-fused `conv2d_nchw_init` / `conv2d_nchw_update`, direct `lv347/param_0` convolution access pattern, scheduled h/w tiling, reduction split, outer parallel tile count `64`, 16-lane x-vectorization

## Payload Result

- load_ms: `3.847`
- vm_init_ms: `0.436`
- run_median_ms: `162.029`
- run_mean_ms: `162.38`
- run_min_ms: `161.7`
- run_max_ms: `165.703`
- run_variance_ms2: `1.263174`

## Comparison

- accepted conv2d3_add15 v1 median: `161.000 ms`
- P4 delta vs conv2d3_add15 v1: `+1.029 ms` (`+0.64%`)
- reference staging median: `159.943 ms`
- P4 delta vs reference staging: `+2.086 ms` (`+1.30%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.9073486328125e-05`
- note: numerically acceptable locally, but slower on the real target path

## Conclusion

This conv2d3_add15 P4 auto-unroll micro-tune regresses on the Phytium Pi and should be dropped. Keep conv2d3_add15 v1 as the accepted baseline.

## Logs

- transport log: `./session_bootstrap/logs/conv2d3_add15_p4_remote_payload_20260331_224339.log`
- payload log: `./session_bootstrap/logs/conv2d3_add15_p4_remote_payload_20260331_224339_payload.log`
