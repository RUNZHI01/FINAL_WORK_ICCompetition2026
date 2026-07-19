# 飞腾弱网安全语义通信演示系统

本仓库用于集创赛现场演示和软件复现。系统由 Windows 上位机、两台 NI USRP-2922 和飞腾派组成。现场默认链路为：

```text
原图 -> JSCC latent -> USRP QPSK -> 飞腾派 TVM 重建 -> 上位机结果对比
```

OpenAMP 负责板端任务准入和运行状态。ML-KEM、SM4-GCM、ML-DSA 与 SM2 用于设备认证和控制信道保护。射频 IQ 数据由两台 USRP 直接传输，不经过 Tailscale。

## 环境要求

Windows 上位机需要预先安装：

- PowerShell 7
- Git for Windows
- Docker Desktop
- Tailscale（已登录并加入板卡所在网络）
- Python 3
- Node.js 20

## 首次初始化

在仓库根目录运行：

```powershell
.\demo.ps1 init
```

脚本会创建 `.venv`、安装前端依赖、准备演示输入并构建 `iccomp-usrp-tx:latest`。初始化只处理上位机，不连接飞腾派。首次运行需要联网下载 Python、Node.js 和 Docker 依赖。

检查本机是否已经完成初始化：

```powershell
.\demo.ps1 check
```

## 日常启动

启动 Docker Desktop 和 Tailscale，再给飞腾派与两台 USRP 上电。确认板卡已出现在 Tailscale 中后，在仓库根目录运行：

```powershell
.\demo.ps1
```

也可以使用 `.\demo.ps1 start`。脚本先检查本机环境和板端服务，再恢复 USRP 网口、启动 Cockpit 后端并打开 Electron 界面。启动阶段不发送图片。

默认板卡地址和用户名已经写入入口脚本。需要临时更换时，在当前 PowerShell 会话设置：

```powershell
$env:REMOTE_HOST = "目标 IP"
$env:REMOTE_USER = "目标用户名"
.\demo.ps1
```

命令行参数优先于环境变量；两者都未提供时使用默认值。SSH 密码由脚本安全询问，输入不回显。

现场演示步骤和故障处理见 [scripts/demo/STARTUP.md](scripts/demo/STARTUP.md)。

## 无硬件复现

没有飞腾派和 USRP 时，可检查依赖、API 和 Electron 主进程：

```powershell
pwsh -File .\docker\repro.ps1
```

Linux 或 WSL 使用：

```bash
./docker/repro.sh
```

该流程验证软件交付是否完整，不等价于真机无线链路测试。

## 目录

| 路径 | 内容 |
|---|---|
| `scripts/demo/` | Windows 初始化、启动脚本和现场说明 |
| `Semantic-Communication/cockpit_desktop/` | Electron/React 上位机 |
| `Semantic-Communication/session_bootstrap/` | Cockpit 后端、重建调度和演示数据 |
| `USRP292x/` | QPSK、IQ 直传和 USRP 网络脚本 |
| `mlkem_link/` | ML-KEM、SM4-GCM 和双签认证实现 |
| `board_deps/` | 板端运行时、模型、固件和离线恢复材料 |
| `docker/` | 容器复现、板端 smoke 和维护入口 |
| `docs/` | 链路、安全边界和输出目录说明 |

技术文档入口见 [docs/README.md](docs/README.md)。真实密码、私钥、本机定位配置和运行缓存不得写入 Git。
