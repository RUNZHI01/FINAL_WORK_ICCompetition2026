# Docker 入口说明

本目录的主要复现入口是 `repro.*`、`run-demo.*`、`run-demo-wslg-tailscale.ps1` 和 `run-board-cli-smoke.*`。日常快速测速可使用 `run-board-cli-benchmark-fast.*`；维护脚本单列在最后，常规复现通常不需要使用。

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

当前 Windows 现场复现优先使用原生 PowerShell + Docker，不走 WSL：

```powershell
$env:REMOTE_HOST="100.121.87.73"
$env:REMOTE_USER="user"
$env:REMOTE_PASS="<board password>"
.\docker\run-demo-tailscale.ps1
```

切 USRP/IQ 现场链路时，同一入口会转发 `REMOTE_USRP_RX_DIR`，例如：

```powershell
$env:MLKEM_TRANSPORT_MODE="usrp"
$env:OPENAMP_DEMO_INPUT_SOURCE_MODE="usrp"
$env:REMOTE_USRP_RX_DIR="/home/user/cockpit_usrp_rx"
$env:JSCC_LINK_MODE="iq-direct"
$env:ANALOG_RX_TAIL_SEC="0.12"
$env:ANALOG_REMOTE_CLEANUP_MODE="async"
.\docker\run-demo-tailscale.ps1
```

`run-demo-tailscale.*` 默认设置 `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded`。该 profile 固定为预录 latent 输入、TCP/Tailscale 控制连接，并默认关闭 ML-KEM auth gate：

```text
OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded
MLKEM_TRANSPORT_MODE=tcp
MLKEM_AUTH_ENABLED=0
MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
```

普通 `start-electron-prod-demo.sh` profile 仍默认 `MLKEM_AUTH_ENABLED=1`、`MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`；上面的关闭只用于复现 TVM 重建性能指标，避免把未配置完整的认证 gate 混入 250 ms 口径。

这一路用于恢复 cockpit desktop 下的 handwritten TVM + big.LITTLE 300 张测速口径。2026-07-09 的 Windows cockpit 真机验证结果为 `300/300`、fallback `0`、mean `244.44 ms`、median `243.77 ms`、p95 `248.31 ms`；报告位于 `Semantic-Communication/session_bootstrap/reports/openamp3_handwritten_mean4_v7_big_little_current_20260709_020321.*`。

如果不走 Docker cockpit、而是在 Windows 原生后端里临时调试，请不要调用 WSL 的 `bash.exe`。使用 Git Bash，并让密码 SSH helper 走 Docker runner：

```powershell
$env:OPENAMP_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:GIT_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:OPENAMP_SSH_RUNNER="docker"
$env:OPENAMP_SSH_DOCKER_IMAGE="iccomp-usrp-tx:latest"
```

旧 WSLg 入口仍保留给已有 WSLg 环境使用；当前 Windows 现场不要走这条路径：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

也可以先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

前提是运行机器已经能登录到与飞腾派板卡相同的 Tailscale 网络。脚本内置的默认地址只适用于既有验证环境；复测时可用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定实际板卡地址。板卡密码在 Electron demo 内填写。

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

该入口是完整自包含复现路径，会上传仓库内的板端 runtime、模型和输入。当前仓库的压缩传输流约 `421 MB`，完整运行后的板端隔离目录通常为 `1.7 GB` 到 `2.0 GB`。脚本会输出每个阶段的耗时，便于判断是在上传、解包还是推理阶段。

如需为快速测速准备板端缓存，可在完整 smoke 前设置：

```powershell
$env:BOARD_CLI_REFRESH_CACHE="1"
.\docker\run-board-cli-smoke.ps1
```

Linux / WSL:

```bash
BOARD_CLI_REFRESH_CACHE=1 bash docker/run-board-cli-smoke.sh
```

缓存默认写到 `/home/user/iccomp_board_deps_cache`。

## 板端快速测速

Windows PowerShell:

```powershell
.\docker\run-board-cli-benchmark-fast.ps1
```

Linux / WSL:

```bash
bash docker/run-board-cli-benchmark-fast.sh
```

快速入口要求板端已有 `/home/user/iccomp_board_deps_cache/board_deps`。它只上传代码覆盖层，不上传 `board_deps/runtime`、模型和输入大包；运行时把这些重依赖软链接到缓存目录。首次快速运行会在缓存下解出便携 Python runtime，后续复用该目录。默认只保留本次运行的 `logs/`，会清理临时 `repo/` 和 `work/`；需要保留完整输出时设置 `BOARD_CLI_FAST_KEEP_WORK=1`。

性能统计字段与 Electron 前端一致：

- TVM：`inference_ms.median_ms`
- MNN：`total_ms.median_ms`
- PyTorch：`run_median_ms`

MNN 选 `total_ms` 是为了匹配 demo 的端到端展示值；`run_ms` 只包含 `interpreter.runSession`，不用于交付 KPI。

## 队伍维护入口

以下脚本用于刷新依赖、维护 Tailscale 登录态或生成额外交付压缩包，不属于最小复现步骤：

- `pull-board-deps.*`：从当前板端刷新 `board_deps/`。
- `package-submission.sh`：从 GitHub fresh clone 生成 tar 包。
- `start-tailscale.sh`、`tailscale-login.*`：维护 Docker volume 中的 Tailscale 登录态。
