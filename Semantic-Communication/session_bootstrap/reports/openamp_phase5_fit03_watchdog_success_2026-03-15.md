# OpenAMP Phase 5 FIT-03 心跳超时 / watchdog 真机验证成功记录

> 日期：2026-03-15  
> 目标：在部署 heartbeat-timeout watchdog 修复后的 live firmware 上，复跑 FIT-03 并确认 `F003` 是否真实出现。
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md`
> - `session_bootstrap/reports/openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410/`

## 1. 本轮结论

`FIT-03` 已在飞腾派真机上验证成功。部署新 live firmware（SHA `2c4240e03deedd2cc6bbd1c7c34abee852aa8f7927a5187a5131659c4ce7878a`）后，按完全相同的探针顺序执行：

1. pre `STATUS_REQ`：`READY / active_job_id=0 / last_fault=0 / heartbeat_ok=0`；
2. `JOB_REQ(ALLOW)`：作业进入 `JOB_ACTIVE`；
3. `HEARTBEAT_ACK(heartbeat_ok=1)`：运行中心跳路径仍正常；
4. 故意停发 heartbeat `5.0 s`；
5. follow-up `STATUS_REQ`：现在返回 `READY / active_job_id=0 / last_fault=HEARTBEAT_TIMEOUT(3) / heartbeat_ok=0 / total_fault_count=1`。

这说明 heartbeat-timeout watchdog 已经真实接入到当前 live firmware，FIT-03 已从之前的“缺口确认”转为正式 PASS。

## 2. 关键证据

来自 `remote_probe.json`：

- `job_req.rx.job_ack.decision = 1`
- `heartbeat.rx.heartbeat_ack.heartbeat_ok = 1`
- `timeout_status.status.last_fault_code = 3`
- `timeout_status.status.active_job_id = 0`
- `timeout_status.status.guard_state = 1`
- `final_status.status.last_fault_code = 3`

## 3. 边界说明

本轮采用的是最小 lazy watchdog 语义：

- 没有新增 wire message
- 没有增加周期性 ISR/task
- timeout 在“下一次入站控制帧”上变得可观测

这已经足以支撑当前答辩/收证层面的 `FIT-03` 要求。

## 4. 当前 P1 状态

至此，P1 三个正式 FIT 的状态全部为：

- `FIT-01`：PASS
- `FIT-02`：PASS
- `FIT-03`：PASS

下一步最值钱的工作已经从“补缺口”转向“汇总证据矩阵与总报告”。
