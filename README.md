# 飞腾弱网安全语义通信演示系统

本仓库是集创赛现场演示与复现用的最终代码。系统由 Windows 上位机、两台 NI USRP-2922 和飞腾派组成，默认演示链路为：

```text
原图 -> JSCC latent -> USRP QPSK -> 飞腾派 TVM 重建 -> 上位机结果对比
```

OpenAMP 负责板端任务准入和运行状态，ML-KEM、SM4-GCM、ML-DSA 与 SM2 用于控制信道和设备认证。射频 IQ 数据本身不经过 Tailscale，也不宣称由 ML-KEM 加密。

## 首次初始化

Windows 上位机需要安装：

- PowerShell 7
- Git for Windows
- Docker Desktop
- Python 3
- Node.js 20

克隆仓库后，在仓库根目录运行：

```powershell
pwsh -File .\init.ps1
```

脚本会创建 `.venv`、执行 `npm ci`、构建 `iccomp-usrp-tx:latest`，并检查本地 Python 和 Docker 依赖。它不连接飞腾派，不修改板端文件。首次构建 Docker 镜像需要下载依赖，耗时取决于网络和电脑性能。

只检查当前电脑是否完成初始化：

```powershell
pwsh -File .\init.ps1 -CheckOnly
```

## 日常启动

板卡和 Docker Desktop 启动后，在仓库根目录运行：

```powershell
.\Semantic-Communication\cockpit_desktop\start-demo.ps1
```

默认板卡地址为 `100.121.87.73`，用户名为 `user`。脚本会安全询问 SSH 密码，输入内容不回显。也可以显式指定连接参数：

```powershell
.\Semantic-Communication\cockpit_desktop\start-demo.ps1 `
  -BoardHost 100.121.87.73 `
  -BoardUser user
```

一键脚本会先检查本地环境，然后恢复板端 USRP 网口、启动 Cockpit 后端、建立安全会话并检查常驻 TX/RX，最后打开 Electron 界面。启动阶段不发送图片。

完整现场步骤和故障处理见 [docs/runbooks/STARTUP.md](docs/runbooks/STARTUP.md)。技术文档索引见 [docs/README.md](docs/README.md)。

## 本地复现

没有飞腾派和 USRP 时，可运行容器内的依赖、API 和 Electron smoke：

```powershell
pwsh -File .\docker\repro.ps1
```

Linux 或 WSL 使用：

```bash
./docker/repro.sh
```

这条路径只验证软件交付是否完整，不等价于真机无线链路测试。

## 目录

| 路径 | 内容 |
|---|---|
| `Semantic-Communication/cockpit_desktop/` | Electron/React 上位机和一键启动脚本 |
| `Semantic-Communication/session_bootstrap/` | Cockpit 后端、重建调度和演示数据 |
| `USRP292x/` | QPSK、IQ 直传和 USRP 网络脚本 |
| `mlkem_link/` | ML-KEM、SM4-GCM 和双签认证实现 |
| `board_deps/` | 板端 runtime、模型、固件和离线恢复材料 |
| `docker/` | 复现、打包和容器入口 |
| `docs/` | 运行手册、链路说明和安全边界 |

密码、私钥、本机定位配置、运行日志和重建缓存不纳入 Git。
