# 飞腾多核弱网安全语义视觉回传

这是第十届全国大学生集成电路创新创业大赛的源码和复现仓库。

本项目是一套面向低空弱网场景的视觉回传 demo：上位机发起任务，图像侧走预录 latent 或现场输入，飞腾派板端用 TVM / MNN / PyTorch 做语义重建，OpenAMP 负责板端控制面，ML-KEM / Tongsuo / liboqs 负责安全信道（默认 `DUAL_REQUIRED`，SM2 + ML-DSA-65 双签）。

复现时不需要再拉额外 submodule。源码、模型、板端 runtime、OpenAMP 固件、UHD images、输入样本和 Docker 脚本都已经随仓库放好，`Semantic-Communication/`、`liboqs/`、`board_deps/` 都是交付包的一部分。

## 先跑哪一个

| 如果现场只有 | 跑这个 | 能看到 |
|---|---|---|
| 一台能跑 Docker 的电脑 | `docker/repro.*` | 镜像构建、依赖检查、预录 API、Electron smoke |
| 想先看桌面端界面 | `docker/run-demo.*` | 原生 Electron cockpit，使用预录数据 |
| 能连上飞腾派和 USRP | `Semantic-Communication/cockpit_desktop/start-demo.ps1` | 现场主流程：USRP IQ 直传、认证加密默认开启、10 张隐藏预热 |
| 要跑旧交付容器入口 | `docker/run-demo-tailscale.ps1` | 原生 PowerShell + Docker 的 Electron 真机链路 |
| 要从零复测板端性能 | `docker/run-board-cli-smoke.*` | 自包含上传依赖后跑 TVM / MNN / PyTorch |
| 要日常快速复测性能 | `docker/run-board-cli-benchmark-fast.*` | 复用板端依赖缓存，只同步代码层 |

## 当前演示 Quick Start

现场演示主线是 `Cockpit Desktop -> USRP IQ 直传 -> 板端 TVM big.LITTLE 重建`。Windows 现场入口已经封装成 PowerShell 脚本；它会查找 Git Bash 作为启动外壳，Bash/SSH/TX 热路径优先走 Docker，不使用 WSL：

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\Semantic-Communication\cockpit_desktop
.\start-demo.ps1
```

`start-demo.ps1` 默认按当前板卡恢复口径使用 `user/user`。如果现场改过板卡地址或密码，用参数覆盖：

```powershell
.\start-demo.ps1 -BoardHost '<board-ip>' -BoardUser '<board-user>' -BoardPassword '<board-password>'
```

`start-demo.ps1` 是当前推荐入口。`start-dev.sh` 仍是底层 Git Bash 入口，保留给调试；`docker/run-demo-tailscale.ps1` 是旧交付容器入口，也可以直接运行：

```powershell
.\docker\run-demo-tailscale.ps1
```

当前默认值：`REMOTE_HOST=100.121.87.73`、`REMOTE_USER=user`、`REMOTE_PASS=user`、`MLKEM_TRANSPORT_MODE=usrp`、`OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp`、`JSCC_LINK_MODE=iq-direct`、`MLKEM_AUTH_ENABLED=1`、`MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`、`REMOTE_USRP_RX_DIR=/home/user/cockpit_usrp_rx`、板端 IQ decode Python 为 `/home/user/venv/bin/python`、`OPENAMP_IQ_SEGMENT_SIZE=30`、`OPENAMP_IQ_SEGMENT_REPAIR_PASSES=2`、`ANALOG_TX_NORMALIZATION_REFERENCE_PEAK=6`、`COCKPIT_STARTUP_USRP_WARMUP=1`、`COCKPIT_STARTUP_USRP_WARMUP_COUNT=10`。

`start-dev.sh` 会在显示 Cockpit Desktop 前静默尝试 10 张 `USRP IQ + TVM` warm-up；默认至少 5 张有效完成即可放行 UI，并清掉隐藏 batch 状态，避免第一批冷启动 decode / TVM 尾部污染演示指标。这 10 张只是冷启动预热，不是 IQ streaming 微批。如需调试界面而跳过预热，可临时设置 `COCKPIT_STARTUP_USRP_WARMUP=0`。

USRP2922 网口恢复入口按用途分开：

```powershell
# Windows 上位机现场入口：先只看状态，不改配置
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status

