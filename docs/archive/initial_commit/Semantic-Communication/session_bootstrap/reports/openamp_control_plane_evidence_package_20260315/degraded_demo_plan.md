# OpenAMP 降级 / 兜底 Demo 方案

- purpose: `当 live OpenAMP 互动不稳时，确保答辩仍然完整、可信、可控`
- default_policy: `从一开始就按 evidence-led 设计，live 只是可选加分项`

## 1. 三层模式

| 模式 | 触发条件 | 操作方式 | 是否触板 |
|---|---|---|---|
| L0: Zero-board | 默认模式；任何不确定性存在 | 全程展示既有 evidence package | 否 |
| L1: Board-visible | 板在线，但未做最后人工彩排 | 只展示板已在线的静态窗口或状态截图 | 最多“看见”，不交互 |
| L2: Low-touch live | 板在线、窗口已预置、presentation-day 人工确认稳定 | 仅插入一个低扰动在线确认 | 极低 |

推荐默认选择 `L0`。只有明确确认稳定时，才升级到 `L1/L2`。

## 2. 明确红线

现场不要做这些事：

- 不 reboot
- 不重新走 bring-up
- 不手工 stop/start `remoteproc0`
- 不现场运行新的 wrapper smoke
- 不现场做 `FIT-01/02/03` fault injection
- 不把排障过程展示给评委
- 不把第三幕默认 compare 改写成 baseline live；默认仍是归档 `PyTorch reference`
- 不在第三幕混写除 `1846.9 -> 130.219 ms`、`1850.0 -> 230.339 ms/image` 之外的 demo live / drift 数字
- 不把 `300/300` 的 live reconstruction 收口延伸成 `TC-010` / `RESET_REQ/ACK` 已完成

## 3. 常见异常与切换动作

| 触发情况 | 立即动作 | 改看什么 | 还可以安全主张什么 |
|---|---|---|---|
| 板无法接入或无视频输出 | 直接切到 `L0` | [summary_report.md](summary_report.md) + [coverage_matrix.md](coverage_matrix.md) | 全部当前正式结论 |
| RPMsg 窗口卡住 / 输出不一致 | 10 秒内放弃 live cue | [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md) + [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md) | P0 闭环已落证 |
| wrapper/hook 页面无法打开 | 不解释故障原因，直接跳到 evidence | [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md) | firmware-backed `ALLOW` 已驱动 runner |
| 评委要求“现场打错 SHA” | 拒绝 live fault injection，切到 FIT 证据 | [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md) | `FIT-01` 正式 PASS |
| 评委要求“现场证明 watchdog” | 不做 live timeout 试验，切到 pre/post 两页 | [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) + [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) | `FIT-03` 的 fail -> fix -> pass 历史 |
| 演示时间被压到 5 分钟 | 直接走压缩版 | [summary_report.md](summary_report.md) + [coverage_matrix.md](coverage_matrix.md) + 两份性能报告 | 总判定 + FIT 总表 + 性能定位 |

## 4. 最小生存包

如果现场只能保留 8 个页面，保留这 8 个：

1. [summary_report.md](summary_report.md)
2. [coverage_matrix.md](coverage_matrix.md)
3. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
4. [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md)
5. [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md)
6. [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md)
7. [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)
8. [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)

用这 8 页仍然能讲完整：

- 系统总体结论
- 最近一次 live 板端真实状态（8115 / current / baseline signed sideband / 300/300）
- `TC-002` 已由 live reconstruction 收口、`TC-010` 仍属边界
- 最小控制闭环
- FIT 收口与历史完整性
- 性能价值与系统定位

## 5. 现场切换话术

### 从 L2 切回 L0

> 现场 live 我们不继续展开，因为这套系统的正式结论已经有完整板级证据。  
> 接下来我直接展示 evidence bundle 里的对应页，避免把答辩变成新的实验。

### 面对“为什么不继续试”

> 当前目标是 defense，不是再跑一轮实验。  
> 这套包的价值就在于：即使 live cue 不展开，系统性结论仍然成立，而且证据比现场重做一次更完整。

## 6. 压缩版顺序

如果只剩 3~5 分钟，按下面顺序：

1. [summary_report.md](summary_report.md)：10 秒说总判定
2. [coverage_matrix.md](coverage_matrix.md)：30 秒说 P0/P1 覆盖
3. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md) + [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md)：45 秒把 `8115 / 300/300` 的 live 事实与 `TC-002` / `TC-010` 边界一次讲清
4. [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) + [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)：60 秒讲最关键的 fail -> fix -> pass
5. [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md) + [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)：60 秒只讲两条正式性能口径与 trusted SHA
6. 最后 10 秒讲边界：只主张已收口的最小控制闭环、`FIT-01/02/03`，以及 `TC-002` 已收口 / `TC-010` 未 claim
