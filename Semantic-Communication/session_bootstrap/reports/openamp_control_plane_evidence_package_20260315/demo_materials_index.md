# OpenAMP 答辩 / Demo 材料索引

- package_date: `2026-03-15`
- package_id: `openamp_control_plane_evidence_package_20260315`
- default_mode: `offline-first, evidence-led`
- live_policy: `live 只做低扰动确认；没有最终人工彩排确认时，默认不用板`
- source_of_truth:
  - [README.md](README.md)
  - [summary_report.md](summary_report.md)
  - [coverage_matrix.md](coverage_matrix.md)
  - [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
  - [../openamp_demo_dashboard_local_acceptance_20260317.md](../openamp_demo_dashboard_local_acceptance_20260317.md)
  - [../openamp_demo_live_delivery_snapshot_20260317.md](../openamp_demo_live_delivery_snapshot_20260317.md)
  - [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md)

## 使用原则

1. 默认把这套材料当作**证据驱动的答辩包**，而不是现场重新做一轮板级实验。
2. `Act 1` 和 `Act 2` 可以在**板已在线且状态稳定**时做低扰动 live cue；`Act 3` 默认只展示既有 FIT 证据，不做现场 fault injection。
3. 不主张任何超出证据包边界的能力：`FIT-04/05`、`RESET_REQ/ACK`、deadline enforcement、sticky fault reset 仍是 out of scope。
4. 对外统一定位为**飞腾多核弱网安全语义视觉回传系统**，不要把 demo 讲回 generic TVM/MNN optimization project。
5. headline performance 只引用 `4-core Linux performance mode`；OpenAMP live cue 一律解释为 `3-core Linux + RTOS demo mode`。
6. OpenAMP 当前负责的是 control plane / safety / admission / heartbeat / SAFE_STOP，不宣称它直接带来数据面 speedup。

## 主文档分工

| 文档 | 用途 | 推荐模式 |
|---|---|---|
| [demo_four_act_runbook.md](demo_four_act_runbook.md) | 四幕演示脚本、操作顺序、每幕话术与证据落点 | 主文档 |
| [defense_talk_outline.md](defense_talk_outline.md) | PPT 页结构 + speaking outline + 高频问答口径 | 讲稿 / 做页 |
| [degraded_demo_plan.md](degraded_demo_plan.md) | live 不稳时的降级策略、时间压缩版与红线 | 兜底文档 |
| [../openamp_demo_video_script_alignment_2026-04-03.md](../openamp_demo_video_script_alignment_2026-04-03.md) | 72 秒脚本 / cheat sheet / operator runbook 的统一口径说明 | 视频脚本收口 |
| [../openamp_demo_topline_acceptance_note_2026-04-03.md](../openamp_demo_topline_acceptance_note_2026-04-03.md) | 首屏 / top-line status 的 docs-first 验收标准 | 首屏验收 |
| [../openamp_demo_presentation_day_checklist_2026-04-03.md](../openamp_demo_presentation_day_checklist_2026-04-03.md) | presentation-day 的 GO/NO-GO、四幕核对与降级切换清单 | 彩排清单 |
| [../openamp_demo_rehearsal_go_nogo_template_2026-04-03.md](../openamp_demo_rehearsal_go_nogo_template_2026-04-03.md) | 彩排结束后的结果回填与任务板勾选模板 | 回填模板 |
| [../openamp_demo_docs_closure_summary_2026-04-03.md](../openamp_demo_docs_closure_summary_2026-04-03.md) | April 3 这轮 Demo 文档收尾链的单页交接总览 | 总入口 |
| [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md) | `TC-002` 已收口 / `TC-010` 仍属边界的正式说明 | 边界口径 |
| [../../demo/openamp_control_plane_demo/README.md](../../demo/openamp_control_plane_demo/README.md) | 集成 dashboard 软件说明、启动命令与 live probe 边界 | 软件入口 |
| [../../scripts/run_openamp_demo.sh](../../scripts/run_openamp_demo.sh) | 本地启动集成 OpenAMP demo UI | 启动器 |

## 最短准备路径

如果答辩前只剩 10 分钟，按这个顺序打开：

1. [demo_four_act_runbook.md](demo_four_act_runbook.md)
2. [../openamp_demo_topline_acceptance_note_2026-04-03.md](../openamp_demo_topline_acceptance_note_2026-04-03.md)
3. [../openamp_demo_presentation_day_checklist_2026-04-03.md](../openamp_demo_presentation_day_checklist_2026-04-03.md)
4. [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md)
5. [../openamp_demo_video_script_alignment_2026-04-03.md](../openamp_demo_video_script_alignment_2026-04-03.md)
6. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
7. [degraded_demo_plan.md](degraded_demo_plan.md)
8. [summary_report.md](summary_report.md)
9. [coverage_matrix.md](coverage_matrix.md)
10. [../../scripts/run_openamp_demo.sh](../../scripts/run_openamp_demo.sh)

## 四幕与证据映射

| Act | 目标 | 主证据 |
|---|---|---|
| Act 1 | trusted boot / board-online / control-plane online | [summary_report.md](summary_report.md) / [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md) / [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md) |
| Act 2 | 最小控制闭环能力 | [coverage_matrix.md](coverage_matrix.md) / [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md) / [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md) |
| Act 3 | 正式 FIT 证据 | [coverage_matrix.md](coverage_matrix.md) / [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md) / [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md) / [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) / [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) |
| Act 4 | 性能结果 + 安全可靠定位 | [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md) / [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md) / [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md) |

## 建议开场口径

> 今天这套 OpenAMP 演示以既有真机证据为主，不在现场做破坏性 bring-up 或 fault injection。  
> live 部分如果出现，只做已经在线系统的低扰动确认；正式结论以证据包为准。

## 结束口径

> 这轮已经 demo-ready 的，是一套有统一索引、四幕叙事、FIT 收口与性能定位的 defense package；  
> 还需要 presentation-day 人工最终确认的，只是“是否加一个低扰动 live cue”，而不是重新验证系统是否成立。