# 管理员 PowerShell：配置上位机/TX 网口，网卡名按 Status 输出填写
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target UpperHost -InterfaceAlias "以太网"

# 板端/RX 网口默认由 systemd 开机自恢复；不通时先跑快速兜底
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Board -BoardHost 100.121.87.73 -Fast
```

Windows 入口采用 `192.168.10.1/32 + 192.168.10.2/32` 显式 host route，避免现场多网卡或旧 `/24` 配置把 USRP 包路由到错误网口。

板端自启动服务为 `usrp2922-board-autostart.service`，一次性安装入口在板端运行：

```bash
bash /home/user/USRP292x/InstallBoardUsrp2922Autostart.sh
```

服务会在开机后检查 `eth0 -> 192.168.10.22`，不通时用快速恢复重建板端 USRP 网口；完整排障时再使用不带 `-Fast` 的 `ConfigureUsrp2922DemoNetwork.ps1 -Target Board`。

```bash
# 上位机/TX 侧：本机网口 192.168.10.1/32 -> USRP 192.168.10.2
sudo ./USRP292x/SetupUsrp2922UpperHostNetwork.sh

# 板端/RX 侧：板端网口 192.168.10.11/32 -> USRP 192.168.10.22
sudo ./USRP292x/SetupUsrp2922BoardNetwork.sh
```

通用诊断入口是 `./USRP292x/Usrp2922Network.sh detect|probe|auto-init|status`。板端当前部署在 `/home/user/USRP292x/`，若自动探测选错双网口设备，可显式加 `USRP2922_BOARD_IFACE=eth0`。

写材料时优先引用当前严格可靠性回归：USRP IQ `300/300` accepted，传输/解包 median `411.59 ms`、p95 `3423.45 ms`；板端 TVM 重建 median `245.42 ms`、mean `254.71 ms`、p95 `301.73 ms`。历史速度 profile 的 IQ median `166.63 ms`、p95 `198.46 ms` 可作为单独优化记录，不能与当前严格 profile 混写。预录 TVM 250 ms 参考线为 median `243.30 ms`、mean `252.91 ms`；QPSK fallback 约 `2.96 s/image`；PSNR `37.0445`，SSIM `0.97494`。USRP IQ 数据面走射频链路，不经过 Tailscale，也不宣称 IQ payload 已被 ML-KEM/SM4 加密；安全信道用于控制/认证面准入。

当前交接入口是 [`HANDOFF.md`](./HANDOFF.md)。它面向下一位开发同学和写材料同学，包含默认参数、实验开关、典型指标、安全边界和文件组织现状；旧 handoff、计划、运行记录和过程审计仅本地保留，不作为提交入口。

## 板端备份与恢复边界

`board_deps/` 是板端文件备份包，不是上位机程序目录。它保存可恢复飞腾派环境的 aarch64 runtime、模型、输入、OpenAMP 固件/DTB、UHD images、ML-KEM 远端脚本快照和公钥材料；上位机启动脚本在 `Semantic-Communication/cockpit_desktop/` 和 `docker/`。当前仓库内 `board_deps/` 约 718 MB，共 38 个文件，配有 `FILES.txt` 和 `SHA256SUMS`。2026-07-15 已做两项校验：本地 `sha256sum -c board_deps/SHA256SUMS` 通过，当前板卡执行 `board_deps/verify-board-deps.sh` 返回 `board-deps-ok`。

板端备份刷新入口是 `docker/pull-board-deps.ps1` / `.sh`，会从当前飞腾派拉取运行时、模型、固件、OpenAMP 材料和 ML-KEM helper 到 `board_deps/`。这一步会改动大文件，只在确认板端状态比仓库更新时使用。恢复干净板卡时，把仓库放到板端后运行：

```bash
bash board_deps/install-board-deps.sh
bash board_deps/verify-board-deps.sh
```

当前板卡默认 SSH 账号口令是 `user/user`，已写入现场启动脚本，方便断电或换机后快速恢复。Tailscale 凭据和私钥不进入仓库；`board_deps/crypto/public_keys/` 只保存演示需要的公钥归档。

如果要抽查原图和重建图误差，不需要接入主 demo，直接跑独立脚本：

```powershell
python scripts/audit_reconstruction_error.py `
  --original-dir path\to\originals `
  --recon-dir path\to\reconstructions `
  --sample-size 20 `
  --seed 0 `
  --output-json artifacts\recon_error_audit.json `
  --output-csv artifacts\recon_error_audit.csv
