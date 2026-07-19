# Runtime-joint-top6 refine staging 诊断结论（2026-03-31）

## 结论一句话

这轮 `runtime-joint-top6 refine-from-best-staging` **没有产生新的更优候选**：最终 artifact SHA 与当前最佳 staging 候选完全相同，payload 结果也略差于基线候选，因此本轮应记为 **confirm / no-op refine**，而不是新的升级点。

## 本轮对象

- run id: `phytium_runtime_joint_top6_refine_staging_search_20260331_0054`
- reference candidate:
  - `phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
- reference artifact sha256:
  - `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`

## 1. 本轮最关键事实：artifact 没变

本轮 refine summary：

- `session_bootstrap/reports/phytium_runtime_joint_top6_refine_staging_search_20260331_0054.md`

对比上一轮 current best staging candidate：

- previous best staging candidate sha:
  - `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- this refine sha:
  - `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`

结论：

- 本轮虽然重新跑了 `240` trials；
- 但最终编译出的 `optimized_model.so` 与上一轮 best staging candidate **完全相同**；
- 因此它没有形成新的 artifact 身份。

## 2. payload 对比：也没有带来改善

### previous best staging candidate

- run id: `phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
- `run_median_ms = 159.943`
- `run_mean_ms = 160.450`
- `run_variance_ms2 = 1.356879`

### this refine run

- run id: `phytium_runtime_joint_top6_refine_staging_search_20260331_0054`
- `run_median_ms = 161.900`
- `run_mean_ms = 162.062`
- `run_variance_ms2 = 0.637957`

结论：

- median 从 `159.943 ms` 变成 `161.900 ms`
- mean 从 `160.450 ms` 变成 `162.062 ms`
- variance 虽略小，但主要原因更可能是重复测试波动，而不是新 artifact 改善，因为 artifact 根本没变

因此：

> 这轮 refine 没有在 payload 层面带来更优结果。

## 3. 应如何解释这轮 refine

最合理的解释不是“失败到要丢弃”，而是：

- 当前 best staging candidate 所在的 joint-top6 解，在这组目标 / 这组预算 / 这份 warm-start DB 附近已经比较稳定；
- 本轮 `240 trials` 的小步 refine 没有把系统带到新的更优 schedule 区域；
- 所以它验证了当前 best staging candidate 的稳定性，但没有产生新的更优候选。

换句话说：

> 这是一次有效的 **确认性实验**，结果是“当前 best staging candidate 仍然是 best”。

## 4. 当前项目状态更新

截至现在：

- trusted current 主线：仍然固定在 `6f236b07...`
- current best staging candidate：仍然是 `5bd14b9f...`
- refine result：未超过 `5bd14b9f...`

因此，后续所有工作默认应继续以：

- `5bd14b9f...` 作为唯一 staging 对照基线；
- 不再把 `0054` 这一轮当成新候选；
- 也不需要再单独保留一条新的“refine candidate 线”。

## 5. 下一步建议

当前更合理的继续方向，不是再做同构 refine，而是二选一：

### A. 做 hand-written hotspot path 准备

既然 repo 内已有 runtime hotspot 证据，且多轮 auto tuning 已经把 candidate 拉到当前水平但没有继续突破，下一步可以开始把：

- `fused_conv2d_transpose1_add9`
- `fused_conv2d_transpose2_add12`
- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`

这些热点转入 **手写 TIR / NEON 候选筛查**。

### B. 如果仍坚持 auto tuning，只做结构性变化，不做同构小步 refine

例如：

- 改 target / target attributes 的更强约束；
- 改搜索规则；
- 改 postproc / schedule rule；
- 而不是继续在同一 target + 同一 target set + 同一 warm-start DB 附近做小预算重复搜索。

## 6. 当前推荐口径

推荐统一写法：

> `joint-top6 refine-from-best-staging` 未产生新的更优 artifact；最终产物 SHA 与 current best staging candidate 完全一致，payload 结果也略差。因此当前 best staging candidate 维持不变，后续应转入更结构性的优化路线（优先考虑手写热点算子 / TIR / NEON）。

## 7. 证据入口

- refine summary:
  - `session_bootstrap/reports/phytium_runtime_joint_top6_refine_staging_search_20260331_0054.md`
- current best staging freeze:
  - `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- current best staging diagnosis:
  - `session_bootstrap/reports/runtime_joint_top6_targeted_staging_search_diagnosis_20260331.md`
