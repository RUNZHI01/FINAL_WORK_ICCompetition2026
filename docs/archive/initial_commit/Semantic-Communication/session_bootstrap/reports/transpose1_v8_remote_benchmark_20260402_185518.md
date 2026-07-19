# Transpose1 v8 Remote Benchmark

- generated_at: `2026-04-02T18:55:18+08:00`
- operator: `fused_conv2d_transpose1_add9`
- stage: `v8 single-channel slice follow-up on top of v7`
- status: `remote_regression_drop`

## Artifact

- local artifact: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v8_20260402_single_channel_slice/fused_conv2d_transpose1_add9_post_db_swap.so`
- local sha256: `2968e548b40d1cc0942daa87947afc13962134a7d66bfab63042390ab9f4b3a5`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9_v8/tvm_tune_logs/optimized_model.so`
- remote sha256: `2968e548b40d1cc0942daa87947afc13962134a7d66bfab63042390ab9f4b3a5`
- local/remote sha match: `true`

## Structural Change

On top of the winning transpose1 `v7` candidate, this `v8` follow-up:

- keeps materialized `data_dilate`, `data_pad`, and `kernel_transform`
- keeps the winning `h_1` stripe-staging family
- keeps the `dc_0`-slice idea from `v7`, but narrows the staged reduction slice further from one `4`-channel `dc_0` slice to one input channel at a time
- keeps the same broad reuse/locality family while further shrinking the live staged reduction-channel footprint

## Local Correctness Context

- scheduled reference vs `v8`: `exact_equal = false`, `allclose(atol=1e-5, rtol=1e-5) = true`, `max_abs_diff = 7.62939453125e-06`, `nonzero_diff_count = 309445`
- leading `v7` vs `v8`: `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- interpretation: `v8` is artifact-distinct from the frozen scheduled reference, but functionally identical to `v7` under the local proof checks

## Payload Result

- load_ms: `3.874`
- vm_init_ms: `0.460`
- run_median_ms: `174.005`
- run_mean_ms: `175.876`
- run_min_ms: `173.606`
- run_max_ms: `184.793`
- run_variance_ms2: `14.137438`
- run_count: `10`

## Comparison

- leading transpose1 `v7` median: `156.785 ms`
- `transpose1 v8` delta vs leading `v7`: `+17.220 ms` (`+10.98%`)
- transpose1 `v6` median: `158.421 ms`
- `transpose1 v8` delta vs `v6`: `+15.584 ms` (`+9.84%`)
- transpose1 `v4` median: `158.621 ms`
- `transpose1 v8` delta vs `v4`: `+15.384 ms` (`+9.70%`)
- older accepted transpose1 `P2+P4` median: `159.356 ms`
- `transpose1 v8` delta vs older accepted `P2+P4`: `+14.649 ms` (`+9.19%`)
- reference staging median: `159.943 ms`
- `transpose1 v8` delta vs reference staging: `+14.062 ms` (`+8.79%`)

## Conclusion

This `transpose1 v8` single-channel slice follow-up is a **clear regression** on the Phytium Pi.

Decision:

- **drop `transpose1 v8` as a promotion candidate**
- keep `transpose1 v7` as the leading handwritten candidate for this operator
- do not continue the over-narrow single-channel slice direction as the immediate next branch

## Benchmark Command

```bash
source ./session_bootstrap/tmp/transpose1_v8_remote_benchmark_20260402_185518.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v8_remote_payload_20260402_185518.log`
- payload log: `./session_bootstrap/logs/transpose1_v8_remote_payload_20260402_185518_payload.log`
