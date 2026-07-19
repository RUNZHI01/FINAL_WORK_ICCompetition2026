# Phytium Pi baseline-seeded warm-start current incremental (2026-03-11 09:45 rerun) — resume conclusion

## Summary

This rerun did **finish the incremental tuning/build/upload path successfully**.

The wrapper exited with `rc=1`, but the immediate cause was **not** tuning failure and **not** remote runtime incompatibility. The blocker was that the safe inference env still pinned the **previous** current-safe artifact SHA, while this rerun intentionally produced a **new** current artifact.

## What completed successfully

From `session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548.log`:

- `tune_total_trials=500`
- `tune_runner=rpc`
- `build_search_mode=baseline_seeded_warm_start_incremental`
- local build completed
- compiled artifact exported:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so`
- local artifact SHA:
  - `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- local artifact size:
  - `1653592` bytes
- remote upload completed
- remote archive artifact SHA matched the new local artifact:
  - `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`

## Why the wrapper reported failure

The final safe runtime inference step failed with:

```text
ERROR: artifact sha256 mismatch variant=current \
expected=d8e801eeb25a87d340311015fe475f00d0f324dacd88bd5936654d3eedd03cc6 \
actual=1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
```

Interpretation:

- the SHA guard worked as designed;
- the env was still pinned to the prior hotfix artifact SHA;
- this rerun produced a new current artifact, so the old expected SHA became stale.

## Follow-up validation

A focused rerun of `run_remote_tvm_inference_payload.sh --variant current` with:

- `INFERENCE_CURRENT_EXPECTED_SHA256=1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- `INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc`

succeeded, with key results:

- `artifact_sha256_match=true`
- `load_ms=3.741`
- `vm_init_ms=0.479`
- `run_median_ms=163.635`
- `output_shape=[1, 3, 256, 256]`
- `output_dtype=float32`

## Operator conclusion

This run should be classified as:

- **incremental tuning/build/upload: success**
- **initial wrapper result: failed only because expected SHA was stale**
- **new artifact runtime validation: success after updating expected SHA**

## Required env update

`session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env`

should track the new current-safe artifact SHA:

```bash
INFERENCE_CURRENT_EXPECTED_SHA256=1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644
```
