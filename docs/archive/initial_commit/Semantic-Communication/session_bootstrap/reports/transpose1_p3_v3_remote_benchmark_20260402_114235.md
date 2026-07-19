# Transpose1 P3 v3 Remote Benchmark

- generated_at: `2026-04-02T11:42:35+08:00`
- stage: `P3 path A direct-stride-read on top of accepted P2+P4`
- operator: `fused_conv2d_transpose1_add9`
- status: `catastrophic_regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p3_v3_20260402/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `e80aa54fc3eb1eabf8e34696ab1f0c24c22a20bd362339d155e812d90bc79676`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v3/tvm_tune_logs/optimized_model.so`
- remote sha256: `e80aa54fc3eb1eabf8e34696ab1f0c24c22a20bd362339d155e812d90bc79676`
- local/remote sha match: `true`

## Structural Change

- accepted transpose1 `P2+P4` baseline kept intact in `v1`
- new `v3` candidate change:
  - remove materialized `data_dilate`
  - remove materialized `data_pad`
  - read `lv318` directly from `compute_update` through stride/parity guards
- unchanged:
  - materialized `kernel_transform`
  - bias-fused compute path
  - accepted output-channel tiling `c_1 x c_3 = 3 x 8`
  - accepted `pragma_auto_unroll_max_step = 64`
  - scheduled h/w tiling, reduction split, and 4-lane vectorized inner loops

## Payload Result

- load_ms: `3.926`
- vm_init_ms: `0.457`
- run_median_ms: `376.035`
- run_mean_ms: `376.386`
- run_min_ms: `375.279`
- run_max_ms: `377.531`
- run_variance_ms2: `0.739178`
- run_count: `10`

## Comparison

- accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 p3 v3` delta vs accepted `P2+P4`: `+216.679 ms` (`+135.97%`)
- reference staging median: `159.943 ms`
- `transpose1 p3 v3` delta vs reference staging: `+216.092 ms` (`+135.10%`)
- accepted transpose_add6 `v1` median: `159.503 ms`
- `transpose1 p3 v3` delta vs accepted transpose_add6 `v1`: `+216.532 ms` (`+135.75%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `8.58306884765625e-06`
- note: this candidate is numerically acceptable locally, but it destroys runtime on the real target path

## Interpretation

The schedule-preserving seam stayed mechanically valid, but this direct-guarded-read rewrite is not performance-compatible with the accepted A72-friendly scheduled form. The most likely explanation is that the direct conditional indexing path defeats the locality/vectorization assumptions that made the accepted `P2+P4` lane fast, even though the candidate remains buildable and numerically acceptable.

## Conclusion

This `transpose1` `P3 path A` `v3` candidate is a **clear real-hardware regression** and should be dropped immediately.

Decision:

- **drop `transpose1 v3` as a promotion candidate**
- **keep accepted `transpose1 P2+P4` as the current best handwritten state**
- do **not** pursue further direct-guarded-read variants on this scheduled form without a fundamentally different loop structure / schedule strategy

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_p3_v3_remote_benchmark_20260402_114235.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_p3_v3_remote_payload_20260402_114235.log`
- payload log: `./session_bootstrap/logs/transpose1_p3_v3_remote_payload_20260402_114235_payload.log`
