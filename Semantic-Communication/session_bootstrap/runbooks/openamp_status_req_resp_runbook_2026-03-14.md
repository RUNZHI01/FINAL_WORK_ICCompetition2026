# OpenAMP STATUS_REQ/RESP 最小探测 Runbook

> 日期：2026-03-14  
> 目标：在已经打通的 OpenAMP / RPMsg demo transport 基础上，补齐 Linux 侧最小 bridge 与落证流程，但不伪造从核 `STATUS_RESP`。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase4_runtime_channel_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase4_bringup_root_cause_2026-03-13.md`
> - `session_bootstrap/runbooks/openamp_trusted_current_control_wrapper_2026-03-13.md`
> - `paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`
> - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 1. 当前已经验证到哪一层

截至 2026-03-14，真实验证边界如下：

1. `/boot/phytium-pi-board.dtb` 已切到 OpenAMP DTB，`remoteproc0` 已真实出现。
2. `remoteproc0` 可从 `offline` 拉到 `running`，`firmware=openamp_core0.elf`。
3. dmesg 已出现：
   - `Booting fw image openamp_core0.elf`
   - `rpmsg host is online`
   - `creating channel rpmsg-openamp-demo-channel`
4. 板载 `set_env.sh` 与 `rpmsg-demo` 路径已帮助拿到：
   - `/dev/rpmsg_ctrl0`
   - `/dev/rpmsg0`
5. `rpmsg-demo` 已跑通多轮 echo。

因此，当前可以明确说：

- `remoteproc0` 已打通
- RPMsg demo channel 已打通
- Linux 用户态 `/dev/rpmsg0` 读写路径已打通

当前不能说：

- 从核已经实现 `STATUS_REQ/RESP`
- `openamp_control_wrapper.py` 已经走了真实控制授权闭环

## 2. 当前 bridge 的职责边界

`session_bootstrap/scripts/openamp_rpmsg_bridge.py` 当前只做 Phase 5 前置准备：

1. 校验 `/dev/rpmsg_ctrl0`、`/dev/rpmsg0` 是否真实存在。
2. 通过 `/dev/rpmsg0` 发送一个候选二进制 `STATUS_REQ` 帧。
3. 把请求与响应以 `json`、`hex`、`raw bytes` 三种形式落盘。
4. 若响应只是 demo echo，则明确标记：
   - `transport_status=transport_echo_only`
   - `protocol_semantics=not_implemented`
5. 提供 `--hook-stdin` 入口，兼容 `openamp_control_wrapper.py --transport hook` 的 stdin 事件契约。

当前 bridge **不做**：

1. 不通过 `/dev/rpmsg_ctrl0` 主动创建新 endpoint；本轮只校验它存在。
2. 不伪造 `STATUS_RESP`。
3. 不为 `JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP` 提供真实协议语义。

## 3. 直接探测用法

### 3.1 最小 STATUS_REQ 探测

```bash
python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py \
  --rpmsg-ctrl /dev/rpmsg_ctrl0 \
  --rpmsg-dev /dev/rpmsg0 \
  --job-id 5001 \
  --seq 1 \
  --output-dir ./session_bootstrap/reports/openamp_status_req_probe_20260314_001
```

预期结果分三类：

1. `transport_echo_only`
   - 说明：Linux -> RPMsg -> 从核 demo -> Linux 往返可达
   - 结论：transport 可用，但从核仍是 echo demo，不是 `STATUS_RESP`
2. `status_resp_received`
   - 说明：收到了可解析的 `STATUS_RESP`
   - 结论：这时才可宣称 `STATUS_REQ/RESP` 语义已接通
3. `tx_ok_rx_timeout` 或 `unexpected_response`
   - 说明：只能说明部分 transport 动作已发生
   - 结论：不能宣称 `STATUS_RESP`

### 3.2 产物目录

每次运行至少生成：

- `status_req_tx.bin`
- `status_req_tx.hex`
- `status_req_tx.json`
- `status_resp_or_echo_rx.bin`
- `status_resp_or_echo_rx.hex`
- `status_resp_or_echo_rx.json`
- `bridge_summary.json`

其中 `bridge_summary.json` 是本轮结论主文件，关键字段包括：

- `transport_status`
- `protocol_semantics`
- `note`
- `tx_frame`
- `rx_frame`
- `blocker`

## 4. 作为 wrapper hook skeleton 的用法

### 4.1 hook 调用方式

```bash
python3 ./session_bootstrap/scripts/openamp_control_wrapper.py \
  --job-id 5002 \
  --variant current_reconstruction \
  --runner-cmd 'bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1' \
  --expected-sha256 "${INFERENCE_CURRENT_EXPECTED_SHA256}" \
  --output-dir ./session_bootstrap/reports/openamp_wrapper_hook_probe_20260314 \
  --transport hook \
  --control-hook-cmd 'python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py --hook-stdin --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0 --output-dir ./session_bootstrap/reports/openamp_wrapper_hook_bridge_20260314'
