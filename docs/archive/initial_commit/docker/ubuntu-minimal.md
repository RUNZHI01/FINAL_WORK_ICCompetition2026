# Ubuntu Electron 复现镜像

这个镜像是比赛评委复现入口，目标是复现真实 Electron 上位机 demo，而不是把 renderer 改成浏览器预览版。

它包含：

- Ubuntu 22.04 基础系统、构建工具和 Electron 所需 GUI 运行库
- Node.js 20.x、npm、`cockpit_desktop/package-lock.json` 固定的 Electron 依赖
- 使用 `uv` 创建的 Python 虚拟环境和 `requirements.txt` 依赖
- 从 `liboqs` submodule 编译安装的标准化 `ML-KEM` / `ML-DSA` C 后端
- `Semantic-Communication/cockpit_desktop` 的 `npm ci` 与 `electron-vite build` 产物

镜像不包含 Codex，也不依赖评委机器安装 Node、Python 包或 Tongsuo。

## 一键复现

Linux / WSL / Git Bash：

```bash
./docker/repro.sh
```

Windows PowerShell：

```powershell
./docker/repro.ps1
```

一键脚本会执行：

1. `git submodule update --init --recursive`
2. `docker build`
3. 容器内 Python、`liboqs`、Node/npm 和 Electron 构建产物检查
4. 容器内最小 Python 测试集
5. 使用 Xvfb 启动真实 Electron 主进程，确认它能拉起 Python 后端并通过 `/api/health`

## 启动 Electron Demo

Linux X11 / WSLg 环境：

```bash
./docker/run-demo.sh
```

Windows PowerShell：

```powershell
./docker/run-demo.ps1
```

Windows 下需要先启动 VcXsrv 或 Xming，并允许来自 Docker 的连接；脚本默认使用 `DISPLAY=host.docker.internal:0.0`。这不是浏览器版 demo，Electron 进程仍在容器内运行，只是窗口显示转发到宿主机。

## 启动带 Tailscale 的真机 Demo

需要连接下位机 Tailscale IP 时，使用专门入口：

手动登录一次：

```bash
./docker/tailscale-login.sh
./docker/run-demo-tailscale.sh
```

Windows PowerShell：

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

或使用 auth key 非交互登录：

```bash
export TS_AUTHKEY=tskey-auth-...
export TAILSCALE_HOSTNAME=iccomp-demo
./docker/run-demo-tailscale.sh
```

Windows PowerShell：

```powershell
$env:TS_AUTHKEY="tskey-auth-..."
$env:TAILSCALE_HOSTNAME="iccomp-demo"
.\docker\run-demo-tailscale.ps1
```

该入口会为容器打开 `/dev/net/tun` 和 `NET_ADMIN` / `NET_RAW` capability，并挂载 Docker volume `iccomp-tailscale-state` 保存 Tailscale 登录状态。不要把 `TS_AUTHKEY` 写入源码、README 示例以外的配置文件或镜像层。

## 范围说明

复现镜像默认使用无板卡演示档位：

- `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded`
- `MLKEM_AUTH_ENABLED=0`
- `REMOTE_PASS` / `PHYTIUM_PI_PASSWORD` 为空

仓库只随镜像带入当前 demo 已引用的两张最小重建样例图，位置为 `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/static/demo_samples/`；不带入完整 `finalWork.zip` 业务资源包。这样保持 Electron 视觉与 API 交互不变，同时避免缺图时退化成 1x1 占位图。

`start.sh` 仍保留为队伍本地真机/板端部署入口。评委复现默认只需要 `docker/repro.*` 和 `docker/run-demo.*`。
