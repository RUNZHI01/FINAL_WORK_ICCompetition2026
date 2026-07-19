# Phytium `openamp_for_linux` STATUS_REQ/RESP Patch Runbook

> 日期：2026-03-14
> 目标：把官方 `phytium-standalone-sdk` 的 `example/system/amp/openamp_for_linux` 从 echo demo 最小改成 `STATUS_REQ -> STATUS_RESP`，并给出应用、构建、部署、验证路径。
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_source_entry_discovery_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase4_runtime_channel_success_2026-03-14.md`
> - `session_bootstrap/runbooks/openamp_status_req_resp_runbook_2026-03-14.md`
> - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_2026-03-14.patch`

## 1. Patch 作用范围

本 patch 当前只改一个官方 SDK 源码文件：

- `example/system/amp/openamp_for_linux/src/slaver_00_example.c`

行为变化：

- 保持 `third-party/openamp/ports/rpmsg_service.h` 里的 service name 不变，仍然是 `rpmsg-openamp-demo-channel`
- 保持 `main.c -> slave00_rpmsg_echo_process()` 入口不变，避免额外改动构建入口
- 把原来的 echo callback 改成最小二进制控制帧处理器
- 仅实现：
  - `STATUS_REQ (0x08)` -> `STATUS_RESP (0x09)`
- 对非 `STATUS_REQ` 输入采取保守行为：
  - 非控制帧：日志告警后忽略
  - 非 `STATUS_REQ` 的控制帧：日志告警后忽略
  - 带 payload 的 `STATUS_REQ`：日志告警后忽略

当前最小 `STATUS_RESP` 负载固定返回：

- `guard_state=1`，约定为 `READY`
- `active_job_id=0`
- `last_fault_code=0`
- `heartbeat_ok=0`
- `sticky_fault=0`
- `total_fault_count=0`

这只是最小从核占位实现，不扩张到 `JOB_REQ/JOB_ACK`、`HEARTBEAT`、`RESET_REQ/ACK`。

## 2. 为什么优先改 `openamp_for_linux`

优先改这个目录，而不是 `example/system/amp/openamp/driver_core` 或 `device_core`，原因已经由本地证据链收敛：

1. `session_bootstrap/reports/openamp_phase5_source_entry_discovery_2026-03-14.md` 已确认，飞腾派 Linux + `remoteproc/rpmsg/virtio` 路径对应的官方例程就是 `example/system/amp/openamp_for_linux`。
2. `main.c` 当前直接进入 `slave00_rpmsg_echo_process()`，说明 `openamp_core0.elf` 的 demo 行为就来自这里。
3. `third-party/openamp/ports/rpmsg_service.h` 中的 `RPMSG_SERVICE_NAME` 与板端 dmesg 里真实出现的 `rpmsg-openamp-demo-channel` 一致。
4. `session_bootstrap/reports/openamp_phase4_runtime_channel_success_2026-03-14.md` 已证明当前通道就是 Linux `remoteproc0` 拉起的 demo service，不是裸机对裸机的 AMP 示例。

因此，最小风险路线是：

- 不改 service name
- 不改 Linux 侧 channel 绑定
- 只改 `openamp_for_linux` 的回调逻辑

## 3. 在官方 SDK 上应用 patch

默认官方 SDK 工作副本：

```bash
SDK_ROOT=/tmp/phytium-standalone-sdk
PATCH_FILE=/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_2026-03-14.patch
```

先做可应用性检查：

```bash
git -C "$SDK_ROOT" apply --check "$PATCH_FILE"
```

正式应用：

```bash
git -C "$SDK_ROOT" apply "$PATCH_FILE"
```

如果想先判断 patch 是否已经在该 SDK 树里：

```bash
git -C "$SDK_ROOT" apply --reverse --check "$PATCH_FILE"
```

返回成功表示该 patch 很可能已经被应用过。

## 4. 按 `pe2204_aarch64_phytiumpi_openamp_core0.config` 构建

进入官方例程目录：

```bash
cd /tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux
```

加载飞腾派 aarch64 配置：

```bash
make load_kconfig LOAD_CONFIG_NAME=pe2204_aarch64_phytiumpi_openamp_core0
```

构建：

```bash
make clean
make all -j"$(nproc)"
```

按当前 SDK `build.mk` 和 `sdkconfig` 组合，预期 ELF 名称为：

```text
pe2204_aarch64_phytiumpi_openamp_core0.elf
```

如果希望同时输出标准部署名 `openamp_core0.elf`，可以让 `image` 目标拷贝：

