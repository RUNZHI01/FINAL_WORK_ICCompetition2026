# 现场启动

本说明适用于 Windows 上位机。现场默认使用 USRP QPSK 链路。

## 首次初始化

首次使用时，打开包含 `demo.ps1` 的交付目录并运行：

```powershell
.\demo.ps1 init
```

上位机需要预先安装 PowerShell 7、Git for Windows（提供 Git Bash）、Docker Desktop、Tailscale、Python 3 和 Node.js 20。Tailscale 需要提前登录并加入板卡所在网络。交付目录已经包含初始化所需的项目文件；初始化只准备 Python、前端依赖、演示输入和 Docker 镜像，不连接板卡。

## 上电启动

1. 启动 Docker Desktop 和 Tailscale。
2. 给飞腾派和两台 USRP 上电。
3. 等待飞腾派启动，通常约 2 分钟。
4. 在 PowerShell 中检查上位机和板卡连接：

```powershell
docker info
tailscale status
tailscale ping 100.121.87.73
.\demo.ps1 check
```

5. 检查通过后，在包含 `demo.ps1` 的交付目录运行：

```powershell
.\demo.ps1
```

脚本使用默认板卡地址和用户名，并询问 SSH 密码。密码输入不回显。界面打开前，脚本会检查板卡会话、安全服务和 USRP TX/RX；此时不会发送图片。

临时更换板卡地址或用户名：

```powershell
$env:REMOTE_HOST = "目标 IP"
$env:REMOTE_USER = "目标用户名"
.\demo.ps1
```

环境变量只在当前 PowerShell 会话生效。命令行参数优先于环境变量；变量未设置时继续使用默认值。

恢复默认连接配置：

```powershell
Remove-Item Env:REMOTE_HOST -ErrorAction SilentlyContinue
Remove-Item Env:REMOTE_USER -ErrorAction SilentlyContinue
```

只检查上位机环境：

```powershell
.\demo.ps1 check
```

## 演示步骤

1. 确认输入来源为 `USRP-QPSK`。
2. 确认加密、双签认证和板卡会话均已就绪。
3. 将批量数量改为 `20`。
4. 启动 TVM 推理，等待任务成功完成。

首页的原图与 TVM 指标只在 USRP QPSK 或 IQ-direct 的 TVM 任务成功后出现。这里显示固定 300 张审计结果，当前均值为 PSNR `24.97 dB`、SSIM `0.9612`；同一界面会话内不会被后续轮询改写。

右下角“本次重建对比图”使用实际拉取的原图和重建图重新计算 PSNR、SSIM，因此数值随当前选择的任务和图片变化。

## 常见问题

- 提示未初始化：运行 `.\demo.ps1 init`。
- Docker 未就绪：启动 Docker Desktop，再运行 `.\demo.ps1 check`。
- Tailscale 未就绪：启动 Tailscale，确认已经登录，再运行 `tailscale ping 100.121.87.73`。
- 密码或板卡会话失败：关闭 Cockpit，重新运行 `.\demo.ps1` 并输入密码。
- USRP 网口异常：运行 `.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status` 查看状态。
- 射频重试过多：先检查天线位置、间距、频点和收发增益，再重新运行任务。

板端环境由维护人员预先准备，日常启动不执行板端部署。输出目录见 [`../../docs/USRP_OUTPUT_LAYOUT.md`](../../docs/USRP_OUTPUT_LAYOUT.md)。
