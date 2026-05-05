# Conv2d3_Add15 v2 Remote Benchmark

- generated_at: `2026-04-02T12:47:24+08:00`
- operator: `fused_conv2d3_add15`
- stage: `v2 kernel repack on top of accepted v1`
- status: `regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_v2_20260402/fused_conv2d3_add15_post_db_swap.so`
- local sha256: `22ba6c819e034dec8122ec6e759b72a6c2b9101af552f2de5fd8d5c8d33c6f00`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d3_add15_v2/tvm_tune_logs/optimized_model.so`
- remote sha256: `22ba6c819e034dec8122ec6e759b72a6c2b9101af552f2de5fd8d5c8d33c6f00`
- local/remote sha match: `true`

## Structural Change

On top of the accepted `v1` bias-fused scheduled-form state, this candidate:

- adds a one-time `kernel_pack(6,7,7,2,3)` materialization
- rewrites the update path to read packed kernel values as:
  - `kernel_pack[v_rc // 2, v_ry, v_rx, v_rc % 2, v_ff]`
- keeps unchanged:
  - accepted bias-fused `conv2d_nchw_init` / `conv2d_nchw_update`
  - direct `lv347` reads in the scheduled compute path
  - outer parallel tile count `64`
  - output tile coverage `16 x 64`
  - reduction split `rc_0 x rc_1 = 6 x 2`
  - `pragma_auto_unroll_max_step = 256`

## Payload Result

- load_ms: `3.840`
- vm_init_ms: `0.468`
- run_median_ms: `161.999`
- run_mean_ms: `162.619`
- run_min_ms: `161.613`
- run_max_ms: `166.836`
- run_variance_ms2: `2.217162`
- run_count: `10`

## Comparison

- accepted `conv2d3_add15 v1` median: `161.000 ms`
- `conv2d3_add15 v2` delta vs accepted `v1`: `+0.999 ms` (`+0.62%`)
- reference staging median: `159.943 ms`
- `conv2d3_add15 v2` delta vs reference staging: `+2.056 ms` (`+1.29%`)
- accepted `transpose_add6 v1` median: `159.503 ms`
- `conv2d3_add15 v2` delta vs accepted `transpose_add6 v1`: `+2.496 ms` (`+1.57%`)
- current best `transpose1 P2+P4` median: `159.356 ms`
- `conv2d3_add15 v2` delta vs current best handwritten state: `+2.643 ms` (`+1.66%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `1.9073486328125e-05`
- note: the candidate is numerically acceptable locally, but it does not improve runtime on the real target path

## Conclusion

This `conv2d3_add15 v2` kernel-repack candidate is buildable, swappable, numerically acceptable, and remotely benchmarked, but it is still a **real regression** versus the accepted `v1` baseline on the Phytium Pi.

Decision:

- **drop `conv2d3_add15 v2` kernel-repack as a promotion candidate**
- keep accepted `conv2d3_add15 v1` as the stable baseline for this operator
- do not spend more iterations on this kernel-repack direction for this lane

## Benchmark Command

```bash
source ./session_bootstrap/tmp/conv2d3_add15_v2_remote_benchmark_20260402_124724.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/conv2d3_add15_v2_remote_payload_20260402_124724.log`
- payload log: `./session_bootstrap/logs/conv2d3_add15_v2_remote_payload_20260402_124724_payload.log`
