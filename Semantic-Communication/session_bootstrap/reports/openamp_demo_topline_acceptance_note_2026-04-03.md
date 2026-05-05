# OpenAMP Demo 首屏 / Top-line Status 验收口径说明（2026-04-03）

## 目的

把总清单里“Demo 首屏显示：飞腾派在线、OpenAMP 从核在线、trusted current SHA、当前 target、当前 runtime”这件事，收敛成一份**可人工核对的验收口径**，避免后续继续把“首屏看起来有很多字段”误当成“首屏口径已经冻结”。

## 1. 当前首屏必须稳定表达的内容

### A. 在线 / 实例事实

必须能说明：

- `8115` 是当前唯一有效 demo 实例
- `current live = 300 / 300`
- `PyTorch reference archive = 300 / 300`
- 首屏是 `docs-first / operator-assist`，不是自动编排页面

这部分的用途是先把“系统在线且有既有 live 事实”立住。

### B. 模式边界

首屏必须继续明确区分：

- `4-core Linux performance mode`：只负责 headline performance
- `3-core Linux + RTOS demo mode`：只负责 live OpenAMP operator flow / safety

这是首屏最关键的防混写护栏之一。

### C. trusted current 身份

首屏或与首屏同层级的默认资料入口，必须能把 trusted current 身份讲清楚：

- trusted current SHA：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 该 SHA 对应的正式性能口径只能引用：
  - payload：`1846.9 -> 130.219 ms`
  - real reconstruction：`1850.0 -> 230.339 ms/image`

### D. 第三幕默认 compare 边界

首屏相关口径必须与第三幕保持一致：

- 默认 compare 仍是归档 `PyTorch reference`
- `2026-03-17` baseline `300 / 300` 是历史 live 证据，不是本场默认 operator flow

### E. `TC-002 / TC-010` 边界

首屏允许提 recent live `300 / 300`，但只能落到：

- `TC-002` 已由 live reconstruction 收口

不能被偷换成：

- `TC-010`
- `RESET_REQ/ACK`
- sticky fault reset 已闭环

## 2. 当前可接受的最小验收来源

当前仓库里，下面几份材料合起来已经足够支撑“首屏口径已基本冻结，但仍以 docs-first 为准”：

1. `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md`
   - 证明本地启动路径存在，`/api/health` 与 `/api/snapshot` 正常
   - 已核对 `8115 / current 300/300 / baseline 300/300`

2. `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md`
   - 已把 top-line quick sanity 固化成 operator checklist

3. `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md`
   - 已把第三幕默认 compare、两条正式口径和 mode boundary 说清

4. `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
   - 已把 `TC-002` / `TC-010` 的 claim boundary 单独钉死

## 3. 当前仍不应把这项“完全勾完成”的原因

虽然首屏相关信息已经基本齐了，但这项目前更准确的状态是：

> **口径与验收标准已冻结，UI 是否在 presentation-day 版本中逐字段稳定露出，还应在最终答辩版彩排时再做一次人工核对。**

也就是说，当前本地最值钱的工作不是继续猜 UI，而是先把“什么才算首屏合格”写清楚，防止后面把历史 live、第三幕 compare、性能 headline 和 reset 边界混写。

## 4. presentation-day 人工核对清单

如果现场要做最后一次人工确认，建议只核对这些：

- 是否能看到 `8115`
- 是否能看到 `current 300 / 300`
- 是否能看到 `PyTorch reference 300 / 300 (archive)`
- 是否还能看到 `4-core Linux performance mode` vs `3-core Linux + RTOS demo mode` 边界
- 是否还能从默认资料入口快速跳到 trusted current SHA 与两条正式性能口径
- 是否没有把 `300 / 300` 误讲成 `TC-010` / `RESET_REQ/ACK` 已完成

## 5. 对任务板的建议解释

因此，总清单里这项现在更适合解释成：

- **不是缺字段定义**；字段定义已经有了
- **也不是缺口径**；口径已经有了
- **剩下的是 presentation-day 的最终人工核对**

## 6. 关联入口

- `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md`
- `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md`
- `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
