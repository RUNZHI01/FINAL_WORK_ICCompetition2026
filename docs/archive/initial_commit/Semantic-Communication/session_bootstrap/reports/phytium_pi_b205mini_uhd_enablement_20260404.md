# 飞腾派 B205mini UHD 驱动使能记录（2026-04-04）

## 结论

飞腾派 `Ubuntu 20.04` 上的 `USRP B205mini` 已完成 UHD 驱动安装与验证，且**未升级系统版本**。

最终可用状态：

- `uhd-host 3.15.0.0-2build5`
- `libuhd3.15.0 3.15.0.0-2build5`
- `libuhd-dev 3.15.0.0-2build5`
- `python3-uhd 3.15.0.0-2build5`
- `uhd_usrp_probe --args serial=31E74E3` 通过
- 官方例程 `/usr/lib/uhd/examples/rx_samples_to_file` 通过
- 官方例程 `/usr/lib/uhd/examples/benchmark_rate --args serial=31E74E3 ...` 通过

## 根因

这次阻塞不是 Ubuntu 20.04 本身不支持 B205mini，而是有两层环境问题叠加：

1. 飞腾派是 `arm64`，但 `/etc/apt/sources.list` 还在使用 `http://mirrors.aliyun.com/ubuntu/` 这种 x86 常见源。
2. 对 `arm64` 来说，该源会请求 `binary-arm64/Packages` 并返回 `404`，导致 Ubuntu 官方 `uhd-host/libuhd-dev/python3-uhd` 包一直不可见。
3. 板上之前残留了来自 Ettus PPA 的 `uhd-rfnoc-dev 4.9.0.0`，这并不能提供 B205mini 需要的完整运行时，反而会制造版本错层。
4. Ubuntu 20.04 自带的 `60-uhd-host.rules` 过旧，未包含 `B205mini` 的 USB ID `2500:0022`，导致设备节点权限不完整。

## 远端实际修复

在飞腾派上做了以下变更：

1. 备份原 `/etc/apt/sources.list`。
2. 将 Ubuntu 源切换为 `http://ports.ubuntu.com/ubuntu-ports`，保留 `focal/focal-updates/focal-security`。
3. 安装：
   - `uhd-host`
   - `libuhd-dev`
   - `python3-uhd`
4. 运行 `uhd_images_downloader -t b2 -y` 下载 B2xx 镜像。
5. 新增远端 udev 规则 `/etc/udev/rules.d/99-uhd-b205mini.rules`：

```udev
SUBSYSTEMS=="usb", ATTRS{idVendor}=="2500", ATTRS{idProduct}=="0022", MODE:="0666"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="2500", ATTRS{idProduct}=="0023", MODE:="0666"
```

6. 重载 `udev` 规则并触发：
   - `udevadm control --reload-rules`
   - `udevadm trigger`
7. 禁用 Ettus PPA：
   - `/etc/apt/sources.list.d/ettusresearch-ubuntu-uhd-focal.list.disabled`
8. 清理残留包：
   - `apt-get purge -y uhd-rfnoc-dev`

## 验证结果

### 设备探测

`uhd_usrp_probe --args serial=31E74E3` 输出关键结果：

- 检测到设备 `B205mini`
- `Operating over USB 3`
- 固件版本 `FW Version: 8.0`
- FPGA 版本 `FPGA Version: 7.0`

### 官方例程 1

```bash
/usr/lib/uhd/examples/rx_samples_to_file \
  --args serial=31E74E3 \
  --rate 1000000 \
  --freq 100000000 \
  --gain 10 \
  --duration 1 \
  --null \
  --stats
```

结果：

- 成功初始化 B205mini
- 成功锁定 LO
- `Received 1000000 samples in 1.004665 seconds`
- 实测约 `0.995356 Msps`

### 官方例程 2

```bash
/usr/lib/uhd/examples/benchmark_rate \
  --args serial=31E74E3 \
  --rx_rate 1000000 \
  --duration 5
```

结果：

- `Num received samples: 5000221`
- `Num dropped samples: 0`
- `Num overruns detected: 0`
- `Num underruns detected: 0`

## 备注

1. `benchmark_rate` 若直接只写 `--args type=b200`，在 B2xx 固件重枚举窗口里有概率撞到 `No devices found` 或 `libusb_claim_interface`。固定到 `serial=31E74E3` 更稳。
2. 设备在验证后已经稳定跑在 `USB 3` 链路上。
3. 当前板上仍有一个**与 UHD 无关**的第三方 Docker 源异常，可能导致 `apt update` 偶发失败：

```text
/etc/apt/sources.list.d/docker.list
```

这不影响当前 B205mini/UHD 使用；如需，我可以下一步单独把这个 APT 源也收拾干净。
