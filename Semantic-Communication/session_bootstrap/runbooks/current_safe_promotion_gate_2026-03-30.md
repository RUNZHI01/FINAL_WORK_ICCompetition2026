# Current-safe Promotion Gate（2026-03-30）

## 目的

在 `runtime-top2` 和 `runtime-shifted-top3` 两轮定向深搜后，已经确认：

- 单算子 / 局部热点可以显著优化；
- 但新 artifact 可能在 integrated payload 上严重回归；
- 如果直接上传覆盖 remote current archive，会污染 trusted current 主线。

因此，从现在起，新的 current-safe tuning artifact 应先走 **staging 验证**，再决定是否 promote。

## 默认入口

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_staging_validate.sh
```

默认 staging 远端目录：

```text
/home/user/Downloads/jscc-test/jscc_staging
```

## 什么时候用这个入口

适用于：

- 新 target / 新预算 / 新 op filter 的 tuning 轮次；
- 任何尚未被证明能进入 trusted current 的候选 artifact；
- 尤其适合 runtime hotspot 定向深搜之后的候选验证。

不适用于：

- 已经确定要恢复 trusted current 主线时；
- 直接复现已知 trusted artifact 时。

## 执行流程

1. 本地调优生成新 artifact
2. 上传到 remote **staging archive**，而不是 current archive
3. 在 staging archive 上跑 safe runtime payload / reprobe
4. 只有当下面条件同时满足时，才允许 promote：
   - payload / real run 不出现量级回归
   - runtime reprobe 没有出现新的致命 hotspot snapback
   - SHA / 产物路径 / DB 都可追溯

## promote 前最低检查项

- `run_median_ms` 至少处于 trusted current 同量级，而不是回到秒级
- `artifact_sha256_match = true`
- 如做 runtime reprobe：新的 top ops 不应再次把旧热点推回到支配性位置
- 若失败：保留候选报告，但 **不覆盖** trusted current archive

## 背景依据

- `session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- `session_bootstrap/reports/runtime_shifted_top3_targeted_search_diagnosis_20260330.md`

这两份诊断已经证明：

- 直接把新 artifact 覆盖到 current archive，会造成主线 repeatedly 被坏 artifact 污染；
- 因此 promotion gate 不是“额外流程”，而是当前 TVM 主线继续迭代的必要护栏。
