# Transpose1 P0 v1 Remote Benchmark

- generated_at: `2026-03-31T18:58:04+08:00`
- stage: `P0`
- operator: `fused_conv2d_transpose1_add9`
- candidate: `scheduled-form v1 bias fusion`
- status: `completed`

## Local Build

```bash
/home/tianxing/.venvs/tvm-ms/bin/python ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p0
```

- artifact path: `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_p0/fused_conv2d_transpose1_add9_post_db_swap.so`
- artifact sha256: `4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`
- artifact size bytes: `1678648`
- swap_succeeded: `true`
- build_status: `built`
- export_status: `exported`

## Remote Staging + Payload Benchmark

- remote archive: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9`
- remote artifact path: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9/tvm_tune_logs/optimized_model.so`
- remote sha256: `4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`
- local/remote sha match: `true`
- runner: `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`
- warmup runs: `2`
- repeat: `10`

## Payload Result

- load_ms: `49.663`
- vm_init_ms: `5.53`
- run_median_ms: `162.954`
- run_mean_ms: `163.323`
- run_min_ms: `162.408`
- run_max_ms: `166.19`
- run_variance_ms2: `1.14544`
- output_shape: `[1, 3, 256, 256]`
- output_dtype: `float32`

## Comparison Against Staging Reference

- reference artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- reference payload median: `159.943 ms`
- current v1 delta vs reference: `+3.011 ms` (`+1.88%`)

## Conclusion

P0 passes the plan gate: v1 is within the documented `±5%` acceptance band relative to the `159.943 ms` staging reference, so the bias-fusion edit is acceptable and execution can proceed to `P3`.

## Logs

- transport log: `./session_bootstrap/logs/transpose1_v1_remote_payload_20260331_185804.log`
- payload log: `./session_bootstrap/logs/transpose1_v1_remote_payload_20260331_185804_payload.log`
