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
.\docker\run-demo-tailscale.ps1
```

`run-demo-tailscale.*` 内置当前验证环境默认值：`REMOTE_HOST=100.121.87.73`、`REMOTE_USER=user`、`REMOTE_SSH_PORT=22`、`OPENAMP_SSH_RUNNER=docker`、`OPENAMP_USRP_TX_RUNNER=docker`、`MLKEM_TRANSPORT_MODE=usrp`、`OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp`、`REMOTE_USRP_RX_DIR=/home/user/cockpit_usrp_rx`、`REMOTE_USRP_DECODE_PYTHON=/home/user/venv/bin/python`、`JSCC_LINK_MODE=iq-direct`、`MLKEM_AUTH_ENABLED=1`、`MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`、`ANALOG_RX_TAIL_SEC=0.040`、`RX_ARM_WAIT_MS=500`、`ANALOG_SYNC_PROFILE=fast-first`、`ANALOG_FAST_SYNC_CANDIDATES=4`、`ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS=1024`、`ANALOG_FALLBACK_SYNC_CANDIDATES=4`、`ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS=1024`、`ANALOG_IQ_QUALITY_GATE=1`、`ANALOG_IQ_QUALITY_MIN_SYNC_METRIC=0.75`、`ANALOG_IQ_MIN_PILOT_GAIN_RATIO=0.85`、`ANALOG_IQ_MAX_EVM_RMS=0.75`、`ANALOG_IQ_MIN_SNR_DB=3.0`、`ANALOG_REMOTE_DECODED_FORMAT=npy`、`ANALOG_RX_SC16_MMAP=1`、`ANALOG_RX_CLIPPING_DECIMATION=8`、`ANALOG_RX_POST_QUANTIZE=0`、`ANALOG_RX_BATCH_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16`、`ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1`、`ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal`、`ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1`、`ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05`、`ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5`、`ANALOG_RETRY_ON_BURST_MISS=1`、`ANALOG_RETRY_ON_LOW_SYNC=1`、`ANALOG_LOW_SYNC_RETRY_THRESHOLD=0.08`、`ANALOG_ROBUST_SYNC=0`、`ANALOG_DECODE_PIPELINE_WARMUP=1`、`OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0`、`MLKEM_USRP_MAX_ARQ_ROUNDS=12`、`USRP_MAX_ARQ_ROUNDS=12`、`OPENAMP_TVM_BATCH_RUNNER=biglittle`。质量门限开启时 `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC` 会被安全地压成 0，等待完整 sync/pilot summary 后再放行 TVM。板卡密码不写入脚本；在 Electron 界面里填写，或运行前按需设置 `REMOTE_PASS`。

名字里的 Tailscale 只表示控制面：cockpit API、SSH 拉起板端进程、状态和日志走 Tailscale。USRP 数据面应由本机 TX USRP 和板端 RX USRP 通过射频链路承载，不能把 IQ/latent 主数据绕到 Tailscale 文件传输。默认 `ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir` 会在板端解码后再取结果，避免把原始 IQ 捕获文件拉回控制面。快速 IQ profile 使用 `OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0` 保持 TX/RX 常驻，使用 `RX_ARM_WAIT_MS=500` 等待 RX capture 真正启动，使用 `ANALOG_SYNC_PROFILE=fast-first` 和 IQ quality gate 拒绝低质量 decoded latent，并用 ARQ 重试，避免 300/300 但 TVM 重建为彩色噪声；quality gate 要求 `sync_metric>=0.25` 且 `pilot_gain_min_over_initial>=0.25`，并默认等待完整 summary。使用 `ANALOG_DECODE_PIPELINE_WARMUP=1` 预热板端 decode-server，并用 `ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5` 限制“未开始接收”的恢复长尾；正常 `STOP` drain 仍保持 8 秒保护。`ANALOG_REMOTE_CLEANUP_MODE=skip` 用于避免热路径后台删除抢板端 I/O；演示后可清理板端 `/tmp/usrp292x_remote_runs`。USRP 后接重建当前支持 TVM 和 MNN；PyTorch 只作为预录参考对照，不走 USRP 数据面。USRP transport 结果卡片使用 raw round records 的 median/p95，避免 RF/RX 单次离群值污染典型时延。

切 USRP/IQ 现场链路时，同一入口会转发 USRP 相关环境变量，例如：

```powershell
$env:MLKEM_TRANSPORT_MODE="usrp"
$env:OPENAMP_DEMO_INPUT_SOURCE_MODE="usrp"
$env:REMOTE_USRP_RX_DIR="/home/user/cockpit_usrp_rx"
$env:JSCC_LINK_MODE="iq-direct"
$env:MLKEM_AUTH_ENABLED="1"
$env:MLKEM_AUTH_SIG_POLICY="DUAL_REQUIRED"
$env:ANALOG_SPS="2"
$env:ANALOG_AMPLITUDE="6000"
$env:ANALOG_RX_TAIL_SEC="0.040"
$env:ANALOG_REMOTE_DECODED_FORMAT="npy"
$env:ANALOG_RX_SC16_MMAP="1"
$env:ANALOG_RX_CLIPPING_DECIMATION="8"
$env:ANALOG_RX_BATCH_SESSION_CONTROL="1"
$env:ANALOG_RX_BATCH_SESSION_MAX_IMAGES="16"
$env:ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS="1"
$env:ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY="1"
$env:ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC="0.05"
$env:ANALOG_MIN_SYNC_METRIC="0.05"
$env:ANALOG_ROBUST_SYNC="0"
$env:ANALOG_REMOTE_CLEANUP_MODE="skip"
$env:ANALOG_DECODE_PIPELINE_WARMUP="1"
$env:OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="0"
$env:MLKEM_USRP_MAX_ARQ_ROUNDS="12"
$env:USRP_MAX_ARQ_ROUNDS="12"
$env:ANALOG_RETRY_ON_BURST_MISS="1"
$env:ANALOG_RETRY_ON_LOW_SYNC="1"
$env:ANALOG_LOW_SYNC_RETRY_THRESHOLD="0.08"
.\docker\run-demo-tailscale.ps1
```

`run-demo-tailscale.*` 仍默认设置 `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded` 这个历史 profile 名称，但脚本会先显式设置 USRP IQ 和认证默认值：

```text
OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp
MLKEM_TRANSPORT_MODE=usrp
JSCC_LINK_MODE=iq-direct
MLKEM_AUTH_ENABLED=1
MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
```

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
