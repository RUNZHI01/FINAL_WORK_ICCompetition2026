# OpenAMP Demo 文档收尾总览（2026-04-03）

## 这份文档是干什么的

这不是新的设计稿，也不是新的 claim。

它的作用只有一个：

> 把 2026-04-03 这轮围绕 OpenAMP Demo / 答辩 / presentation-day 收尾补出来的文档链，压成一个可直接交接的入口。

如果后面有人要接手彩排、做最终人工核对、或者决定任务板哪些项能勾完成，先看这一页就够了。

---

## 1. 今天这轮实际收口了什么

### A. 口径冻结

已经固定下来的核心口径：

- 第三幕默认 compare 仍是归档 `PyTorch reference`
- 第三幕正式只引用两条性能口径：
  - `1846.9 -> 130.219 ms`
  - `1850.0 -> 230.339 ms/image`
- `8115 / 300 / 300` 只用于 `TC-002` live reconstruction 收口
- `TC-010` / `RESET_REQ/ACK` / sticky fault reset 仍不在当前正式 claim 内
- `4-core Linux performance mode` 与 `3-core Linux + RTOS demo mode` 必须继续分开讲

### B. 文档链打通

今天已经把这些层都接上了：

- 四幕 runbook / defense outline
- 72 秒脚本 / cheat sheet / operator runbook
- degraded fallback
- top-line acceptance
- readiness / QA / delivery index
- presentation-day checklist
- rehearsal go/no-go template
- README / demo materials index / 任务板入口

### C. 任务板解释被拆清楚了

当前任务板里还没勾掉的 Demo 项，不再应该理解为“口径还没定”，而应理解为：

- `docs frozen`
- `pending presentation-day verification`

---

## 2. 最值得看的 6 份文档

如果只看最关键的 6 份，按这个顺序：

1. `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
   - 看“第三幕到底怎么讲”
2. `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
   - 看“首屏到底怎样才算合格”
3. `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
   - 看“`TC-002` / `TC-010` 到底怎么 claim”
4. `session_bootstrap/reports/openamp_demo_open_items_split_2026-04-03.md`
   - 看“哪些是文档已冻结，哪些还真要靠彩排验证”
5. `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`
   - 看“presentation-day 到底要核对什么”
6. `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`
   - 看“彩排完怎么回填、怎么判 GO / NO-GO、怎么改任务板”
7. `session_bootstrap/reports/openamp_demo_task_completion_gate_matrix_2026-04-03.md`
   - 看“任务板里哪些 Demo 项满足什么条件才允许勾完成”

---

## 3. 对后续接手者的最短路径

### 如果你现在要准备上台 / 彩排

按这个顺序：

1. 先读 `openamp_demo_presentation_day_checklist_2026-04-03.md`
2. 再读 `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`
3. 遇到口径问题时，再回查：
   - `openamp_demo_video_script_alignment_2026-04-03.md`
   - `openamp_demo_topline_acceptance_note_2026-04-03.md`
   - `openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

### 如果你现在要决定任务板能不能勾完成

按这个顺序：

1. 先看 `openamp_demo_open_items_split_2026-04-03.md`
2. 再按 `openamp_demo_presentation_day_checklist_2026-04-03.md` 做真实核对
3. 最后用 `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` 回填结果

---

## 4. 当前仍然不是文档能替代的东西

今天这轮文档收口已经做到了“口径统一 + 入口打通 + 彩排模板就绪”。

但以下事情，仍然必须靠真实演示环境来决定：

- 首屏字段是否在最终 build 中稳定露出
- 四幕是否能在 presentation-day 版本上顺畅走完
- 三个 fault 入口是否在最终 UI 中形成诚实、可操作的体验
- 最终是否能上 `L2 low-touch live`，还是只能 `GO_WITH_DOCS_FIRST_ONLY`

也就是说：

> **文档链已经基本收完；下一阶段真正高价值的动作，是拿这套 checklist + template 去接真实彩排。**

---

## 5. 入口回链

- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_materials_index.md`
- `session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md`
- `session_bootstrap/README.md`
- `session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md`
- `session_bootstrap/tasks/赛题对齐执行追踪板_2026-03-13.md`
