# Docker 入口说明

本目录只保留评委复现、原生 Electron smoke、板端真机验证和交付打包需要的脚本。不要把 `TS_AUTHKEY`、`REMOTE_PASS`、`PHYTIUM_PI_PASSWORD` 或任何私钥写入脚本、Dockerfile 或 README。

## 评委复现

评委最小路径只需要：

- `ubuntu-minimal.Dockerfile`
- `repro.sh` / `repro.ps1`
- `api-smoke.sh`
- `electron-smoke.sh`

Linux / WSL:

```bash
./docker/repro.sh
```

Windows PowerShell:

```powershell
.\docker\repro.ps1
```

预期关键输出：

```text
deps-ok
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

`repro.*` 会构建镜像、安装 Python/Node/Electron/liboqs 依赖、运行最小 pytest 集、校验 prerecorded API 返回非空图像，并在 Xvfb 下启动真实 Electron 主进程。这里没有浏览器 preview 替代路径。

## 原生窗口

需要在宿主机看到原生 Electron 窗口时使用：

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

Linux / WSL 需要可用 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。无显示环境请使用 `repro.*`，它会用 Xvfb 做无头 Electron smoke。

## Tailscale 真机链路

需要容器内 Electron 直连飞腾派时使用：

```powershell
$env:REMOTE_PASS="..."
$env:PHYTIUM_PI_PASSWORD="..."
.\docker\run-demo-wslg-tailscale.ps1
```

也可以先登录 Tailscale，再启动：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Tailscale 状态保存在 Docker volume `iccomp-tailscale-state`。默认板端地址是 `100.121.87.73`，可以用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 覆盖。

## 板端 CLI Smoke

`run-board-cli-smoke.ps1` 用于验证本仓库里的板端推理产物是否足够自包含。脚本会通过 Docker 内的 Tailscale 连接飞腾派，把当前仓库复制到新的 `/home/user/iccomp_repo_selfcontained_<timestamp>` 目录，然后默认每条路径处理 300 张输入：

- TVM CLI 推理
- MNN CLI 推理
- PyTorch CLI 推理

执行：

```powershell
$env:REMOTE_PASS="..."
.\docker\run-board-cli-smoke.ps1
```

预期最后一行：

```text
cli-smoke-ok
```

需要短调试时可以覆盖输入数量：

```powershell
$env:REMOTE_PASS="..."
$env:BOARD_CLI_MAX_INPUTS="3"
.\docker\run-board-cli-smoke.ps1
```

该脚本不会修改板端现有仓库，也不会向板端 conda 环境安装任何包；它只解压 `board_deps/runtime/` 中的便携运行时到新的隔离目录。

## 依赖拉取

需要从当前板端重新拉取运行产物时使用：

```powershell
$env:REMOTE_PASS="..."
.\docker\pull-board-deps.ps1
```

对应 Linux / WSL 脚本是：

```bash
REMOTE_PASS=... bash docker/pull-board-deps.sh
```

## 打包

提交并推送本仓库后生成交付源码包：

```bash
./docker/package-submission.sh
```

脚本会从 `https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git` fresh clone 远端源码，校验本地 HEAD 与远端 HEAD 一致，然后生成 `iccomp2026-submission.tar.gz`。本仓库已经实物化 `Semantic-Communication/` 和 `liboqs/`，不再使用 submodule。
