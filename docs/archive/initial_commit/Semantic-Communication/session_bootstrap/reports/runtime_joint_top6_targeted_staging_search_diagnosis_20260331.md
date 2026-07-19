# Runtime-joint-top6 targeted staging search 诊断结论（2026-03-31）

## 结论一句话

这轮 `runtime-joint-top6 + staging` 是当前所有定向深搜里 **最好的 integrated staging 候选**：safe runtime payload 已进一步降到 `159.943 ms`，明显优于上一轮 joint-top5 的 `223.182 ms`，并且 runtime reprobe 不再出现秒级灾难或单点 40%+ 的极端支配；但它仍然 **没有超过 trusted current 主线**，因此当前结论仍是：

> **best-so-far staging candidate，可继续保留和迭代，但暂不 promote。**

## 本轮对象

- run id: `phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
- staging artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- trusted current sha256 (mainline unchanged): `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## 1. joint-top6 是如何来的

joint-top5 staging 候选虽然第一次把 integrated payload 拉回正常量级，但其 runtime reprobe 显示新的 top-1 已转成：

- `fused_conv2d_add2`

因此这一轮把下面 6 个目标一起纳入保护集：

- `fused_conv2d3_add15`
- `fused_conv2d_add2`
- `fused_conv2d_transpose_add6`
- `fused_conv2d2_add2`
- `fused_conv2d_transpose2_add12`
- `fused_conv2d_transpose1_add9`

## 2. 局部调优结果

本轮最终可确认的局部 best：

- `fused_conv2d3_add15` → `11673.1037 us`
- `fused_conv2d_add2` → `3501.1720 us`
- `fused_conv2d_transpose_add6` → `17440.0493 us`
- `fused_conv2d2_add2` → `887.8953 us`
- `fused_conv2d_transpose2_add12` → `19437.2130 us`
- `fused_conv2d_transpose1_add9` → `23503.5664 us`

其中最明显的后段改善包括：

- `fused_conv2d_transpose2_add12`：继续压到 `19437.2130 us`
- `fused_conv2d2_add2`：压到 `887.8953 us`
- `fused_conv2d_transpose_add6`：压到 `17440.0493 us`

## 3. staging payload：目前最好的一版 integrated 候选

summary 见：

- `session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`

关键结果：

- `run_median_ms = 159.943`
- `run_mean_ms = 160.450`
- `run_min_ms = 159.488`
- `run_max_ms = 162.985`
- `run_variance_ms2 = 1.356879`

与前几轮 staging/坏候选对比：

- runtime-top2 candidate payload：`1470.67 ms`
- runtime-shifted-top3 candidate payload：`2110.348 ms`
- runtime-joint-top5 staging payload：`223.182 ms`
- runtime-joint-top6 staging payload：`159.943 ms`

因此：

- joint-top6 比 joint-top5 又前进了一步；
- 并且方差仍然很小，没有出现灾难性抖动。

## 4. runtime reprobe：结构比前几轮健康得多

joint-top6 staging candidate reprobe：

- report: `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
- `run_median_ms = 329.928`

新的 runtime top ops：

1. `fused_conv2d_transpose1_add9` → `24275.261 us` (`14.60%`)
2. `fused_conv2d_transpose2_add12` → `20234.681 us` (`12.17%`)
3. `fused_conv2d_transpose_add6` → `17385.325 us` (`10.46%`)
4. `fused_conv2d3_add15` → `11800.990 us` (`7.10%`)
5. `fused_mean4_subtract4_divide4_multiply4_add14_relu3` → `11065.872 us` (`6.66%`)
6. `fused_variance4_add13_tir_sqrt4` → `7099.569 us` (`4.27%`)
7. `fused_mean3_subtract3_divide3_multiply3_add11_relu2` → `5825.708 us` (`3.50%`)
8. `fused_variance3_add10_tir_sqrt3` → `3575.034 us` (`2.15%`)

关键观察：

- 旧 top-2 仍然在前列，但已经不再像前两轮那样重新膨胀到 `500ms+ / 40%+` 的灾难级支配；
- shifted-top3 中的 `transpose_add6 / conv2d3_add15` 仍然留在前列，而且量级被控制住了；
- `fused_conv2d_add2` 已不再是 dominant top-1；
- 整个 top-op 结构更分散、更像“可继续调的健康候选”，而不是单点爆炸。

## 5. 为什么仍然不 promote

虽然 joint-top6 是当前最好候选，但当前仍不建议 promote 到 trusted current，原因只有一个：

- 它还没有明确赢过 trusted current 正式主线口径。

换句话说：

- **前两轮：局部成功、整体失败（不可保留）**
- **joint-top5：局部成功、整体恢复到正常量级（staging 可保留）**
- **joint-top6：目前最好，且结构健康很多（best-so-far staging candidate）**
- **但尚不足以覆盖 trusted current 主线**

## 6. 当前推荐动作

### 推荐动作 A：冻结为“当前最佳 staging 候选”

建议明确把 `5bd14b9f...` 标成：

- current best staging candidate
- 不 promote
- 后续所有新尝试都必须拿它做对比，而不是再回到更差的 joint-top5 或 blind retarget

### 推荐动作 B：如果继续优化，优先做小步增量而不是再大改目标集

因为 joint-top6 已经把已知大热点基本纳进来了，此时更合理的是：

- 温和扩预算；
- 或对当前 top-op 结构中 5-8 名的稳定项做小范围增补；
- 不建议立刻再做大幅 retarget 到 joint-top7 / joint-top8，除非有新 evidence 证明当前结构又在明显漂移。

## 7. 当前最推荐的项目口径

推荐一句话：

> 我们已经从“局部热点优化导致 integrated artifact 灾难性回归”，推进到“joint-top6 在 staging 中产出当前最佳候选：payload 159.943 ms，runtime 结构不再极端失衡”。这说明联合保护集方向是对的，但当前仍以 staging 候选身份保留，主线暂不替换。

## 8. 证据入口

- joint-top6 summary:
  - `session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`
- joint-top6 staging reprobe:
  - `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
- joint-top5 diagnosis:
  - `session_bootstrap/reports/runtime_joint_top5_targeted_staging_search_diagnosis_20260330.md`
- promotion gate:
  - `session_bootstrap/runbooks/current_safe_promotion_gate_2026-03-30.md`
