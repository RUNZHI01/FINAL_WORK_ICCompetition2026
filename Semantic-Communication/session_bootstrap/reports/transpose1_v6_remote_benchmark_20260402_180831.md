# Transpose1 v6 Remote Benchmark

- generated_at: `2026-04-02T18:08:31+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v6 h_1-stripe staging follow-up on top of v4`
- status: `remote_gain_candidate`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v6_20260402_h1_stripe/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `9371c8d3287d24ffc02a3db0c63d56dcebc14329722350f59324dfe49361bb42`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v6/tvm_tune_logs/optimized_model.so`
- remote sha256: `9371c8d3287d24ffc02a3db0c63d56dcebc14329722350f59324dfe49361bb42`
- local/remote sha match: `true`

## Structural Change

On top of the winning transpose1 `v4` candidate, this `v6` follow-up:

- keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized
- keeps the successful `v4` strategy of reusing staged data across all three `c_1` groups
- narrows the staged data region from the full `66 x 10` tile to the `34 x 10` stripe needed by one `h_1` region at a time
- keeps consumer order `h_1 -> c_1 -> w_1`, so each staged stripe is reused across all three `c_1` groups and both `w_1` positions before moving on

## Local Correctness Context

- scheduled reference vs `v6`: `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- leading `v4` vs `v6`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- accepted `v1/P2/P4` vs `v6`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- interpretation: `v6` is artifact-distinct from the frozen scheduled reference, but functionally identical to the prior winning `v4` path under the current local proof checks

## Payload Result

- load_ms: `3.733`
- vm_init_ms: `0.467`
- run_median_ms: `158.421`
- run_mean_ms: `158.450`
- run_min_ms: `157.991`
- run_max_ms: `159.238`
- run_variance_ms2: `0.117301`
- run_count: `10`

## Comparison

- leading transpose1 `v4` median: `158.621 ms`
- `transpose1 v6` delta vs leading `v4`: `-0.200 ms` (`-0.13%`)
- older accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 v6` delta vs older accepted `P2+P4`: `-0.935 ms` (`-0.59%`)
- reference staging median: `159.943 ms`
- `transpose1 v6` delta vs reference staging: `-1.522 ms` (`-0.95%`)

## Conclusion

This `transpose1 v6` stripe-staging follow-up remains in the same winning family as `v4` and produces a further, modest board-side improvement.

Decision:

- **promote `transpose1 v6` as the new leading transpose1 handwritten candidate**
- keep `v4` and older accepted baselines for reference, but treat `v6` as the new target to beat
- further follow-up work should continue in the same staging/reuse family, while being careful not to reopen the already-losing `v5` consumer-order branch or earlier P1/P3 families

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_v6_remote_benchmark_20260402_180831.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v6_remote_payload_20260402_180831.log`
- payload log: `./session_bootstrap/logs/transpose1_v6_remote_payload_20260402_180831_payload.log`
