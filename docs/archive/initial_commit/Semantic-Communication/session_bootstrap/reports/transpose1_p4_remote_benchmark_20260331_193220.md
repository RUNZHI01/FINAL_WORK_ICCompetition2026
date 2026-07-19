# Transpose1 P4 Remote Benchmark

- generated_at: `2026-03-31T19:32:20+08:00`
- stage: `P4`
- operator: `fused_conv2d_transpose1_add9`
- status: `accepted`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p4/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `e165fb0316981ef408ffe53c07c8aefe02e9937203877ca679cf29ff6c86ce1d`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `e165fb0316981ef408ffe53c07c8aefe02e9937203877ca679cf29ff6c86ce1d`
- local/remote sha match: `true`

## Micro-Change

- accepted P2 state kept intact: output-channel tiling `c_1 x c_3 = 3 x 8`
- P4 change: `pragma_auto_unroll_max_step` raised from `32` to `64`
- unchanged: outer parallel tile count `32`, `h_2 x h_3 = 16 x 2`, `dc_0 x dc_1 = 12 x 4`, 4-lane vectorized inner loops, bias-fused compute path

## Payload Result

- load_ms: `3.739`
- vm_init_ms: `0.487`
- run_median_ms: `159.356`
- run_mean_ms: `159.776`
- run_min_ms: `158.964`
- run_max_ms: `162.525`
- run_variance_ms2: `1.118145`

## Comparison

- accepted P2 median: `159.977 ms`
- P4 delta vs P2: `-0.621 ms` (`-0.39%`)
- accepted P0/v1 median: `162.954 ms`
- P4 delta vs P0/v1: `-3.598 ms` (`-2.21%`)
- reference staging median: `159.943 ms`
- P4 delta vs reference staging: `-0.587 ms` (`-0.37%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `7.62939453125e-06`
- note: not bitwise-equal locally, but within the same tolerance gate used for P2 and slightly faster on the real target path

## Conclusion

P4 is a small but real improvement on top of the accepted P2 state and should be kept. This makes the current best handwritten scheduled-form candidate the `P2 + P4` state.

## Logs

- transport log: `./session_bootstrap/logs/transpose1_p4_remote_payload_20260331_193220.log`
- payload log: `./session_bootstrap/logs/transpose1_p4_remote_payload_20260331_193220_payload.log`
