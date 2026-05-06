# FINAL_WORK_ICCompetition2026

第十届全国大学生集成电路创新创业大赛参赛源码交付仓库。

本仓库是独立交付包：`Semantic-Communication/`、`liboqs/`、`board_deps/` 和板端运行产物已经实物化，评委不需要初始化 submodule。目标是复现原生 Electron demo，并在具备飞腾派板卡时验证 TVM、MNN、PyTorch 三条推理路径。

## 0. 评委 30 秒路径选择

- 只有 Docker、没有板卡：运行 `docker/repro.*`，验证镜像、API、预录图像和原生 Electron smoke。
- 想看原生 Electron 窗口：运行 `docker/run-demo.*`。该入口使用预录数据，不接入板端。
- 有飞腾派和 Tailscale：运行 `docker/run-demo-wslg-tailscale.ps1`，在 demo 界面填写板卡密码后执行真机链路。
- 要复现性能数字：运行 `docker/run-board-cli-smoke.*`，默认每条路径处理 300 个输入，输出 `logs/demo-kpi-summary.json`。
- `internal/legacy-launchers/` 是历史主机直连入口，评委复现不需要使用。

## 1. 基础 Docker 复现

基础复现不连接板卡，也不复现 TVM/MNN/PyTorch 性能数字。它用于确认 Docker 镜像、Python/Node/Electron/liboqs 依赖、预录 API 和 Electron 主进程可以工作。

Linux / WSL:

```bash
git clone https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git
cd FINAL_WORK_ICCompetition2026
./docker/repro.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git
cd FINAL_WORK_ICCompetition2026
.\docker\repro.ps1
```

预期关键输出：

```text
deps-ok
48 passed, 1 skipped
api-smoke-ok
electron-smoke-ok
[repro] reproducibility validation completed
```

`repro.*` 会在无显示环境下使用 Xvfb 启动真实 Electron 主进程并完成 smoke 检查。

## 2. 原生 Electron Demo

需要看到原生 Electron 窗口时使用：

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

Linux / WSL 需要可用 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。该入口默认使用预录数据，用于展示上位机界面和基本交互。要连接板卡请走第 3 节。

## 3. 有板卡 Electron 真机演示

前提：评委机器需要能登录到与飞腾派板卡相同的 Tailscale 网络。脚本内置的历史地址只适用于本队验证环境，不是公网地址，也不是通用默认值；复测时可用 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定实际板卡地址。

Windows + WSLg 推荐入口：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

板卡密码在 Electron demo 的板卡连接/授权界面填写；仓库内不保存板卡 SSH 密码、Tailscale 登录凭据或私钥。

## 4. 板端三路 CLI 性能复现

该路径用于证明本仓库内的板端产物足够自包含。脚本会把当前仓库复制到飞腾派新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后只使用仓库内的 runtime、模型、输入和脚本运行三条推理路径。

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

默认 `BOARD_CLI_MAX_INPUTS=300`。预期最后一行：

```text
cli-smoke-ok
```

性能汇总写入板端隔离目录的 `logs/demo-kpi-summary.json`，口径与 Electron 前端一致：

- TVM：`inference_ms.median_ms`
- MNN：`total_ms.median_ms`
- PyTorch：`run_median_ms`

MNN 使用 `total_ms` 是因为 Electron 比较卡片展示端到端 wall time，包括预处理、`runSession`、后处理和保存；`run_ms` 只包含 MNN session 执行时间，不能拿来和 demo 数字对齐。

最近一次 300 输入隔离验证参考值：TVM 约 `257 ms`，MNN 约 `363 ms`，PyTorch 约 `913 ms`。实际数字会受板端温度、DDR 状态和后台进程影响。

## 5. 板端依赖

`board_deps/` 包含完整复现需要的板端产物：

- OpenAMP 当前固件、DTB、源码、构建产物和运行服务
- TVM current/baseline artifact 与 TVM 运行时
- MNN 模型与 MNN/PyTorch 便携运行时
- PyTorch JSCC generator checkpoint
- prerecorded latent / encoder output 输入
- ML-KEM、Tongsuo、公钥和远端 helper 快照

校验：

```bash
bash board_deps/verify-board-deps.sh
```

`board_deps/install-board-deps.sh` 会安装或覆盖板端 firmware、DTB、runtime 和模型，只适合干净板卡初始化。已经能跑 demo 的板卡优先使用第 4 节的 isolated CLI smoke。

## 6. 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── README.md
├── requirements.txt
├── docker/                    # 复现、Electron、Tailscale、板端 smoke 脚本
├── board_deps/                # 板端固件、运行时、模型、输入和校验清单
├── mlkem_link/                # ML-KEM / secure channel Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # Electron 上位机与 OpenAMP 控制面源码
├── liboqs/                    # liboqs 源码，Docker 构建时编译安装
├── host_pic_to_latent/        # JSCC/latent 辅助代码
└── USRP292x/                  # NI USRP-2922 数据面代码
```

NI USRP-2922 是当前无线数据面主线，`USRP292x/` 和 `scripts/setup_usrp2922_network.sh` 需要保留。

## 7. 安全与提交边界

- 仓库不包含板卡 SSH 密码、Tailscale 登录凭据或私钥。
- 板卡密码通过 Electron 界面或 CLI 交互输入，不写入仓库。
- 复现镜像只包含 demo 和 smoke 所需依赖，不包含与复现无关的辅助工具链。
- OpenAMP、TVM/MNN/PyTorch、ML-KEM、Tongsuo、NI USRP-2922 相关目录属于当前复现材料的一部分。
