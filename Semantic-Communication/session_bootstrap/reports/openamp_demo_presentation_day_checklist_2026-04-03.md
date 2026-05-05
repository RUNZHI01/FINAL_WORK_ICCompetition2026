# OpenAMP Demo Presentation-Day 人工核对 Checklist（2026-04-03）

## 用途

这份清单只服务于一件事：

> 在最终答辩 / 演示当天，把当前已经冻结的 docs-first 口径，核对成一个**可上台执行、可诚实降级、可回答追问**的最终版本。

它不是新的设计文档，不新增 claim；它只负责把剩余人工确认动作写清楚。

---

## 0. 使用规则

- 若任一关键项不满足，优先切到 `docs-first / degraded` 路径，不硬上 live。
- 任何不确定项都不靠现场试错解决。
- 本清单默认配合这些文档一起使用：
  - `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
  - `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/degraded_demo_plan.md`

---

## 1. 启动前 GO / NO-GO

### 1.1 环境与入口

- [ ] 使用官方入口启动：`bash ./session_bootstrap/scripts/run_openamp_demo.sh`
- [ ] 页面可正常打开
- [ ] `/api/health` 返回 `{"status":"ok"}`
- [ ] `/api/system-status` 可返回 `operator_cue`
- [ ] 如需读板，已准备正确的 `probe-env`，且只做只读 probe

### 1.2 默认模式判定

- [ ] 若板态、窗口、路径都不稳，直接决定走 `L0 docs-first`
- [ ] 若板在线但未做最终人工彩排，最多走 `L1 board-visible`
- [ ] 只有 presentation-day 已人工确认稳定，才允许 `L2 low-touch live`

### 1.3 红线复述

- [ ] 不 reboot
- [ ] 不 stop/start `remoteproc0`
- [ ] 不把现场排障展示给评委
- [ ] 不现场重打 `FIT-01/02/03`
- [ ] 不把 replay / fallback 讲成 fresh live success

---

## 2. 首屏 / Top-line Status

### 必须看见或能立即指出的字段

- [ ] `8115` 是唯一有效 demo 实例
- [ ] `Current 300 / 300`
- [ ] `PyTorch reference 300 / 300 (archive)`
- [ ] `4-core Linux performance mode` vs `3-core Linux + RTOS demo mode`
- [ ] trusted current SHA 入口可达
- [ ] 第三幕默认 compare 边界可达（默认仍是归档 `PyTorch reference`）

### 首屏口径核对

- [ ] 没有把 `2026-03-17 baseline 300 / 300` 讲成“本场默认 live branch”
- [ ] 没有把 `300 / 300` 讲成 `TC-010 / RESET_REQ/ACK` 已完成
- [ ] 没有把 headline performance 和 live demo mode 混写

---

## 3. 四幕 Operator Flow

### Act 1

- [ ] `Command Center` / `Operator Cue` 正常
- [ ] 会话接入页可用
- [ ] 只读 probe 能跑，或已决定直接走 evidence wording

### Act 2

- [ ] `demo-only` gate preview 能诚实显示 preview-only 边界
- [ ] Current live 若要展示，只在 operator-driven 语义下讲
- [ ] 若 live 不稳，能在 10 秒内切回 evidence / archive 说法

### Act 3

- [ ] 默认 compare 仍停在 `Current vs PyTorch reference archive`
- [ ] 只引用两条正式口径：
  - [ ] `1846.9 -> 130.219 ms`
  - [ ] `1850.0 -> 230.339 ms/image`
- [ ] 不混写 drift / degraded-board 数字
- [ ] 如被追问 test-case，只把 `300 / 300` 解释成 `TC-002` 收口

### Act 4

- [ ] 若时间不足，可直接不做 live fault，而改看 FIT 证据页
- [ ] 若展示 fault 面板，必须明确 replay/live 边界
- [ ] `SAFE_STOP` 只讲 mirror / control surface，不讲 Linux 物理所有权

---

## 4. 追问口径核对

- [ ] `TC-002`：已由 live reconstruction `300 / 300` 收口
- [ ] `TC-010`：仍属 `RESET_REQ/ACK` / sticky fault reset 边界，不在当前正式 claim
- [ ] `FIT-01/02/03`：可 claim
- [ ] `FIT-04/05`：不可 claim
- [ ] `RESET_REQ/ACK`：不可 claim 为已闭环
- [ ] OpenAMP：不可讲成性能加速来源

---

## 5. 降级切换

### 发生以下任一情况时，直接降级

- [ ] 板无法接入
- [ ] RPMsg / probe 输出异常
- [ ] Current live 不稳
- [ ] compare viewer 上下文不完整
- [ ] safety panel 明显不一致

### 降级后还要能讲什么

- [ ] 总判定：`P0 已板级闭环；P1 FIT-01 / FIT-02 / FIT-03 最终 PASS`
- [ ] `8115 / current 300 / 300 / baseline 300 / 300`
- [ ] `TC-002` 已收口、`TC-010` 未 claim
- [ ] 两条正式性能口径
- [ ] `FIT-03 fail -> fix -> pass`

---

## 6. 结束前最终确认

- [ ] 今天对外所有说法都没有超出已冻结口径
- [ ] 所有 live / archive / replay / degraded 分支都被诚实标注
- [ ] 如果最终未做 low-touch live，仍然可以完整走完 docs-first defense
- [ ] 若要在任务板中把某项改成完成，必须基于今天真实 UI / 板侧彩排结果，而不是纯文档推断

---

## 7. 建议现场携带的最小文档组

1. `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
2. `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
3. `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
4. `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_four_act_runbook.md`
5. `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/degraded_demo_plan.md`
6. `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md`
7. `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`

## 8. 彩排后如何回填

完成最终彩排后，直接使用：

- `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`

来记录：

- 实际 chosen mode（`L0/L1/L2`）
- 首屏字段是否齐全
- 四幕是否稳定走通
- 是否只能 docs-first 上台
- 哪些任务板项可以正式勾完成
