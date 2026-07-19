# Phase 4 远端 OpenAMP / RPMsg 审计结论（飞腾板）

> 日期：2026-03-13  
> 审计对象：`Phytium-Pi` (`100.121.87.73`, `user`)  
> 审计方式：使用仓库内 `session_bootstrap/scripts/ssh_with_password.sh` 直连远端，并将 `audit_openamp_linux_platform.py` 通过 stdin 注入执行。  
> 原始证据：`session_bootstrap/reports/openamp_platform_audit_phytium_20260313_231014.json`、`session_bootstrap/reports/openamp_platform_audit_phytium_20260313_231014.md`

## 1. 结论摘要

本轮已完成 Phase 4 的**真实飞腾 Linux 侧平台审计**，结论不是“脚本链路不通”，而是：

- 飞腾板 SSH 可正常登录；
- 内核配置层面已具备 `CONFIG_REMOTEPROC=y`、`CONFIG_RPMSG=y`、`CONFIG_RPMSG_VIRTIO=y`、`CONFIG_MAILBOX=y`；
- 运行态层面**未暴露可用的 remoteproc / rpmsg 用户态入口**：
  - `/sys/class/remoteproc` 存在，但没有 `remoteprocX` 实例；
  - `/sys/bus/rpmsg` 存在，但没有 channel/device；
  - `/dev/rpmsg_ctrl*`、`/dev/rpmsg*`、`/dev/ttyRPMSG*` 均不存在；
  - 当前未见相关模块处于 loaded 状态。

因此，当前 Phase 4 的真实 blocker 已经被定位为：

**板端 OpenAMP / remoteproc 运行态尚未真正 bring-up，导致无法进入 `STATUS_REQ/RESP` 最小闭环。**

## 2. 关键证据

### 2.1 远端登录连通性

已验证：

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user --port 22 -- \
  'hostname && whoami && uname -a'
```

返回：

- hostname: `Phytium-Pi`
- user: `user`
- kernel: `Linux Phytium-Pi 5.10.209-phytium-embedded-v2.2 ... aarch64`

### 2.2 审计脚本结论

远端审计输出摘要：

- readiness=`absent`
- remoteproc_count=`0`
- rpmsg_count=`0`
- device_node_total=`0`

### 2.3 内核能力与运行态反差

远端内核配置快照：

- `CONFIG_REMOTEPROC=y`
- `CONFIG_RPMSG=y`
- `CONFIG_RPMSG_CHAR=m`
- `CONFIG_RPMSG_VIRTIO=y`
- `CONFIG_MAILBOX=y`
- `CONFIG_REMOTEPROC_CDEV=y`（来自 build `auto.conf` 侧证据）

但远端运行态同时满足：

- `/sys/class/remoteproc` 为空；
- `/sys/bus/rpmsg/devices` 无 channel/device；
- `/dev/rpmsg*` 无节点；
- `loaded module matches: []`。

这说明问题不是“内核完全没开 OpenAMP/RPMsg 能力”，而是**没有把具体 remoteproc 实例和 rpmsg 通道实际拉起来**。

## 3. 进一步探测结果

额外远端探测显示：

- 平台设备中仅明显看到：`32a00000.mailbox`
- dmesg 中仅有：`phytium-mbox 32a00000.mailbox: Phytium SoC Mailbox registered`
- `/lib/modules/.../kernel/drivers/rpmsg/` 下可见 `rpmsg_char.ko`
- 未观察到 `remoteprocX`、`rpmsg` 设备、`/dev/remoteproc*` 或其他厂商封装的用户态桥接节点

由此可判断：

1. mailbox 基础驱动已注册；
2. rpmsg/remoteproc 代码路径存在；
3. 但缺少“从核实例 + 资源表/firmware + DT 绑定 + 用户态节点”这一整段 bring-up。

## 4. 当前工程判断

Phase 4 不再是“未知是否可用”，而是已经有了明确结论：

- **可做**：保留现有 `openamp_control_wrapper.py` 作为控制面外层骨架；
- **暂不可做**：真实 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK` 联调；
- **原因**：远端 Linux 侧当前没有可操作的 remoteproc/rpmsg 实例与字符设备入口。

## 5. 建议下一步（按优先级）

1. 在飞腾平台侧确认是否存在配套从核固件、resource table、remoteproc DT 节点与启动流程。  
2. 检查是否有厂商特定驱动/节点未启用，例如 `homo_remoteproc` 对应的平台设备绑定或启动脚本。  
3. 若需要 root 权限，补执行：
   - `modprobe rpmsg_char`
   - 检查 `remoteproc` 相关 sysfs 是否出现实例
   - 检查 `/dev/rpmsg_ctrl*` 是否出现
4. 若板端短期无法 bring-up，则 Demo/答辩先使用：
   - 现有 trusted current 数据面 + mock 控制面证据链
   - 同时把“真实飞腾板 OpenAMP 审计已完成，当前 blocker 为板端 runtime bring-up”写入正式材料

## 6. 对 Phase 5 的影响

- `trusted current` 控制面 wrapper 骨架已具备：`session_bootstrap/scripts/openamp_control_wrapper.py`
- 但在真实飞腾板进入 Phase 5 前，必须先满足：
  - 至少一个可用的 `remoteprocX`
  - 至少一个可用的 RPMsg 用户态入口（`/dev/rpmsg*` 或等价桥接）
  - 能跑通 `STATUS_REQ/RESP`

在这之前，继续推进 wrapper 只会停留在 dry-run / local trace 层面，无法形成真实异构闭环证据。
