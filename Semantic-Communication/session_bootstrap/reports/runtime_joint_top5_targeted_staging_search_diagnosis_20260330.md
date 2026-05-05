# Runtime-joint-top5 targeted staging search 诊断结论（2026-03-30）

## 结论一句话

这轮 `runtime-joint-top5 + staging` 是目前三轮里 **最健康** 的结果：它没有再出现秒级灾难性回归，safe runtime payload 已回到 `223.182 ms` 的同量级区间；但它仍然 **没有超过 trusted current 主线**，因此当前结论应是：

> **可保留为 staging 候选，但暂不 promote。**

## 本轮对象

- run id: `phytium_runtime_joint_top5_targeted_staging_search_20260330_2205`
- staging remote archive: `/home/user/Downloads/jscc-test/jscc_staging`
- new artifact sha256: `9979d906a7eb52772eab3c124aea58246e7e0f0e4391b76d57af6d095ddbc805`
- trusted current sha256 (mainline unchanged): `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## 1. 本轮策略

和前两轮不同，这一轮不是只保护局部子集，而是把旧 top-2 与 shifted-top3 合成 joint-top5：

- `fused_conv2d_transpose2_add12`
- `fused_conv2d_transpose1_add9`
- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`

并且只上传到 **staging archive**，避免污染 trusted current 主线。

## 2. 局部调优结果

从 task scheduler 最终 best 可见：

- `fused_conv2d3_add15` → `15112.1164 us`
- `fused_conv2d_transpose_add6` → `18164.4588 us`
- `fused_conv2d2_add2` → `932.9464 us`
- `fused_conv2d_transpose2_add12` → `23346.2506 us`
- `fused_conv2d_transpose1_add9` → `18861.4402 us`

说明 joint-top5 至少成功把五个关键热点一起压在了可控范围内，没有再出现“只压一边、另一边暴涨”的极端失衡。

## 3. staging payload 结果：这是第一轮没有炸掉的 integrated 候选

summary 见：

- `session_bootstrap/reports/phytium_runtime_joint_top5_targeted_staging_search_20260330_2205.md`

关键结果：

- `run_median_ms = 223.182`
- `run_mean_ms = 223.336`
- `load_ms = 3.829`
- `vm_init_ms = 0.466`
- `artifact_sha256_match = true`

与前两轮对比：

- runtime-top2 candidate payload：`1470.67 ms`
- runtime-shifted-top3 candidate payload：`2110.348 ms`
- runtime-joint-top5 staging candidate payload：`223.182 ms`

因此，这一轮至少证明：

- joint-top5 策略显著缓解了前两轮那种 integrated artifact 级灾难性回归；
- 当前 candidate 已经回到“正常 TVM current 候选”的量级，而不是明显错误产物。

## 4. 但为什么仍不能 promote

当前 trusted current 主线的正式 payload 口径仍明显优于 `223.182 ms`。

因此，虽然这轮 candidate 已经满足“staging 可保留”的基本门槛，但还不满足“覆盖 trusted current 主线”的 promote 条件。

换句话说：

- **前两轮：局部成功、整体失败（不可保留）**
- **这一轮：局部成功、整体不坏，但仍未赢过主线（可保留 staging，不可 promote）**

## 5. 当前最合理的项目判断

到这一步，项目状态已经比之前清晰很多：

1. blind retarget（只盯 top2 或 shifted-top3）不够；
2. joint-top5 是目前三轮里最合理的保护集；
3. 但单纯继续加预算，还不一定能自动超过 trusted current；
4. 因此下一步不应再直接覆盖主线，而应围绕这个 staging candidate 做更谨慎的二次验证/诊断。

## 6. 下一步建议

### 建议优先级 A：先做 runtime reprobe（针对 staging candidate）

目标：确认 joint-top5 candidate 在 integrated payload 下的 runtime top ops 是否仍然存在明显热点回弹。

如果 runtime reprobe 显示：

- 五个关键点都被控制在较均衡区间；
- 没有新的单点支配性 hotspot；

那么才有理由考虑继续加预算或做更细微调。

### 建议优先级 B：保守扩预算，但仍只在 staging 中进行

如果要继续冲：

- 仍建议沿 joint-top5 线；
- 预算可以温和上调；
- 但必须继续走 staging validate wrapper，而不是 current 主线覆盖。

### 当前不建议

- 不建议立即 promote 到 trusted current。
- 不建议现在就切手写 TIR 主线化；当前还缺“staging candidate 已经全局占优”的证据。

## 7. 当前推荐口径

推荐对外/对自己都这样描述：

> 我们已经从“局部热点优化导致整体灾难性回归”推进到“joint-top5 在 staging 中产出同量级、稳定候选”。这说明保护联合热点集是对的，但当前候选还没有赢过 trusted current，因此主线保持不动，下一步以 staging reprobe 和温和扩预算为主。

## 8. 证据入口

- summary:
  - `session_bootstrap/reports/phytium_runtime_joint_top5_targeted_staging_search_20260330_2205.md`
- tune logs / task scheduler:
  - `session_bootstrap/tmp/phytium_runtime_joint_top5_targeted_staging_search_20260330_2205/tuning_logs/logs/`
- promotion gate:
  - `session_bootstrap/runbooks/current_safe_promotion_gate_2026-03-30.md`
- 上两轮诊断：
  - `session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
  - `session_bootstrap/reports/runtime_shifted_top3_targeted_search_diagnosis_20260330.md`
