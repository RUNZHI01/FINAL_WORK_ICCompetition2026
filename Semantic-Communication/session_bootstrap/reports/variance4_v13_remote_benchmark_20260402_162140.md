# Variance4 v13 Remote Benchmark

- generated_at: `2026-04-02T16:21:40+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v13 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_no_gain`

## Artifact

- local artifact: `./session_bootstrap/tmp/variance4_post_db_swap_local_build_evaldiag_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- remote artifact: `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- local/remote sha match: `true`

## What this run proves

This run proves that the variance4 handwritten lane is **not architecture-blocked from remote evaluation**. The current post-db swap path exports a full `VMExecutable` artifact that can be staged exactly like the accepted transpose handwritten artifacts and exercised by the existing remote payload wrapper.

That is the main result of this run.

## Payload Result

- load_ms: `3.924`
- vm_init_ms: `0.463`
- run_median_ms: `161.156`
- run_mean_ms: `161.522`
- run_min_ms: `160.463`
- run_max_ms: `164.310`
- run_variance_ms2: `1.117365`
- run_count: `10`

## Comparison

- reference staging median: `159.943 ms`
- `variance4 v13` delta vs reference staging: `+1.213 ms` (`+0.76%`)
- accepted transpose1 `P2+P4` median: `159.356 ms`
- `variance4 v13` delta vs transpose1 current best handwritten state: `+1.800 ms` (`+1.13%`)
- accepted transpose_add6 `v1` median: `159.503 ms`
- `variance4 v13` delta vs transpose_add6 `v1`: `+1.653 ms` (`+1.04%`)

## Interpretation

This was intentionally a **path-validation run** first, not a promotion-grade speedup claim for `v13` itself.

Why:

- the local diagnostics already showed `v12` and `v13` export the same artifact
- so a remote delta from `v13` was never expected to demonstrate a new speedup by itself
- the important unanswered question was whether variance4 could be evaluated through the same full-artifact remote path as the transpose lanes

That question is now answered: **yes**.

## Conclusion

- **keep** the conclusion that the variance4 handwritten lane is remotely benchmarkable under the current architecture
- **do not** treat `v13` as a speedup candidate based on this run
- **do not** spend more time on `v14`-style syntax cleanup unless a future variance4 edit changes the exported artifact SHA or a new exact-preserving equivalence class is found
- if variance4 work continues, the next useful step should be a genuinely different edit that changes the exported full-module artifact, not another artifact-identical cleanup

## Benchmark Command

```bash
source ./session_bootstrap/tmp/variance4_v13_remote_benchmark_20260402_162140.env
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- transport log: `./session_bootstrap/logs/variance4_v13_remote_payload_20260402_162140.log`
- payload log: `./session_bootstrap/logs/variance4_v13_remote_payload_20260402_162140_payload.log`
