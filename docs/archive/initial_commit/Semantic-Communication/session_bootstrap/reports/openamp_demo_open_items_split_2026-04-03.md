# OpenAMP Demo 未完成项拆分说明（2026-04-03）

## 目的

把当前任务板里仍然挂着的 Demo 类未完成项，拆成两类：

1. **docs / wording 已冻结**：现在继续做纯文档，不会再显著提升确定性
2. **仍需 UI / 板侧 / presentation-day 人工确认**：这才是当前真正剩余的完成条件

这样能避免后续把“还没在任务板上勾掉”误解成“连口径都没定”。

---

## 1. 当前已基本冻结的部分

### A. 四幕主线叙事

当前关于四幕 Demo 的讲法已经基本固定：

- 四幕 runbook 已固定到 `demo_four_act_runbook.md`
- 讲稿骨架已固定到 `defense_talk_outline.md`
- 72 秒脚本 / cheat sheet / operator runbook / readiness / QA / delivery index 都已同步
- 降级方案与首屏 acceptance 也都接上了同一口径

因此，“四幕是什么、每幕讲什么、哪些 live 只能低扰动、哪些只看证据”这件事，**已经不再是开放问题**。

### B. 第三幕 compare 口径

当前第三幕口径也已经冻结：

- 默认 compare 仍是归档 `PyTorch reference`
- 只引用两条正式性能口径：
  - `1846.9 -> 130.219 ms`
  - `1850.0 -> 230.339 ms/image`
- `2026-03-17` baseline `300/300` 继续保留为历史 live 证据，不作为本场默认 operator flow

### C. `TC-002 / TC-010` 边界

这部分也已经不是开放问题：

- `TC-002` 已由 live reconstruction `300/300` 收口
- `TC-010` 仍属于 `RESET_REQ/ACK` / sticky fault reset 边界，不在当前正式 claim 内

---

## 2. 当前真正还没完成的部分

### 2.1 Demo 首屏显示项

任务板原文：

- 飞腾派在线
- OpenAMP 从核在线
- trusted current SHA
- 当前 target
- 当前 runtime

当前状态更准确地说是：

- **首屏合格标准已冻结**
- 但是否在 presentation-day 的最终版本里逐字段稳定露出，仍应做一次人工核对

所以这项的剩余工作不是“再发明首屏口径”，而是：

> 在最终演示构建 / 最终彩排版本上，人工确认首屏是否稳定露出这些字段，并且没有与第三幕 compare、历史 live 事实和 mode boundary 混写。

### 2.2 四幕结构落地到真实可演示 UI

虽然四幕 runbook 已冻结，但任务板里“将 Demo 重构为四幕”仍未勾完成，原因是：

- docs-first 叙事已经完成
- 但“当前 UI 在 presentation-day 版本上是否按这套四幕顺序稳定可演”仍需人工确认
- 尤其第三幕 baseline live 的 admission blocker 仍让“全部按 live 路径走完”不适合作为默认完成定义

所以这项剩余也不是叙事层问题，而是：

> 演示当天是否能稳定按 `四幕 -> 对应页面 -> 对应按钮/证据` 走一遍 operator flow。

### 2.3 三个故障注入按钮

这项当前仍不能在任务板上轻易勾完成，原因不是“fault story 没口径”，而是：

- `FIT-01/02/03` 证据链已经完整
- 但“UI 上三个按钮是否在当前演示构建中形成统一、可上台操作、且诚实标注 replay/live 的一套体验”仍需以最终 demo build 为准

也就是说，这项剩余属于：

> UI / operator flow 验收，而不是 fault 口径缺失。

---

## 3. 对任务板更准确的解释

### 现在不应再把这些项理解为：

- 口径还没定
- 讲法还没统一
- 需要继续补很多新文档

### 更准确的解释应是：

- **口径已冻结**
- **交接链已基本打通**
- **剩余工作主要是 presentation-day 的 UI/板侧人工核对与最终彩排确认**

---

## 4. 建议后续动作顺序

如果继续做本地可闭环工作，优先级建议是：

1. 给任务板里这些 Demo 项统一加上“`docs frozen / pending presentation-day verification`”式说明
2. 已整理 `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`，把 presentation-day 人工核对动作明确化
3. 已补 `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`，供最终彩排后统一回填结果并决定任务板勾选状态
4. 最后如果真要勾完成，再等真实 UI / 板侧彩排结果回填

也就是说，当前最值钱的下一步不是再写更多讲稿，而是把“还差什么确认”写得更像工程收尾条件。

---

## 5. 关联入口

- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_four_act_runbook.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/degraded_demo_plan.md`
- `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md`