```

## 主要目录

- `Semantic-Communication/cockpit_desktop/`：Electron 上位机界面。
- `Semantic-Communication/session_bootstrap/`：demo server、OpenAMP 控制面脚本、板端运行脚本和必要 fixture；新运行报告默认本地忽略。
- `mlkem_link/`：ML-KEM + SM2 + ML-DSA 安全信道 Python 包（kem、auth、kdf、secure_channel、session）。
- `board_deps/`：板端固件、UHD images、模型、runtime、输入样本和校验清单。
- `USRP292x/`：NI USRP-2922 / N210 数据面。包含两条并存路线：analog latent-IQ 直传链路（`AnalogLatentLink.py` + `RunAnalogLatentBatch.py`，当前 USRP 默认），以及原有 QPSK/CRC/ARQ 可靠字节链路兜底。
- `docker/`：Docker 复现、Electron demo、Tailscale 和板端 smoke 的入口脚本。

实际演示时主要分成三块：数据面负责把 latent 或现场输入送到板端；控制面负责下发任务、读取状态和收集日志；Electron 负责把链路状态、重建结果和耗时展示出来。

## 1. Docker 基础复现

这一步不需要飞腾派，适合先检查仓库能不能在干净容器里跑起来。

Linux / WSL:

```bash
./docker/repro.sh
```

Windows PowerShell:

```powershell
.\docker\repro.ps1
```

看到下面几行，基础复现就通过了：

```text
deps-ok
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

`repro.*` 会构建 Docker 镜像，检查 Python、Node、Electron、liboqs 相关依赖，运行一组最小 pytest，然后在 Xvfb 下把 Electron 应用实际拉起来做 smoke 检查。这一步只走预录数据，不连接飞腾派，也不复测板端性能数字。

## 2. 查看 Electron 桌面端

如果只想先看上位机界面，跑下面这个入口：

Linux / WSL:

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

这个模式默认使用预录数据。Linux / WSL 需要可用的 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。

## 3. 飞腾派真机演示

真机演示需要运行机器和飞腾派在同一个 Tailscale 网络内。脚本里保留的默认地址只对应既有验证环境；复测时请用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定实际板卡地址。

Windows 现场优先使用原生 PowerShell + Docker，不走 WSL。用于启动当前 USRP IQ 直传 + handwritten TVM + big.LITTLE 演示时，运行：

```powershell
.\docker\run-demo-tailscale.ps1
```

`run-demo-tailscale.*` 默认写入当前验证环境：`REMOTE_HOST=100.121.87.73`、`REMOTE_USER=user`、`REMOTE_SSH_PORT=22`、Docker SSH runner、Docker USRP TX runner、`MLKEM_TRANSPORT_MODE=usrp`、`OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp`、`JSCC_LINK_MODE=iq-direct`、`MLKEM_AUTH_ENABLED=1`、`MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`、板端 `/home/user/venv/bin/python`、`ANALOG_SPS=2`、`ANALOG_AMPLITUDE=6000`、`ANALOG_TX_NORMALIZATION_REFERENCE_PEAK=6`、`ANALOG_RX_TAIL_SEC=0.040`、`RX_ARM_WAIT_MS=500`、`ANALOG_MIN_SYNC_METRIC=0.05`、`ANALOG_SYNC_PROFILE=fast-first`、`ANALOG_FAST_SYNC_CANDIDATES=4`、`ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS=1024`、`ANALOG_FALLBACK_SYNC_CANDIDATES=4`、`ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS=1024`、`ANALOG_IQ_QUALITY_GATE=1`、`ANALOG_IQ_QUALITY_MIN_SYNC_METRIC=0.75`、`ANALOG_IQ_MIN_PILOT_GAIN_RATIO=0.85`、`ANALOG_IQ_MAX_EVM_RMS=0.75`、`ANALOG_IQ_MIN_SNR_DB=3.0`、`ANALOG_ROBUST_SYNC=0`、`ANALOG_REMOTE_DECODED_FORMAT=npy`、`ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal`、`ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1`、`ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05`、`ANALOG_RX_BATCH_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16`、`ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5`、`ANALOG_RETRY_ON_BURST_MISS=1`、`ANALOG_RETRY_ON_LOW_SYNC=1`、`ANALOG_LOW_SYNC_RETRY_THRESHOLD=0.08`、`MLKEM_USRP_MAX_ARQ_ROUNDS=12`、`ANALOG_DECODE_PIPELINE_WARMUP=1`、`OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0`、`OPENAMP_TVM_BATCH_RUNNER=biglittle`。质量门限开启时 `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC` 会被安全地压成 0，等待完整 sync/pilot summary 后再放行 TVM。板卡密码不进仓库；在 Electron 界面填写，或运行前临时设置 `REMOTE_PASS`。

