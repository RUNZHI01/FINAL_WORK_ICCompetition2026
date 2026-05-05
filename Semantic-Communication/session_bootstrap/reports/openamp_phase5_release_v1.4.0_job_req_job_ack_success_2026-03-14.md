# Phase 5 `release_v1.4.0` 基线上的真实 `JOB_REQ/JOB_ACK` 验证成功

> 日期：2026-03-14  
> 目标：记录在 `release_v1.4.0` 兼容最小控制 patch 基础上，飞腾板上 `JOB_REQ -> JOB_ACK` admission path 已经真实打通，并且后续 `STATUS_RESP` 已能反映非空闲状态。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_status_req_resp_success_2026-03-14.md`
> - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
> - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 1. 本轮结论

本轮已经把 OpenAMP 控制闭环从最小 `STATUS_REQ/RESP` 进一步推进到最小 `JOB_REQ/JOB_ACK`：

1. 新 `JOB_ACK` 版固件已成功构建并部署到板上 live firmware 位：
   - `size=1640048`
   - `sha256=98ab501c1e71f9e1d20013a7ccf7ee83c2289a423d08bdb371dbf0171f48647e`
2. 在当前固件上，手工 `sudo /home/user/open-amp/set_env.sh` 后：
   - `remoteproc0=running`
   - `rpmsg-openamp-demo-channel` 已建立
   - `/dev/rpmsg_ctrl0` 与 `/dev/rpmsg0` 存在
3. 通过 `/dev/rpmsg0` 发出的真实二进制 `JOB_REQ`，已收到真实二进制 `JOB_ACK`。
4. 紧接着再次发 `STATUS_REQ`，返回的 `STATUS_RESP` 已不再是固定空闲占位，而是反映了本次作业授权后的非空闲状态。

因此，当前最准确的工程结论应更新为：

**`release_v1.4.0` 基线上的最小 admission path `JOB_REQ -> JOB_ACK(ALLOW)` 已在飞腾板上真实打通，并且 `STATUS_RESP` 已能反映 `JOB_ACTIVE + active_job_id`。**

## 2. 板上 live patched 固件身份

| 项目 | 值 |
| --- | --- |
| live 路径 | `/lib/firmware/openamp_core0.elf` |
| 当前身份 | `release_v1.4.0` + `STATUS_REQ/RESP` + `JOB_REQ/JOB_ACK` minimal patch |
| 大小 | `1640048` |
| SHA-256 | `98ab501c1e71f9e1d20013a7ccf7ee83c2289a423d08bdb371dbf0171f48647e` |

## 3. 真实 `JOB_REQ` 探测结果

本轮发出的真实 `JOB_REQ` 为：

- `msg_type = 0x01` (`JOB_REQ`)
- `seq = 1`
- `job_id = 9001`
- `payload_len = 44`
- payload 含：
  - `expected_sha256 = 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
  - `deadline_ms = 60000`
  - `expected_outputs = 1`
  - `flags = 3` (`smoke`)

发送十六进制：

```text
4d4f43530100010001000000292300002c000000ad3b27916f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc160ea00000100000003000000
```

收到的真实 `JOB_ACK`：

```text
4d4f43530100020001000000292300000c00000048b1744d010000000000000002000000
```

解析结果：

- `msg_type = 0x02` (`JOB_ACK`)
- `seq = 1`
- `job_id = 9001`
- `payload_len = 12`
- payload：
  - `decision = 1` (`ALLOW`)
  - `fault_code = 0`
  - `guard_state = 2` (`JOB_ACTIVE`)

这已经满足“不是 echo、不是本地假 ACK，而是真实 firmware-backed `JOB_ACK(ALLOW)`”的判定标准。

## 4. follow-up `STATUS_REQ` 结果

在收到 `JOB_ACK` 之后，继续对同一个 `job_id=9001` 发 `STATUS_REQ`：

```text
4d4f4353010008000200000029230000000000009b060ba2
```

收到的 `STATUS_RESP`：

```text
4d4f4353010009000200000029230000180000009d98a9aa020000002923000000000000010000000000000000000000
```

解析结果：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `2` |
| `active_job_id` | `9001` |
| `last_fault_code` | `0` |
| `heartbeat_ok` | `1` |
| `sticky_fault` | `0` |
| `total_fault_count` | `0` |

这一步非常关键，因为它说明：

- `JOB_ACK(ALLOW)` 不是一次性回包而已
- 从核内部状态已经发生了可观测变化
- Linux 侧后续可以通过 `STATUS_REQ` 观察 admission 结果

## 5. 为什么这次结果是实质突破

此前我们已经证明：

- `STATUS_REQ -> STATUS_RESP` 已打通

但那时还不能说明：

- Linux 发起作业请求后，从核会不会真正做 admission decision
- wrapper 有没有可能接入真实 firmware decision

本轮的实质突破是：

1. 从核已能解析真实 `JOB_REQ`
2. 从核已能返回真实 `JOB_ACK(ALLOW)`
3. 从核已能把 `active_job_id` / `guard_state` 更新成非空闲态
4. Linux 侧可以通过 follow-up `STATUS_REQ` 读到这个状态变化

所以当前工程阶段已经从：

- “状态查询可用”

推进到：

- “最小作业授权可用”

## 6. 结论边界

这次成功验证的边界仍然需要写清楚：

1. 已打通的是最小 admission path：`JOB_REQ -> JOB_ACK(ALLOW)`。
2. 当前还**没有**证明：
   - `JOB_DONE`
   - `HEARTBEAT watchdog`
   - `SAFE_STOP`
   - deadline 超时强制停机
   - 真实 TVM 数据面与从核状态机联动
3. 但它已经足以说明：
   - **Linux wrapper 不再只能依赖本地假 `DENY` 保护；现在已经具备接入真实 firmware decision 的基础。**

## 7. 下一步建议

最自然的下一步已经不是版本问题，而是继续扩控制闭环：

1. `HEARTBEAT`
2. `SAFE_STOP`
3. `JOB_DONE`
4. 再把 `openamp_control_wrapper.py --transport hook` 接到真实 `JOB_REQ/JOB_ACK` 路径上，替换当前本地 skeleton ACK

一句话总结：

> 现在 OpenAMP 已经不只是“transport 通”，也不只是“状态查询通”，而是已经进入“最小作业授权闭环可用”阶段。