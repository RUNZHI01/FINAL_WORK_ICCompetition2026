# Docker 入口说明

评委复现只需要 `ubuntu-minimal.Dockerfile` 和 `repro.*`。镜像会构建 Python 后端、`liboqs`、Node/Electron 依赖，并验证真实 Electron production demo。这里没有浏览器 preview 替代路径。

| 文件 | 用途 | 评委是否需要 |
|---|---|---|
| `ubuntu-minimal.Dockerfile` | 评委复现镜像，包含 Python、Node 20、Electron build、Xvfb、Tailscale CLI 和 `liboqs` | 是 |
| `repro.sh` / `repro.ps1` | 构建镜像并运行依赖检查、pytest、API smoke、Electron Xvfb smoke | 是 |
| `api-smoke.sh` | 启动 `server.py`，校验 prerecorded API、图像 data URI 和 `execution_mode=prerecorded` | 间接使用 |
| `electron-smoke.sh` | 在 Xvfb 下启动真实 Electron 主进程并检查 `/api/health` | 间接使用 |
| `run-demo.sh` / `run-demo.ps1` | 启动容器内真实 Electron demo，并把窗口转发到宿主机显示 | 可选 |
| `package-submission.sh` | 从 GitHub 新仓库 fresh clone 并生成源码压缩包 | 交付前使用 |
| `run-demo-tailscale.*` | 容器内启动 Tailscale 后运行真实 Electron demo | 队伍真机演示 |
| `run-demo-wslg-tailscale.*` | Windows + WSLg 下显示原生 Electron，并启用 Tailscale | 队伍真机演示推荐 |
| `tailscale-login.*` | 手动浏览器登录 Tailscale，并把状态保存到 Docker volume | 队伍真机演示可选 |
| `start-tailscale.sh` | 容器内部 Tailscale daemon 启动脚本 | 间接使用 |

## 最小复现

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
```

`api-smoke.sh` 默认要求重建图像解码后不少于 50000 bytes，并要求 `execution_mode` 为 `prerecorded`。如果 demo 图像退化为 1x1 占位图，复现会直接失败。

## 原生窗口

Linux / WSL:

```bash
./docker/run-demo.sh
```

Windows PowerShell:

```powershell
.\docker\run-demo.ps1
```

`run-demo.*` 需要宿主机提供 X server。无显示环境下请使用 `repro.*`，它会在容器内用 Xvfb 做无头 Electron smoke。

## Tailscale 真机链路

无板卡复现不需要登录 Tailscale。需要让容器内 demo 直连下位机 Tailscale IP 时，使用：

```bash
./docker/tailscale-login.sh
./docker/run-demo-tailscale.sh
```

Windows PowerShell:

```powershell
.\docker\tailscale-login.ps1
.\docker\run-demo-tailscale.ps1
```

Windows + WSLg 推荐：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要把板端 SSH 密码传给 live 路径，只通过当前 shell 环境变量传入：

```powershell
$env:REMOTE_PASS="..."
$env:PHYTIUM_PI_PASSWORD="..."
.\docker\run-demo-wslg-tailscale.ps1
```

使用 auth key 非交互登录时：

```bash
export TS_AUTHKEY=tskey-auth-...
./docker/run-demo-tailscale.sh
```

注意：

- auth key、板端密码、私钥只能通过环境变量传入，不能提交到仓库或写进 Dockerfile。
- 登录状态保存在 Docker volume `iccomp-tailscale-state`。
- 默认板端检查地址为 `100.121.87.73`，可用 `TAILSCALE_PING_TARGET=<新的 100.x 地址>` 覆盖。

## 打包

```bash
./docker/package-submission.sh
```

脚本默认从 `https://github.com/RUNZHI01/FINAL_WORK_ICCompetition2026.git` fresh clone 远端源码，校验本地 HEAD 与远端 HEAD 一致，然后生成 `iccomp2026-submission.tar.gz`。本交付仓库已经实物化 `Semantic-Communication/` 和 `liboqs/`，不再使用 submodule。
