# Transpose1 P1 v2 Remote Benchmark

- generated_at: `2026-04-02T01:58:30+08:00`
- stage: `P1-style dilate+pad fusion on top of accepted P2+P4`
- operator: `fused_conv2d_transpose1_add9`
- status: `no_gain_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p1_v2_20260402_rerun/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `2349df5dc2270385efd842516e6c3bdf55dd28bf9e0a3ac34febffe0aee878ca`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `2349df5dc2270385efd842516e6c3bdf55dd28bf9e0a3ac34febffe0aee878ca`
- local/remote sha match: `true`

## Structural Change

- accepted P2+P4 baseline kept intact in its own `v1` path
- new `v2` candidate change:
  - remove separate materialized `data_dilate` `(127x127)` intermediate
  - remove separate `data_pad` producer block
  - replace both with one materialized `data_dilate_pad` `(130x130)` buffer that emits padded+dilated values directly from `lv318`
- unchanged:
  - accepted P2 output-channel tiling `c_1 x c_3 = 3 x 8`
  - accepted P4 `pragma_auto_unroll_max_step = 64`
  - bias-fused compute path
  - materialized `kernel_transform`
  - scheduled h/w tiling, reduction split, and 4-lane vectorized inner loops

## Payload Result

- load_ms: `3.832`
- vm_init_ms: `0.458`
- run_median_ms: `160.114`
- run_mean_ms: `160.167`
- run_min_ms: `159.793`
- run_max_ms: `160.514`
- run_variance_ms2: `0.051281`
- run_count: `10`

## Comparison

- accepted P2+P4 median: `159.356 ms`
- P1 v2 delta vs accepted P2+P4: `+0.758 ms` (`+0.48%`)
- accepted P2 median: `159.977 ms`
- P1 v2 delta vs accepted P2: `+0.137 ms` (`+0.09%`)
- reference staging median: `159.943 ms`
- P1 v2 delta vs reference staging: `+0.171 ms` (`+0.11%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `7.62939453125e-06`
- note: this candidate is numerically acceptable locally, but it does not beat the accepted P2+P4 runtime on the real target path

## Conclusion

This `transpose1` P1-style `v2` dilate+pad fusion candidate is a valid buildable and numerically acceptable handwritten lane, but it does **not** improve runtime on the Phytium Pi under the accepted payload benchmark protocol.

Decision:

- **drop `v2` as a promotion candidate**
- **keep accepted `transpose1 P2+P4` as the current best handwritten state**
- restore the handwritten staging archive back to the accepted P4 artifact after recording this result

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_p1_v2_remote_benchmark_20260402_0158.env
export INFERENCE_WARMUP_RUNS=2
export INFERENCE_REPEAT=10
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```
