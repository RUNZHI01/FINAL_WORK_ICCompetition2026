# verifyloop2_snapdragon r01 decision

## Input round snapshot
- stage: prep
- iter: 1/2
- quick: success (`baseline_count=2`, `current_count=2`, improvement `49.04%`)
- full: skipped_by_flag (no full datapoint in this iteration)

## Decision for next round (prep 2/2)
1. Keep command bodies unchanged (quick/full command templates are healthy in smoke mode).
2. Increase statistical confidence for quick by raising repeats from 2 to 3.
3. Increase full micro-benchmark confidence by raising trials-per-task from 2 to 3.
4. Slightly enlarge time budgets to avoid timeout risk after repeat/trial increase.

## Delta applied
- `QUICK_REPEAT=3`
- `QUICK_TIMEOUT_SEC=45`
- `FULL_TIMEOUT_SEC=180`
- `FULL_TRIALS_PER_TASK=3`
- update daily notes to reflect stability-focused single-variable change.

## Why
- r01 already shows directional separation (baseline > current), so next priority is not speed but confidence.
- prep stage still smoke-mode: best ROI is reducing variance before switching payload to real RPC tune/eval.
