# 飞腾平台 OpenAMP / RPMsg Linux 侧平台审计报告

> 生成时间：2026-03-13T23:10:16+08:00
> 探测标签：`phytium_remote`
> 宿主机：`Phytium-Pi` / `5.10.209-phytium-embedded-v2.2` / `aarch64`

## 1. 本次结论

- readiness: `absent`
- 本机是否飞腾目标板：`yes`
- /sys/class/remoteproc 存在，但没有 remoteprocX 实例。
- /sys/bus/rpmsg 存在，但未发现已绑定的 channel/device。
- 未发现 /dev/rpmsg_ctrl*、/dev/rpmsg* 或 /dev/ttyRPMSG* 设备节点。
- 当前内核未加载 remoteproc/rpmsg 相关模块。

## 2. Linux 侧必须检查项

- `用户态入口`: /dev/rpmsg_ctrl*、/dev/rpmsg*、/dev/ttyRPMSG* 是否存在且权限可读写
- `sysfs`: /sys/class/remoteproc/remoteprocX 的 name/state/firmware/recovery/coredump
- `sysfs`: /sys/bus/rpmsg/devices/* 的 channel 名称、src/dst、绑定 driver
- `内核模块`: remoteproc、rpmsg、rpmsg_char、virtio_rpmsg_bus、mailbox 是否已加载
- `内核配置`: CONFIG_REMOTEPROC / CONFIG_RPMSG / CONFIG_RPMSG_CHAR / CONFIG_RPMSG_VIRTIO
- `日志证据`: dmesg 中是否出现 remoteproc boot、virtio rpmsg、name service、mailbox 错误
- `联调前置`: 先 STATUS_REQ/RESP，再 JOB_REQ/JOB_ACK，再 heartbeat/deadline/safe-stop

## 3. 本地已验证结果

### 3.1 sysfs / dev 节点

- `/sys/class/remoteproc`: exists=`True` sample_children=`[]`
- `/sys/bus/rpmsg`: exists=`True` sample_children=`['devices', 'drivers', 'drivers_autoprobe', 'drivers_probe', 'uevent']`
- `/sys/class/rpmsg`: exists=`False` sample_children=`[]`
- `/sys/kernel/config`: exists=`True` sample_children=`['device-tree', 'nvmet', 'pci_ep', 'usb_gadget']`
- `/sys/module/remoteproc`: exists=`False` sample_children=`[]`
- `/sys/module/rpmsg`: exists=`False` sample_children=`[]`
- `/sys/module/rpmsg_char`: exists=`False` sample_children=`[]`
- `/sys/module/virtio_rpmsg_bus`: exists=`False` sample_children=`[]`
- `rpmsg_ctrl`: []
- `rpmsg_endpoints`: []
- `tty_rpmsg`: []

### 3.2 remoteproc / rpmsg 实例

- 未发现 `remoteprocX` 实例。
- 未发现 `rpmsg` channel/device 实例。

### 3.3 模块 / 内核配置 / 日志

- loaded module matches: `[]`
- expected_loaded: `{'remoteproc': False, 'rpmsg': False, 'rpmsg_char': False, 'rpmsg_ctrl': False, 'virtio_rpmsg_bus': False, 'rpmsg_ns': False, 'mailbox': False}`
- module_root: `/lib/modules/5.10.209-phytium-embedded-v2.2` exists=`True`
- module path samples: `['/lib/modules/5.10.209-phytium-embedded-v2.2/kernel/drivers/rpmsg/rpmsg_char.ko']`
- kernel config snapshot: `{'_source': '/proc/config.gz', 'CONFIG_REMOTEPROC': 'y', 'CONFIG_RPMSG': 'y', 'CONFIG_RPMSG_CHAR': 'm', 'CONFIG_RPMSG_CTRL': 'missing', 'CONFIG_RPMSG_NS': 'missing', 'CONFIG_RPMSG_VIRTIO': 'y', 'CONFIG_MAILBOX': 'y'}`
- dmesg 过滤摘录：

```text
[    2.588260] phytium-mbox 32a00000.mailbox: Phytium SoC Mailbox registered
```

## 4. 常见缺口

- remoteproc 实例缺失
- rpmsg channel 缺失
- rpmsg 设备节点缺失
- 相关内核模块未加载
- 典型缺口还包括：remoteproc 固件名不匹配、device tree 未绑定 mailbox/shared-memory、rpmsg_char 未启用、从核未拉起。

## 5. 最小联调路径

- 先确认 remoteproc 实例存在，并能读取 name/state/firmware；若 state=offline，再确认从核固件装载路径和启动方式。
- 确认 RPMsg 用户态入口至少具备一项：/dev/rpmsg_ctrl*、/dev/rpmsg* 或厂商封装的 /dev/ttyRPMSG*。
- 确认内核侧至少暴露 remoteproc + rpmsg_char/virtio_rpmsg_bus，若未自动加载则补驱动或设备树绑定。
- 先打通 STATUS_REQ/STATUS_RESP，验证 Linux -> 从核 -> Linux 的最短控制回环，再接 JOB_REQ/JOB_ACK。
- 最后再用独立控制面 wrapper 包裹现有 trusted current runner，只在执行前后加控制消息与心跳，不改推理数据面。

## 6. 远端待执行命令与预期证据路径

- 当前本机不是已确认的飞腾目标板时，不伪造 RPMsg/remoteproc 结果；下面命令应在真实飞腾 Linux 侧仓库根目录执行。
- 预期证据路径：`session_bootstrap/reports/openamp_platform_audit_phytium_<timestamp>.json` 和对应 `.md`。

```bash
STAMP="$(date +%Y%m%d_%H%M%S)"
python3 ./session_bootstrap/scripts/audit_openamp_linux_platform.py \
  --label phytium_remote \
  --output-json "./session_bootstrap/reports/openamp_platform_audit_phytium_${STAMP}.json" \
  --output-md "./session_bootstrap/reports/openamp_platform_audit_phytium_${STAMP}.md"
ls -l /dev/rpmsg* /dev/ttyRPMSG* 2>/dev/null || true
lsmod | grep -E 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp' || true
for p in /sys/class/remoteproc/remoteproc*; do [ -e "$p" ] || continue; echo "== $p =="; for f in name state firmware recovery coredump; do [ -f "$p/$f" ] && printf '%s=%s\n' "$f" "$(cat "$p/$f")"; done; done
for p in /sys/bus/rpmsg/devices/*; do [ -e "$p" ] || continue; basename "$p"; for f in name src dst modalias; do [ -f "$p/$f" ] && printf '  %s=%s\n' "$f" "$(cat "$p/$f")"; done; done
dmesg | grep -Ei 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp|virtio' | tail -n 80
```

## 7. 控制面包裹边界

- OpenAMP 只包裹控制面：执行授权、状态查询、心跳、deadline、安全停止、故障上报。
- 现有 trusted current 数据面继续走 `run_remote_current_real_reconstruction.sh` / `current_real_reconstruction.py` / `run_inference_benchmark.sh`。
- 后续 wrapper 只在 runner 前后插入 `STATUS_REQ/JOB_REQ/HEARTBEAT/JOB_DONE`，不重写推理逻辑。

