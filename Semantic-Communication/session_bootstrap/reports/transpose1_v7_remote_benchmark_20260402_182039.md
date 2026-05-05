# Transpose1 v7 Remote Benchmark

- generated_at: `2026-04-02T18:20:39+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v7 dc_0-slice stripe staging follow-up on top of v6`
- status: `remote_gain_candidate`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v7_20260402_dc0_slice/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `6ebc1377fbbc9cab36a81d586acb2f2b4a8b9e7cce01d1241022835245718131`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v7/tvm_tune_logs/optimized_model.so`
- remote sha256: `6ebc1377fbbc9cab36a81d586acb2f2b4a8b9e7cce01d1241022835245718131`
- local/remote sha match: `true`

## Structural Change

On top of the winning transpose1 `v6` candidate, this `v7` follow-up:

- keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized
- keeps the winning `h_1` stripe-staging family
- further narrows the staged input slice so only one `dc_0` chunk (`4` input channels) of the `34 x 10` stripe is prepared at a time
- immediately reuses that staged `dc_0` slice across all three `c_1` groups and both `w_1` positions before advancing

## Local Correctness Context

- scheduled reference vs `v7`: `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- leading `v6` vs `v7`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- accepted `v1/P2/P4` vs `v7`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- interpretation: `v7` is artifact-distinct from the frozen scheduled reference, but functionally identical to the prior winning `v6` path under the current local proof checks

## Payload Result

- load_ms: `3.742`
- vm_init_ms: `0.487`
- run_median_ms: `156.785`
- run_mean_ms: `156.812`
- run_min_ms: `156.107`
- run_max_ms: `157.962`
- run_variance_ms2: `0.267525`
- run_count: `10`

## Comparison

- leading transpose1 `v6` median: `158.421 ms`
- `transpose1 v7` delta vs leading `v6`: `-1.636 ms` (`-1.03%`)
- transpose1 `v4` median: `158.621 ms`
- `transpose1 v7` delta vs `v4`: `-1.836 ms` (`-1.16%`)
- older accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 v7` delta vs older accepted `P2+P4`: `-2.571 ms` (`-1.61%`)
- reference staging median: `159.943 ms`
- `transpose1 v7` delta vs reference staging: `-3.158 ms` (`-1.97%`)

## Conclusion

This `transpose1 v7` follow-up stays in the same winning staging/reuse family and produces a clearly stronger board-side improvement than both `v6` and `v4`.

Decision:

- **promote `transpose1 v7` as the new leading transpose1 handwritten candidate**
- keep `v6`, `v4`, and older baselines for reference, but treat `v7` as the new target to beat
- further follow-up work should continue in the same staging/reuse family, while being careful not to reopen the already-losing `v5` consumer-order branch or earlier P1/P3 families

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_v7_remote_benchmark_20260402_182039.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v7_remote_payload_20260402_182039.log`
- payload log: `./session_bootstrap/logs/transpose1_v7_remote_payload_20260402_182039_payload.log`