这个入口仍保留 `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded` 这个历史 profile 名称，但脚本已经显式设置 USRP IQ 和认证默认值，所以当前演示按 USRP IQ 主线理解。若只想复现预录 TVM 250 ms，可临时覆盖 `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded`、`MLKEM_TRANSPORT_MODE=tcp`，并保持认证设置按测试目的单独说明。2026-07-16 当前严格 profile 已完成 IQ `300/300` 和 TVM `300/300`：传输/解包 median `411.59 ms`、p95 `3423.45 ms`；后接 TVM median `245.42 ms`、mean `254.71 ms`、p95 `301.73 ms`。预录 TVM 参考线为 median `243.30 ms`、mean `252.91 ms`。

切到 USRP 模式时，Tailscale 只承载控制面：cockpit API、SSH 启停板端进程、状态、日志和结果取回。IQ/latent 主数据面应由本机 TX USRP 到板端 RX USRP 的射频链路承载，不经过 Tailscale；`ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir` 用于让板端就地解码，避免把原始 IQ 捕获文件拉回控制面。默认 `JSCC_LINK_MODE=iq-direct`，也可在 cockpit 里切回 `qpsk` 兜底。快速 IQ profile 默认 `OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0`，保持 TX/RX 常驻，避免每轮反复初始化；`RX_ARM_WAIT_MS=500` 给 RX server 更保守的启动确认窗口；`ANALOG_DECODE_PIPELINE_WARMUP=1` 会把板端 decode 冷启动挪到 worker startup；`ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5` 只缩短未真正开始接收时的 arm-failure 恢复，不改变正常 `STOP` drain 的 8 秒保护；`ANALOG_REMOTE_CLEANUP_MODE=skip` 用于避免热路径后台删除抢板端 I/O，演示后可清理 `/tmp/usrp292x_remote_runs`。USRP 后接重建目前支持 TVM 和 MNN；PyTorch 在 cockpit 中只作为预录参考对照，不启动 USRP 数据面。Cockpit 的 USRP transport 对比优先显示 raw round records 的 median/p95，避免单个 RF/RX outlier 把结果卡片拉歪。

IQ 串行长批次默认按 30 张分段。分段边界会重建 RX streamer，TX streamer 保持常驻并清空上一段发送状态，避免反复创建 TX streamer 导致 UHD FIFO ACK 超时。段内仍使用现有单图 ARQ 和质量门限，首轮失败项默认最多补传两轮；每段结束后通过常驻 decode worker 清理板端临时 capture，防止 `/dev/shm` 累积。所有图像 accepted 后才启动 TVM，不会把部分结果发布成有效重建。`OPENAMP_IQ_SEGMENT_SIZE=0` 可恢复旧的连续长批次；`OPENAMP_IQ_SEGMENT_REPAIR_PASSES=0` 只关闭段级失败项补传。`ANALOG_PIPELINE_DEPTH>1` 仍使用原 pipeline 路径，为避免存在在途 capture 时重置 RF，该路径不做分段 RESET。QPSK 不受此配置影响。

IQ 波形默认使用固定参考峰值 `ANALOG_TX_NORMALIZATION_REFERENCE_PEAK=6`，避免高峰值 latent 把整帧导频一起压低。若波形可能触及 SC16 上限，编码器会自动增大实际除数并保留余量；`0` 可恢复旧的逐帧峰值归一化。该修复不改变 latent 数值或 TVM 输入，只稳定不同图片之间的导频发射幅度。

如果临时绕开 Docker cockpit、直接在 Windows 原生后端调试，必须避免 `C:\Windows\System32\bash.exe` 的 WSL stub。使用 Git Bash，并让 SSH helper 走 Paramiko runner：

