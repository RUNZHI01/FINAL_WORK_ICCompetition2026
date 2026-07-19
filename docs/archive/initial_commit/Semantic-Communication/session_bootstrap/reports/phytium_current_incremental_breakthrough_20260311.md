# Phytium Pi current incremental breakthrough (2026-03-11)

## Executive summary

The first successful **baseline-seeded warm-start current incremental** artifact has now completed the full path:

1. nonzero-budget incremental tuning (`500` trials, `runner=rpc`),
2. local compile,
3. upload to the Phytium Pi current archive,
4. safe runtime validation,
5. formal baseline-vs-current-safe inference benchmark rerun.

This is no longer just a recovery story. It is now a **real performance breakthrough** on the current line.

## New current artifact

- artifact path (local):
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so`
- artifact SHA256:
  - `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- artifact size:
  - `1653592` bytes
- remote archive path:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`

## Incremental tuning/build result

From the resumed incremental run:

- `tune_total_trials=500`
- `tune_runner=rpc`
- `build_search_mode=baseline_seeded_warm_start_incremental`
- local compile: success
- remote upload: success
- SHA identity after upload: matched the new artifact

Reference:
- `session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548_resume.md`

## Safe runtime validation

A focused current-safe validation using the new SHA succeeded:

- `artifact_sha256_match=true`
- `load_ms=3.741`
- `vm_init_ms=0.479`
- `run_median_ms=163.635`
- `output_shape=[1, 3, 256, 256]`

Interpretation:
- the new incremental artifact is not only uploaded, but is already runnable on the Phytium Pi safe runtime path.

## Formal benchmark rerun result

Report:
- `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md`

Key numbers:
- baseline median: `1844.1 ms`
- current-safe median: `153.778 ms`
- delta: `-1690.322 ms`
- improvement: `91.66%`

Artifact identity in the benchmark:
- `current_artifact_sha256=1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`
- `current_artifact_sha256_match=True`

## Interpretation

Compared with the previous baseline:

- the new current artifact reduces median inference latency from `1844.1 ms` to `153.778 ms`;
- this is roughly a **12x-class speedup**;
- the benchmark proves the gain on the real protected current-safe path, not on a synthetic or unchecked execution route.

Compared with the earlier current-safe artifact line:

- this run is far beyond merely “restoring current-safe execution”;
- it demonstrates that the first nonzero-budget incremental tuning run produced a materially better artifact.

## Operational takeaway

Current state should be considered:

- **current incremental artifact generation: working**
- **artifact SHA guard: working**
- **Phytium Pi current-safe execution of the new artifact: working**
- **formal benchmark advantage over baseline: confirmed**

## Next recommended step

The next most valuable action is a short **stability revalidation**:

- rerun the protected baseline-vs-current-safe benchmark 2–3 more times against the same SHA
- confirm the `~154 ms` current-safe latency band is stable
- then promote this artifact/SHA as the new trusted current-safe reference point
