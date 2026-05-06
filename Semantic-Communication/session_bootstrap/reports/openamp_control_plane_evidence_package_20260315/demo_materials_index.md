# OpenAMP 控制面材料索引

- package_date: `2026-03-15`
- package_id: `openamp_control_plane_evidence_package_20260315`
- default_mode: `evidence-first`
- live_policy: `板卡在线时仅作为状态验证，正式结论以复现脚本和记录证据为准`

## 主索引

| 文档 | 类别 | 内容 |
|---|---|---|
| [summary_report.md](summary_report.md) | 总览 | 控制面证据链、最终状态和边界 |
| [coverage_matrix.md](coverage_matrix.md) | 覆盖矩阵 | P0/P1 项目和证据映射 |
| [demo_four_act_runbook.md](demo_four_act_runbook.md) | 证据说明 | OpenAMP 控制面、FIT 和性能证据关系 |
| [degraded_demo_plan.md](degraded_demo_plan.md) | 离线验证 | 无板卡时可核验内容与边界 |
| [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md) | live 记录 | 8115 实例 current / baseline 最近一次真机结果 |
| [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md) | 板级状态 | cold boot、remoteproc、RPMsg demo 路径 |
| [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md) | 控制闭环 | `JOB_DONE` 后状态收敛记录 |
| [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) | FIT 记录 | heartbeat watchdog 修复后验证 |
| [../../../../board_deps/README.md](../../../../board_deps/README.md) | 板端依赖 | 板端 runtime、模型、输入和 CLI smoke 说明 |

## 复现入口

| 目标 | 入口 |
|---|---|
| 无板卡 Docker 复现 | `docker/repro.sh` / `docker/repro.ps1` |
| 原生 Electron 窗口 | `docker/run-demo.sh` / `docker/run-demo.ps1` / `docker/run-demo-wslg-tailscale.ps1` |
| 板端三路性能复现 | `docker/run-board-cli-smoke.sh` / `docker/run-board-cli-smoke.ps1` |

## 边界

本索引只列出评审复现需要的材料。与现场展示流程、临时操作策略、内部排练记录相关的内容不纳入交付材料。
