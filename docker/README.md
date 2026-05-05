# Docker 入口说明

评委复现只需要使用 `ubuntu-minimal.Dockerfile`，它会构建 Python 后端、`liboqs` 后端和真实 Electron 上位机 demo。

| 文件 | 用途 | 评委是否需要 |
|---|---|---|
| `ubuntu-minimal.Dockerfile` | 评委复现镜像，包含 Electron build、Python 依赖和 `liboqs` | 是 |
| `repro.sh` / `repro.ps1` | 构建镜像并运行依赖、测试和 Electron Xvfb smoke | 是 |
| `run-demo.sh` / `run-demo.ps1` | 启动容器内真实 Electron demo，并把窗口转发到宿主机显示 | 是 |
| `run-demo-tailscale.sh` / `run-demo-tailscale.ps1` | 在容器内启动 Tailscale 后再启动真实 Electron demo，用于连接 `100.x` 下位机 | 队伍真机演示需要 |
| `run-demo-wslg-tailscale.sh` / `run-demo-wslg-tailscale.ps1` | 使用 WSLg 显示原生 Electron，并在同一容器内启用 Tailscale | Windows + WSLg 真机演示推荐 |
| `tailscale-login.sh` / `tailscale-login.ps1` | 手动浏览器登录 Tailscale，并把状态保存到 Docker volume | 队伍真机演示可选 |
| `start-tailscale.sh` | 容器内部 Tailscale daemon 启动脚本，要求运行容器时提供 TUN 和 NET_ADMIN | 间接使用 |
| `package-submission.sh` | 在 Linux/WSL 大小写敏感文件系统中重新克隆并打包源码 | 交付前使用 |
| `dev.Dockerfile` / `dev.sh` | 队伍开发环境，包含更完整的 Tongsuo 开发链路 | 否 |
| `Dockerfile` / `docker-build.sh` | 历史板端/交叉构建链路 | 否 |

不要在 Windows 工作树直接打包提交源码。`Semantic-Communication` submodule 同时包含 `DOCUMENTS/` 和 `Documents`，Windows 默认大小写不敏感，会污染 submodule 状态。交付前请在 Linux/WSL 文件系统执行：

```bash
./docker/package-submission.sh
```

执行打包前必须先提交并推送父仓库和所有 submodule pinned commit。`package-submission.sh` 会重新从 GitHub clone 一份干净源码，并校验本地 HEAD、submodule SHA 与远端 clone 一致；不一致会直接失败。

复现镜像只带入当前 demo 需要的两张最小样例图：

- `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/static/demo_samples/places365_208_current.png`
- `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/static/demo_samples/places365_208_baseline.png`

这不是 UI 截图替代方案；它只是把 `demo_data.py` 使用的预录图像资源固定在 demo 模块内，Electron、Python 后端和 API 交互链路仍按原 demo 执行。

## Tailscale 真机链路

无板卡复现不需要登录 Tailscale。需要让容器内 demo 直连下位机 Tailscale IP 时，使用：

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

Windows + WSLg 推荐使用专用入口，它会挂载 `/mnt/wslg`、复用 `iccomp-tailscale-state`，并默认检查 `100.121.87.73`：

```powershell
.\docker\run-demo-wslg-tailscale.ps1
```

如果需要把板卡 SSH 密码传给 demo 的 live 路径，只通过当前 shell 环境变量传入，不要写进脚本或 Dockerfile：

```powershell
$env:REMOTE_PASS="..."
.\docker\run-demo-wslg-tailscale.ps1
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

注意：

- auth key 只通过环境变量传入，不能提交到仓库或写进 Dockerfile。
- 登录状态保存在 Docker volume `iccomp-tailscale-state`，同一台机器下次运行可复用；需要强制重新登录时删除该 volume。
- 脚本使用 kernel TUN 模式，让 `server.py`、`ssh`、`sshpass` 等现有逻辑直接访问 `100.121.87.73`，不需要改成 SOCKS/HTTP 代理。
- 如果板端 Tailscale IP 变化，设置 `TAILSCALE_PING_TARGET=<新的 100.x 地址>`。
