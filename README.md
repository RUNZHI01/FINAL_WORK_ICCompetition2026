# ICCompetition2026

## 评委复现（最小路径）

这条路径用于比赛源码提交后的复现验证：构建 Docker 镜像、校验后端依赖、构建真实 Electron 上位机，并在无板卡档位启动同一个 Electron demo。它不是浏览器预览版。

```bash
git submodule update --init --recursive
./docker/repro.sh
./docker/run-demo.sh
```

Windows PowerShell：

```powershell
git submodule update --init --recursive
.\docker\repro.ps1
.\docker\run-demo.ps1
```

需要连接 Tailscale 下位机时，不要把认证密钥写入源码。请在运行时传入一次性或可复用 auth key，并使用带 TUN 的启动入口：

也可以先手动登录一次，把状态保存到 Docker volume：

```bash
./docker/tailscale-login.sh
./docker/run-demo-tailscale.sh
```

PowerShell：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

登录脚本会打印 Tailscale 浏览器登录 URL。完成登录后，状态会保存在 `iccomp-tailscale-state`，后续不需要再次输入 auth key。

```bash
export TS_AUTHKEY=tskey-auth-...
export TAILSCALE_HOSTNAME=iccomp-demo
./docker/run-demo-tailscale.sh
```

PowerShell：

```powershell
$env:TS_AUTHKEY="tskey-auth-..."
$env:TAILSCALE_HOSTNAME="iccomp-demo"
.\docker\run-demo-tailscale.ps1
```

`run-demo-tailscale.*` 会为容器开启 `NET_ADMIN` / `NET_RAW`、挂载 `/dev/net/tun`，并把 Tailscale 登录状态保存在 Docker volume `iccomp-tailscale-state`。默认会检查板端 Tailscale 地址 `100.121.87.73`；可用 `TAILSCALE_PING_TARGET` 覆盖。

说明：

- `docker/repro.*` 会构建 `iccomp-ubuntu-minimal` 镜像，运行 Python 测试，并用 Xvfb 启动 Electron 主进程做 smoke test。
- `docker/run-demo.*` 启动的是容器内真实 Electron 上位机，并直连宿主 X server 显示原生窗口。Windows 需要先启动 VcXsrv/Xming；Linux/WSL 需要可用的 `DISPLAY`。
- 无板卡演示档位固定为 `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded`、`MLKEM_AUTH_ENABLED=0`，不会读取板卡密码。
- 仓库只带入当前 demo 需要的两张最小重建样例图，位置为 `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/static/demo_samples/`；不会把完整 `finalWork.zip` 作为主线代码资源包。
- `docker/dev.*` 与 `docker/Dockerfile` 是开发/板端构建入口，评委复现可忽略。

## 交付打包注意

不要在 Windows 工作树直接 `zip` 或 `git archive`。`Semantic-Communication` submodule 上游同时包含 `DOCUMENTS/` 目录和 `Documents` 文件，Windows 默认大小写不敏感，会把 submodule 状态污染成大量删除项。

交付前在 Linux/WSL 的大小写敏感文件系统执行：

```bash
./docker/package-submission.sh
```

打包脚本会从 GitHub 重新 clone 干净源码，并校验本地 HEAD、submodule SHA 与远端 clone 一致。执行前必须先提交并推送父仓库和所有 submodule pinned commit。

> 第十届全国大学生集成电路创新创业大赛（集创赛）2026 · 飞腾企业命题
>
> 更新时间：2026-05-03
>
> 本仓库当前收口为一条混合双平面路线：
>
> - 控制面 / 认证面：`TCP + ML-KEM-768 密钥交换 + SM4-GCM 加密 + HKDF-SHA256 + SM2 / ML-DSA-65 双签名`
> - 数据面：`NI USRP-2922 OTA` 发送明文 `latent / quant .npz`（QPSK 调制）
> - TCP 加密传输路径：控制面与加密数据传输共用同一 TCP socket，保留为 USRP 不可用时的 fallback

## 当前口径

- 控制面默认加密套件为 SM4-GCM（非 AES-256-GCM），可选 AES-256-GCM。
- `./start.sh` 仍是当前正式主演示入口，但它主要收口的是控制面 / 认证面。
- `USRP292x/` 是当前 `NI USRP-2922` 数据面新主线；旧 `usrp_tensor/` 和 B205mini 相关实现保留作历史参考。
- 当前 live runtime 默认仍以 `tcp/Tailscale` 为主；USRP 数据面与 `ML-KEM` 控制面的完全协同还在收口中。

## 当前状态

