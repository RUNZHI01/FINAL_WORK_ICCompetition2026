# Phase 5 minimal `JOB_DONE` 真机闭环打通

> 日期：2026-03-15  
> 目标：记录在 `release_v1.4.0` 兼容控制 patch 基础上，飞腾板上 `JOB_DONE` 最小闭环已经真实打通的结果。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_safe_stop_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_wrapper_hook_board_smoke_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase5_minimal_job_done_impl_2026-03-15.md`

## 1. 本轮结论

本轮已经把控制面从“可准入 + 可 heartbeat + 可 safe stop”继续推进到最小 `JOB_DONE`：

1. 新 `JOB_DONE` 版固件已成功构建并部署到板上 live firmware：
   - `size=1649896`
   - `sha256=afa9679f24f0d9d4ccd4c35e0c779e72573bfe839799d7f95586706977b23803`
2. fresh boot 后经手工 bring-up：
   - `remoteproc0=running`
   - `rpmsg-openamp-demo-channel` 已建立
   - `/dev/rpmsg_ctrl0` 与 `/dev/rpmsg0` 存在
3. 在真机上按顺序发送：
   - 初始 `STATUS_REQ`
   - `JOB_REQ(ALLOW)`
   - `HEARTBEAT_ACK(heartbeat_ok=1)`
   - `JOB_DONE(success)`
4. `JOB_DONE` 返回的 `STATUS_RESP` 已满足预期 done 后状态：
   - `guard_state = READY`
   - `active_job_id = 0`
   - `last_fault_code = NONE`
   - `heartbeat_ok = 0`
   - `total_fault_count = 0`
5. 再发 follow-up `STATUS_REQ`，返回状态与上面的 done 后状态一致。

因此，当前最准确的工程结论应更新为：

**OpenAMP 最小控制闭环已经从 admission + heartbeat + safe stop，进一步推进到 `JOB_DONE` 真机可用。**

## 2. 板上 live 固件身份

| 项目 | 值 |
| --- | --- |
| live 路径 | `/lib/firmware/openamp_core0.elf` |
| 当前身份 | `release_v1.4.0` + `STATUS_REQ/RESP` + `JOB_REQ/JOB_ACK` + `HEARTBEAT` + `SAFE_STOP` + `JOB_DONE` minimal patch |
| 大小 | `1649896` |
| SHA-256 | `afa9679f24f0d9d4ccd4c35e0c779e72573bfe839799d7f95586706977b23803` |

## 3. 真机探测结果

### 3.1 初始 `STATUS_REQ`

初始 fresh-boot + bring-up 后：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `0` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `0` |

### 3.2 `JOB_REQ`

收到：
- `decision = 1` (`ALLOW`)
- `fault_code = 0`
- `guard_state = 2` (`JOB_ACTIVE`)

### 3.3 `HEARTBEAT_ACK`

收到：
- `guard_state = 2`
- `heartbeat_ok = 1`

### 3.4 `JOB_DONE(success)`

发送固定 16-byte `JOB_DONE` payload：
- `result_code = 0`
- `output_count = 1`
- `result_crc32 = 0`
- `reserved = 0`

返回的 `STATUS_RESP` 为：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `0` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `0` |

### 3.5 follow-up `STATUS_REQ`

再次发 `STATUS_REQ` 后，状态保持一致：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `0` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `0` |

## 4. 为什么这次结果重要

这次证明了：

1. 从核不仅能进入 `JOB_ACTIVE`
2. 还能在收到完成上报后清理 active job
3. 并且这个 done 后状态是后续 `STATUS_REQ` 可持续观察到的

这说明当前控制面已经从：
- `STATUS_REQ/RESP`
- `JOB_REQ/JOB_ACK`
- `HEARTBEAT/HEARTBEAT_ACK`
- `SAFE_STOP`

进一步推进到了：
- **`JOB_DONE` 可真实改变并稳定保持运行后状态**

## 5. 结论边界

这次成功验证的边界仍需写清楚：

1. 已打通的是最小 `JOB_DONE`：
   - Linux 发 `JOB_DONE(success)`
   - 从核回 `STATUS_RESP`
   - 状态回到 `READY`
2. 当前还没有：
   - 基于 `output_count/result_crc32` 的严格校验
   - `FAULT_REPORT`
   - `FAULT_LATCHED` / `RESET_REQ` 级故障恢复
3. 但它已经足以说明：
   - **控制面现在已经具备：准入、心跳、停止、完成 四个最小闭环。**

## 6. 下一步建议

最自然的下一步已经从“消息类型打通”转向“收口与强化”：

1. 真实 `DENY` 场景系统化收证
2. heartbeat watchdog 驱动的自动 `SAFE_STOP`
3. 必要时再补 `RESET_REQ/ACK` 或 `FAULT_REPORT`

一句话总结：

> 到这一轮为止，OpenAMP 最小控制闭环已经具备了：状态查询、作业准入、运行心跳、安全停止、作业完成。