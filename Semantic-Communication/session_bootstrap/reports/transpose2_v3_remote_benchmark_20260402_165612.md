# Transpose2 v3 Remote Benchmark

- generated_at: `2026-04-02T16:56:12+08:00`
- operator: `fused_conv2d_transpose2_add12`
- stage: `v3 kernel_transform output-channel-inner pack`
- status: `remote_regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3_kernel_pack_20260402_1644/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256: `25cdc5a8e402f6859f4e2418f5fe45d3b25f72a54e12bf96a77deb1dc2551fd9`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v3/tvm_tune_logs/optimized_model.so`
- remote sha256: `25cdc5a8e402f6859f4e2418f5fe45d3b25f72a54e12bf96a77deb1dc2551fd9`
- local/remote sha match: `true`

## Structural Change

On top of the accepted transpose2 `v1` baseline, this `v3` candidate:

- keeps `data_dilate` materialized
- keeps `data_pad` materialized
- keeps the accepted bias-fused `compute_init` / `compute_update` path
- keeps the accepted scheduled h/w tiling, reduction split `dc_0 x dc_1 = 4 x 6`, outer `w_0` sweep `= 8`, and `pragma_auto_unroll_max_step = 32`
- changes only the materialized `kernel_transform` layout:
  - from `[output_channel, input_channel, kh, kw]`
  - to `[input_channel, kh, kw, output_channel]`
- updates `compute_update` to read `kernel_transform[v_dc, v_dh, v_dw, v_c]`

Intended effect:

- keep the inner `c_3` output-channel walk on contiguous packed weights
- avoid reopening the already-regressed `v2` `data_dilate + data_pad -> data_dilate_pad` fusion branch

## Local Correctness Context

- `exact_equal = false`
- `allclose_atol1e-5_rtol1e-5 = true`
- `max_abs_diff = 4.76837158203125e-06`
- `mean_abs_diff = 2.3944838289935433e-07`
- `nonzero_diff_count = 607527`

## Payload Result

- load_ms: `3.760`
- vm_init_ms: `0.448`
- run_median_ms: `162.729`
- run_mean_ms: `163.065`
- run_min_ms: `162.373`
- run_max_ms: `165.313`
- run_variance_ms2: `0.692887`
- run_count: `10`

## Comparison

- accepted transpose2 `v1` median: `161.416 ms`
- `transpose2 v3` delta vs accepted `v1`: `+1.313 ms` (`+0.81%`)
- reference staging median: `159.943 ms`
- `transpose2 v3` delta vs reference staging: `+2.786 ms` (`+1.74%`)
- accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose2 v3` delta vs current best handwritten state: `+3.373 ms` (`+2.12%`)

## Conclusion

This `transpose2 v3` kernel-transform repack candidate is:

- buildable
- swappable
- numerically acceptable under the current local `allclose(1e-5)` gate
- remotely benchmarkable under the existing payload path

But it is still a **real regression** on the Phytium Pi.

Decision:

- **drop `transpose2 v3` kernel-pack as a promotion candidate**
- keep accepted `transpose2 v1` as the stable baseline for this operator
- do not spend more time on this particular output-channel-inner kernel-pack layout

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose2_v3_remote_benchmark_20260402_165612.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose2_v3_remote_payload_20260402_165612.log`
- payload log: `./session_bootstrap/logs/transpose2_v3_remote_payload_20260402_165612_payload.log`
