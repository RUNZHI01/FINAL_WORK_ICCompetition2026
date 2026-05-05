# Phase 5 minimal `SAFE_STOP` 真机闭环打通

> 日期：2026-03-14  
> 目标：记录在 `release_v1.4.0` 兼容控制 patch 基础上，飞腾板上 `SAFE_STOP` 最小闭环已经真实打通的结果。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase5_minimal_heartbeat_impl_2026-03-14.md`
> - `session_bootstrap/reports/openamp_wrapper_hook_board_smoke_success_2026-03-14.md`

## 1. 本轮结论

本轮已经把控制面从“可准入 + 可 heartbeat”继续推进到最小 `SAFE_STOP`：

1. 新 `SAFE_STOP` 版固件已成功构建并部署到板上 live firmware：
   - `size=1647272`
   - `sha256=3e7512fef57b0581afd319aaccd0a3144cf0e08052b30b043c2c87908dfe0424`
2. 板上手工 bring-up 后：
   - `remoteproc0=running`
   - `rpmsg-openamp-demo-channel` 已建立
   - `/dev/rpmsg_ctrl0` 与 `/dev/rpmsg0` 存在
3. 在真机上按顺序发送：
   - `JOB_REQ(ALLOW)`
   - `HEARTBEAT_ACK(heartbeat_ok=1)`
   - `SAFE_STOP`
4. `SAFE_STOP` 返回的 `STATUS_RESP` 已满足预期停机后状态：
   - `guard_state = READY`
   - `active_job_id = 0`
   - `last_fault_code = MANUAL_SAFE_STOP (10)`
   - `heartbeat_ok = 0`
   - `total_fault_count = 1`
5. 再发 follow-up `STATUS_REQ`，返回状态与上面的 stop 后状态一致。

因此，当前最准确的工程结论应更新为：

**OpenAMP 最小控制闭环已经从 admission + heartbeat 进一步推进到 `SAFE_STOP` 真机可用。**

## 2. 板上 live 固件身份

| 项目 | 值 |
| --- | --- |
| live 路径 | `/lib/firmware/openamp_core0.elf` |
| 当前身份 | `release_v1.4.0` + `STATUS_REQ/RESP` + `JOB_REQ/JOB_ACK` + `HEARTBEAT` + `SAFE_STOP` minimal patch |
| 大小 | `1647272` |
| SHA-256 | `3e7512fef57b0581afd319aaccd0a3144cf0e08052b30b043c2c87908dfe0424` |

## 3. 真机探测结果

### 3.1 `JOB_REQ`

收到：
- `decision = 1` (`ALLOW`)
- `fault_code = 0`
- `guard_state = 2` (`JOB_ACTIVE`)

### 3.2 `HEARTBEAT_ACK`

收到：
- `guard_state = 2`
- `heartbeat_ok = 1`

### 3.3 `SAFE_STOP`

发送 `SAFE_STOP(msg_type=0x07, payload_len=0)` 后，返回的 `STATUS_RESP` 为：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `10` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `1` |

### 3.4 follow-up `STATUS_REQ`

再次发 `STATUS_REQ` 后，状态保持一致：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `10` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `1` |

## 4. 为什么这次结果重要

这次不只是又多了一条消息类型，而是证明：

1. 从核不仅能进入 `JOB_ACTIVE`
2. 还能在收到控制面 stop 请求后回到 `READY`
3. 并且这个状态变化是后续 `STATUS_REQ` 可持续观察到的

这说明当前控制面已经从：
- `STATUS_REQ/RESP`
- `JOB_REQ/JOB_ACK`
- `HEARTBEAT/HEARTBEAT_ACK`

进一步推进到了：
- **`SAFE_STOP` 可真实改变运行态**

## 5. 结论边界

这次成功验证的边界仍需写清楚：

1. 已打通的是最小 `SAFE_STOP`：
   - 手工发 stop
   - 从核回 `STATUS_RESP`
   - 状态回到 `READY`
2. 当前还没有：
   - heartbeat watchdog 驱动的自动 stop
   - firmware 主动 `JOB_DONE`
   - `RESET_REQ/ACK` 级别的 fault latch 恢复
3. 但它已经足以说明：
   - **控制面现在不只会“允许开始”，也已经会“明确停止并回到安全状态”。**

## 6. 下一步建议

最自然的下一步已经从 stop 本身转向“自动化与完整收尾”：

1. heartbeat timeout / watchdog 驱动的 stop
2. firmware-backed `JOB_DONE`
3. 必要时再补 `RESET_REQ/ACK`

一句话总结：

> 到这一轮为止，OpenAMP 最小控制闭环已经具备了：状态查询、作业准入、运行心跳、以及安全停止。