```

### 4.2 当前预期行为

当前 bridge 只真正转发 `STATUS_REQ`。

因此，wrapper 在当前阶段的预期是：

1. `STATUS_REQ` 会由 bridge 真实发到 `/dev/rpmsg0`。
2. 紧接着 wrapper 会发 `JOB_REQ` hook 事件。
3. bridge 会对 `JOB_REQ` 返回本地 `DENY`，并显式标注：
   - `source=linux_bridge_local_guard`
   - `transport_status=not_attempted`
   - `protocol_semantics=not_available`

这个 `DENY` 是 Linux 侧保护动作，不是伪造的从核 `JOB_ACK(DENY)`。

因此，在从核控制协议没有实现前：

- 可以把 bridge 当成 wrapper 的候选 hook 入口
- 不能把它当成真实控制授权路径

## 5. 当前 blocker 是否已经明确

是。当前 blocker 不是 Linux 侧 transport，也不是 DTB / remoteproc bring-up。

当前 blocker 是：

**从核 firmware 仍然是 `rpmsg-openamp-demo-channel` echo demo，而不是 `STATUS_REQ/RESP` 处理器。**

更具体地说：

1. transport 已被 Phase 4 证据和 `rpmsg-demo` echo 证明可用；
2. Linux 侧 bridge 已能把候选 `STATUS_REQ` 发出去并落证；
3. 若返回仍是原样 echo，只能说明“通道通了”，不能说明“协议实现了”；
4. 真正缺的是从核源码或等效 firmware 交付，用来实现 `STATUS_REQ -> STATUS_RESP` 的语义处理。

## 6. 如果拿不到从核源码，下一步怎么收口

若短期内拿不到从核源码或可替换 firmware，建议按下面方式收口：

1. 固化当前 Linux 侧可复用资产：
   - `openamp_rpmsg_bridge.py`
   - 本 runbook
   - `openamp_status_req_resp_evidence_template.md`
2. 在真实飞腾板上至少回收一轮 `STATUS_REQ` 探测证据，明确写成：
   - `transport verified`
   - `protocol semantics blocked by firmware`
3. 将 blocker 升级为显式外部依赖：
   - 需要从核源码
   - 或需要带 `STATUS_REQ/RESP` 处理器的可烧录 firmware
   - 或需要 vendor/team 提供消息格式与 endpoint 行为说明
4. 在任务板和后续报告中统一口径：
   - Linux bridge 已准备完成
   - 真闭环尚未完成
   - 原因是从核协议处理器缺位

这样收口后，工程状态是明确的：

- 不是“Linux 侧还没准备”
- 也不是“协议已经打通”
- 而是“Linux 侧已就绪，等待从核 `STATUS_REQ/RESP` 处理器接入”

## 7. 后续通过标准

只有同时满足以下条件，才能把 `STATUS_REQ/RESP` 标记为真实接通：

1. bridge 发出的 `STATUS_REQ` 有真实响应；
2. 响应 `msg_type=STATUS_RESP`，不是原样 echo；
3. `bridge_summary.json` 中出现：
   - `transport_status=status_resp_received`
   - `protocol_semantics=implemented`
4. 证据按 `session_bootstrap/templates/openamp_status_req_resp_evidence_template.md` 落盘。
