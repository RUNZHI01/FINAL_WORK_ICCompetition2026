# Docker 与复现入口

现场启动优先使用仓库根目录的 `.\demo.ps1`。本目录提供无硬件复现、兼容启动、板端 CLI smoke 和队伍维护脚本。

## 无硬件复现

Windows PowerShell：

```powershell
.\docker\repro.ps1
```

Linux 或 WSL：

```bash
./docker/repro.sh
```

脚本构建 `ubuntu-minimal.Dockerfile`，检查 Python、Node.js、Electron 和 liboqs 依赖，运行最小 pytest、预录 API smoke 和 Electron 主进程 smoke。预期关键输出为：

```text
deps-ok
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

该流程不连接飞腾派和 USRP。

## 兼容启动入口

```powershell
.\docker\run-demo-tailscale.ps1
```

```bash
./docker/run-demo-tailscale.sh
```

兼容入口默认使用 IQ-direct；现场统一入口 `.\demo.ps1` 默认使用 QPSK。两者都通过 `REMOTE_HOST`、`REMOTE_USER` 和 `REMOTE_SSH_PORT` 读取板卡连接信息，未设置时使用既有验证环境的默认值。密码不写入脚本，由 Electron 界面或当前进程提供。

Tailscale 只承载 SSH、状态、日志和结果拉取。JSCC latent 对应的数据面由本机 TX USRP 和板端 RX USRP 通过射频链路传输。

IQ-direct 的主要运行变量：

| 变量 | 默认值 |
|---|---|
| `MLKEM_TRANSPORT_MODE` | `usrp` |
| `OPENAMP_DEMO_INPUT_SOURCE_MODE` | `usrp` |
| `JSCC_LINK_MODE` / `OPENAMP_DEMO_LINK_MODE` | `iq-direct` |
| `MLKEM_AUTH_ENABLED` | `1` |
| `MLKEM_AUTH_SIG_POLICY` | `DUAL_REQUIRED` |
| `OPENAMP_IQ_SEGMENT_SIZE` | `30` |
| `OPENAMP_IQ_SEGMENT_REPAIR_PASSES` | `2` |

执行顺序和质量门限见 [`../docs/USRP_IQ_RUNTIME.md`](../docs/USRP_IQ_RUNTIME.md)。

旧 WSLg 入口 `run-demo-wslg-tailscale.ps1` 只用于已经配置好的 WSLg 环境，不作为 Windows 现场入口。

## 板端 CLI smoke

完整隔离复现：

```powershell
.\docker\run-board-cli-smoke.ps1
```

```bash
bash docker/run-board-cli-smoke.sh
```

脚本通过 Tailscale 连接飞腾派，把当前仓库复制到新的隔离目录，再运行 TVM、MNN 和 PyTorch。默认每条路径处理 300 个输入；调试时设置 `BOARD_CLI_MAX_INPUTS=3`。

准备可复用缓存：

```powershell
$env:BOARD_CLI_REFRESH_CACHE = "1"
.\docker\run-board-cli-smoke.ps1
```

缓存默认位于 `/home/user/iccomp_board_deps_cache`。

## 快速测速

```powershell
.\docker\run-board-cli-benchmark-fast.ps1
```

```bash
bash docker/run-board-cli-benchmark-fast.sh
```

快速入口要求板端缓存已经存在。它只上传代码层并复用模型、输入和运行时；默认保留本次 `logs/`，设置 `BOARD_CLI_FAST_KEEP_WORK=1` 可保留完整工作目录。

## 维护脚本

- `pull-board-deps.*`：从已验证板卡刷新 `board_deps/`。
- `package-submission.sh`：从干净克隆生成交付包。
- `start-tailscale.sh`：优先复用容器已有的板卡路由；目标不可达时再启动容器内 Tailscale。
- `tailscale-login.*`：只用于初始化容器内 Tailscale 的备用登录状态。

这些脚本会更新备份、登录状态或交付文件，不属于日常启动步骤。
