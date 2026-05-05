# offline_prep_snapdragon r02 decision

## Round snapshot
- stage: prep
- iter: 2/3
- readiness: pass
- quick: success (`baseline_count=2`, `current_count=2`, improvement `49.13%`)
- full: skipped_by_flag (`full_state=skipped_by_flag`)

## Decision for next round (iter 3/3)
1. Keep QUICK/FULL command bodies unchanged (still in offline prep lane).
2. Increase `QUICK_REPEAT` from 2 to 3 to tighten confidence on quick measurement.
3. Increase `FULL_TRIALS_PER_TASK` from 2 to 3 to prepare a more stable full micro-benchmark once full is enabled.
4. Increase timeouts proportionally to avoid false timeout after repeat/trial increases.

## Delta applied
- `QUICK_REPEAT=3`
- `QUICK_TIMEOUT_SEC=45`
- `FULL_TRIALS_PER_TASK=3`
- `FULL_TIMEOUT_SEC=180`
- update daily notes to reflect "final prep stability check" objective.

## Why
The direction is already clear and consistent (about 49% improvement in quick). With one prep iteration left, best ROI is confidence-up (repeat/trial increase) before transitioning to real RPC payload in the next stage.
