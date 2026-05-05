# msloop_prep_snapdragon r01 decision

## Round snapshot
- stage: prep
- iter: 1/3
- readiness: pass
- quick: success (baseline_count=2, current_count=2, improvement=49.48%)
- full: skipped_by_flag

## Decision for r02
1. Keep QUICK/FULL command bodies unchanged (current prep payload is healthy).
2. Increase quick repeat from 2 to 3 to improve confidence.
3. Increase full trials-per-task from 2 to 3 for better micro-benchmark stability before payload switch.
4. Slightly increase quick/full timeout to absorb longer repeat/trial duration.

## Delta
- QUICK_REPEAT=3
- QUICK_TIMEOUT_SEC=180
- FULL_TRIALS_PER_TASK=3
- FULL_TIMEOUT_SEC=240
- Update DAILY_SINGLE_CHANGE / DAILY_NEXT_CHANGE to reflect confidence-first prep strategy.

## Rationale
r01 signal is strongly directional and execution is stable; with full skipped in prep, highest ROI is to raise measurement confidence first, then switch to real TVM RPC payload in later prep iteration.