```powershell
$env:OPENAMP_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:GIT_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:OPENAMP_SSH_RUNNER="paramiko"
$env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER="1"
```

Electron 真机 demo 会沿用原始板端目录结构，所以板卡上要先有固件、模型、runtime 和 Tongsuo / liboqs 相关文件。`docker/run-demo-tailscale.*` 只负责启动上位机和网络链路，不会自动改写板端的 `/lib/firmware`、`/boot`、`/usr/local/tongsuo` 或 `/home/user/Downloads`。

如果是干净飞腾派，先把本仓库放到板端，然后在板端执行：

```bash
bash board_deps/install-board-deps.sh
bash board_deps/verify-board-deps.sh
```

如果板卡已经跑过 demo，先做一次校验即可：

```bash
bash board_deps/verify-board-deps.sh
```

校验通过后再启动 Electron 真机入口：

```powershell
.\docker\run-demo-tailscale.ps1
```

如果需要先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Electron 界面里的板卡连接/授权区域会要求填写板卡 SSH 密码。

## 4. 板端三路性能复测

如果要看板端实测数字，优先跑完整自包含 smoke。它会通过 Docker 内的 Tailscale 连接飞腾派，把当前仓库复制到板端新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后在隔离目录里跑 TVM、MNN、PyTorch 三条推理路径。

这和第 3 节的 Electron 真机 demo 不一样：CLI smoke 优先使用仓库内的 `board_deps/runtime`、`board_deps/tvm`、`board_deps/mnn`、`board_deps/inputs`，不要求板端已经存在 demo 使用的固定 `/home/user/Downloads/...` 目录结构。它适合复测性能数字，但不替代 Electron 真机 demo 的板端环境。

Windows PowerShell:

```powershell
.\docker\run-board-cli-smoke.ps1
```

Linux / WSL:

```bash
bash docker/run-board-cli-smoke.sh
```

脚本会交互式询问板卡 SSH 密码。调试时可以先把输入数量调小：

```powershell
$env:BOARD_CLI_MAX_INPUTS="3"
.\docker\run-board-cli-smoke.ps1
```

默认 `BOARD_CLI_MAX_INPUTS=300`。跑完最后一行应为：

```text
cli-smoke-ok
```

完整 smoke 会显示每个阶段的开始、结束和耗时，包括 Tailscale、远端目录创建、仓库上传、远端解包、三路 benchmark 和结果汇总。当前仓库按这条路径上传的压缩流约 `421 MB`，板端完整隔离目录通常占用 `1.7 GB` 到 `2.0 GB`。这是为了验证“干净板端可从仓库材料复现”，不适合作为日常反复测速入口。

如果要反复测速度，先准备一次板端依赖缓存，然后使用快速入口：

```powershell
$env:BOARD_CLI_REFRESH_CACHE="1"
.\docker\run-board-cli-smoke.ps1
Remove-Item Env:BOARD_CLI_REFRESH_CACHE

.\docker\run-board-cli-benchmark-fast.ps1
```

Linux / WSL:

```bash
BOARD_CLI_REFRESH_CACHE=1 bash docker/run-board-cli-smoke.sh
bash docker/run-board-cli-benchmark-fast.sh
```

快速入口默认复用 `/home/user/iccomp_board_deps_cache/board_deps`，不再上传 `board_deps/runtime`、TVM/MNN/PyTorch 模型和输入大包，只同步代码覆盖层并软链接板端缓存。首次运行时会把缓存中的 Python runtime 解到 `/home/user/iccomp_board_deps_cache/runtime`；后续运行会复用该目录。快速入口默认只保留 `logs/`，会清理本次运行的临时 `repo/` 和 `work/`，避免持续占用板端空间。如需保留完整临时输出，可设置 `BOARD_CLI_FAST_KEEP_WORK=1`。

KPI 汇总写在板端隔离目录的 `logs/demo-kpi-summary.json`。统计字段和 Electron 前端展示值一致：

| 路径 | KPI 字段 |
|---|---|
| TVM | `inference_ms.median_ms` |
| MNN | `total_ms.median_ms` |
| PyTorch | `run_median_ms` |

