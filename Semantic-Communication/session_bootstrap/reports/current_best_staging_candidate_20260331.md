# 当前最佳 staging 候选冻结记录（2026-03-31）

## 结论

截至 `2026-03-31 00:34`，当前 TVM-飞腾派项目中 **最佳 staging 候选** 已明确为：

- candidate line: `runtime-joint-top6 targeted staging`
- run id: `phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
- artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`

它是目前所有近期定向深搜里：

- 第一个没有出现 integrated payload 灾难性回归的 staging 候选；
- 第一个把 payload 进一步压到 `159.943 ms` 的 staging 候选；
- 第一个 runtime reprobe 结构没有出现秒级 / 单点 40%+ 爆炸的 staging 候选。

因此，从现在开始：

> 所有新的 TVM 定向调优候选，都应默认与 `5bd14b9f...` 这版 staging 候选对比，而不是再回到更差的 top2 / shifted-top3 / joint-top5 候选。

## 为什么是它，而不是前面的候选

### 1) runtime-top2 candidate

- 结论：局部成功，整体失败
- 代表诊断：`session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- 主要问题：safe runtime payload 回归到 `1470.67 ms`

### 2) runtime-shifted-top3 candidate

- 结论：局部成功，整体仍失败
- 代表诊断：`session_bootstrap/reports/runtime_shifted_top3_targeted_search_diagnosis_20260330.md`
- 主要问题：safe runtime payload 进一步恶化到 `2110.348 ms`

### 3) runtime-joint-top5 staging candidate

- 结论：第一次回到正常量级，但仍只是 staging 候选
- summary：`session_bootstrap/reports/phytium_runtime_joint_top5_targeted_staging_search_20260330_2205.md`
- payload：`223.182 ms`
- 代表诊断：`session_bootstrap/reports/runtime_joint_top5_targeted_staging_search_diagnosis_20260330.md`

### 4) runtime-joint-top6 staging candidate

- summary：`session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`
- payload：`159.943 ms`
- reprobe：`session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
- 代表诊断：`session_bootstrap/reports/runtime_joint_top6_targeted_staging_search_diagnosis_20260331.md`

相较 joint-top5：

- payload 从 `223.182 ms` 进一步压到 `159.943 ms`
- runtime 结构更健康，没有出现前两轮那种“局部变快但 integrated artifact 重新秒级爆炸”的模式

## 当前推荐口径

推荐对内统一这样描述：

- trusted current 主线：仍然保持 `6f236b07...`
- current best staging candidate：`5bd14b9f...`
- promotion state：`staging-only / not promoted`

也就是说：

- **主线稳定**
- **候选最优版本明确**
- **后续工作有对照基准**

## 当前最合理的下一步

如果继续推进，不建议再 blind 扩 target 集；建议按下面顺序：

1. 以 `5bd14b9f...` 为固定对照；
2. 只做小步增量（温和扩预算 / 微调 target 集）;
3. 所有新候选仍然只在 staging 验证；
4. 只有当 staging payload + runtime reprobe 都明显优于 `5bd14b9f...` 时，才有资格讨论 promote。

## 证据入口

- best staging summary:
  - `session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`
- best staging reprobe:
  - `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
- best staging diagnosis:
  - `session_bootstrap/reports/runtime_joint_top6_targeted_staging_search_diagnosis_20260331.md`
- promotion gate:
  - `session_bootstrap/runbooks/current_safe_promotion_gate_2026-03-30.md`
