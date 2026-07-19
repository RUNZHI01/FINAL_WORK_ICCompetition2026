# verifyloop3_snapdragon r01 decision

## Round snapshot
- stage: prep
- iter: 1/2
- readiness: pass
- quick: success (baseline_count=2, current_count=2, improvement=49.20%)
- full: skipped_by_flag

## Strategy for next round (iter 2/2)
- Keep QUICK/FULL command bodies unchanged.
- Increase repeat/trial counts to improve confidence before leaving smoke stage.
- Expand timeout proportionally to avoid false timeout after repeat increase.

## Delta
- QUICK_REPEAT: 2 -> 3
- QUICK_TIMEOUT_SEC: 30 -> 45
- FULL_TRIALS_PER_TASK: 2 -> 3
- FULL_TIMEOUT_SEC: 120 -> 180
- Update DAILY_SINGLE_CHANGE / DAILY_NEXT_CHANGE to reflect stability-first objective.

## Rationale
Current signal is directionally clear and stable enough to justify confidence-up iteration. In prep stage, raising measurement confidence has higher ROI than adding new variable changes.