```bash
make image USR_BOOT_DIR=/tmp/phytium_openamp_out
```

预期得到：

```text
/tmp/phytium_openamp_out/openamp_core0.elf
```

说明：

- 本仓库本轮没有代替你执行真实构建
- 本仓库本轮也没有伪造 `make all` 成功

## 5. 把新的 `openamp_core0.elf` 部署到飞腾板

下面步骤需要在真实飞腾板或远端构建机上人工执行。

先把新 ELF 送到板子，例如：

```bash
scp /tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux/pe2204_aarch64_phytiumpi_openamp_core0.elf user@BOARD_IP:/tmp/openamp_core0.elf
```

在板上替换 firmware：

```bash
sudo install -m 0644 /tmp/openamp_core0.elf /lib/firmware/openamp_core0.elf
```

如果 `remoteproc0` 当前已经在跑旧固件，先查看状态：

```bash
cat /sys/class/remoteproc/remoteproc0/state
```

若状态为 `running`，再停止并重启：

```bash
echo stop | sudo tee /sys/class/remoteproc/remoteproc0/state
echo start | sudo tee /sys/class/remoteproc/remoteproc0/state
```

启动后建议立即确认：

```bash
dmesg | tail -n 80
```

重点看：

- 仍然是 `Booting fw image openamp_core0.elf`
- 仍然出现 `creating channel rpmsg-openamp-demo-channel`

这样才能确认 service name 没被意外改掉。

## 6. 准备 `/dev/rpmsg_ctrl0` 和 `/dev/rpmsg0`

沿用板端已经验证过的 OpenAMP bring-up 路径：

```bash
sudo /home/user/open-amp/set_env.sh
```

确认：

```bash
ls -l /dev/rpmsg_ctrl0
ls -l /dev/rpmsg0
```

注意：

- 当前 `session_bootstrap/scripts/openamp_rpmsg_bridge.py` 只校验 `/dev/rpmsg_ctrl0` 是否存在，并直接读写 `/dev/rpmsg0`
- 它本轮不会自己通过 `rpmsg_ctrl` 创建 endpoint
- 如果板端当前流程仍需要额外一步才能稳定拿到 `/dev/rpmsg0`，继续沿用你在 Phase 4 已验证过的板端做法，不要假设本 runbook 已替代那一步

## 7. 用 `openamp_rpmsg_bridge.py` 验证真实 `STATUS_RESP`

在仓库根目录执行：

```bash
python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py \
  --rpmsg-ctrl /dev/rpmsg_ctrl0 \
  --rpmsg-dev /dev/rpmsg0 \
  --job-id 5001 \
  --seq 1 \
  --output-dir ./session_bootstrap/reports/openamp_status_req_probe_real_status_resp_20260314
```

这一步只有在刷入了新从核 firmware 后，才应该期待真实 `STATUS_RESP`。

验证成功的判据：

- `bridge_summary.json` 中出现：
  - `transport_status=status_resp_received`
  - `protocol_semantics=implemented`
- `status_resp_or_echo_rx.json` 中：
  - `parsed_frame.msg_type = 9`
  - `parsed_frame.status_resp.parsed = true`
- 当前最小回包应体现：
  - `guard_state = 1`
  - `active_job_id = 0`
  - `last_fault_code = 0`
  - `heartbeat_ok = 0`
  - `sticky_fault = 0`
  - `total_fault_count = 0`

如果结果仍然是：

- `transport_echo_only`
- `tx_ok_rx_timeout`
- `unexpected_response`

则不能宣称真实 `STATUS_REQ/RESP` 已接通，应回到以下排查项：

1. 新 `openamp_core0.elf` 是否真的覆盖进了 `/lib/firmware/openamp_core0.elf`
2. `remoteproc0` 是否在替换后重新 `stop/start`
3. `dmesg` 中的 channel 是否仍为目标 demo channel
4. `/dev/rpmsg0` 是否仍连接到新 firmware 对应 endpoint

## 8. 当前边界

这个 patch 预案只覆盖：

- 官方 SDK 的最小从核 `STATUS_REQ -> STATUS_RESP`

它还没有覆盖：

- `JOB_REQ/JOB_ACK`
- `HEARTBEAT/SAFE_STOP`
- `RESET_REQ/ACK`
- 基于真实从核状态机的 fault latch、active job、heartbeat watchdog

因此，它的定位仍然是：

- 先把真实飞腾板上的最短 `STATUS_REQ/RESP` 回路打通
- 再在此基础上继续扩展后续控制语义
