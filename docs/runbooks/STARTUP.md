# 现场启动手册

本文按 Windows 上位机编写。默认板卡地址 `100.121.87.73`，用户名 `user`，演示链路为 USRP QPSK。

## 首次准备

在仓库根目录运行：

```powershell
pwsh -File .\init.ps1
```

初始化只处理上位机：Python 虚拟环境、前端依赖、Docker 镜像和随仓库提供的示例 latent。它不连接板卡。

只有首次部署板端环境或 IQ 源码更新后，才执行下面的同步。该命令会连接并修改板端：

```powershell
pwsh -File .\docker\prepare-iq-board-sync.ps1 `
  -Deploy -Verify `
  -BoardHost 100.121.87.73 `
  -BoardUser user
```

日常演示不要重复同步。

## 冷启动

1. 打开 Docker Desktop，给飞腾派和两台 USRP 上电。板卡启动后等约 2 分钟。

2. 在仓库根目录检查上位机环境：

```powershell
pwsh -File .\init.ps1 -CheckOnly
```

3. 查看上位机 USRP 网口：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status
```

如果 `192.168.10.2` 不通，用管理员 PowerShell 配置上位机网口。`InterfaceAlias` 按状态命令的输出填写：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 `
  -Target UpperHost `
  -InterfaceAlias "以太网"
```

4. 启动 Cockpit：

```powershell
.\Semantic-Communication\cockpit_desktop\start-demo.ps1
```

脚本保留默认 IP 和用户名，只询问 SSH 密码，输入不回显。也可以传入其他地址：

```powershell
.\Semantic-Communication\cockpit_desktop\start-demo.ps1 `
  -BoardHost 100.121.87.73 `
  -BoardUser user
```

脚本先检查本地依赖，再恢复板端 RX 网口，随后启动后端、安全会话和常驻 USRP TX/RX。所有探活通过后才打开界面；启动过程不发送图片。

## 演示前检查

界面打开后确认：

- 输入来源为 `USRP-QPSK`；
- 加密与双签认证均已启用；
- 板卡会话显示就绪；
- 硬件遥测持续更新。

将批量数量改为 `20`，启动 TVM 推理。正常顺序为上位机准备、USRP 传输与解包、板端 TVM 重建。只有任务成功完成后，首页才保留原图与 TVM 的 PSNR/SSIM 指标；重启 Cockpit 后重新等待下一次成功任务。

需要逐图核对时，点击“本次重建对比图”。浏览器页面运行在上位机的 `http://127.0.0.1:8786/`，每次拉取图片时计算该图的 PSNR 和 SSIM。

## 常用输出目录

| 内容 | 位置 |
|---|---|
| 上位机示例 latent | `host_pic_to_latent/encoder_outputs/` |
| 上位机现场 latent 缓存 | `host_pic_to_latent/encoder_outputs_top300/` |
| 板端 QPSK TVM 输出 | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` |
| 板端 IQ-direct TVM 输出 | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` |
| 板端 USRP 接收目录 | `/home/user/cockpit_usrp_rx` |

完整规则见 [`../USRP_OUTPUT_LAYOUT.md`](../USRP_OUTPUT_LAYOUT.md)。

## 故障处理

`init.ps1 -CheckOnly` 报错时，不要继续启动。按提示补齐 `.venv`、`node_modules`、Docker 镜像或示例输入，再重新检查。

板端 USRP 地址不通时，先运行快速恢复：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 `
  -Target Board `
  -BoardHost 100.121.87.73 `
  -Fast
```

仍不通时去掉 `-Fast`，执行完整恢复和 UHD 探测。

出现 `board status endpoint unavailable` 时，先重启 Cockpit 并重新输入密码。不要切换到 WSL。

Cockpit 对比页不可用时，可单独拉取最新重建图：

```powershell
.\scripts\pull_board_images.ps1
```

指定板端目录：

```powershell
.\scripts\pull_board_images.ps1 `
  -RemotePath "/home/user/Downloads/jscc-test-usrp/qpsk/tvm/<job>/reconstructions"
```

重新运行 `start-demo.ps1` 时，脚本会先清理上一轮留下的本地 Cockpit 和后端进程。
