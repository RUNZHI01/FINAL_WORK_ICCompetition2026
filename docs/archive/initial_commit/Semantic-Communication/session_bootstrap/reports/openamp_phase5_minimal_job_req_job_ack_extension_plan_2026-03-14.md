# Phase 5 最小 `JOB_REQ/JOB_ACK` 扩展计划（基于已打通的 `STATUS_REQ/RESP`）

> 日期：2026-03-14  
> 前提：
> - 当前板上 live firmware 已是 `release_v1.4.0` 兼容最小 patch，size `1635728`，SHA-256 `daf889e376a2da8165ddcf0444fcf29182110066eeb82b9aebe3b6f6acd3fcb6`
> - 真实 `STATUS_REQ -> STATUS_RESP` 已在板上打通
> - 本文只定义下一步最小工程计划，不包含实现、部署或刷板

## 1. 第一版先实现什么语义

- 继续复用当前 `rpmsg-openamp-demo-channel`、现有控制帧头和 `release_v1.4.0` 的旧 `rpmsg_endpoint_cb(...)` 路径，不新开 channel，不改 Linux runner 数据面。
- `JOB_REQ` 的第一版只做 **admission / acknowledge**：
  1. Linux 在 `STATUS_RESP` 显示可接收后发送真实二进制 `JOB_REQ`
  2. 从核解析最小 payload 并做少量本地判定
  3. 返回真实二进制 `JOB_ACK`
  4. 若 `ALLOW`，从核仅把内存态更新为“已有 active job”，不在这一版里接 heartbeat watchdog、deadline kill 或 `JOB_DONE`
- `JOB_ACK` 的第一版最小 payload 固定为：
  - `decision`
  - `fault_code`
  - `guard_state`
- 语义边界要写清楚：
  - `JOB_ACK(ALLOW)` = “从核接受这份 job manifest，允许 Linux 启动现有 runner”
  - `JOB_ACK(DENY)` = “从核拒绝这份 job manifest，Linux wrapper 不应启动 runner”
  - 这 **不等于** heartbeat、deadline、safe-stop、JOB_DONE 已接入

## 2. 第一版真实 ACK 必要字段

第一版建议只下沉当前 wrapper 已经稳定产出的字段，避免改 `openamp_control_wrapper.py` 的 manifest/schema：

- 控制头继续承载：`magic`、`version`、`msg_type`、`seq`、`job_id`、`payload_len`、`header_crc32`
- `JOB_REQ` payload 只保留 4 个必要字段：
  - `expected_sha256`
  - `deadline_ms`
  - `expected_outputs`
  - `flags`（由现有 `job_flags` 映射而来）

建议的最小 wire 方向：

- `job_id` 保持在控制头里，不再在 payload 重复
- `expected_sha256` 由 bridge 从现有 64 字符 hex 解码成 32 字节摘要
- `flags` 由 bridge 做枚举映射：
  - `1=payload`
  - `2=reconstruction`
  - `3=smoke`
  - `0=unknown`

第一版不建议让从核依赖这些字段：

- `runner_cmd`
- `variant`
- `heartbeat_interval_sec`
- `output_dir`

这些字段继续只留在 Linux 侧 manifest / trace。

同样先延期，不要为了第一版 ACK 去扩 wrapper 的字段面：

- `input_shape_*`
- `input_dtype`
- `snr_db_x100`
- `payload_crc32`

## 3. 第一版应只做 `ALLOW` 还是做 `ALLOW/DENY`

建议第一版就支持 **两种决策**，但 `DENY` 范围故意收窄。

推荐的最小判定基线：

- `ALLOW` 条件：
  - 当前 guard 处于 `READY`
  - `expected_sha256` 与当前 trusted current 摘要一致
  - `deadline_ms > 0`
  - `expected_outputs` 在允许集合内（当前只需支持 `1` 或 `300`）
  - `flags` 是已知枚举
- `DENY` 条件只先做这几类本地可判定项：
  - guard 不在 `READY`，或已有 `active_job_id`
  - `expected_sha256` 不匹配
  - `deadline_ms == 0`
  - `expected_outputs` 非法
  - `flags` 未知

推荐同时支持 `DENY` 的依据：

