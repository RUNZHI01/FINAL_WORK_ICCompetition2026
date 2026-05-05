# OpenAMP Demo Compare Viewer M4

## UI wiring added

- Extended `guided_demo` snapshot data with a `compare_viewer` section so Act 3 can render a compare slice without introducing a new live API.
- Added an Act 3 `Compare Viewer` panel in the existing dashboard, below the performance comparison cards and above the run buttons.
- Reused the existing global `selectedImageIndex` from the Act 2 sample picker. When the picker changes, Act 3 now rerenders the compare viewer for that sample.
- The compare viewer prefers the latest in-memory `currentResult` / `baselineResult` when they match the selected sample index; otherwise it falls back to the snapshot-provided archive/reference assets.

## Image sources used

- Left pane fallback: existing current reconstruction archive from `session_bootstrap/tmp/quality_samples_20260311/current/Places365_val_00000208_recon.png`
- Right pane fallback: existing PyTorch reference reconstruction archive from `session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions/Places365_val_00000208_recon.png`
- Sample context / selected index: existing `guided_demo.sample_catalog` and the shared `imageSelect` picker
- The compare viewer also surfaces the original sample path as context metadata, but the M4 UI itself stays side-by-side on reconstruction outputs.

## Fallback behavior

- If `state.currentResult` matches the selected sample, the left pane uses that result label/message.
- If `state.baselineResult` matches the selected sample, the right pane uses that result label/message.
- If a matching result is absent, the viewer explicitly labels the pane as `current archive` or `reference archive` and uses the existing archive/reference reconstruction image already bundled in the demo snapshot.
- No pane claims a newly generated image when the UI is still showing archive/reference material. The path note under each pane keeps that provenance visible.

## Current limitation

- M4 is a narrow side-by-side compare slice only. It is not yet a true interactive wipe/slider viewer, and it does not introduce pixel-diff tooling or a drag handle.
