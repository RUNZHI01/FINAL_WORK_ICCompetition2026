# Phase 4 运行态 OpenAMP / RPMsg 通道打通记录

> 日期：2026-03-14  
> 目标：记录飞腾板切到 OpenAMP DTB 之后，`remoteproc0`、RPMsg channel 与 `/dev/rpmsg*` 用户态入口的真实打通情况。  
> 范围：只记录本轮已验证的事实，不扩写尚未实现的控制协议。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase4_bringup_root_cause_2026-03-13.md`
> - `session_bootstrap/reports/openamp_phase4_remote_audit_summary_2026-03-13.md`
> - `session_bootstrap/runbooks/phytium_openamp_dtb_switch_runbook_2026-03-13.md`

## 1. 本轮结论

本轮已经不再停留在“推断 boot/DTB 选错”，而是完成了真实运行态打通：

1. `/boot/phytium-pi-board.dtb` 已切到 `phytium-pi-board-v3-openamp.dtb`，并且飞腾板成功重启进入界面。
2. 重启后 `/sys/class/remoteproc/remoteproc0` 已真实出现，platform device 出现 `homo_rproc@0`。
3. `remoteproc0` 初始状态为 `offline`，手动 `start` 后进入 `running`。
4. dmesg 已明确记录：
   - `Booting fw image openamp_core0.elf`
   - `rpmsg host is online`
   - `creating channel rpmsg-openamp-demo-channel`
5. 说明 OpenAMP 固件 `openamp_core0.elf` 已被真正装载，RPMsg demo channel 已成功建立。
6. 进一步执行板载 `set_env.sh` 与 `rpmsg-demo` 后，已真实出现：
   - `/dev/rpmsg_ctrl0`
   - `/dev/rpmsg0`
7. `rpmsg-demo` 已成功完成多轮 echo 往返，证明 Linux 用户态到从核 demo service 的消息收发路径可用。

因此，Phase 4 已经从“找不到入口”推进到：

**真实 OpenAMP / RPMsg demo 通道已打通；当前剩余任务是把 demo echo 通道替换为赛题所需控制协议。**

## 2. 关键证据

### 2.1 DTB 切换后 remoteproc 实例出现

重启后检查结果：

- `/boot/phytium-pi-board.dtb -> phytium-pi-board-v3-openamp.dtb`
- `/sys/class/remoteproc/remoteproc0` 存在
- platform device 中可见 `homo_rproc@0`

### 2.2 remoteproc0 状态与固件

验证结果：

- `name=homo_rproc`
- `state=offline`（启动前）
- `firmware=openamp_core0.elf`
- `recovery=enabled`
- `coredump=disabled`

之后手动执行：

```bash
echo start > /sys/class/remoteproc/remoteproc0/state
```

结果：

- `state=running`

### 2.3 RPMsg channel 已创建

启动 `remoteproc0` 后，dmesg 关键行：

```text
remoteproc remoteproc0: Booting fw image openamp_core0.elf, size 1650448
virtio_rpmsg_bus virtio0: rpmsg host is online
remoteproc remoteproc0: remote processor homo_rproc is now up
virtio_rpmsg_bus virtio0: creating channel rpmsg-openamp-demo-channel addr 0x0
```

同时 `/sys/bus/rpmsg/devices/` 下已出现：

- `virtio0.rpmsg-openamp-demo-channel.-1.0`

## 3. 为什么一开始没有 `/dev/rpmsg*`

这轮还额外定位了一个很具体的原因：

- Linux 侧 `rpmsg_char` 暴露的 alias 是：
  - `rpmsg:rpmsg_chrdev`
- 当前从核固件 `openamp_core0.elf` 暴露的 service/channel 名是：
  - `rpmsg-openamp-demo-channel`
- 当前 rpmsg 设备的 modalias 也是：
  - `rpmsg:rpmsg-openamp-demo-channel`

这解释了为什么：

- `remoteproc0` 和 RPMsg channel 已经有了
- 但不会自动出现 `/dev/rpmsg*`

因为它不是自动命中 `rpmsg_chrdev` 的默认名字，需要额外做一次板载文档里的环境配置。

## 4. 板载 OpenAMP 文档与现成工具

飞腾板上已有：

- `/home/user/open-amp/readme.txt`
- `/home/user/open-amp/set_env.sh`
- `/home/user/open-amp/rpmsg-demo`
- `/home/user/open-amp/rpmsg-demo.c`

其中 `readme.txt` 的官方步骤是：

1. 切换到 openamp dtb
2. 重启
3. `sudo ./set_env.sh`
4. `sudo ./rpmsg-demo`

`set_env.sh` 的关键动作包括：

- `echo start > /sys/class/remoteproc/remoteproc0/state`
- `echo rpmsg_chrdev > /sys/bus/rpmsg/devices/virtio0.rpmsg-openamp-demo-channel.-1.0/driver_override`
- `insmod .../rpmsg_char.ko`

## 5. 用户态入口已验证成功

执行板载 `set_env.sh` 后：

- `/dev/rpmsg_ctrl0` 出现

执行 `rpmsg-demo` 后：

- `/dev/rpmsg0` 出现
- demo 成功打印多轮：
  - `received message: Hello World! No:...`

这说明：

- RPMsg ctrl 入口可用
- endpoint 可创建
- 数据收发路径可用

## 6. 当前阶段判断

截至本轮，Phase 4 的状态应更新为：

- **OpenAMP DTB 切换验证成功**
- **remoteproc0 已打通**
- **RPMsg demo channel 已打通**
- **Linux 用户态 `/dev/rpmsg_ctrl0` / `/dev/rpmsg0` 已打通**

当前不再卡在 boot/DTB bring-up。

当前新的主 blocker 是：

**现有通道还是 demo echo 服务 `rpmsg-openamp-demo-channel`，还没有替换成赛题所需的控制协议 endpoint。**

## 7. 建议下一步

1. 把 Phase 4 从“bring-up 问题”切换到“协议接线问题”。
2. 优先决定控制协议接入方式：
   - 路线 A：修改从核 OpenAMP firmware 的 service name / endpoint 行为，使其承载 `STATUS_REQ/RESP`、`JOB_REQ/ACK` 等控制消息。
   - 路线 B：保留 demo channel 名称，但在其收发逻辑上替换 echo demo，为控制协议实现。
3. Linux 侧随后新增最小 bridge：
   - 打开 `/dev/rpmsg_ctrl0`
   - 创建 endpoint
   - 用 `/dev/rpmsg0` 发送控制帧
4. 在此基础上，才把 `openamp_control_wrapper.py` 从 dry-run / local trace 推进到真实通道。

## 8. 对后续工作的影响

- 之前的“是否必须重装系统”已经可以排除。
- “是否必须先装 OpenAMP 包”也不是主阻塞。
- 当前最关键的前提条件已经具备：
  - DTB 正确
  - 固件可启动
  - RPMsg demo 通道可达
  - Linux 用户态设备节点可生成

后续真正的工程工作，已经进入**协议实现与 wrapper 接线**阶段。
