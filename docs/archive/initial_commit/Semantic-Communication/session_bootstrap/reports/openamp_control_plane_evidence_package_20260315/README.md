# OpenAMP 控制面证据包索引

- package_date: `2026-03-15`
- package_id: `openamp_control_plane_evidence_package_20260315`
- scope: `release_v1.4.0` 派生最小控制面在飞腾派真机上的答辩 / 演示证据收口
- final_verdict: `P0 milestones verified on board; P1 FIT-01 / FIT-02 / FIT-03 final PASS`
- historical_note: `FIT-03` 明确保留了 pre-fix FAIL -> post-fix PASS 的两阶段证据；`FIT-02` 已补历史 `batch=4` vs `batch=1` 的正式案例卡；`TC-002/010` 已补“live reconstruction 已收口 / sticky reset 仍属边界”的拆分说明

## 答辩最短路径

只看六份文件时，按这个顺序：

1. [summary_report.md](summary_report.md)
2. [coverage_matrix.md](coverage_matrix.md)
3. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
4. [../openamp_demo_dashboard_local_acceptance_20260317.md](../openamp_demo_dashboard_local_acceptance_20260317.md)
5. [../openamp_demo_live_delivery_snapshot_20260317.md](../openamp_demo_live_delivery_snapshot_20260317.md)
6. [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)

## 答辩 / Demo 材料

如果当前任务不是继续补板级实验，而是准备 defense / live demo，优先看下面这些：

1. [demo_materials_index.md](demo_materials_index.md)
2. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
3. [../openamp_demo_dashboard_local_acceptance_20260317.md](../openamp_demo_dashboard_local_acceptance_20260317.md)
4. [../openamp_demo_live_delivery_snapshot_20260317.md](../openamp_demo_live_delivery_snapshot_20260317.md)
5. [demo_four_act_runbook.md](demo_four_act_runbook.md)
6. [defense_talk_outline.md](defense_talk_outline.md)
7. [degraded_demo_plan.md](degraded_demo_plan.md)
8. [../../demo/openamp_control_plane_demo/README.md](../../demo/openamp_control_plane_demo/README.md)
9. [../../scripts/run_openamp_demo.sh](../../scripts/run_openamp_demo.sh)

## 阅读顺序

1. [summary_report.md](summary_report.md)
2. [coverage_matrix.md](coverage_matrix.md)
3. [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md)
4. [../openamp_phase5_release_v1.4.0_status_req_resp_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_status_req_resp_success_2026-03-14.md)
5. [../openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md)
6. [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md)
7. [../openamp_phase5_safe_stop_success_2026-03-14.md](../openamp_phase5_safe_stop_success_2026-03-14.md)
8. [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md)
9. [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md)
10. [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md)
11. [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md)
12. [../openamp_phase5_minimal_heartbeat_timeout_impl_2026-03-15.md](../openamp_phase5_minimal_heartbeat_timeout_impl_2026-03-15.md)
13. [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)
14. [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md)

## 关键证据包根目录

- FIT-01 bundle:
  - [../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md](../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md)
- FIT-02 bundle:
  - [../openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md](../openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md)
  - [../openamp_fit02_batch_contract_case_card_2026-04-03.md](../openamp_fit02_batch_contract_case_card_2026-04-03.md)
- `TC-002/010` defense scope note:
  - [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md)
- FIT-03 pre-fix bundle:
  - [../openamp_heartbeat_timeout_fit_20260315_015841/fit_report_FIT-03.md](../openamp_heartbeat_timeout_fit_20260315_015841/fit_report_FIT-03.md)
- FIT-03 post-fix bundle:
  - [../openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410/fit_report_FIT-03.md](../openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410/fit_report_FIT-03.md)

## 使用边界

这份包只对以下声明负责：

- P0 最小控制面里已完成并已真机落证的里程碑
- P1 里已经完成的 `FIT-01`、`FIT-02`、`FIT-03`

这份包不主张以下尚未收口的能力：

- `FIT-04` / `FIT-05`
- `RESET_REQ/ACK`
- deadline enforcement
- sticky fault reset 流程
