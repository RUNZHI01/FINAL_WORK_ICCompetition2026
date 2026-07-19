# msloop_prep_snapdragon r02 decision

## Round snapshot
- stage: prep
- iter: 2/3
- quick: success (`baseline_count=3`, `current_count=3`, improvement `49.32%`)
- full: skipped_by_flag

## Decision
- No parameter tuning change for r03 budget/repeat knobs.
- Keep `QUICK_REPEAT=3`, `QUICK_TIMEOUT_SEC=180`, `FULL_TRIALS_PER_TASK=3`, `FULL_TIMEOUT_SEC=240`.
- Use r03 as payload transition step: swap mock QUICK/FULL commands to real TVM RPC tune/eval commands.

## Why
r02 confirms stable separation with higher repeat count; additional budget tuning now has low ROI compared to moving prep pipeline to real payload.
