# 现场启动

适用于 Windows 上位机。默认板卡地址为 `100.121.87.73`，用户名为 `user`，演示链路为 USRP QPSK。

## 首次初始化

评委从 Git 克隆代码后，在仓库根目录运行：

```powershell
.\demo.ps1 init
```

脚本准备 Python、Node.js、示例输入和 Docker 镜像，不连接板卡。电脑需要预先安装 PowerShell 7、Git for Windows、Docker Desktop、Python 3 和 Node.js 20。

## 上电启动

1. 打开 Docker Desktop，给飞腾派和两台 USRP 上电。
2. 等待板卡启动，通常约 2 分钟。
3. 在仓库根目录运行：

```powershell
.\demo.ps1
```

也可以写成 `.\demo.ps1 start`。脚本保留默认 IP 和用户名，只询问板卡 SSH 密码，输入不回显。启动完成前不会发送图片。

需要换地址时：

```powershell
.\demo.ps1 start -BoardHost 100.121.87.73 -BoardUser user
```

只检查本机环境：

```powershell
.\demo.ps1 check
```

## 演示

界面打开后确认输入来源为 `USRP-QPSK`，加密、双签认证和板卡会话均已就绪。将批量数量设为 `20`，再启动 TVM 推理。

任务成功后，首页常驻显示原图与 TVM 重建结果的 PSNR/SSIM。右下角“本次重建对比图”会按拉取到的图片实时计算指标。

## 常见问题

- 提示未初始化：运行 `.\demo.ps1 init`。
- Docker 未就绪：启动 Docker Desktop，再运行 `.\demo.ps1 check`。
- 密码或板卡会话失败：关闭 Cockpit，重新运行 `.\demo.ps1` 并输入密码。
- 上位机 USRP 网口异常：运行 `.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status` 查看状态。

板端环境由维护人员预先准备，日常启动不做板端部署。

输出目录规则见 [`../../docs/USRP_OUTPUT_LAYOUT.md`](../../docs/USRP_OUTPUT_LAYOUT.md)。
