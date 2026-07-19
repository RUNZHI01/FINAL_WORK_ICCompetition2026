# Transpose1 v4 Remote Benchmark

- generated_at: `2026-04-02T17:28:12+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v4 data-staging hoist outside c_1`
- status: `remote_gain_candidate`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v4_20260402_first_locality_candidate/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `42b17ee6b458f1440fd6cd40f70ea88ace4d9b547f5960854c911ab1f94a4f95`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v4/tvm_tune_logs/optimized_model.so`
- remote sha256: `42b17ee6b458f1440fd6cd40f70ea88ace4d9b547f5960854c911ab1f94a4f95`
- local/remote sha match: `true`

## Structural Change

On top of the accepted transpose1 `P2+P4` state, this `v4` candidate:

- keeps `data_dilate` materialized
- keeps `data_pad` materialized
- keeps `kernel_transform` materialized
- keeps the accepted bias-fused `compute_init` / `compute_update` path
- keeps the accepted output-channel tiling `c_1 x c_3 = 3 x 8`
- keeps the accepted `pragma_auto_unroll_max_step = 64`
- changes only the staging placement of the spatial data tile:
  - hoist the `data_dilate` / `data_pad` tile fill outside the `c_1` loop
  - stage each spatial tile once
  - reuse that staged tile across all three output-channel groups

## Local Correctness Context

- `exact_equal = true`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 0.0`
- `nonzero_diff_count = 0`

## Payload Result

- load_ms: `3.797`
- vm_init_ms: `0.476`
- run_median_ms: `158.621`
- run_mean_ms: `158.849`
- run_min_ms: `157.973`
- run_max_ms: `160.339`
- run_variance_ms2: `0.432389`
- run_count: `10`

## Comparison

- accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 v4` delta vs accepted `P2+P4`: `-0.735 ms` (`-0.46%`)
- reference staging median: `159.943 ms`
- `transpose1 v4` delta vs reference staging: `-1.322 ms` (`-0.83%`)
- accepted transpose_add6 `v1` median: `159.503 ms`
- `transpose1 v4` delta vs accepted transpose_add6 `v1`: `-0.882 ms` (`-0.55%`)

## Interpretation

This `transpose1 v4` candidate is the first post-variance4 / post-transpose2 reprioritization branch to produce a fresh **board-side improvement**.

The result is modest but real:

- it preserves exact local correctness
- it changes the exported full-module artifact
- it outperforms the accepted transpose1 `P2+P4` baseline on the Phytium Pi

That makes the staging-placement idea worth keeping and iterating from.

## Conclusion

- **promote `transpose1 v4` as the new leading transpose1 handwritten candidate**
- keep the accepted older `P2+P4` state for reference, but treat `v4` as the next baseline for follow-up work
- next follow-up should stay in the same family: preserve exactness and test whether more staging reuse / loop-placement cleanup can compound this gain without reopening previously dropped branches

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_v4_remote_benchmark_20260402_172812.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v4_remote_payload_20260402_172812.log`
- payload log: `./session_bootstrap/logs/transpose1_v4_remote_payload_20260402_172812_payload.log`
