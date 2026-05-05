# Transpose1 v5 Remote Benchmark

- generated_at: `2026-04-02T17:53:09+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v5 h_1/w_1 consumer-outer follow-up on top of v4`
- status: `remote_regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v5_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `e8ad20741e13b18cf4476cb4b7e798d379a0a6bec89a5c6c16bdda2b7805eb9f`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v5/tvm_tune_logs/optimized_model.so`
- remote sha256: `e8ad20741e13b18cf4476cb4b7e798d379a0a6bec89a5c6c16bdda2b7805eb9f`
- local/remote sha match: `true`

## Structural Change

On top of the winning transpose1 `v4` candidate, this `v5` follow-up:

- keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized
- keeps the `v4` stage-once `data_dilate` / `data_pad` tile hoist outside `c_1`
- changes only the compute consumer order from:
  - `c_1 -> h_1/w_1`
  to:
  - `h_1/w_1 -> c_1`
- intent: consume each staged spatial subtile across all three output-channel groups before advancing to the next subtile

## Local Correctness Context

- scheduled reference vs `v5`: `exact_equal = false`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- accepted `v1/P2/P4` vs `v5`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- leading `v4` vs `v5`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- interpretation: `v5` is artifact-distinct from the frozen scheduled reference, but functionally identical to the prior winning `v4` path under the current local proof checks

## Payload Result

- load_ms: `3.758`
- vm_init_ms: `0.473`
- run_median_ms: `158.972`
- run_mean_ms: `159.143`
- run_min_ms: `158.708`
- run_max_ms: `160.082`
- run_variance_ms2: `0.193041`
- run_count: `10`

## Comparison

- leading transpose1 `v4` median: `158.621 ms`
- `transpose1 v5` delta vs leading `v4`: `+0.351 ms` (`+0.22%`)
- older accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 v5` delta vs older accepted `P2+P4`: `-0.384 ms` (`-0.24%`)
- reference staging median: `159.943 ms`
- `transpose1 v5` delta vs reference staging: `-0.971 ms` (`-0.61%`)

## Conclusion

This `transpose1 v5` follow-up remains better than the old accepted `P2+P4` baseline, but it does **not** beat the current winning `v4` candidate.

Decision:

- **drop `transpose1 v5` as the leading candidate**
- keep `transpose1 v4` as the current best handwritten state for this operator
- do not continue the `h_1/w_1 -> c_1` consumer-order direction as the immediate next branch

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_v5_remote_benchmark_20260402_175309.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v5_remote_payload_20260402_175309.log`
- payload log: `./session_bootstrap/logs/transpose1_v5_remote_payload_20260402_175309_payload.log`
