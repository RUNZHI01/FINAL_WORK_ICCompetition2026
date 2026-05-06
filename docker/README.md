# Docker 入口说明

本目录面向评委的入口是 `repro.*`、`run-demo.*`、`run-demo-wslg-tailscale.ps1` 和 `run-board-cli-smoke.*`。维护脚本单列在最后，评委完成复现通常不需要使用。

## 基础复现

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

`repro.*` 会构建 `ubuntu-minimal.Dockerfile`，安装 Python/Node/Electron/liboqs 依赖，运行最小 pytest 集、prerecorded API smoke，并在 Xvfb 下启动真实 Electron 主进程。

## 原生 Electron 窗口

```bash
./docker/run-demo.sh
```

```powershell
.\docker\run-demo.ps1
```

Linux / WSL 需要可用 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。该入口默认走预录数据，不自动接板。

## Tailscale 真机链路

Windows + WSLg 推荐：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

也可以先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

前提是评委机器已经能登录到与飞腾派板卡相同的 Tailscale 网络。脚本内置的历史地址只适用于本队验证环境；复测时可用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定实际板卡地址。板卡密码在 Electron demo 内填写。

## 板端 CLI Smoke

Windows PowerShell:

```powershell
.\docker\run-board-cli-smoke.ps1
```

Linux / WSL:

```bash
bash docker/run-board-cli-smoke.sh
```

脚本通过 Docker 内 Tailscale 连接飞腾派，将当前仓库复制到新的 `/home/user/iccomp_repo_selfcontained_<timestamp>`，再运行 `board_deps/scripts/run-isolated-cli-smoke.sh`。默认每条路径处理 300 个输入；调试可设置 `BOARD_CLI_MAX_INPUTS=3`。

性能口径与 Electron 前端一致：

- TVM：`inference_ms.median_ms`
- MNN：`total_ms.median_ms`
- PyTorch：`run_median_ms`

MNN 选 `total_ms` 是为了匹配 demo 的端到端展示值；`run_ms` 只包含 `interpreter.runSession`，不用于交付 KPI。

## 队伍维护入口

以下脚本用于刷新依赖、维护 Tailscale 登录态或生成额外交付压缩包，不属于评委最小复现步骤：

- `pull-board-deps.*`：从当前板端刷新 `board_deps/`。
- `package-submission.sh`：从 GitHub fresh clone 生成 tar 包。
- `start-tailscale.sh`、`tailscale-login.*`：维护 Docker volume 中的 Tailscale 登录态。
