# FINAL_WORK_ICCompetition2026

第十届全国大学生集成电路创新创业大赛参赛源码交付仓库。

本仓库是评委复现用的独立源码包，已经将原工程依赖的 `Semantic-Communication/` 与 `liboqs/` 实物化为普通目录，不再要求评委初始化 submodule。评委复现路径只依赖 Docker，不依赖板卡、Tailscale、VcXsrv，也不会启动浏览器版替代界面；Electron smoke 使用 Xvfb 启动真实 Electron 主进程。

## 评委最小复现

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

`docker/repro.*` 会执行以下验证：

- 构建 `iccomp-ubuntu-minimal` Docker 镜像。
- 安装 Python 依赖、Node 20、Electron 依赖和 `liboqs`。
- 构建真实 Electron production 产物。
- 运行 ML-KEM / transport 最小回归测试。
- 启动 `server.py`，检查预录 demo API 返回非空图像。
- 在 Xvfb 下启动真实 Electron 主进程并检查后端健康状态。

## 原生 Electron Demo

如果要在宿主机上看到原生 Electron 窗口：

Linux / WSL:

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

说明：

- `run-demo.*` 启动的是容器内真实 Electron，不是浏览器 preview。
- Linux / WSL 需要可用的 `DISPLAY`；Windows 原生 PowerShell 需要先启动 VcXsrv 或 Xming。
- 无板卡默认档位为 `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded` 和 `MLKEM_AUTH_ENABLED=0`。
- 预录图像固定在 `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/static/demo_samples/`，用于避免 `finalWork/` 外部资源缺失导致 UI 空图。

## 真机演示入口

真机链路用于队伍答辩演示，不是评委最小复现的前提。需要连接 Tailscale 下位机时，不要把认证密钥或板端密码写入源码，只通过当前 shell 的环境变量传入。

Windows + WSLg 推荐入口：

```powershell
$env:REMOTE_PASS="..."
$env:PHYTIUM_PI_PASSWORD="..."
.\docker\run-demo-wslg-tailscale.ps1
```

也可以先手动登录 Tailscale：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

或使用一次性 auth key：

```powershell
$env:TS_AUTHKEY="tskey-auth-..."
.\docker\run-demo-tailscale.ps1
```

Tailscale 状态会保存到 Docker volume `iccomp-tailscale-state`。默认板端检查地址为 `100.121.87.73`，可通过 `TAILSCALE_PING_TARGET` 覆盖。

## 交付打包

需要生成源码压缩包时，在本仓库提交并推送后执行：

```bash
./docker/package-submission.sh
```

脚本会从 `https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git` fresh clone 当前远端源码，校验本地 HEAD 与远端 HEAD 一致，然后输出 `iccomp2026-submission.tar.gz`。本仓库不使用 submodule，因此打包脚本不会再执行 submodule 校验。

## 仓库结构

```text
FINAL_WORK_ICCompetition2026/
├── README.md
├── requirements.txt
├── docker/                    # 评委复现、Electron smoke、Tailscale 真机演示脚本
├── mlkem_link/                # ML-KEM / secure channel 最小 Python 包
├── scripts/                   # transport、run logger、TVM helper 和测试脚本
├── Semantic-Communication/    # 已实物化的 Electron 上位机与 OpenAMP 控制面源码
├── liboqs/                    # 已实物化的 liboqs 源码，Docker 构建时编译安装
├── host_pic_to_latent/        # JSCC/latent 辅助代码，不包含大体积 checkpoint 或数据集
├── USRP292x/                  # USRP-2922 数据面代码
└── tools/                     # 板端辅助安装脚本
```

明确不进入交付主线的本地资源：

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

## Docker 入口

评委只需要：

- `docker/ubuntu-minimal.Dockerfile`
- `docker/repro.sh` / `docker/repro.ps1`
- `docker/run-demo.sh` / `docker/run-demo.ps1`

队伍内部真机演示入口：

- `docker/run-demo-tailscale.*`
- `docker/run-demo-wslg-tailscale.*`
- `docker/tailscale-login.*`
- `docker/start-tailscale.sh`

## 安全说明

- 不要提交 `TS_AUTHKEY`、`TAILSCALE_AUTHKEY`、`REMOTE_PASS`、`PHYTIUM_PI_PASSWORD` 或任何私钥。
- 不要往 Docker 镜像里安装 Codex 或其他 AI 工具链。
- 不要把 Electron demo 改成浏览器 preview；当前验证链路要求原生 Electron。
- 不要删除 `Semantic-Communication/openamp_mock/`、OpenAMP bridge、TVM/MNN 脚本或根目录 `scripts/` 里的 transport helper；这些路径仍被 demo 和真机链路引用。
