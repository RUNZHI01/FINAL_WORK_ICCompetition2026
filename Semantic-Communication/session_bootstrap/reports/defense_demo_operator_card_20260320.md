# 飞腾杯答辩 Demo Operator Card（2026-03-20）

- 用途：今晚上台前最后 1 页操作卡
- 默认策略：`docs-first`，live 只做低扰动加分，不做现场试错
- 主持人口径：先讲系统定位，再讲双模式，再讲性能和安全

## 今晚台上默认展示顺序

1. 先讲一句定位：`不是 generic TVM 项目，而是飞腾多核弱网安全语义视觉回传系统`
2. 再讲双模式：`4-core Linux performance mode` vs `3-core Linux + RTOS demo mode`
3. 性能页只说 `484.183 / 231.522 / 134.617 / +56.077%`
4. Demo 页默认只说：`Current 数据面在线推进`、`PyTorch reference archive 300/300`、`OpenAMP 负责 control plane / safety`；如果被问 test-case 编号，只把这页当 `TC-002` 的 live reconstruction 收口
5. 安全页只说 OpenAMP 控制闭环和 `FIT-01/02/03`

## 台上可以展示什么

- 已做好的 deck 页
- `openamp_demo_live_dualpath_status_20260317.md` 的 `8115 + 300/300 + signed sideband` 结论
- 已开好的 dashboard / snapshot 静态页
- `summary_report.md` 的总判定
- `coverage_matrix.md` 的 `P0 PASS` 与 `FIT-01/02/03 PASS`

## 台上不要展示什么

- 任何 reboot / bring-up / SSH 重连过程
- 手工 stop/start `remoteproc0`
- 新的 wrapper smoke 或新的 fault injection
- 实时排障、滚日志找原因、切终端试命令
- 把 `RESET_REQ/ACK` / sticky fault reset 讲成当前正式 claim
- `347.375 / 295.255 / 239.233` 这组 drift 数字，除非评委追问板态风险
- `363.687`、`1891.9` 这类 live demo run median，避免和 headline performance 混写

## 台上该说的数字

- 性能模式：`PyTorch 484.183 ms/image`，`TVM serial current 231.522 ms/image`，`pipeline current 134.617 ms/image`，`same-run uplift +56.077%`
- Demo 模式：`8115 是唯一有效 demo 实例`，`current live 300/300`，`PyTorch reference archive 300/300`
- 模式边界：`remoteproc0=running` 时 Linux 在线核 `0-3 -> 0-2`，所以 demo mode 是 `3-core Linux + RTOS`

## 绝对不要说的句子

- `OpenAMP 让 TVM 更快`
- `所有数字都来自同一种 operating mode`
- `demo mode 也是完整 4-core Linux`
- `第三幕这些 live 数字就是 headline performance`
- `我们现场再打一遍 FIT 给您看`
- `TC-010 也已经靠 300/300 一起收口了`

## 备份窗口

- 主窗口 1：`session_bootstrap/reports/defense_talk_track_2min_20260320.md`
- 主窗口 1b：`session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- 主窗口 1c：`session_bootstrap/reports/defense_ppt_pages_1_5_cn_20260405.md`
- 主窗口 1d：`session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- 主窗口 1e：`session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- 主窗口 1f：`session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- 主窗口 1g：`session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- 主窗口 1h：`session_bootstrap/reports/defense_rehearsal_checklist_20260405.md`
- 主窗口 1i：`session_bootstrap/reports/defense_day_onepage_index_20260405.md`
- 主窗口 1j：`session_bootstrap/reports/defense_materials_bundle_readme_20260405.md`
- 主窗口 1k：`session_bootstrap/reports/defense_dual_role_coordination_card_20260405.md`
- 主窗口 2：`session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- 主窗口 3：`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- 主窗口 4：`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- 主窗口 5：`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`

## 追问时跳转到哪里

| 评委追问 | 立刻打开 |
|---|---|
| 这些性能数字从哪来 | `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md` |
| 为什么要分两种 mode | `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md` + `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log` |
| OpenAMP 是不是只会 echo | `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md` + `session_bootstrap/reports/openamp_wrapper_hook_board_smoke_success_2026-03-14.md` |
| 最新 live 还有没有板级事实 | `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md` + `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md` |
| `TC-002/010` 现在到底怎么讲 | `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md` + `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md` |
| FIT 怎么证明不是口头承诺 | `session_bootstrap/reports/openamp_phase5_fit01_wrong_sha_success_2026-03-15.md` + `session_bootstrap/reports/openamp_phase5_fit02_input_contract_success_2026-03-15.md` + `session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md` + `session_bootstrap/reports/openamp_phase5_fit03_watchdog_success_2026-03-15.md` |

## 现场失稳时的 10 秒切换话术

“现场 live 我们不继续展开，因为这套系统的正式结论已经有完整板级证据。下面我直接切到对应 evidence 页面，避免把答辩变成新的实验。”
