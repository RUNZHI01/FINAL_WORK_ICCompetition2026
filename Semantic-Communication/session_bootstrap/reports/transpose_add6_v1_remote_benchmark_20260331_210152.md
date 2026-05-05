# Transpose_Add6 V1 Remote Benchmark

- generated_at: `2026-03-31T21:01:52+08:00`
- stage: `v1 bias fusion`
- operator: `fused_conv2d_transpose_add6`
- status: `accepted`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v1_20260331_205230/fused_conv2d_transpose_add6_post_db_swap.so`
- local sha256: `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.731`
- vm_init_ms: `0.461`
- run_median_ms: `159.503`
- run_mean_ms: `159.56`
- run_min_ms: `159.303`
- run_max_ms: `160.072`
- run_variance_ms2: `0.056066`

## Comparison

- reference staging median: `159.943 ms`
- transpose_add6 v1 delta vs reference staging: `-0.440 ms` (`-0.28%`)
- accepted transpose2 v1 median: `161.416 ms`
- transpose_add6 v1 delta vs transpose2 v1: `-1.913 ms` (`-1.19%`)
- current best transpose1 state (P2+P4): `159.356 ms`
- transpose_add6 v1 delta vs transpose1 best: `+0.147 ms` (`+0.09%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.33514404296875e-05`
- note: not bitwise-equal locally, but within the same tolerance gate used for other accepted handwritten candidates and competitive on the real target path

## Conclusion

This first transpose_add6 scheduled-form v1 bias-fusion candidate is accepted. It slightly outperforms the best staging reference and becomes the current accepted baseline for any follow-up transpose_add6 P2/P4 exploration.

## Logs

- transport log: `./session_bootstrap/logs/transpose_add6_v1_remote_payload_20260331_210152.log`
- payload log: `./session_bootstrap/logs/transpose_add6_v1_remote_payload_20260331_210152_payload.log`