| 方向 | 当前状态 | 说明 |
|---|---|---|
| 控制面 / 认证面 | 已收口 | `ML-KEM + HKDF-SHA256 + AEAD + SM2 / ML-DSA` 已接入主 demo 与 TUI |
| 主演示入口 | 验收通过 | 2026-05-02 飞腾派板端验收通过（TVM 后端）；USRP 模式 MNN / PyTorch 后端待修复 |
| 最小认证演示 | 可用 | `./tui_start.sh --encrypt` |
| USRP-2922 新数据面 | 已独立打通 | `USRP292x/` 已落地 `QPSK 文件链路 + selective ARQ + persistent TX/RX + TUI` |
| USRP 新线基线 | 已通过 | 单机与双机 `imini` 均已 `300/300 PASS`；双机 `remote-decode` 已通 |
| 飞腾派板端 USRP | 环境就绪 | UHD probe、构建与部署路径已确认，实际 OTA 验证待继续推进 |
| 主 demo 整合 | 已验收 | 控制面 + 预录数据面已跑通；USRP 数据面 MNN / PyTorch 后端待修复 |

主 demo 当前默认仍是预录输入源，板端读取：

```text
/home/user/Downloads/jscc-test/简化版latent
```

这一路径来自 `Semantic-Communication/session_bootstrap/config/inference_demo_openamp_mean4_v7.2026-04-20.phytium_pi.env` 的 `REMOTE_INPUT_DIR`。板端存在的 `简化版latent_npz` 和 `encoder_outputs` 暂时作为辅助资源，不是当前主 demo 默认输入。预录 / USRP 输入源切换与当前工作树相对最新提交的差异见 [doc/4.国赛复试冲刺方案/02_主demo输入源与当前差异.md](./doc/4.国赛复试冲刺方案/02_主demo输入源与当前差异.md)。

当前对外口径建议保持为：

- 主 demo（TVM 后端）已于 2026-05-02 在飞腾派板端验收通过。
- USRP 模式下 MNN 和 PyTorch 后端尚未修复，不要写成已通过。

## 常用入口

### `./start.sh`

当前正式主演示入口。

- 后台启动 `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- 前台启动 `cockpit_desktop`
- 启动前询问飞腾派 SSH 密码；直接回车可跳过
- 自动清理代理变量，避免 localhost 被代理拦截
- 默认导出：
  - `MLKEM_AUTH_ENABLED=1`
  - `MLKEM_AUTH_SERVER_ID=phytium-board`
  - `MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`

```bash
./start.sh
./start.sh --server-only
```

### `./tui_start.sh`

当前是模式分发入口；不带参数只显示帮助。

```bash
./tui_start.sh --help
./tui_start.sh --encrypt
./tui_start.sh --usrp
```

- `--encrypt`：控制面 / 认证面 TUI，走 `scripts/demo_tui.py`
- `--usrp`：USRP-2922 数据面 TUI，走 `USRP292x/UsrpTui.py`

常用自检：

```bash
./tui_start.sh --usrp --smoke
```

### `./cleanup.sh`

清理 `start.sh` 残留进程。

```bash
./cleanup.sh
./cleanup.sh --restart
```

## 快速开始

### 1. 一键初始化（推荐）

```bash
git submodule update --init --recursive
./init.sh              # .venv + Tongsuo + bridge + SM2/ML-DSA/ML-KEM 自检
./init.sh --board      # 额外初始化板端认证资产
```

或手动初始化：

```bash
git submodule update --init --recursive

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

说明：

- `init.sh` 会自动创建 `.venv`、构建 Tongsuo runtime 到 `tongsuo-dist/`、编译 KEM/SIG bridge、运行 SM2 + ML-DSA + ML-KEM 本机自检
- `.venv/bin/activate` 自动设置 `OQS_INSTALL_PATH` 和 `LD_LIBRARY_PATH`
- 仓库代码也会自动探测 `./liboqs/liboqs-dist` 与 `./liboqs-dist`
- `tui_start.sh` 会检查 `textual` 是否已安装

### 2. 如需跑 Cockpit 前端

```bash
cd Semantic-Communication/cockpit_desktop
npm install
cd ../..
```

### 3. 如需 Docker 开发环境

```bash
./docker/dev.sh build
./docker/dev.sh pytest mlkem_link/tests/ -v
./docker/dev.sh bash
```

### 4. 如需本地构建 Tongsuo 桥接产物

```bash
./docker/docker-build.sh
```

## 最常用验证命令

先激活虚拟环境：

```bash
source .venv/bin/activate
```

控制面 / 认证面最小回归：

```bash
pytest -q mlkem_link/tests/test_auth.py
pytest -q mlkem_link/tests/test_tui_remote_tcp_server.py
```

