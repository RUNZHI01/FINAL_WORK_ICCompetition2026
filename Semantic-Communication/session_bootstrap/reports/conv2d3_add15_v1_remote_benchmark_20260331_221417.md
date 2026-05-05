# Conv2d3_Add15 V1 Remote Benchmark

- generated_at: `2026-03-31T22:14:17+08:00`
- stage: `v1 bias fusion`
- operator: `fused_conv2d3_add15`
- status: `accepted_baseline`

## Artifact

- local artifact: `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_v1_20260331_220515/fused_conv2d3_add15_post_db_swap.so`
- local sha256: `1cd1cec28900c24442a49e79139206d964eb21d9188c08cafdf56d9624fb1552`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `1cd1cec28900c24442a49e79139206d964eb21d9188c08cafdf56d9624fb1552`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.871`
- vm_init_ms: `0.456`
- run_median_ms: `161.000`
- run_mean_ms: `161.201`
- run_min_ms: `160.717`
- run_max_ms: `162.845`
- run_variance_ms2: `0.381139`

## Comparison

- reference staging median: `159.943 ms`
- conv2d3_add15 v1 delta vs reference staging: `+1.057 ms` (`+0.66%`)
- accepted transpose_add6 v1 median: `159.503 ms`
- conv2d3_add15 v1 delta vs transpose_add6 v1: `+1.497 ms` (`+0.94%`)
- current best transpose1 state (P2+P4): `159.356 ms`
- conv2d3_add15 v1 delta vs transpose1 best: `+1.644 ms` (`+1.03%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.9073486328125e-05`
- note: not bitwise-equal locally, but within the established tolerance gate and acceptable as a first local/remote baseline for further conv2d3_add15 iteration

## Conclusion

This first conv2d3_add15 scheduled-form v1 bias-fusion candidate is acceptable as the local/remote baseline for follow-up conv2d3_add15 tuning. It does not beat the best accepted handwritten deconv baselines, but it stays within the established acceptance band relative to the best staging reference and is suitable for subsequent P2/P4 exploration.

## Logs

- transport log: `./session_bootstrap/logs/conv2d3_add15_v1_remote_payload_20260331_221417.log`
- payload log: `./session_bootstrap/logs/conv2d3_add15_v1_remote_payload_20260331_221417_payload.log`
