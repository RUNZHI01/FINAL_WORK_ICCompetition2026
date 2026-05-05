# Why The 2026-03-13 Trusted Current Is Faster

## Conclusion

- previous trusted payload benchmark:
  - report: `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md`
  - current median: `153.778 ms`
  - artifact SHA256: `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- new trusted payload benchmark:
  - report: `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002.md`
  - current median: `131.343 ms`
  - artifact SHA256: `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
- net change vs the previous trusted current:
  - `22.435 ms` lower median
  - `14.59%` faster

## Causal Chain

1. **Hotspot extraction on the previous trusted current**
   - `session_bootstrap/reports/profiling_trusted_current_20260312_153906.md`
   - `session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.md`
   - Result:
     - the trusted current SHA was still `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`;
     - `legalized_fused_tir` remained the recommended tuning stage;
     - the top 8 tasks covered `80.247%` of tuned-stage weight, led by `reshape2`, `fused_variance1_add3_tir_sqrt1`, `reshape1`, `fused_mean1_subtract1_divide1_multiply1_add4`, `fused_conv2d1_add2`, `fused_conv2d2_add2`, `mirror_pad1`, and `fused_mean1_subtract1_divide1_multiply1_add4_relu`.

2. **Warm-start continuation from the `resume_from_1549` DB**
   - `session_bootstrap/tmp/rpc_tune_split_stageA_topup15_20260312_200613.env`
   - This env:
     - sources `session_bootstrap/tmp/rpc_tune_resume_from_1549_20260312_1738.env`;
     - points `TUNE_EXISTING_DB` to `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_resume_from_1549_20260312_1738/tuning_logs`;
     - sets `TUNE_TOTAL_TRIALS=15`.
   - The corresponding topup logs confirm the warm-start copy from that DB before tuning:
     - `session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_split_topup15_20260312_2000.log`
     - `session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_split_stageA_topup15_20260312_200657.log`

3. **`split_stageA_topup15` / `split_topup15` produced the new current artifact**
   - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_split_stageA_topup15_20260312_200657/tune_report.json`
   - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_split_topup15_20260312_2000/tune_report.json`
   - Both tune reports keep the same:
     - ONNX path: `/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx`
     - target: `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}`
     - input shape: `1,32,32,32`
     - runner: `rpc`
     - tuning stage: `legalized_fused_tir`
     - configured topup budget: `15` trials
   - Both corresponding logs end with a successful compile of `optimized_model.so`.
   - The two emitted local `.so` files hash to the same new SHA256:
     - `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
   - Operationally, that means the stage-A wrapper and the direct split topup converged to one promoted artifact, not two competing candidates.

4. **Formal payload validation promoted the new SHA**
   - `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002.md`
   - Result:
     - `current_artifact_path=/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
     - `current_artifact_sha256=65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
     - `current_artifact_sha256_match=True`
     - `current_run_median_ms=131.343`

## Why The Speedup Is Attributable To The New Artifact

The old trusted rerun and the new validation kept the current benchmark path fixed:

| Item | Previous trusted current | New trusted current |
|---|---|---|
| Benchmark report | `inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md` | `inference_compare_currentsafe_split_topup15_validate_20260313_0002.md` |
| target | `{kind:llvm,mtriple:aarch64-linux-gnu,mcpu:cortex-a72,mattr:[+neon],num-cores:4}` | same |
| current command | `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current` | same |
| remote current artifact path | `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so` | same |
| shape buckets | `1x3x224x224,1x3x256x256` | same |
| threads / repeat / warmup | `4 / 10 / 2` | same |
| remote runtime env snapshot | `session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.env` | `session_bootstrap/tmp/inference_compare_currentsafe_split_topup15_validate_20260313_0002.env` |

The paired env snapshots also keep the same runtime path:

- same `REMOTE_TVM_PYTHON`
- same `REMOTE_CURRENT_ARTIFACT`
- same `INFERENCE_CURRENT_CMD`
- same archive root `/home/user/Downloads/jscc-test/jscc`
- only the trusted current SHA guard changes:
  - old: `INFERENCE_CURRENT_EXPECTED_SHA256=1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
  - new: `INFERENCE_CURRENT_EXPECTED_SHA256=65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`

Because the target, safe-runtime command path, remote archive path, benchmark script, and benchmark parameters stayed the same, the `153.778 ms -> 131.343 ms` change is attributable to the new MetaSchedule search result and promoted artifact, not to benchmark path drift.

## Validation Numbers

| Metric | Previous trusted current | New trusted current |
|---|---:|---:|
| artifact SHA256 | `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644` | `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377` |
| current median | `153.778 ms` | `131.343 ms` |
| delta vs previous current | baseline | `-22.435 ms` |
| speedup vs previous current | baseline | `14.59%` |
| improvement vs baseline in that run | `91.66%` | `92.91%` |

## Note

The baseline rerun moved slightly between the two formal benchmark dates (`1844.1 ms` vs `1853.7 ms`), but that does not change the central attribution here. The current-side target, runtime path, and benchmark path were held constant while the artifact SHA changed from `1946...` to `65747...`, so the faster median is explained by the new trusted current artifact.
