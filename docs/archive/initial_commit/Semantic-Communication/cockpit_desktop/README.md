# Cockpit Desktop

基于 **Electron + Vite + React 18 + TypeScript + Ant Design 5** 的上位机座舱演示，消费 `session_bootstrap/demo/openamp_control_plane_demo/server.py` HTTP API。

## 开发

```bash
cd cockpit_desktop
npm install
npm run dev
```

## 运行要求

- 需要放在完整仓库里运行，不是只拷贝 `cockpit_desktop/` 一个子目录；Electron 会启动同仓库下的 `session_bootstrap/demo/openamp_control_plane_demo/server.py`
- 主机至少需要 `python3` 或 `python`
- 真机链路相关流程依赖 `bash`、`ssh`；若有 `sshpass` 会优先使用，没有也会退回到 `SSH_ASKPASS`

## 常用环境变量

- `COCKPIT_REPO_ROOT`: 显式指定仓库根目录
- `COCKPIT_SERVER_SCRIPT`: 显式指定后端 `server.py` 路径
- `COCKPIT_PYTHON`: 显式指定 Python 可执行文件
- `COCKPIT_BACKEND_HOST` / `COCKPIT_BACKEND_PORT`: 指定 Electron 与 Vite 使用的后端地址
- `COCKPIT_AIRCRAFT_POSITION_ENV`: 指定本机外部定位源 env 文件；未指定时，若存在 `session_bootstrap/tmp/aircraft_position_baidu_ip.local.env`，Electron 会自动带上它启动后端
- `COCKPIT_SKIP_PYTHON=1`: 已有外部后端时，跳过 Electron 自动拉起 Python
- `MLKEM_CLIENT_SCRIPT` / `MLKEM_LOCAL_REPO_ROOT`: 指定本机 `tcp_client.py` 或其仓库根目录；未指定时会自动搜索当前仓库同级目录
- `MLKEM_REMOTE_PROJECT_ROOT` / `MLKEM_REMOTE_SERVER_SCRIPT`: 指定板端 `tcp_server.py` 所在目录或脚本路径
- `MLKEM_REMOTE_PYTHON` / `REMOTE_TVM_PYTHON`: 指定板端启动 `tcp_server.py` 的 Python
- `MLKEM_REMOTE_STARTUP_CMD`: 完全覆盖板端 `tcp_server.py` 启动命令，适合两台机器环境差异较大时使用
- `MLKEM_REMOTE_ACTIVATE` / `MLKEM_REMOTE_CONDA_SH` / `MLKEM_REMOTE_CONDA_ENV`: 可选，板端启动前额外激活指定环境
- `MLKEM_PORT` / `MLKEM_STATUS_PORT` / `MLKEM_CIPHER_SUITE`: 指定 ML-KEM 数据端口、状态端口、AEAD 套件

如果你要让 Electron 直接吃本机百度 IP 定位，可先准备：

```bash
cp session_bootstrap/config/aircraft_position_baidu_ip.example.env \
   session_bootstrap/tmp/aircraft_position_baidu_ip.local.env
```

然后把其中的 `AK` 改成自己的，接着直接运行：

```bash
cd cockpit_desktop
npm run dev
```

如果 `session_bootstrap/tmp/aircraft_position_baidu_ip.local.env` 存在，Electron 自动拉起的 Python 后端会自动带上 `--aircraft-position-env`。

## 目录

- `electron/` — 主进程、预加载、pythonManager
- `src/renderer/` — React 应用
  - `components/dashboard/` — 仪表盘页面组件
    - `FlightPanel/` — 战术地图 + 遥测
    - `SidebarPanel/` — 链路/安全/引导/闸机/事件
    - `MissionStagePanel/` — 执行模式/遥测/快照/推理/对比
    - `ActionToolbar/` — 操作按钮栏
  - `components/shared/` — PanelCard, ToneTag, EmptyState
  - `components/ios/` — IOSTag, IOSSwitch, IOSProgress
  - `components/charts/` — PerformanceGauge, InferenceTimeline
  - `components/WorldMapStage/` — 战术地图 Canvas
  - `theme/` — tokens.ts (design tokens), echarts-theme.ts
- `public/geo/` — GeoJSON 地图数据
