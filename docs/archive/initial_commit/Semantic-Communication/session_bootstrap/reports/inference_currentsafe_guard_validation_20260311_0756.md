# Current-safe artifact guard validation (2026-03-11 07:56 +08:00)

## Scope

Validate that the newly added current-safe artifact SHA guard is active during real remote inference execution on the Phytium Pi.

## Command

```bash
set -a
source ./session_bootstrap/tmp/inference_compare_baseline_vs_currentsafe_final_20260311_024434.env
set +a
export INFERENCE_CURRENT_EXPECTED_SHA256=d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Result

- status: success
- variant: `current`
- archive: `/home/user/Downloads/jscc-test/jscc`
- artifact_path: `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- artifact_sha256: `d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6`
- artifact_sha256_expected: `d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6`
- artifact_sha256_match: `true`
- load_ms: `3.745`
- vm_init_ms: `2.962`
- run_median_ms: `2486.617`
- run_mean_ms: `2486.944`
- run_min_ms: `2484.825`
- run_max_ms: `2490.947`
- output_shape: `[1, 3, 256, 256]`
- output_dtype: `float32`

## Interpretation

The guard is now part of the real current-safe execution path:

1. the remote `optimized_model.so` hash is measured at execution time;
2. the measured hash matched the configured expected SHA;
3. inference then completed successfully.

So future remote artifact drift should fail fast at the guard boundary instead of silently producing misleading benchmark results.

## Related artifacts

- final compare report: `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_final_20260311_024434.md`
- guard handoff: `session_bootstrap/reports/inference_currentsafe_artifact_guard_handoff_20260311.md`
- guard commits:
  - `03e96d4` `Add current-safe artifact guard for inference benchmark`
  - `97dde7c` `Wire expected current-safe artifact hash into safe env`