MNN 这里看 `total_ms`，因为前端展示的是端到端 wall time，包含预处理、`runSession`、后处理和保存。`run_ms` 只覆盖 MNN session 执行时间，不能直接拿来和 demo 卡片里的数字对齐。

最近一次 300 输入隔离验证的参考值：TVM 约 `257 ms`，MNN 约 `363 ms`，PyTorch 约 `913 ms`。复测时数值会受板端温度、DDR 状态和后台进程影响。

## 5. 板端文件

`board_deps/` 里放的是板端运行会用到的文件：

- OpenAMP 当前固件、DTB、源码、构建产物和运行服务。
- NI USRP-2922 / N210 使用的 UHD 4.6.0.0 images 官方包分片。
- TVM current / baseline artifact 与 TVM runtime。
- MNN 模型，以及 MNN / PyTorch 便携 runtime。
- PyTorch JSCC generator checkpoint。
- 预录 latent 和 encoder output 输入。
- ML-KEM、Tongsuo、公钥和远端 helper 快照。

完整性检查：

```bash
bash board_deps/verify-board-deps.sh
```

UHD images 包因为超过 GitHub 单文件限制，以分片形式放在 `board_deps/usrp/uhd-images/`。需要使用官方 images 包时先重组：

```bash
bash board_deps/reassemble-large-files.sh
```

重组后得到：

```text
board_deps/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz
```

该文件可解压到 UHD 使用的 images 目录，也可以通过 `UHD_IMAGES_DIR` 指向解压后的 images 目录。

`board_deps/install-board-deps.sh` 会写入或覆盖板端 firmware、DTB、runtime 和模型，只适合初始化干净板卡。已经能跑 demo 的板卡，建议直接走第 4 节的 isolated CLI smoke。

Electron 真机 demo 主要会用到下面这些板端路径：

```text
/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so
/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so
/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
/home/user/Downloads/jscc-test/简化版latent
/home/user/Downloads/jscc-test/encoder_outputs
/home/user/Downloads/MNNversion/origin/model1.mnn
/home/user/anaconda3/envs/tvm310_safe
/home/user/tvm_samegen_safe_20260309/build
/home/user/tvm_samegen_20260307/python
/home/user/liboqs-dist
/home/user/libtongsuo_sig_bridge.so
/usr/local/tongsuo
/lib/firmware/openamp_core0.elf
/boot/phytium-pi-board-v3-openamp.dtb
/home/user/.openamp-demo/
/home/user/keys/server_sm2_identity.key
/home/user/keys/server_sm2_identity.pub
/home/user/keys/server_mldsa_identity.key
/home/user/keys/server_mldsa_identity.pub
```

这些路径可以由 `board_deps/install-board-deps.sh` 从仓库内材料恢复。没有先准备这些文件时，Electron 界面仍可能启动，但 live 推理、OpenAMP 固件状态或安全信道相关功能可能会失败或回退。

## 6. ML-KEM 安全信道（默认启用）

控制面跑在 ML-KEM + Tongsuo SM2 + liboqs ML-DSA-65 之上，认证策略默认 `DUAL_REQUIRED`：每次握手同时校验 SM2 和 ML-DSA 两种签名，抗量子 + 国密合规一起拿。容器是 Initiator/client，飞腾派是 Responder/server。

### 6.1 关键组件

```text
mlkem_link/                 # Python 包：kem / auth / kdf / secure_channel / session
docker/tongsuo_kem_bridge.c # ML-KEM-768 KEM 桥接（Tongsuo → Python ctypes）
docker/tongsuo_sig_bridge.c # SM2 签名桥接（Tongsuo → Python ctypes）
board_deps/crypto/          # aarch64 板端 libtongsuo_sig_bridge.so / liboqs-dist / public_keys
```

容器端额外需要的 x86_64 桥接库（`libtongsuo_sig_bridge.so`、liboqs）由 Dockerfile 在镜像构建阶段编译到 `/opt/liboqs` 与 `/workspace/artifacts/crypto/`。

### 6.2 容器内启动带认证的 server

`scripts/start_server_auth.sh` 是带认证模式启动 server.py 的入口，已经把 15 个 `MLKEM_AUTH_*` 环境变量配齐：

```bash
# 容器内（推荐用 start_server_auth.sh，不要直接 export）
bash /workspace/scripts/start_server_auth.sh
```

关键环境变量（已写在脚本里，无需手动设置）：

