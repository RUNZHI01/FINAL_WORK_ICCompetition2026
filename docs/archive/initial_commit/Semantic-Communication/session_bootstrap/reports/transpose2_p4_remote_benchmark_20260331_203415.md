# Transpose2 P4 Remote Benchmark

- generated_at: `2026-03-31T20:34:15+08:00`
- stage: `P4`
- operator: `fused_conv2d_transpose2_add12`
- status: `no_gain_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p4_20260331_202942/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256: `0d818524c63b94ede51aad1335165160107f9bf35da52a4fcc08f8384ec4aaef`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `0d818524c63b94ede51aad1335165160107f9bf35da52a4fcc08f8384ec4aaef`
- local/remote sha match: `true`

## Micro-Change

- accepted transpose2 v1 state kept intact
- P4 change: `pragma_auto_unroll_max_step` raised from `32` to `64`
- unchanged: data_dilate/data_pad/kernel_transform, bias-fused path, scheduled h/w tiling, reduction split, outer `w_0` sweep, vectorized inner-width lanes

## Payload Result

- load_ms: `3.832`
- vm_init_ms: `0.47`
- run_median_ms: `161.468`
- run_mean_ms: `161.506`
- run_min_ms: `161.327`
- run_max_ms: `161.982`
- run_variance_ms2: `0.036119`

## Comparison

- accepted transpose2 v1 median: `161.416 ms`
- P4 delta vs transpose2 v1: `+0.052 ms` (`+0.03%`)
- reference staging median: `159.943 ms`
- P4 delta vs reference staging: `+1.525 ms` (`+0.95%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `4.76837158203125e-06`
- note: numerically acceptable locally, but no meaningful runtime gain on the real target path

## Conclusion

This transpose2 P4 auto-unroll micro-tune does not produce a real improvement over the accepted transpose2 v1 baseline. Keep transpose2 v1 as the current best state and drop this P4 candidate.

## Logs

- transport log: `./session_bootstrap/logs/transpose2_p4_remote_payload_20260331_203415.log`
- payload log: `./session_bootstrap/logs/transpose2_p4_remote_payload_20260331_203415_payload.log`
