# 飞腾多核弱网安全语义视觉回传

这是第十届全国大学生集成电路创新创业大赛的源码和复现仓库。

我们做的是一套面向低空弱网场景的视觉回传 demo：上位机发起任务，图像侧走预录 latent 或现场输入，飞腾派板端用 TVM / MNN / PyTorch 做语义重建，OpenAMP 负责板端控制面，ML-KEM / Tongsuo 负责安全信道。

评委复现时不需要再拉额外 submodule。源码、模型、板端 runtime、OpenAMP 固件、输入样本和 Docker 脚本都已经随仓库放好，`Semantic-Communication/`、`liboqs/`、`board_deps/` 都是交付包的一部分。

## 先跑哪一个

| 如果现场只有 | 跑这个 | 能看到 |
|---|---|---|
| 一台能跑 Docker 的电脑 | `docker/repro.*` | 镜像构建、依赖检查、预录 API、Electron smoke |
| 想先看桌面端界面 | `docker/run-demo.*` | 原生 Electron cockpit，使用预录数据 |
| 能连上飞腾派和 Tailscale | `docker/run-demo-wslg-tailscale.ps1` | Electron 连板端的真机链路 |
| 要复测板端性能 | `docker/run-board-cli-smoke.*` | TVM / MNN / PyTorch 三路结果和 `logs/demo-kpi-summary.json` |

## demo 里有什么

看代码时可以先从这几处进：

- `Semantic-Communication/cockpit_desktop/`：Electron 上位机界面。
- `Semantic-Communication/session_bootstrap/`：demo server、OpenAMP 控制面脚本、板端运行脚本和报告。
- `mlkem_link/`：ML-KEM 安全信道相关 Python 代码。
- `board_deps/`：板端固件、模型、runtime、输入样本和校验清单。
- `docker/`：Docker 复现、Electron demo、Tailscale 和板端 smoke 的入口脚本。

实际演示时主要分成三块：数据面负责把 latent 或现场输入送到板端；控制面负责下发任务、读取状态和收集日志；Electron 负责把链路状态、重建结果和耗时展示出来。

## 1. Docker 基础复现

这一步不需要飞腾派，适合评委先检查仓库能不能在干净容器里跑起来。

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

真机演示需要评审机器和飞腾派在同一个 Tailscale 网络内。脚本里保留的历史地址只对应我们自己的验证环境；复测时请用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定现场板卡地址。

Electron 真机 demo 会沿用原始板端目录结构，所以板卡上要先有固件、模型、runtime 和 Tongsuo / liboqs 相关文件。`docker/run-demo-wslg-tailscale.ps1` 只负责启动上位机和网络链路，不会自动改写板端的 `/lib/firmware`、`/boot`、`/usr/local/tongsuo` 或 `/home/user/Downloads`。

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
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Electron 界面里的板卡连接/授权区域会要求填写板卡 SSH 密码。

## 4. 板端三路性能复测

如果评委要看板端实测数字，跑这一组脚本。它会通过 Docker 内的 Tailscale 连接飞腾派，把当前仓库复制到板端新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后在隔离目录里跑 TVM、MNN、PyTorch 三条推理路径。

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

KPI 汇总写在板端隔离目录的 `logs/demo-kpi-summary.json`。字段和 Electron 前端展示口径一致：

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
- TVM current / baseline artifact 与 TVM runtime。
- MNN 模型，以及 MNN / PyTorch 便携 runtime。
- PyTorch JSCC generator checkpoint。
- 预录 latent 和 encoder output 输入。
- ML-KEM、Tongsuo、公钥和远端 helper 快照。

完整性检查：

```bash
bash board_deps/verify-board-deps.sh
```

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
```

这些路径可以由 `board_deps/install-board-deps.sh` 从仓库内材料恢复。没有先准备这些文件时，Electron 界面仍可能启动，但 live 推理、OpenAMP 固件状态或安全信道相关功能可能会失败或回退。

## 6. 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── README.md
├── requirements.txt
├── docker/                    # Docker 复现、Electron、Tailscale、板端 smoke 入口
├── board_deps/                # 板端固件、runtime、模型、输入和校验清单
├── mlkem_link/                # ML-KEM / secure channel Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # Electron 上位机、OpenAMP 控制面和板端脚本
├── liboqs/                    # liboqs 源码，Docker 构建时编译安装
└── host_pic_to_latent/        # JSCC / latent 编解码辅助代码
```