完整 `mlkem_link` 测试：

```bash
python -m pytest mlkem_link/tests/ -v
```

FIT：

```bash
python -m pytest scripts/test_fit.py -v
python -m pytest scripts/test_system_fit.py -v
```

主 demo 后端定向回归：

```bash
python -m pytest \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_crypto_runtime.py \
  -q

python -m pytest \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py \
  -q -k 'usrp or mlkem or crypto or batch'
```

脚本语法检查：

```bash
bash -n start.sh
bash -n tui_start.sh
bash -n cleanup.sh
```

USRP TUI 自检：

```bash
./tui_start.sh --usrp --smoke
```

## 目录概览

```text
ICCompetition2026/
├── start.sh / tui_start.sh / cleanup.sh / init.sh
├── mlkem_link/              # 控制面 / 认证面密码核心库
├── Semantic-Communication/  # 主系统（git submodule，队友仓库）
├── scripts/                 # demo、TUI、TCP 联调、测试脚本
├── USRP292x/                # NI USRP-2922 新数据面主线
├── usrp_tensor/             # B205mini 历史实现，仅作参考
├── Tongsuo/                 # 铜锁 8.5.0-pre1（git submodule）
├── liboqs/                  # liboqs 0.14.0（git submodule，detached）
├── tools/                   # 板端安装脚本（UHD 等）
├── doc/                     # 当前文档总入口
├── docker/                  # 开发环境与 Tongsuo 构建工具链
├── artifacts/               # 运行产物、实验留证、认证资产
├── evidence/                # 提交素材与索引
├── ppt_assets/              # 演示文稿素材
├── Archive/                 # 历史归档（RISCV 等）
├── 文档更新/                # 竞赛技术文档草稿
│
├── .venv/                   # (生成) python3 -m venv / init.sh
├── build/                   # (生成) init.sh 构建 Tongsuo
├── tongsuo-dist/            # (生成) init.sh 安装 Tongsuo runtime
└── finalWork/               # (外部，可选) 业务资源包；评委复现路径不依赖
```

## 文档入口

推荐从这些文档开始：

1. [doc/README.md](./doc/README.md)
2. [doc/加密套件/README.md](./doc/加密套件/README.md)
3. [doc/加密套件/00_总览与入口/00_总览.md](./doc/加密套件/00_总览与入口/00_总览.md)
4. [doc/加密套件/00_总览与入口/03_队友快速上手.md](./doc/加密套件/00_总览与入口/03_队友快速上手.md)
5. [doc/3.上位机 USRP B205 连接/README.md](./doc/3.上位机%20USRP%20B205%20连接/README.md)
6. [doc/3.上位机 USRP B205 连接/08_NI_USRP_2922迁移与官方例程.md](./doc/3.上位机%20USRP%20B205%20连接/08_NI_USRP_2922迁移与官方例程.md)
7. [USRP292x/README_TUI_DUAL_HOST.md](./USRP292x/README_TUI_DUAL_HOST.md)
8. [doc/加密套件/01_方案与设计/04_安全与可靠性审计_2026-05-01.md](./doc/加密套件/01_方案与设计/04_安全与可靠性审计_2026-05-01.md)
9. [doc/4.国赛复试冲刺方案/02_主demo输入源与当前差异.md](./doc/4.国赛复试冲刺方案/02_主demo输入源与当前差异.md)
10. [doc/4.国赛复试冲刺方案/03_主demo_USRP_MNN_安全信道测试方案.md](./doc/4.国赛复试冲刺方案/03_主demo_USRP_MNN_安全信道测试方案.md)

## 备注

- USRP-2922 是 `1GbE` 设备；UHD device args 使用 `addr=<ip>`，不要沿用旧 B205 的 `serial=...`。
- 数据面当前是“明文 OTA + 控制面独立加密”的有意设计，不是漏做。
- `finalWork.zip` 当前只应视为“真实业务资源包”：可复用其中的权重、latent 样例、TVM/MNN artifact 与 `quant/scale/zero_point` 数据契约；不要直接拿其中的旧编排脚本覆盖当前仓库主线。详细边界见 [doc/4.国赛复试冲刺方案/01_finalWork接入边界与过时说明.md](./doc/4.国赛复试冲刺方案/01_finalWork接入边界与过时说明.md)。
- 主 demo 预录模式的 canonical 板端输入目录是 `/home/user/Downloads/jscc-test/简化版latent`；切到 USRP 模式前必须显式配置 `REMOTE_USRP_RX_DIR`。
- 若 README 与当前代码、最新文档或 `artifacts/` 留证冲突，以当前代码和最新留证为准。
