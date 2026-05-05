# OpenAMP Demo 与底层当前行为不适配：兼容性诊断（2026-03-17）

## 结论

当前问题已经不应再被描述为“demo 偶发 timeout”，而应明确收敛为：

> **demo 当前假设的 OpenAMP 控制协议链，与板上当前 live firmware / lower-layer 能实际返回的行为不再一致。**

也就是说，问题的主体已不是前端文案，而是 **demo ↔ lower layer compatibility mismatch**。

---

## 1. 现在已经确认的事实

### A. 当前板子在线，但这不等于控制协议可用

只读探板结果：
- `remoteproc0=running`
- `/dev/rpmsg0`、`/dev/rpmsg_ctrl0` 存在
- channel: `rpmsg-openamp-demo-channel`
- 当前 live firmware SHA：
  - `ef14bc26c4f63ab07fc617cf9bac54abccb44a45520d8acb3af6cb74a82e6007`

证据：
- `session_bootstrap/reports/openamp_demo_live_probe_latest.json`

这只能证明：
- 板在线；
- RPMsg 设备节点存在；
- remoteproc 正在跑。

这**不能**证明：
- 当前 firmware 仍实现 repo 中 demo 所依赖的 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、signed sideband 语义。

### B. 之前正式收口的成功证据对应的是别的 live firmware

此前正式证据包中，可工作的 live firmware 不是当前 `ef14...`，而是：

- 控制面最终 evidence package：
  - `2c4240e03deedd2cc6bbd1c7c34abee852aa8f7927a5187a5131659c4ce7878a`
- 3/16 signed-admission 真机成功证据：
  - `140e2e8ca22d951d518907ab92a3ec910969fba6830481fc3d397193ac1712f1`

证据：
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- `session_bootstrap/reports/openamp_signed_admission_real_board_success_20260316/evidence_summary.json`

因此最强的当前根因假设是：

> **板上的 live firmware 已漂移到一个不同版本（`ef14...`），而 demo / wrapper / bridge 仍然在按之前已验证版本（`2c42...` / `140e...`）的协议契约行事。**

---

## 2. 当前 demo 依赖的底层协议假设

当前 repo 内 demo / wrapper / bridge 仍然依赖以下前提：

1. `STATUS_REQ` 发出后，能拿到结构化 `STATUS_RESP`
2. `JOB_REQ` 发出后，能拿到结构化 `JOB_ACK`
3. signed sideband (`BEGIN/CHUNK/SIGNATURE/COMMIT`) 也能收到 ACK
4. lower layer 返回的数据格式仍符合当前 bridge 解析逻辑

