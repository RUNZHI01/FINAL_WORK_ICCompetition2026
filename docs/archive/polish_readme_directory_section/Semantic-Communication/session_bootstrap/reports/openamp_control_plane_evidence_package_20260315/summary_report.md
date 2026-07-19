# OpenAMP 控制面证据总报告

- recorded_at: `2026-03-15T03:20:00+0800`
- package_id: `openamp_control_plane_evidence_package_20260315`
- scope: `release_v1.4.0 派生最小控制面在飞腾派真机上的控制闭环与正式 FIT 验证记录`
- primary_matrix: [coverage_matrix.md](coverage_matrix.md)
- latest_live_status: [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
- final_verdict: `P0 已板级闭环；P1 FIT-01 / FIT-02 / FIT-03 最终均为 PASS`

## 执行摘要

当前仓库保留了一组 OpenAMP 控制面证据链。底座方面，`release_v1.4.0` 派生控制固件已经在飞腾派真实板上依次打通 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT/HEARTBEAT_ACK`、`SAFE_STOP`、`JOB_DONE`，并由 wrapper-backed board smoke 证明 Linux wrapper 会基于真实 firmware `JOB_ACK(ALLOW)` 放行 runner。

风险收口方面，`FIT-01` 与 `FIT-02` 已分别证明错误 SHA 和输入契约违规会在 admission gate 被真机拒绝；`FIT-03` 保留了完整历史链条，即旧 live firmware 先真实暴露 watchdog 缺口，随后在部署 heartbeat-timeout watchdog 修复固件后，以同一探针顺序复跑转为 PASS。

最近一轮 live 事实见 [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)。该记录确认 `8115` 是当前有效 demo 实例，current 已成功跑通，baseline 也已通过 signed sideband 进入真机执行，两侧 reconstruction 均完成 `300/300`。

## 最终状态

| Area | Verdict | Primary Evidence |
|---|---|---|
| P0 最小控制闭环 | PASS | [coverage_matrix.md](coverage_matrix.md) |
| P1 正式 FIT | `FIT-01 PASS / FIT-02 PASS / FIT-03 PASS` | [coverage_matrix.md](coverage_matrix.md) |
| FIT-03 历史完整性 | 保留 `pre-fix FAIL -> post-fix PASS`，未擦除旧 live firmware 的真实缺口 | [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) / [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) |

## FIT-02 输入契约说明

历史记录中曾出现 `batch=4` 与模型固定 `batch=1` 不匹配导致的 runtime 失败。当前证据包将其归入输入契约风险：mock 层保留原始 `batch=4` 样本，真机层通过 `expected_outputs=2 -> ILLEGAL_PARAM_RANGE` 证明同类契约 / 计数违规已经被前移到 admission gate。

当前板级协议没有单独暴露 literal `batch` 字段；已有真机证据证明的是同类输入契约违规会被 admission gate 拒绝，且 runner 未启动。

## FIT-03 历史说明

`FIT-03` 保留两段历史：

- old live firmware 阶段：停发 heartbeat `5.0 s` 后板子仍保持 `JOB_ACTIVE`，说明 watchdog 缺口客观存在。
- watchdog-fix firmware 阶段：新 live firmware SHA 为 `2c4240e03deedd2cc6bbd1c7c34abee852aa8f7927a5187a5131659c4ce7878a`；同一探针顺序复跑后，follow-up `STATUS_RESP` 变为 `READY / HEARTBEAT_TIMEOUT(F003)`。

这条历史用于说明缺口确认、修复和复验过程。

## 边界

这份总结包只覆盖当前已经完成并已真机落证的 OpenAMP 控制面能力：

- P0 最小控制闭环里已经通过的里程碑
- P1 里已经正式收口的 `FIT-01`、`FIT-02`、`FIT-03`

这份包不声明以下能力已经完成：

- `FIT-04`
- `FIT-05`
- `RESET_REQ/ACK`
- deadline enforcement
- sticky fault reset
