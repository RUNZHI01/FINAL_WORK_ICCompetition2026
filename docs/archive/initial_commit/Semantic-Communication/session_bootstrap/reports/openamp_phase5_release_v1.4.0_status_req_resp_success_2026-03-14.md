# Phase 5 `release_v1.4.0` 基线上的真实 `STATUS_REQ/RESP` 验证成功

> 日期：2026-03-14  
> 目标：记录在真实 `release_v1.4.0` 基线源码上适配最小 patch 后，飞腾板上 `STATUS_REQ -> STATUS_RESP` 控制语义已被真实打通的结果。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md`
> - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
> - `session_bootstrap/reports/openamp_phase5_firmware_delta_classification_2026-03-14.md`
> - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 1. 本轮结论

本轮已经从“transport 已通 / demo echo 可跑”推进到真正的控制协议闭环最小成功：

1. 已在真实 `release_v1.4.0` 源树上应用适配旧 `FRpmsgEchoApp(...)` 结构的最小 `STATUS_REQ/RESP` patch。
2. patched 固件已用官方 10.3 工具链成功构建：
   - `size=1635728`
   - `sha256=daf889e376a2da8165ddcf0444fcf29182110066eeb82b9aebe3b6f6acd3fcb6`
3. 板上 live `/lib/firmware/openamp_core0.elf` 已替换为这份 patched 固件。
4. patched 固件在当前板上可通过官方路径 bring-up：
   - `remoteproc0=running`
   - dmesg 已出现：
     - `Booting fw image openamp_core0.elf, size 1635728`
     - `remote processor homo_rproc is now up`
     - `creating channel rpmsg-openamp-demo-channel`
5. 在 `/dev/rpmsg0` 上发送真实二进制 `STATUS_REQ` 后，板上返回了真实 `STATUS_RESP`，而不是 demo echo。

因此，当前最精确的工程结论应更新为：

**基于 `release_v1.4.0` 的适配 patch，飞腾板上的最小控制协议 `STATUS_REQ -> STATUS_RESP` 已经真实打通。**

## 2. 板上 live patched 固件身份

| 项目 | 值 |
| --- | --- |
| live 路径 | `/lib/firmware/openamp_core0.elf` |
| 当前身份 | `release_v1.4.0` + minimal `STATUS_REQ/RESP` patch |
| 大小 | `1635728` |
| SHA-256 | `daf889e376a2da8165ddcf0444fcf29182110066eeb82b9aebe3b6f6acd3fcb6` |
| toolchain comment | `GNU Toolchain for the A-profile Architecture 10.3-2021.07 (arm-10.29) 10.3.1 20210621` |

这说明当前板上运行的已经不再是纯 demo echo 固件，而是带最小控制语义的 patched 基线固件。

## 3. 真实 `STATUS_REQ` 探测结果

本轮对 `/dev/rpmsg0` 发出的请求帧为：

- `magic = 0x53434F4D`
- `version = 1`
- `msg_type = 8` (`STATUS_REQ`)
- `seq = 1`
- `job_id = 5001`
- `payload_len = 0`

发送十六进制：

```text
4d4f435301000800010000008913000000000000b596bbd7
```

收到返回帧：

```text
4d4f435301000900010000008913000018000000b30819df010000000000000000000000000000000000000000000000
```

解析结果：

- `magic = 0x53434F4D`
- `version = 1`
- `msg_type = 9` (`STATUS_RESP`)
- `seq = 1`
- `job_id = 5001`
- `payload_len = 24`

返回 payload：

| 字段 | 值 |
| --- | ---: |
| `guard_state` | `1` |
| `active_job_id` | `0` |
| `last_fault_code` | `0` |
| `heartbeat_ok` | `0` |
| `sticky_fault` | `0` |
| `total_fault_count` | `0` |

这已经满足“不是 demo echo，而是最小 `STATUS_RESP`”的判断标准。

## 4. 为什么这次结果是实质突破

此前我们只证明到：

- candidate 固件能冷启动
- `remoteproc0` 能起来
- `rpmsg-openamp-demo-channel` 能建立
- `rpmsg-demo` 能回显 `Hello World!`

但那还只是 transport 与 demo service 可用。

本轮不同之处在于：

1. 固件侧已经不再只是 echo callback，而是最小控制帧处理器；
2. Linux 侧发出去的是明确结构化的 `STATUS_REQ` 控制帧；
3. 返回的不是原样 echo，而是解析后可确认为 `STATUS_RESP`；
4. `seq/job_id/payload_len/msg_type` 都满足协议语义。

因此，这次不是“transport 又通了一次”，而是：

**控制协议语义第一次在真实飞腾板上成立。**

## 5. 结论边界

这次成功验证的边界也要写清楚：

1. 已打通的是最小控制语义：`STATUS_REQ -> STATUS_RESP`。
2. 当前 `STATUS_RESP` 仍是最小占位实现：
   - `guard_state=1`
   - 其余字段为 `0`
3. 这不等于：
   - `JOB_REQ/JOB_ACK` 已打通
   - `HEARTBEAT/SAFE_STOP` 已打通
   - fault latch / active job / heartbeat watchdog 已接入真实状态机
4. 但它足以说明：
   - **OpenAMP 从“demo echo transport”正式进入“最小控制协议可用”阶段**。

## 6. 下一步建议

当前最自然的下一步已经不再是继续研究固件版本，而是继续扩最小控制语义：

1. `JOB_REQ -> JOB_ACK`
2. `HEARTBEAT`
3. `SAFE_STOP`
4. 再把 Linux 侧 `openamp_control_wrapper.py` 从 skeleton / hook 推进到真实控制闭环

一句话总结：

> `release_v1.4.0` 作为基线已经足够推进工程；当前最小 `STATUS_REQ/RESP` 已在真机打通，后续重点应转到扩展控制协议与 wrapper 接线，而不是继续做版本收敛。