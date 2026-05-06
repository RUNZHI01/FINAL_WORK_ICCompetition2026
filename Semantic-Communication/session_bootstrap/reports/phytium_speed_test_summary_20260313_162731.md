# Phytium Pi Speed Test Summary

- recorded_at: `2026-03-13T16:27:31+08:00`
- scope: `TVM payload inference and real end-to-end reconstruction speed`
- board: `Phytium Pi`
- sample_set: `300 inputs`

## Validated Current Artifact

- artifact: `optimized_model.so`
- SHA256: `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
- validation_status: `validated on Phytium Pi for payload-only inference and real end-to-end reconstruction`

## Payload Inference

Source report:

- `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002.md`

Results:

| Path | Median |
|---|---:|
| baseline | `1853.7 ms` |
| current | `131.343 ms` |

The current artifact SHA guard matched the validated artifact SHA listed above.

## Real End-To-End Reconstruction

Source report:

- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140.md`

Results:

| Path | Median | Samples |
|---|---:|---:|
| baseline | `1834.1 ms/image` | `300` |
| current | `234.219 ms/image` | `300` |

The current artifact SHA guard matched the validated artifact SHA listed above.

## Tuned Candidate Record

A later `chunk4` candidate was recorded on `2026-03-13`:

- candidate SHA256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- current-only payload median: `127.322 ms`
- source report: `session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.md`

This candidate has a current-only payload result in the repository. The validated current artifact for paired baseline-vs-current payload and paired end-to-end reconstruction remains SHA `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`.

## KPI Boundary

This file records historical TVM speed evidence. The current board-side three-path reproducibility entry is:

- Windows PowerShell: `docker/run-board-cli-smoke.ps1`
- Linux / WSL: `docker/run-board-cli-smoke.sh`

That CLI smoke writes the demo-compatible KPI summary to `logs/demo-kpi-summary.json` in the board-side isolated run directory.