| 变量 | 容器（x86_64） | 板端（aarch64） |
|---|---|---|
| `TONGSUO_SIG_BRIDGE` | `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so` | `/home/user/libtongsuo_sig_bridge.so` |
| `MLKEM_REMOTE_TONGSUO_SIG_BRIDGE` | `/home/user/libtongsuo_sig_bridge.so`（板端路径） | — |
| `OQS_INSTALL_PATH` | `/opt/liboqs` | `/home/user/liboqs-dist` |
| `MLKEM_REMOTE_OQS_INSTALL` | `/home/user/liboqs-dist`（板端路径） | — |
| `MLKEM_AUTH_SIG_POLICY` | `DUAL_REQUIRED` | `DUAL_REQUIRED` |
| `MLKEM_AUTH_ENABLED` | `1` | `1` |
| `MLKEM_AUTH_SERVER_ID` | `phytium-board` | `phytium-board` |

容器只验签不签发，所以容器的 SM2 私钥可以缺失，但容器必须能读到板端 SM2/ML-DSA **公钥**（`/workspace/keys/server_*_identity.pub`），用于校验板端发来的签名。

### 6.3 验证 handshake

```bash
# 容器内
python /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py
```

成功时日志应包含 `handshake_ms ≈ 1400`、`last_sha256_match=true`、`session_count=1`、`auth_enabled=true`、`sig_policy=DUAL_REQUIRED`、`server_id=phytium-board`。

### 6.4 容器 x86_64 SM2 桥接编译

容器是 x86_64，不能直接用 `board_deps/crypto/libtongsuo_sig_bridge.so`（aarch64 二进制）。Dockerfile 已经处理这部分，但如果需要重新编译：

```bash
# 容器内
apt-get install -y libssl-dev
gcc -O2 -fPIC -shared /workspace/docker/tongsuo_sig_bridge.c \
  -o /workspace/artifacts/crypto/libtongsuo_sig_bridge.so -lcrypto
```

编译输出会有 `EC_KEY_*` deprecation 警告，无害。Ubuntu 22.04 自带的 vanilla OpenSSL 3.0.2 支持 SM2 sign/verify（走 deprecated `EC_KEY` 路径），**但不支持** SM2 keygen via `EVP_PKEY_Q_keygen("SM2")`，调用会返回 `rc=-1`。这不影响容器使用，因为容器只验签，keygen 在板端 Tongsuo 里完成。

详细部署指南、典型故障和健康检查脚本见 [`security/mlkem_auth_setup.md`](./security/mlkem_auth_setup.md)。

