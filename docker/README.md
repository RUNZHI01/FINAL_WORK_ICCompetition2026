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

当前 Windows 现场推荐入口是仓库根目录的 `.\demo.ps1 start`，默认 QPSK。本节的 `run-demo-tailscale.*` 是默认 IQ-direct 的兼容容器入口，同样不走 WSL：

```powershell
.\docker\run-demo-tailscale.ps1
```

兼容入口的关键默认值如下；IQ 运行顺序和限制见 [`../docs/USRP_IQ_RUNTIME.md`](../docs/USRP_IQ_RUNTIME.md)。

| 参数 | 默认值 |
|---|---|
| `REMOTE_HOST` / `REMOTE_USER` / `REMOTE_SSH_PORT` | `100.121.87.73` / `user` / `22` |
| `MLKEM_TRANSPORT_MODE` / `OPENAMP_DEMO_INPUT_SOURCE_MODE` | `usrp` / `usrp` |
| `JSCC_LINK_MODE` / `OPENAMP_DEMO_LINK_MODE` | `iq-direct` / `iq-direct` |
| `OPENAMP_SSH_RUNNER` / `OPENAMP_USRP_TX_RUNNER` | `docker` / `docker` |
| `MLKEM_AUTH_ENABLED` / `MLKEM_AUTH_SIG_POLICY` | `1` / `DUAL_REQUIRED` |
| `OPENAMP_IQ_SEGMENT_SIZE` / `OPENAMP_IQ_SEGMENT_REPAIR_PASSES` | `30` / `2` |
| `ANALOG_IQ_QUALITY_MIN_SYNC_METRIC` | `0.75` |
| `ANALOG_IQ_MIN_PILOT_GAIN_RATIO` | `0.85` |

板卡密码不写入脚本；在 Electron 界面填写，或在运行前设置 `REMOTE_PASS`。

名字里的 Tailscale 只表示控制面：cockpit API、SSH 拉起板端进程、状态和日志走 Tailscale。IQ/latent 数据面由本机 TX USRP 和板端 RX USRP 通过射频链路承载，不绕到 Tailscale 文件传输。`ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir` 让板端就地解码，避免拉回原始 IQ capture。快速 IQ profile 保持 TX/RX 常驻，并用 ARQ 和 quality gate 拒绝低质量 latent；当前门限是 `sync_metric >= 0.75`、`pilot_gain_min_over_initial >= 0.85`、EVM `<= 0.75`、估计 SNR `>= 3.0 dB`。正常 `STOP` drain 保留 8 秒保护。

`run-demo-tailscale.*` 仍设置历史名称 `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded`，但同时显式设置 `OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp`、`MLKEM_TRANSPORT_MODE=usrp`、`JSCC_LINK_MODE=iq-direct` 和双签认证，因此实际运行的是 IQ-direct 真机链路。

如果只想复现预录 TVM 250 ms，请在运行前临时覆盖 `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded`、`MLKEM_TRANSPORT_MODE=tcp`，并在记录里说明是否启用认证 gate。

这一路用于当前 cockpit desktop 下的 USRP IQ 直传 + handwritten TVM + big.LITTLE 300 张演示口径。典型值：USRP IQ 传输/解包 median `166.63 ms`、p95 `198.46 ms`；后接 TVM median `241.20 ms`、p95 `242.59 ms`。预录 TVM 250 ms 参考线为 300 张 median `243.30 ms`、mean `252.91 ms`。

如果不走 Docker cockpit、而是在 Windows 原生后端里临时调试，请不要调用 WSL 的 `bash.exe`。使用 Git Bash 作为脚本解释器，并优先让 SSH helper 和本机 TX 都走 Docker：

```powershell
$env:OPENAMP_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:GIT_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:OPENAMP_SSH_RUNNER="docker"
$env:OPENAMP_USRP_TX_RUNNER="docker"
```

`usrp_runtime.py` 在 Windows 且 Docker 可用时也会默认选择 Docker TX；显式设置上面的环境变量只是为了现场排障时避免继承旧进程状态。若 Docker 不可用，可临时把 `OPENAMP_SSH_RUNNER` 改成 `paramiko`，但仍不要使用 WSL bash。

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
