# FINAL_WORK_ICCompetition2026

第十届全国大学生集成电路创新创业大赛参赛源码交付仓库。

本仓库是独立交付包：`Semantic-Communication/`、`liboqs/` 和板端运行产物已经实物化，不再要求评委初始化 submodule。仓库目标是复现原生 Electron demo，并在有飞腾派板卡时验证 TVM、MNN、PyTorch 三条推理路径。

## 1. 基础 Docker 复现

基础复现不连接板卡，用于确认镜像、依赖、后端 API、预录图像和原生 Electron smoke 可运行。

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

`repro.*` 启动的是真实 Electron 主进程，不是浏览器 preview。无显示环境下使用 Xvfb 做 smoke。

## 2. 原生 Electron Demo

需要看到原生 Electron 窗口时使用：

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

Linux / WSL 需要可用 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。无板卡时默认使用 prerecorded 档位；有板卡时使用 Tailscale 真机入口。

## 3. 有板卡完整复现

飞腾派默认 Tailscale 地址：`100.121.87.73`。密码、auth key 和私钥只允许通过当前 shell 环境变量传入，不能写入仓库。

Windows + WSLg 推荐入口：

```powershell
$env:REMOTE_PASS="..."
$env:PHYTIUM_PI_PASSWORD="..."
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要先登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Tailscale 登录状态保存在 Docker volume `iccomp-tailscale-state`。如板端地址变化，可以设置 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET`。

## 4. 板端三路 CLI Smoke

该路径用于证明本仓库里的板端产物足够自包含。脚本会把当前仓库复制到飞腾派新的隔离目录 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后只使用仓库内的 runtime、模型、输入和脚本运行三条推理路径，默认每条路径处理 300 张输入：

- TVM：`scripts/tvm_inference_helper.py`
- MNN：`Semantic-Communication/session_bootstrap/scripts/mnn_real_reconstruction.py`
- PyTorch：`Semantic-Communication/session_bootstrap/scripts/pytorch_reference_reconstruction.py`

执行：

```powershell
$env:REMOTE_PASS="..."
.\docker\run-board-cli-smoke.ps1
```

预期最后一行：

```text
cli-smoke-ok
```

需要缩短调试时间时可以临时覆盖输入数量：

```powershell
$env:REMOTE_PASS="..."
$env:BOARD_CLI_MAX_INPUTS="3"
.\docker\run-board-cli-smoke.ps1
```

该脚本不会修改板端现有仓库，不会向板端 conda 环境安装包；所有 Python 运行时解压到本次 smoke 的隔离目录。

## 5. 板端依赖

`board_deps/` 包含完整复现需要的板端产物：

- OpenAMP 当前固件、DTB、源码和运行服务
- TVM current/baseline artifact 和 TVM 运行时
- MNN 模型和 MNN/PyTorch 便携运行时
- PyTorch JSCC generator checkpoint
- prerecorded latent / encoder output 输入
- ML-KEM、Tongsuo、公钥和远端 helper 快照

校验：

```bash
bash board_deps/verify-board-deps.sh
```

重新从板端拉取依赖：

```powershell
$env:REMOTE_PASS="..."
.\docker\pull-board-deps.ps1
```

## 6. 打包

提交并推送本仓库后，在 Linux / WSL 上生成交付源码包：

```bash
./docker/package-submission.sh
```

脚本会从 `https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git` fresh clone 远端源码，校验本地 HEAD 与远端 HEAD 一致，然后输出 `iccomp2026-submission.tar.gz`。

## 7. 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── README.md
├── requirements.txt
├── docker/                    # 复现、Electron、Tailscale、板端 smoke 和打包脚本
├── board_deps/                # 板端固件、运行时、模型、输入和校验清单
├── mlkem_link/                # ML-KEM / secure channel Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # Electron 上位机与 OpenAMP 控制面源码
├── liboqs/                    # liboqs 源码，Docker 构建时编译安装
├── host_pic_to_latent/        # JSCC/latent 辅助代码
├── USRP292x/                  # NI USRP-2922 数据面代码
└── tools/                     # 板端辅助安装脚本
```

不应提交的本地资源：

```text
finalWork/
downloads/
node_modules/
.venv/
build/
dist/
tongsuo-dist/
tongsuo-dist-board-aarch64.tar.gz
```

## 8. 安全约束

- 不提交 `TS_AUTHKEY`、`REMOTE_PASS`、`PHYTIUM_PI_PASSWORD` 或任何私钥。
- 不把 Codex 或其他 AI 工具链装进复现镜像。
- 不把 Electron demo 改成浏览器 preview。
- 不删除 OpenAMP bridge、TVM/MNN/PyTorch 脚本、`mlkem_link/` 或 `scripts/` 中的 transport helper；这些仍被 demo 和板端链路引用。