## 7. 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── requirements.txt
├── docker/                    # Docker 复现、Electron、Tailscale、板端 smoke 入口
├── board_deps/                # 板端固件、runtime、模型、输入和校验清单
├── USRP292x/                  # NI USRP-2922 / N210 数据面（QPSK + IQ 直传并存）
├── mlkem_link/                # ML-KEM / secure channel Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # Electron 上位机、OpenAMP 控制面和板端脚本
├── liboqs/                    # liboqs 源码，Docker 构建时编译安装
├── host_pic_to_latent/        # JSCC / latent 编解码辅助代码
└── docs/                      # README、现场启动、当前交接、设计说明和 archive 历史文档
```

## 8. IQ 直传路线（WIP）

`feat/iq-direct-tx` 分支新增的 analog latent-IQ 直传链路把链路从

```text
JSCC Enc → 实数 latent → QPSK Mod → Channel → QPSK Demod → 实数 latent → JSCC Dec
```

简化为

```text
JSCC Enc → 实数 latent → I/Q 配对 → Channel → I/Q 还原 → JSCC Dec
```

跳过量化、QPSK 调制、CRC/ARQ，让真实无线信道直接作用在语义 latent 上。

当前阶段：

- QPSK 链路保留为兜底演示路径；Cockpit 切到 USRP 模式时默认使用 `iq-direct`，也可在界面手动切回 `qpsk`。`JSCC_LINK_MODE` 环境变量和 Cockpit 的 JSCC 链路开关都可切换：`qpsk` 走原可靠字节链路，`iq-direct` 切到 `RunAnalogLatentBatch.py`。
- IQ 直传 PHY 层（`USRP292x/AnalogLatentLink.py`）已完成并通过软件 loopback、CFO/AWGN/相位扫描测试。
- 2026-07-09 早期真机 cockpit USRP/IQ fast profile（`sps=2`、`amp=6000`、`tail=0.05`、`min_sync=0.05`、`robust=0`、`ARQ2`、`remote-dir`、`cleanup=skip`、`decode warmup=1`）验证 `20/20` 通过，fallback `0`，USRP transport median `213.53 ms`、decode median `67.04 ms`、airtime `9.578 ms`；同轮 TVM big.LITTLE median `240.89 ms`。当前 cockpit 默认已改为 ARQ5、low-sync retry 和 `.npy` remote-dir，仍需新一轮 300 张 gate 验证。
- 2026-07-11 USRP 模式下 MNN 已接入 remote-dir latent；一次 MNN/USRP 启动卡死的根因为后端在持有 `DashboardState` 锁时 arm ML-KEM security，已改为锁外执行并加回归测试。PyTorch 未接入 USRP 后接推理，点击 PyTorch 会返回预录参考，不消耗 USRP 链路。
- IQ 直传 batch runner 默认启用进程内本地 codec（`ANALOG_IN_PROCESS_LOCAL_CODEC=1`）、首次 latent loader warmup（`ANALOG_WARMUP_LOCAL_CODEC=1`）和板端 decode-server pipeline warmup（`ANALOG_DECODE_PIPELINE_WARMUP=1`），避免每张图重复启动 Python/torch 或承担 FFT/NumPy 冷启动。warmup 单独记录为 `codec_warmup_wall_sec` 和 `remote_decode_worker_ready.decode_pipeline_warmup_*`。
- 真机 IQ 直传前可先生成板端同步包：Windows 运行 `.\docker\prepare-iq-board-sync.ps1`；容器内实际执行 `bash /workspace/scripts/prepare_iq_board_sync.sh`。该脚本只打包，不保存密码；manifest 会提示运行时输入 `SSHPASS` 后再 scp/ssh 到板端，并在板端验证步骤中激活 `tvm310_safe` 环境。
- 现场切 USRP/IQ 前可运行 `python Semantic-Communication/session_bootstrap/scripts/check_openamp_demo_session_readiness.py --format text`。输出里的 `usrp:` 行会报告是否启用 USRP、当前 `qpsk`/`iq-direct`、`REMOTE_USRP_RX_DIR` 是否缺失，以及 IQ 同步包脚本/产物是否存在；Cockpit 的板卡连接设置也会同步显示会话、USRP RX、JSCC 链路和图库输入的就绪/阻塞状态，并可直接保存板端 USRP RX 目录。
- Encoder/TVM helper/latent_transport 三处增量补丁已落地，对 QPSK 路径零破坏（默认行为不变，需通过 `JSCC_CHANNEL_MODE=real-usrp` 等环境变量激活）。
- Server 端 `JSCC_LINK_MODE` 开关、双机 SSH/SCP 远端 RX（`local` / `remote-pull` / `remote-decode` 三档）、Cockpit UI IQ/QPSK 选择与结果 badge 全部 wire 完成。USRP 默认资产发现会优先使用 final 包内 latent，也会兼容工作区根目录的 `原始图像/00000001.jpg...` 和 `jscc-test/encoder_outputs/`；USRP live payload 会附带 `original_gallery`，例如 50 张任务展示 `00000001-00000050` 的原图范围。
- ML-KEM 安全信道（见第 6 节）已经独立可用，`DUAL_REQUIRED` 默认启用，handshake 在 1.4 s 量级、SHA-256 校验通过。
- 仍未做：真机线缆 + 30 dB 衰减器系统化扫描、TX/RX gain 配对调优、长批量 p95/outlier 抑制。
- 已知 OpenAMP 控制面问题：`control_guard_state=PROBE_ERROR`、`board status endpoint unavailable: timed out`，与 ML-KEM 数据面相互独立，不影响握手和加密通道本身。

当前差距、风险点、默认参数、典型指标和软件验证命令见 [`HANDOFF.md`](./HANDOFF.md)。设计原理和完整 0-16 Pro 方案见 [`design/analog_latent_iq_phy.md`](./design/analog_latent_iq_phy.md) 与 [`design/analog_latent_iq_phy_full_proposal.md`](./design/analog_latent_iq_phy_full_proposal.md)。