相关代码：
- `session_bootstrap/scripts/openamp_control_wrapper.py`
- `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
- `session_bootstrap/demo/openamp_control_plane_demo/*`

现在仓内已经补上的防御性修复包括：

### 已落地修复 1：失败时不再假装成功
- commit: `1e0eb10`
- 作用：当 `STATUS_REQ/JOB_REQ` 只是 `tx_ok_rx_timeout` 时，UI 明确显示“握手未完成，已回退”，并把 timing/quality 标成归档参考，不再像一次完成的 live run。

### 已落地修复 2：fail-closed after handshake failure
- commit: `61499e9`
- 作用：如果 `STATUS_REQ` 或 signed-admission 阶段本身未得到可确认响应，则 wrapper 直接在该 phase 终止，不再继续往后推 `JOB_REQ`。

### 已落地修复 3：启动前 STATUS 预检不通过时不再 launch
- commit: `50e9055`
- 作用：server 在 live launch 之前先做 `STATUS_REQ` 预检；若预检失败，则直接给出“启动前检查失败，回退展示（归档样例）”，并阻止 live job 启动。

这些修复已经让系统：
- **更诚实**；
- **更安全**；
- **不再把 incompatible lower layer 硬当成可用 live path**。

但它们**没有证明 live path 已恢复**。

---

## 3. 为什么现在会看到 `guard=BOOT`

这点也已经基本澄清：

- 在 transport timeout / deny summary 路径里，bridge 可能会综合成本地 fallback/denied 结果；
- 因此你在 timeout 场景里看到的 `guard=BOOT`，**不能直接当成板子真的返回了一个可靠的 firmware guard state**；
- 更可信的原始事实是：
  - `write to /dev/rpmsg0 succeeded`
  - `no STATUS_RESP / no JOB_ACK before timeout`

也就是说，真正该盯的不是 `BOOT` 这个词，而是：

> **为什么当前 firmware 对 demo 发出的 `STATUS_REQ` / `JOB_REQ` 不再给出可确认响应。**

---

## 4. 当前最可能的兼容性断点

按证据强弱排序，目前最可能的是：

### 假设 1：板上 live firmware 已切到不同协议实现线（最高概率）
- 之前 PASS 的 live firmware SHA：`2c42...` / `140e...`
- 当前探到的 live firmware SHA：`ef14...`
- 这说明 board 运行的不是此前证据包对应的那条固件线

### 假设 2：当前 firmware 仍在跑，但不再实现 / 不再兼容 demo 依赖的控制协议帧格式
包括但不限于：
- message type 变了
- payload layout 变了
- header / CRC 变了
- sideband stage 处理变了
- 只保留了 `rpmsg-demo` echo 级功能，而没有控制面语义

### 假设 3：用户态 transport 存在设备可见但协议线程不可响应状态
也就是：
- `/dev/rpmsg0` 存在
- `write()` 成功
- 但从核不再消费或不再回复该协议帧

---

## 5. 最小下一步（板侧核查顺序）

这是当前最小、最值钱、且不绕远的核查顺序。

### Step 1：重新确认当前 live firmware 身份
在板上核：

```bash
sha256sum /lib/firmware/openamp_core0.elf
ls -l /lib/firmware/openamp_core0.elf
```

目标：
- 确认是否仍为 `ef14bc26...6007`
- 若不是，再记录新 SHA

### Step 2：直接打一个最小 STATUS_REQ，不经过 demo UI
在板上直接跑 bridge：

```bash
sudo PYTHONPATH=/home/user/tvm_metaschedule_execution_project \
python3 /home/user/tvm_metaschedule_execution_project/session_bootstrap/scripts/openamp_rpmsg_bridge.py \
  --phase STATUS_REQ \
  --job-id 9101 \
  --seq 1 \
  --rpmsg-ctrl /dev/rpmsg_ctrl0 \
  --rpmsg-dev /dev/rpmsg0 \
  --output-dir /tmp/openamp_status_req_probe
```

重点看：
- `/tmp/openamp_status_req_probe/bridge_summary.json`
- `transport_status`
- `protocol_semantics`
- 是否真有 `STATUS_RESP`

### Step 3：如果 Step 2 仍是 `tx_ok_rx_timeout`
继续收这组三件最小证据：

```bash
ls -l /dev/rpmsg0 /dev/rpmsg_ctrl0
dmesg | tail -n 120 | grep -E 'remoteproc|rpmsg|openamp|virtio'
sha256sum /lib/firmware/openamp_core0.elf
```

这样就能明确回答：
- 是不是 firmware 已漂移；
- 是不是 channel 还在；
- 是不是协议层根本没在回。

### Step 4：只有 STATUS_REQ 真返回了 STATUS_RESP，才值得继续试 JOB_REQ
如果 `STATUS_REQ` 自己就死了：
- 再跑 `JOB_REQ` 没价值；
- 那不是 demo launch 问题，而是当前 lower layer 根本不兼容现协议线。

---

## 6. 当前工程判断

当前工程状态应重新表述为：

- **demo 展示层：已修正，不再误导**
- **wrapper / launch 逻辑：已改为 fail-closed**
- **底层 live 握手链：仍 blocked**
- **当前最核心任务：确认 board 上 `ef14...` firmware 与已验证协议线之间的偏差**

所以这不是“demo 还差一点文案优化”，而是：

> **demo 与底层当前行为不适配，且已经被重新定义成一个明确的兼容性工程问题。**
