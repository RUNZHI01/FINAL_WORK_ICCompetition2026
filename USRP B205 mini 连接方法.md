# USRP B205 mini 连接方法

> 说明：以下带 `#` 的命令需要 Windows 管理员权限或 Linux Root 权限。

## 1. 前置条件

- 设备：USRP B205 mini / B205 mini-i
- 环境：Windows + WSL2
- 已安装：`usbipd`、`uhd-host`

## 2. 连接步骤

1. 插入 USRP 设备。

2. 在 Windows PowerShell（管理员）查看设备列表，找到 `WestBridge` 或 `VID:PID=2500:0022` 对应的 `BUSID`：

```pwsh
# win-pwsh
usbipd list
```

3. 将设备挂载到 WSL，并按状态检查：

```pwsh
# win-pwsh
usbipd wsl attach --busid <BUSID>
usbipd list
```

状态变化建议按下列逻辑判断：

- 首次接入常见路径：`Not shared -> Shared -> Attached`
- 已共享过的设备：`Shared -> Attached`
- 使用强制参数时：`Not shared -> Shared (Forced) -> Attached`

成功标准是看到 `Attached`。如果只有 `Shared`，通常表示已共享但未成功附加到 WSL。

如果 attach 失败，可尝试：

```pwsh
# win-pwsh
usbipd wsl attach --busid <BUSID> --force
```

4. 在 WSL 中确认 USB 设备可见：

```bash
# wsl-bash
lsusb
```

预期输出：

```text
ID 2500:0022 Ettus Research LLC USRP B205-mini
```

5. 在 WSL 中使用 UHD 枚举设备：

```bash
# wsl-bash
uhd_find_devices --args="type=b200"
```

预期关键输出：

```text
-- UHD Device 0
serial: 31DDAB3
name: B205i
product: B205mini
type: b200
```

6. 在 WSL 中进行完整探测：

```bash
# wsl-bash
uhd_usrp_probe --args="type=b200"
```

预期关键输出包含：

```text
[INFO] [B200] Detected Device: B205mini
[INFO] [B200] Operating over USB 3.
[INFO] [B200] Register loopback test passed
FW Version: 8.0
FPGA Version: 7.0
```

## 3. 判定标准

- `lsusb` 能看到 `2500:0022`
- `uhd_find_devices` 能识别到 `type: b200`
- `uhd_usrp_probe` 无报错，且出现 `Register loopback test passed`

## 4. 设备差异与标识符说明

- `VID:PID` 不是单设备唯一标识。它标识的是设备型号/类别，同型号设备可能相同。
- `BUSID` 不是稳定唯一标识。它与当前 USB 拓扑相关，换 USB 口、重插设备后可能变化。
- `serial`（如 `31DDAB3`）通常是区分同型号多台设备的更稳定标识，推荐用于最终确认。
- 同一系列不同硬件版本可能在以下字段有差异：`name`、`product`、`FW Version`、`FPGA Version`。

推荐识别顺序：

1. 用 `usbipd list` 通过 `VID:PID` 和设备名称先粗筛目标设备。
2. 用 `BUSID` 执行 attach。
3. 在 WSL 用 `uhd_find_devices` 或 `uhd_usrp_probe` 通过 `serial` 做最终确认。

## 5. 常见问题

- 现象：WSL 与 USRP 偶发断联。
- 可能原因：`usbipd` 桥接不稳定或 USB 连接状态波动。
- 建议排查：
  - 重新执行 `usbipd list` 与 `usbipd wsl attach --busid <BUSID>`
  - 必要时加 `--force`
  - 更换 USB 口或数据线，优先直连主机 USB 3.0 接口

