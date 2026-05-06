# 飞腾多核弱网安全语义视觉回传

这是我们参加第十届全国大学生集成电路创新创业大赛使用的源码和复现仓库。

项目做的是低空弱网场景下的视觉回传：上位机发起任务，链路侧使用预录 latent 或现场输入，飞腾派板端用 TVM / MNN / PyTorch 做语义重建，OpenAMP 负责板端控制面，ML-KEM / Tongsuo 负责安全信道。

源码、模型、板端 runtime、OpenAMP 固件、输入样本和 Docker 复现脚本都已经放在仓库里。`Semantic-Communication/`、`liboqs/`、`board_deps/` 随交付包一起展开，不需要现场再初始化 submodule。

## 先按这个选

| 现场条件 | 入口 | 结果 |
|---|---|---|
| 只有 Docker，没有飞腾派 | `docker/repro.*` | 构建复现镜像，检查依赖、预录 API 和 Electron 主进程 |
| 想先看桌面端界面 | `docker/run-demo.*` | 打开原生 Electron cockpit，默认使用预录数据 |
| 能连接飞腾派和 Tailscale | `docker/run-demo-wslg-tailscale.ps1` | 运行 Electron 真机链路，要求板端固定路径依赖已经安装 |
| 要复测板端性能数字 | `docker/run-board-cli-smoke.*` | 跑 TVM / MNN / PyTorch 三条路径，生成 `logs/demo-kpi-summary.json` |

## 演示链路

```text
图像 / latent 输入
  -> Electron cockpit
  -> ML-KEM / Tongsuo 安全信道
  -> OpenAMP 控制面
  -> 飞腾派板端 TVM / MNN / PyTorch 推理
  -> 重建图像和性能 KPI
```

几个主要目录对应关系如下：

- `Semantic-Communication/cockpit_desktop/`：Electron 上位机界面。
- `Semantic-Communication/session_bootstrap/`：demo server、OpenAMP 控制面脚本、板端运行脚本和报告。
- `mlkem_link/`：ML-KEM 安全信道相关 Python 代码。
- `board_deps/`：板端固件、模型、runtime、输入样本和校验清单。
- `docker/`：复现、Electron demo、Tailscale 和板端 smoke 的入口脚本。

## 1. Docker 基础复现

这一步不需要飞腾派。它用来确认交付包能在容器里完成依赖检查、预录 API smoke 和 Electron 主进程 smoke。

Linux / WSL:

```bash
./docker/repro.sh
```

Windows PowerShell:

```powershell
.\docker\repro.ps1
```

关键成功标记：

```text
deps-ok
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

`repro.*` 会构建 Docker 镜像，检查 Python、Node、Electron、liboqs 相关依赖，运行最小 pytest 集合，然后在 Xvfb 下启动真实 Electron 主进程。这里不会连接飞腾派，也不会复现 TVM / MNN / PyTorch 的板端性能数字。

## 2. 查看 Electron 桌面端

只看上位机界面时运行：

Linux / WSL:

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

这个入口默认使用预录数据。Linux / WSL 需要可用的 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。

## 3. 飞腾派真机演示

真机演示需要评审机器和飞腾派在同一个 Tailscale 网络内。脚本里保留的历史地址只对应我们自己的验证环境；复测时请用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定现场板卡地址。

这一入口会复用 demo 原始启动链路，因此依赖飞腾派上若干固定路径。`docker/run-demo-wslg-tailscale.ps1` 不会自动安装这些文件，因为安装过程会写入 `/lib/firmware`、`/boot`、`/usr/local/tongsuo` 和 `/home/user/Downloads` 等板端路径。

如果评委使用的是干净飞腾派，先把本仓库放到板端，然后在板端执行：

```bash
bash board_deps/install-board-deps.sh
bash board_deps/verify-board-deps.sh
```

如果评委使用的是已经配置好的飞腾派，只需要先做非破坏性校验：

```bash
bash board_deps/verify-board-deps.sh
```

校验通过后再启动 Electron 真机入口。

Windows + WSLg 推荐入口：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Electron 界面里的板卡连接/授权区域会要求填写板卡 SSH 密码。

## 4. 板端三路性能复现

这条路径用于复测板端 KPI。脚本会通过 Docker 内的 Tailscale 连接飞腾派，把当前仓库复制到板端新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，再在这个目录里运行 TVM、MNN、PyTorch 三条推理路径。

这条路径和第 3 节不同：它优先使用仓库内的 `board_deps/runtime`、`board_deps/tvm`、`board_deps/mnn`、`board_deps/inputs`，在隔离目录中解包运行，不要求板端已经存在 demo 的固定 `/home/user/Downloads/...` 目录结构。它用于复测性能数字，但不替代 Electron 真机 demo 的固定路径环境。

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

默认 `BOARD_CLI_MAX_INPUTS=300`。成功结束时最后一行应为：

```text
cli-smoke-ok
```

KPI 汇总写在板端隔离目录的 `logs/demo-kpi-summary.json`，字段和 Electron 前端展示口径一致：

| 路径 | KPI 字段 |
|---|---|
| TVM | `inference_ms.median_ms` |
| MNN | `total_ms.median_ms` |
| PyTorch | `run_median_ms` |

MNN 这里看 `total_ms`，因为前端展示的是端到端 wall time，包含预处理、`runSession`、后处理和保存。`run_ms` 只覆盖 MNN session 执行时间，不能直接拿来和 demo 卡片里的数字对齐。

最近一次 300 输入隔离验证的参考值：TVM 约 `257 ms`，MNN 约 `363 ms`，PyTorch 约 `913 ms`。复测时数值会受板端温度、DDR 状态和后台进程影响。

## 5. 板端材料

`board_deps/` 放的是板端复现需要的材料：

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

真机 Electron demo 依赖的主要板端路径包括：

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

这些文件和目录由 `board_deps/install-board-deps.sh` 从仓库内材料恢复。评委如果只运行 `docker/run-demo-wslg-tailscale.ps1` 而没有先准备这些路径，Electron 可以启动，但 live 推理、OpenAMP 固件状态或安全信道相关功能可能会失败或回退。

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
