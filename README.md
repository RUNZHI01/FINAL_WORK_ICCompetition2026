# 飞腾多核弱网安全语义视觉回传

本仓库是第十届全国大学生集成电路创新创业大赛的参赛交付包。项目面向低空/弱网场景下的视觉回传任务，把语义压缩与重建、飞腾派板端推理、OpenAMP 控制面、后量子安全信道和 NI USRP-2922 无线数据面放在同一个可复现演示系统中。

仓库已经包含源码、模型、板端运行时、固件和复现实验脚本；`Semantic-Communication/`、`liboqs/`、`board_deps/` 等目录不是需要现场初始化的 submodule。评委可以先用 Docker 验证基础可复现性；如果具备飞腾派板卡和同一 Tailscale 网络，再运行真机链路与三路性能复现。

## 评委先看这里

| 场景 | 推荐入口 | 会验证什么 |
|---|---|---|
| 没有板卡，只检查仓库是否能跑 | `docker/repro.*` | Docker 镜像、Python/Node/Electron/liboqs 依赖、预录 API、Electron 主进程 smoke |
| 想直接看上位机界面 | `docker/run-demo.*` | 原生 Electron cockpit，默认使用预录数据 |
| 有飞腾派板卡和 Tailscale | `docker/run-demo-wslg-tailscale.ps1` | Electron + Tailscale + 板端真实链路 |
| 要复现实测 KPI | `docker/run-board-cli-smoke.*` | TVM、MNN、PyTorch 三条板端推理路径，输出 `logs/demo-kpi-summary.json` |

`internal/legacy-launchers/` 是历史主机直连入口，保留用于追溯，不是评审复现的主路径。

## 项目做了什么

系统的主链路可以概括为：

```text
Electron 上位机
  -> ML-KEM / Tongsuo 安全信道
  -> OpenAMP 控制面与任务准入
  -> USRP 或预录 latent 数据输入
  -> 飞腾派板端 TVM / MNN / PyTorch 推理
  -> 重建图像、性能 KPI、FIT/日志证据
```

交付内容包括：

- 一套原生 Electron cockpit，用于展示弱网链路状态、板卡状态、推理进度、图像重建结果和安全信道状态。
- 三条板端推理路径：TVM current/baseline、MNN 动态尺寸重建、PyTorch 参考重建。
- OpenAMP 控制面与 FIT 证据，覆盖任务准入、签名 sideband、心跳超时 watchdog 等板端行为。
- ML-KEM-768 安全信道实现，支持 liboqs 与 Tongsuo 相关运行产物。
- NI USRP-2922 数据面代码，以及预录 latent/encoder output 数据，方便无无线硬件时做基础演示。
- Docker 复现入口，把评审环境中的依赖安装、API smoke 和 Electron smoke 收敛到一条命令。

## 基础复现：不需要板卡

下面的命令默认在仓库根目录执行。如果评委拿到的是压缩包，先解压并进入 `FINAL_WORK_ICCompetition2026`；如果从 GitHub 拉取，请先完成 clone 并进入仓库根目录。

Linux / WSL:

```bash
./docker/repro.sh
```

Windows PowerShell:

```powershell
.\docker\repro.ps1
```

关键成功输出如下：

