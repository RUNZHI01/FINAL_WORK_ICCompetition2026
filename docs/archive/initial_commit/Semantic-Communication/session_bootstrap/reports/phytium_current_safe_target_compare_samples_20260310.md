# Phytium Pi baseline-seeded current-safe target comparison

- mode: baseline-seeded warm-start current rebuild-only target compare + safe runtime
- generated_at: 2026-03-10T03:50:56+08:00
- report_id: phytium_current_safe_target_compare_samples_20260310
- rebuild_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env
- inference_env: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
- validity: INVALID
- validity_note: Stable and experimental targets differ, but the rebuilt optimized_model.so hash is identical. Treat this compare as invalid.

## Runs

| profile | target | build sec | load ms | vm init ms | median ms | mean ms | min ms | max ms | variance ms^2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| recommended stable | `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}` | 3.700 | 4.289 | 0.511 | 2475.476 | 2475.593 | 2474.081 | 2477.618 | 1.009 |
| aggressive experimental | `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}` | 3.500 | 4.258 | 0.514 | 2478.651 | 2478.329 | 2477.343 | 2479.036 | 0.464 |

## Build Identity

| profile | runner | total_trials | search_mode | optimized_model_sha256 |
|---|---|---:|---|---|
| recommended stable | `local` | 0 | `baseline_seeded_rebuild_only` | `2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449` |
| aggressive experimental | `local` | 0 | `baseline_seeded_rebuild_only` | `2fcf773fa34d6aa69f80740ffedde33faaf265a045cae97b72022ae2c62a8449` |

## Invalid Compare

- status: INVALID
- reason: distinct targets produced the same optimized_model.so sha256
- action: discard the timing delta and rerun only after a path that yields distinct artifacts

## Quick Readout

- This compare is invalid; do not use it to rank stable vs experimental targets.
- Recorded experimental vs stable median: 3.175 ms slower. Discard this delta unless a rerun produces distinct artifact hashes.
- Recorded experimental vs stable variance: 0.545 ms^2 lower. Discard this delta unless a rerun produces distinct artifact hashes.
- Compare validity: INVALID (Stable and experimental targets differ, but the rebuilt optimized_model.so hash is identical. Treat this compare as invalid.)
- Stable per-run summary: `/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_current_safe_target_compare_samples_20260310_stable.md`
- Experimental per-run summary: `/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_current_safe_target_compare_samples_20260310_experimental.md`
- Compare log: `/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/phytium_current_safe_target_compare_samples_20260310.log`
- Compare json: `/home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/phytium_current_safe_target_compare_samples_20260310.json`
