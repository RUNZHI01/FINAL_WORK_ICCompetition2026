# 飞腾平台表述策略正式说明（2026-04-03）

## 目的

把任务板里“统一飞腾平台表述策略”这项，从零散提示收敛成一份正式说明，解决两个经常被混写的问题：

1. **硬件介绍页**到底该怎么说
2. **TVM 优化页**里的 target / micro-architecture 表述到底该怎么说

核心原则是：

> **平台介绍用官方/系统级表述，编译优化页再单独说明 LLVM/TVM 当前稳定 target 收敛为 `cortex-a72 + neon`。**

---

## 1. 为什么要分层表述

如果把“飞腾平台硬件介绍”和“TVM codegen target”混成一句话，容易出两个问题：

- 让评委误以为 `cortex-a72 + neon` 就是整个平台的官方命名
- 让编译器 target 看起来像在替代硬件平台定义，而不是作为优化实现细节存在

因此，后续所有材料都应遵守：

- **系统/平台层**：讲飞腾平台 / 飞腾派 / 飞腾多核异构平台
- **编译优化层**：讲当前 LLVM/TVM 稳定 target 为 `llvm / aarch64-linux-gnu / cortex-a72 + neon / num-cores=4`

---

## 2. 第一层：平台 / 硬件介绍怎么说

### 推荐说法

在首页、系统架构图、作品简介、摘要、总览页里，统一优先使用：

- `飞腾平台`
- `飞腾派`
- `飞腾多核异构平台`
- `基于飞腾平台的安全可靠图像语义通信系统`

### 允许的补充硬件说明

如果需要补一层硬件特征，可以说：

- `飞腾派多核 ARMv8 平台`
- `飞腾派 big.LITTLE 异构多核平台`

但这层依然属于**平台能力说明**，不是编译目标说明。

### 不建议在平台介绍页直接说的内容

- `当前平台就是 cortex-a72 + neon`
- `飞腾平台官方定义为 cortex-a72 + neon`
- 把 `num-cores=4` 直接当成平台命名的一部分

这些都更适合放到 TVM 优化实现页，而不是平台介绍页。

---

## 3. 第二层：TVM / LLVM 优化页怎么说

### 推荐说法

在 TVM 优化页、target 对比页、编译配置页、artifact lineage 说明页里，单独写清：

> 当前 LLVM/TVM 稳定 target 收敛为 `llvm / aarch64-linux-gnu / cortex-a72 + neon / num-cores=4`。

必要时也可以简写成：

> 当前稳定 target 为 `cortex-a72 + neon`。

### 这句话的真正含义

它表示的是：

- 当前 TVM / LLVM codegen 的**稳定优化目标**
- 是在当前 builder / runtime / benchmark 约束下选出来的最稳妥收敛点
- 不是在替代飞腾平台官方硬件命名

### 应搭配出现的边界说明

- `mcpu=phytium` / `mcpu=ft2000plus` 不能作为当前默认 builder 方案
- 更激进 target 曾试过，但当前默认收敛仍以稳定性优先
- 因此 `cortex-a72 + neon` 是**编译策略收敛结果**，不是平台主标题

---

## 4. 一句话模板

### 首页 / 摘要 / 系统图

> 本项目是一套基于飞腾平台的安全可靠图像语义通信系统。

### TVM 优化页

> 在当前飞腾板真实 runtime 与 benchmark 约束下，LLVM/TVM 稳定 target 收敛为 `cortex-a72 + neon`。

### 两句话连用版本

> 平台层面，我们面向飞腾多核异构平台构建系统；
> 编译优化层面，TVM 当前稳定 codegen target 收敛为 `cortex-a72 + neon`。

---

## 5. 对现有仓库材料的建议用法

### 应优先使用平台表述的文档

- `paper/CICC0903540初赛技术文档.md`
- `paper/Demo与视频设计方案_2026-03-12.md`
- 各类 PPT 首页 / 系统图 / 总结页 / 答辩口播

### 应显式保留 target 表述的文档

- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
- `session_bootstrap/runbooks/artifact_registry.md`
- target compare / TVM current benchmark / MetaSchedule 路线相关报告

---

## 6. 对任务板更准确的解释

这项任务现在更准确的状态是：

- **规则已经可以明确写出**
- 剩余更多是后续文档是否持续遵守这套分层表述

也就是说，真正需要避免的不是“没有策略”，而是：

- 在平台页混入编译 target
- 在优化页把 target 说成平台官方命名

---

## 7. 关联文档

- `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
- `session_bootstrap/runbooks/artifact_registry.md`
- `session_bootstrap/reports/project_dual_layer_narrative_and_wording_system_2026-04-03.md`
- `session_bootstrap/reports/project_release_baseline_and_optimization_lineage_2026-04-03.md`