```text
deps-ok
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

`repro.*` 会构建最小复现镜像，检查 Python/Node/Electron/liboqs 依赖，运行最小 pytest 集合，调用预录 demo API，并在 Xvfb 下启动真实 Electron 主进程完成 smoke 检查。该路径不连接飞腾派，也不复现板端性能数字；它的作用是先证明交付包不是“只能在队伍机器上跑”的材料。

## 查看 Electron Demo

如果只想看桌面端效果，使用下面入口。该模式默认走预录数据，不需要板卡密码。

Linux / WSL:

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

Linux / WSL 需要可用 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。需要接入飞腾派真机时，请使用下一节的 Tailscale 入口。

## 真机演示：飞腾派 + Tailscale

真机演示要求评委机器能够登录到与飞腾派板卡相同的 Tailscale 网络。脚本里保留的历史地址只对应本队验证环境，不是公网地址，也不是通用默认地址；复测时请用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定实际板卡地址。

Windows + WSLg 推荐入口：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

如需先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

板卡 SSH 密码在 Electron 界面的板卡连接/授权区域填写。仓库不保存板卡 SSH 密码、Tailscale 登录凭据或私钥。

## 板端三路性能复现

三路 CLI smoke 用于复现可交付 KPI。脚本会通过 Docker 内的 Tailscale 连接飞腾派，把当前仓库复制到板端新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后只使用仓库内的 runtime、模型、输入和脚本运行 TVM、MNN、PyTorch 三条路径。

Windows PowerShell:

```powershell
.\docker\run-board-cli-smoke.ps1
```

Linux / WSL:

```bash
bash docker/run-board-cli-smoke.sh
```

脚本会交互式询问板卡 SSH 密码，输入只保存在当前进程中。调试时可以缩短输入数量：

```powershell
$env:BOARD_CLI_MAX_INPUTS="3"
.\docker\run-board-cli-smoke.ps1
```

默认 `BOARD_CLI_MAX_INPUTS=300`。成功结束时最后一行应为：

```text
cli-smoke-ok
```

性能汇总写入板端隔离目录的 `logs/demo-kpi-summary.json`，字段口径与 Electron 前端一致：

| 路径 | KPI 字段 |
|---|---|
| TVM | `inference_ms.median_ms` |
| MNN | `total_ms.median_ms` |
| PyTorch | `run_median_ms` |

MNN 使用 `total_ms`，因为前端展示的是端到端 wall time，包含预处理、`runSession`、后处理和输出保存；`run_ms` 只表示 MNN session 执行时间，不能直接和 demo 展示值对齐。

最近一次 300 输入隔离验证的参考值为：TVM 约 `257 ms`，MNN 约 `363 ms`，PyTorch 约 `913 ms`。这些数字用于评审复测时对齐量级，不应理解为固定常数；板端温度、DDR 状态和后台进程都会影响实际结果。

## 板端依赖和证据材料

`board_deps/` 是板端复现材料目录，包含：

- OpenAMP 当前固件、DTB、源码、构建产物和运行服务。
- TVM current/baseline artifact 与 TVM 运行时。
- MNN 模型与 MNN/PyTorch 便携运行时。
- PyTorch JSCC generator checkpoint。
- 预录 latent / encoder output 输入。
- ML-KEM、Tongsuo、公钥和远端 helper 快照。

校验板端依赖完整性：

```bash
bash board_deps/verify-board-deps.sh
```

`board_deps/install-board-deps.sh` 会安装或覆盖板端 firmware、DTB、runtime 和模型，只适合干净板卡初始化。已经能够运行 demo 的板卡，优先使用上一节的 isolated CLI smoke，不需要重新安装。

关键证据文件：

| 文件 | 内容 |
|---|---|
| `Semantic-Communication/session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md` | OpenAMP demo live 双路径真机状态 |
| `Semantic-Communication/session_bootstrap/reports/openamp_phase5_fit03_watchdog_success_2026-03-15.md` | heartbeat timeout watchdog FIT 真机验证 |
| `Semantic-Communication/session_bootstrap/reports/big_little_compare_20260318_123300.md` | big.LITTLE pipeline 吞吐对比 |

## 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── README.md
├── requirements.txt
├── docker/                    # Docker 复现、Electron、Tailscale、板端 smoke 入口
├── board_deps/                # 板端固件、运行时、模型、输入和校验清单
├── mlkem_link/                # ML-KEM / secure channel Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # Electron 上位机、OpenAMP 控制面、报告和板端脚本
├── liboqs/                    # liboqs 源码，Docker 构建时编译安装
├── host_pic_to_latent/        # JSCC / latent 编解码辅助代码
└── USRP292x/                  # NI USRP-2922 数据面代码
```

NI USRP-2922 是当前无线数据面主线，`USRP292x/` 与 `scripts/setup_usrp2922_network.sh` 属于交付材料的一部分。

## 安全边界

- 仓库不包含板卡 SSH 密码、Tailscale 登录凭据或私钥。
- 板卡密码通过 Electron 界面或 CLI 交互输入，不写入仓库。
- 复现镜像只包含 demo 和 smoke 所需依赖，不额外打包与评审复现无关的工具链。
- OpenAMP、TVM/MNN/PyTorch、ML-KEM、Tongsuo、NI USRP-2922 相关目录均属于当前复现材料，不建议在评审前删除。
