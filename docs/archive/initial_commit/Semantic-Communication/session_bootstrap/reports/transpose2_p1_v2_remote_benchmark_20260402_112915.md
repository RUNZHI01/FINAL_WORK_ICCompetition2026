# Transpose2 P1 v2 Remote Benchmark

- generated_at: `2026-04-02T11:29:15+08:00`
- stage: `P1-style dilate+pad fusion on top of accepted v1`
- operator: `fused_conv2d_transpose2_add12`
- status: `no_gain_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_p1_v2_20260402/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256: `6ce0647a3e6ad762474bd3d5ff29e831c1aa4f705eb3260d67673cc96052292d`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12/tvm_tune_logs/optimized_model.so`
- remote sha256: `6ce0647a3e6ad762474bd3d5ff29e831c1aa4f705eb3260d67673cc96052292d`
- local/remote sha match: `true`

## Structural Change

- accepted `transpose2 v1` baseline kept intact in its own path
- new `v2` candidate change:
  - remove separate materialized `data_dilate` `(255x255)` intermediate
  - remove separate `data_pad` producer block
  - replace both with one materialized `data_dilate_pad` `(258x258)` buffer that emits padded+dilated values directly from `lv332`
- unchanged:
  - accepted `v1` bias-fused compute path
  - materialized `kernel_transform`
  - scheduled h/w tiling
  - reduction split `dc_0 x dc_1 = 4 x 6`
  - outer `w_0` sweep `= 8`
  - `pragma_auto_unroll_max_step = 32`

## Payload Result

- load_ms: `3.905`
- vm_init_ms: `0.610`
- run_median_ms: `163.492`
- run_mean_ms: `163.874`
- run_min_ms: `162.615`
- run_max_ms: `166.991`
- run_variance_ms2: `1.444428`
- run_count: `10`

## Comparison

- accepted `transpose2 v1` median: `161.416 ms`
- `transpose2 p1 v2` delta vs accepted `v1`: `+2.076 ms` (`+1.29%`)
- reference staging median: `159.943 ms`
- `transpose2 p1 v2` delta vs reference staging: `+3.549 ms` (`+2.22%`)
- current best `transpose1` handwritten state (`P2+P4`): `159.356 ms`
- `transpose2 p1 v2` delta vs current best handwritten state: `+4.136 ms` (`+2.60%`)

## Correctness Context

- local correctness compare: `allclose(atol=1e-5, rtol=1e-5)=true`
- max_abs_diff: `4.76837158203125e-06`
- note: this candidate is numerically acceptable locally, but it loses runtime on the real target path

## Conclusion

This `transpose2` `P1`-style `v2` dilate+pad fusion candidate is buildable, swappable, and numerically acceptable, but it is a **real regression** on the Phytium Pi under the accepted payload benchmark protocol.

Decision:

- **drop `transpose2 v2` as a promotion candidate**
- **keep accepted `transpose2 v1` as the stable local/remote baseline**
- pivot further handwritten effort away from this structural fusion move and toward a more promising operator lane

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose2_p1_v2_remote_benchmark_20260402_112915.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose2_p1_v2_remote_payload_20260402_112915.log`
- payload log: `./session_bootstrap/logs/transpose2_p1_v2_remote_payload_20260402_112915_payload.log`