- `openamp_control_wrapper.py` 已经原生支持 `decision=DENY`，Linux 侧几乎不用改逻辑
- 这样可以把 bridge 当前的“本地假 `DENY` 保护”替换成真实 firmware-backed `JOB_ACK(DENY)`
- 这些拒绝条件都是小的标量检查，不需要现在就引入 input-shape/SNR 等更大改动

如果只为实验室首探针保底，也可以先接受“known-good manifest 只回 `ALLOW`”作为临时证明；但正式纳入下一阶段里程碑时，仍应以窄范围 `ALLOW/DENY` 为准。

## 4. 与 `openamp_control_wrapper.py` / `openamp_rpmsg_bridge.py` 的最小接线方式

### `openamp_control_wrapper.py`

- 不改 CLI，不改现有 `job_manifest.json` 结构
- 保持现有时序：
  - `STATUS_REQ`
  - `JOB_REQ`
  - 收到 `ALLOW` 后才启动 runner
- 继续复用现有 `normalize_decision()` 逻辑
- 第一版无需把 `runner_cmd` 下沉到从核

结论：wrapper 侧以“**尽量不动**”为原则，第一版不需要重写。

### `openamp_rpmsg_bridge.py`

- 保留当前 `STATUS_REQ` 路径不变
- 在 `--hook-stdin` 模式下新增 `JOB_REQ` 分支：
  - 从 stdin 事件里读现有 wrapper payload
  - 组装最小二进制 `JOB_REQ`
  - 通过同一个 `/dev/rpmsg0` 发出
  - 解析二进制 `JOB_ACK`
  - 向 wrapper stdout 返回一个最终 JSON，至少包含：
    - `decision`
    - `fault_code`
    - `guard_state`
    - `source="firmware_job_ack"`
- 落证文件建议与 `STATUS_REQ` 一致风格：
  - `job_req_tx.bin/.hex/.json`
  - `job_ack_rx.bin/.hex/.json`
  - `bridge_summary.json`
- 仍未实现的 phase（`HEARTBEAT`、`JOB_DONE`、`SAFE_STOP`）继续保留当前本地 deny 保护

结论：Linux 侧最小代码改动应集中在 bridge，wrapper 只复用既有 hook 合同。

## 5. 最小可信的板级成功标准

最小但可信的成功标准建议是：

1. 板仍保持当前 live patched baseline 正常启动，`remoteproc0=running`
2. Linux 通过 bridge 发出真实二进制 `JOB_REQ`
3. 板返回真实二进制 `JOB_ACK`，并满足：
   - `msg_type = 0x02`
   - `seq` 与 `job_id` 匹配请求
   - `decision = ALLOW`
   - `fault_code = 0`
4. **紧接着再做一次 `STATUS_REQ`**，返回的 `STATUS_RESP` 不再是固定占位：
   - `active_job_id = <本次 job_id>`
   - `guard_state` 体现 `JOB_ACTIVE`（或等价的非空闲态）
5. wrapper 从 hook 返回里读到 `decision=ALLOW` 后，只启动一次现有 runner

不要求纳入这一最小成功标准的内容：

- heartbeat watchdog
- deadline 触发停机
- `JOB_DONE`
- `SAFE_STOP`
- 从核执行任何 TVM 数据面逻辑

## 6. 建议的最小落地顺序

1. 先在当前 `release_v1.4.0` 兼容 patch 基础上，为从核补最小 `JOB_REQ/JOB_ACK` 结构、静态 trusted SHA、`active_job_id/guard_state` 内存态。
2. 再扩 `openamp_rpmsg_bridge.py`，让它真实转发 `JOB_REQ` 并解析 `JOB_ACK`。
3. 最后用现有 `openamp_control_wrapper.py --transport hook` 跑一次 known-good wrapper smoke，按第 5 节标准收证。

一句话收敛：

> 下一步不该去重写 wrapper 或数据面，而应在当前已成功的 `STATUS_REQ/RESP` 基线上，补一个“最小但真实”的 `JOB_REQ -> JOB_ACK` admission path，让 Linux 现有 wrapper 能以最小 churn 从“本地假 deny”切到“真实 firmware decision”。
