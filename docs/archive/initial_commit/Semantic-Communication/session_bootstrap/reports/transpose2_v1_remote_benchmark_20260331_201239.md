# Transpose2 V1 Remote Benchmark

- generated_at: `2026-03-31T20:12:39+08:00`
- stage: `v1 bias fusion`
- operator: `fused_conv2d_transpose2_add12`
- status: `accepted_baseline`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v1_20260331_200744/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256: `bae5c138c3c21fda694bd21db4bbd19144263ec3bab3d7de30ab3942551dd561`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `bae5c138c3c21fda694bd21db4bbd19144263ec3bab3d7de30ab3942551dd561`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.776`
- vm_init_ms: `0.456`
- run_median_ms: `161.416`
- run_mean_ms: `161.975`
- run_min_ms: `161.063`
- run_max_ms: `163.72`
- run_variance_ms2: `0.800006`

## Comparison

- reference staging median: `159.943 ms`
- transpose2 v1 delta vs reference staging: `+1.473 ms` (`+0.92%`)
- current best transpose1 state (P2+P4): `159.356 ms`
- transpose2 v1 delta vs current best transpose1 state: `+2.060 ms` (`+1.29%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `4.76837158203125e-06`
- note: not bitwise-equal locally, but within the existing tolerance gate and no meaningful remote regression

## Conclusion

This first transpose2 scheduled-form v1 bias-fusion candidate is acceptable as the new local/remote baseline for further transpose2 work. It does not deliver a large integrated win by itself, but it stays within the established acceptance band relative to the current best staging reference and is suitable for subsequent P2/P3-style iteration.

## Logs

- transport log: `./session_bootstrap/logs/transpose2_v1_remote_payload_20260331_201239.log`
- payload log: `./session_bootstrap/logs/transpose2_v1_remote_payload_20260331_201239_payload.log`
