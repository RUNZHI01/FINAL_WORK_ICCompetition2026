# Runtime-Joint-Top6 Refine Staging Search（2026-03-31）

## 目的

joint-top6 已经被正式冻结为 current best staging candidate：

- freeze record: `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- best staging artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`

下一步不建议再 blind 扩 target 集，而应该在**相同 joint-top6 目标集上做小步 refine**：

- 继续使用同一组目标；
- 用上一轮的 tuning DB 做 warm-start；
- 用更小预算验证能否在 staging 中继续改善 payload / reprobe；
- 放到新的 staging archive，避免覆盖 current best staging candidate。

## 默认入口

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top6_refine_staging_search.sh
```

默认 staging archive：

```text
/home/user/Downloads/jscc-test/jscc_staging_refine
```

## 特点

- 使用 `joint-top6` 同一目标集；
- warm-start DB 切到：
  - `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- trial budget 更保守：
  - `TUNE_TOTAL_TRIALS=240`
  - `TUNE_MAX_TRIALS_PER_TASK=40`

## 适用场景

适用于：

- 你已经认可 `5bd14b9f...` 是当前最佳 staging 候选；
- 但还想在不扩大目标集的前提下，确认是否还能继续往前推一步；
- 同时不想覆盖 trusted current，也不想覆盖 current best staging candidate。
