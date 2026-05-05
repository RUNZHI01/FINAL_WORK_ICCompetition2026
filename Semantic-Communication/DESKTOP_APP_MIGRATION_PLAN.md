# 桌面端 Demo 迁移方案：Electron/Tauri + React + 成熟组件库

> **文档版本：** v1.1 — 2026-03-29  
> **作者：** AI Assistant  
> **状态：** 方案草案，待评审

---

## 一、背景与动机

### 1.1 现有 Demo 方案回顾

| 维度 | Web Demo（vanilla HTML/JS/CSS） | Qt Demo（PySide6 + QML） |
|---|---|---|
| **技术栈** | `http.server` + 手写 3300 行 `app.js` + 500 行 `index.html` + 纯 CSS | PySide6 + Qt Quick/QML 2.15，20 个 `.qml` 组件 |
| **优点** | 零依赖前端、部署简单 | 原生窗口体验、航电风格；**世界地图主舞台效果出色** |
| **痛点** | 无组件化、无类型安全、3000+ 行 JS 难以维护；UI 风格偏朴素；无构建链、无 HMR；响应式/状态管理全靠手写 | QML 生态组件库匮乏；样式定制受限于 Qt Quick 控件；依赖 PySide6 安装（WSL/Linux GPU 兼容问题）；调试工具链不如 Web DevTools 成熟 |
| **数据层** | `fetch` 轮询 `/api/*` JSON 接口 | `urllib` 调用同一套 `http://127.0.0.1:8079` 接口 |
| **地图** | CSS 模拟雷达圆环 + SVG 航线，无真实地理信息 | **Canvas 绘制等距圆柱投影世界地图**，加载 GeoJSON 国界，支持中国战区模式、雷达扫描、航迹叠加、信息面板浮层 |

### 1.2 部署场景

**本 demo 仅部署在上位机（开发笔记本 / 演示 PC）上**，通过 SSH/RPC 远程控制飞腾派下位机。桌面端无需考虑 arm64 交叉编译或飞腾派 WebKitGTK 兼容性问题。

### 1.3 迁移目标

1. **专业级 UI 品质**：航电/任务指挥风格、暗色主题、数据密度高但层次清晰
2. **工程可维护性**：组件化、TypeScript 类型安全、成熟组件库提供表格/图表/表单/弹窗等基建
3. **桌面端原生体验**：独立窗口、系统托盘、本地文件读写能力（读证据包/日志）
4. **复用现有后端**：Python `server.py` 及其完整 API 保持不变，前端仅作为消费者
5. **迁移 Qt 地图**：将 Qt demo 中效果出色的世界地图主舞台迁移到新方案中
6. **答辩演示效果**：一键启动、离线可用、视觉冲击力强

---

## 二、技术选型对比与推荐

### 2.1 桌面容器：Electron vs Tauri

| 维度 | Electron | Tauri |
|---|---|---|
| 运行时 | Chromium + Node.js（~150MB） | 系统 WebView + Rust 后端（~5MB） |
| 包体积 | 大（150–250MB） | 小（5–15MB） |
| 内存占用 | 较高 | 较低 |
| 生态成熟度 | 极高（VS Code、Slack、Discord） | 快速成长，v2 已稳定 |
| 系统 API 能力 | 完善（Node.js 完整能力） | 完善（Rust + 插件体系） |
| 前端自由度 | 完全等同 Chrome | 依赖系统 WebView（Linux 需 WebKitGTK） |
| 学习曲线 | JS/TS 全栈，低 | 需要 Rust（若自定义后端逻辑）；纯前端使用门槛也低 |
| Canvas 性能 | Chromium 硬件加速 Canvas，性能优秀 | 依赖系统 WebView Canvas 实现 |

**推荐：Electron**

理由：
- 仅部署在上位机，包体积不敏感（150MB 在 PC 上无压力）
- Chromium 硬件加速 Canvas 能完美承载从 Qt 迁移过来的世界地图绘制逻辑，渲染效果有保障
- Node.js `child_process` 直接 spawn Python `server.py`，无需 Rust 编译链
- 团队无需学习 Rust，JS/TS 全栈开发效率最高
- 上位机一般是 x86_64 Linux/WSL 或 Windows，Electron 兼容性零顾虑
- **如果团队更偏好 Tauri**，前端代码完全通用，仅壳层不同，随时可切换

### 2.2 前端框架：React vs Vue

| 维度 | React 18+ | Vue 3 |
|---|---|---|
| 生态规模 | 最大 | 大 |
| TypeScript 支持 | 原生 | 原生（Composition API） |
| 组件库选择 | Ant Design、MUI、shadcn/ui、Mantine | Ant Design Vue、Element Plus、Naive UI、PrimeVue |
| 状态管理 | Zustand / Jotai / Redux Toolkit | Pinia |
| 数据请求 | TanStack Query（React Query） | TanStack Query / VueQuery |
| Canvas 集成 | `useRef` + `useEffect` 直接操作原生 Canvas | `ref` + `onMounted` 同等能力 |

**推荐：React 18 + TypeScript**

理由：
- 组件库生态最丰富，特别是 Ant Design 5.x 的**数据密集型组件**（ProTable、ProDescriptions、StatisticCard）天然契合本项目的仪表板场景
- 社区资源丰富，遇到问题容易搜索到解决方案
- Canvas 组件封装模式成熟，适合承载 Qt 地图迁移

### 2.3 组件库：推荐 Ant Design 5.x

| 备选 | 风格 | 数据组件 | 暗色主题 | 适配度评估 |
|---|---|---|---|---|
| **Ant Design 5.x** | 企业级、信息密度高 | ProTable、Descriptions、Statistic、Progress、Timeline、Tabs、Drawer | CSS-in-JS 原生暗色 | ★★★★★ |
| shadcn/ui + Tailwind | 现代极简、高度可定制 | 需自行组合 | 原生暗色 | ★★★★ 定制空间大但缺数据组件 |
| MUI (Material UI) | Material Design | DataGrid、Timeline | 原生暗色 | ★★★★ 偏 Google 风 |
| Mantine | 现代简洁 | 数据组件在增长中 | 原生暗色 | ★★★☆ |

**推荐：Ant Design 5.x**（`antd` + `@ant-design/pro-components`）

理由：
- **ProComponents** 提供开箱即用的 `ProTable`（展示性能指标表）、`StatisticCard`（关键数字展示）、`ProDescriptions`（证据包详情）
- 内置 `ConfigProvider` 一行代码切换暗色主题
- 中文文档完善，与项目中文 UI 一致
- `Progress`、`Timeline`、`Drawer`、`Tabs`、`Modal` 等能直接映射到现有 Web demo 的四幕结构

### 2.4 补充依赖

| 用途 | 推荐 | 说明 |
|---|---|---|
| 图表/可视化 | **ECharts**（`echarts` + `echarts-for-react`） | 性能指标、弱网对比、推理进度的折线/柱状图；中文支持好 |
| 世界地图 | **HTML5 Canvas**（自研组件，从 Qt 迁移） | 详见第三章地图迁移方案 |
| 状态管理 | **Zustand** | 轻量、TypeScript 友好、无 boilerplate |
| 数据请求 | **TanStack Query v5** | 自动轮询、缓存、retry；替代现有手写 `setInterval` + `fetch` |
| 构建工具 | **Vite** | Electron + Vite 模板（`electron-vite`）；HMR 极快 |
| CSS 方案 | **Tailwind CSS 4** + Ant Design Token | 快速自定义航电风格的间距、颜色、动画 |

---

## 三、Qt 世界地图迁移方案（重点）

### 3.1 现有 Qt 地图实现分析

Qt demo 的世界地图是本项目视觉效果的亮点，实现分布在以下文件中：

| 文件 | 职责 |
|---|---|
| `WorldMapStageCanvas.qml`（~1476 行） | **核心渲染引擎**：三层 Canvas（底图 / 航迹 / 扫描）、等距圆柱投影、GeoJSON 解析与绘制、大陆轮廓 fallback、雷达扫描动画、航迹绘制、当前位置标记 |
| `WorldMapStage.qml`（~331 行） | **后端选择器**：根据环境自动选择 Canvas / SVG / QtLocation 后端 |
| `TacticalView.qml`（~742 行） | **战术视图容器**：包裹地图 + 飞行读数面板 + 弱网建议 + 信息卡片 |
| `qml/assets/world-countries-ne50m.geojson`（1.3MB） | Natural Earth 50m 世界国界 GeoJSON |
| `qml/assets/china-official.geojson`（620KB） | 中国省界 GeoJSON |

### 3.2 Qt 地图技术特征

| 特征 | 实现方式 |
|---|---|
| **投影** | 等距圆柱投影（Equirectangular）：`projectX(lon) = (lon + 180) / 360 * width`，`projectY(lat) = (90 - lat) / 180 * height` |
| **底图** | 三种来源：(1) Canvas 绘制大陆轮廓多边形（内置 `continentPolygons` 数组）；(2) 加载 GeoJSON 逐 feature 绘制国家轮廓；(3) 外部 SVG/图片 |
| **中国战区模式** | 当 `chinaScene=true` 时，投影窗口收缩到 `[72°E–136°E, 16°N–56°N]`，加载 `china-official.geojson`，显示省级标注（北京、上海等） |
| **经纬网** | 世界模式 `[-120°, -60°, 0°, 60°, 120°]` / `[-60°, -30°, 0°, 30°, 60°]`；中国模式 `[80°, 100°, 120°, 130°]` / `[20°, 30°, 40°, 50°]` |
| **航迹绘制** | 分段绘制，每段透明度递增（越新越亮），阴影 → 光晕 → 主线三层渲染 |
| **当前位置** | 十字准线 + 同心圆 + 航向线 + 弧形指示器 |
| **雷达扫描** | 从当前位置出发的扇形渐变扫描，200ms 间隔旋转 12° |
| **浮层面板** | 左上角投影标签、右上角场景焦点、底部信息栏（航迹/锚点/航向）、当前位置 callout |
| **视觉风格** | 深海蓝渐变底色 + 径向光晕 + 暗角 + 大陆蓝绿填充 + 青色海岸线 + 琥珀色告警 |

### 3.3 迁移策略：HTML5 Canvas React 组件

Qt 的 Canvas 绑定本质是调用标准 `CanvasRenderingContext2D` API（`beginPath`、`lineTo`、`fill`、`stroke`、`createRadialGradient` 等），**与 HTML5 Canvas 2D API 完全同源**。迁移核心是将 QML 属性绑定和声明式动画改写为 React 状态 + `requestAnimationFrame`。

#### 迁移对照表

| Qt QML 概念 | React/Canvas 对应 |
|---|---|
| `Canvas { onPaint: { var ctx = getContext("2d"); ... } }` | `<canvas ref={canvasRef}>` + `useEffect` 中 `canvasRef.current.getContext('2d')` |
| `property var trackData: []` | `props.trackData: TrackPoint[]` |
| `Timer { interval: 200; onTriggered: scanSweepDeg += 12 }` | `useRef(sweepDeg)` + `requestAnimationFrame` 循环 |
| `XMLHttpRequest` 加载 GeoJSON | `fetch()` 或构建时直接 `import` JSON（Vite 原生支持） |
| `NumberAnimation on opacity { from: 0; to: 1 }` | CSS `transition` / `@keyframes` / framer-motion |
| `Rectangle { gradient: Gradient { ... } }` | 浮层 `div` + CSS `linear-gradient` / `radial-gradient` |
| `Repeater { model: bannerChips; delegate: Rectangle { ... } }` | `bannerChips.map(chip => <ChipBadge key={...} {...chip} />)` |
| `shellWindow.scaled(x)` | CSS `rem` / `clamp()` 自适应 |

#### 分层 Canvas 架构（保留 Qt 三层设计）

```
┌──────────────────────────────────────────────┐
│  React 容器 div（position: relative）         │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Canvas Layer 1: baseCanvas             │  │  ← 底图：海洋渐变 + 经纬网 + 大陆/GeoJSON
│  ├────────────────────────────────────────┤  │
│  │ Canvas Layer 2: trackCanvas            │  │  ← 航迹线 + 当前位置标记 + 聚光灯
│  ├────────────────────────────────────────┤  │
│  │ Canvas Layer 3: sweepCanvas            │  │  ← 雷达扫描扇形动画
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌─ HTML/CSS 浮层 ──────────────────────┐   │
│  │  投影标签 Badge（左上）               │   │  ← 用 Ant Design Tag/Badge
│  │  场景焦点 Badge（右上）               │   │  ← 用 Ant Design Tag
│  │  命令横幅 Banner（底部/居中）          │   │  ← 自定义 React 组件
│  │  当前位置 Callout（跟随标记点）        │   │  ← absolute 定位 div
│  │  信息栏（底部）                       │   │  ← Ant Design Descriptions 简化版
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

**底图 Canvas 仅在窗口 resize 或 GeoJSON 加载完成时重绘**（与 Qt 逻辑一致），航迹 Canvas 在数据更新时重绘，扫描 Canvas 由 `requestAnimationFrame` 持续驱动。三层分离避免全量重绘，保证性能。

#### 关键绘制函数迁移示例

Qt 的 `paintStaticMap` 函数可以几乎 1:1 翻译为 TypeScript：

```typescript
function paintStaticMap(ctx: CanvasRenderingContext2D, w: number, h: number) {
  // 海洋渐变背景
  const ocean = ctx.createLinearGradient(0, 0, 0, h);
  ocean.addColorStop(0.0,  '#060e1a');
  ocean.addColorStop(0.34, '#0c1e32');
  ocean.addColorStop(0.62, '#081626');
  ocean.addColorStop(1.0,  '#020810');
  ctx.fillStyle = ocean;
  ctx.fillRect(0, 0, w, h);

  // 径向光晕
  const beam = ctx.createRadialGradient(w * 0.72, h * 0.32, 0, w * 0.72, h * 0.32, w * 0.55);
  beam.addColorStop(0.0, 'rgba(120,216,255,0.18)');
  beam.addColorStop(0.52, 'rgba(120,216,255,0.07)');
  beam.addColorStop(1.0, 'rgba(120,216,255,0.0)');
  ctx.fillStyle = beam;
  ctx.fillRect(0, 0, w, h);

  // ... 经纬网、GeoJSON 国界绘制逻辑同 Qt 实现
}
```

#### GeoJSON 资源迁移

| 文件 | 大小 | 迁移方式 |
|---|---|---|
| `world-countries-ne50m.geojson` | 1.3MB | 拷贝到 `public/geo/`，运行时 `fetch` 加载（避免打入 JS bundle） |
| `china-official.geojson` | 620KB | 同上 |
| `world-map-backdrop.svg` | 396KB | 拷贝到 `public/geo/`，作为 SVG 后端 fallback |

### 3.4 新增能力（Qt 没有的）

迁移到 HTML5 Canvas + React 后，可以顺便增强：

| 增强 | 说明 |
|---|---|
| **鼠标交互** | 悬停国家高亮、点击查看坐标信息（Qt Canvas 版缺少此能力） |
| **平滑缩放** | `wheel` 事件控制投影缩放级别，支持从世界视图到中国战区的平滑过渡 |
| **WebGL 备选** | 如果航迹节点极多（>1000），可引入 `deck.gl` 或 Three.js 硬件加速渲染 |
| **截图导出** | `canvas.toDataURL()` 一键导出地图截图，用于答辩材料 |

### 3.5 组件 API 设计

```typescript
interface WorldMapStageProps {
  // 航迹与位置
  trackData: TrackPoint[];
  currentPoint: { latitude: number; longitude: number } | null;
  headingDeg: number;

  // 模式
  chinaTheaterMode?: boolean;
  landingMode?: boolean;

  // 浮层信息
  bannerTitle?: string;
  bannerText?: string;
  bannerChips?: ChipData[];
  scenarioLabel?: string;
  scenarioTone?: 'online' | 'warning' | 'degraded' | 'neutral';
  projectionLabel?: string;

  // 尺寸与交互
  className?: string;
  onPositionClick?: (lat: number, lon: number) => void;
}
```

---

## 四、架构设计

### 4.1 整体架构

```
┌──────────────────────────────────────────────────────┐
│               Electron Shell（上位机）                 │
│  ┌────────────────────────────────────────────────┐  │
│  │        React + TypeScript + Ant Design          │  │
│  │                                                  │  │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────────────┐  │  │
│  │  │Zustand   │ │TanStack  │ │  React Router   │  │  │
│  │  │Store     │ │Query     │ │  (SPA 路由)      │  │  │
│  │  └────┬─────┘ └────┬─────┘ └─────────────────┘  │  │
│  │       │             │                            │  │
│  │       └──────┬──────┘                            │  │
│  │              ▼                                    │  │
│  │      API Service Layer (TypeScript)              │  │
│  │      fetch → http://127.0.0.1:8079/api/*         │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  Main Process (Node.js):                             │
│    child_process.spawn('python3', ['server.py'])     │
│    窗口管理、系统托盘、生命周期                        │
└──────────────────────────────────────────────────────┘
        │                                    │
        │ HTTP JSON API（完全复用）            │ SSH/RPC
        ▼                                    ▼
┌───────────────────────────┐     ┌────────────────────┐
│  Python server.py (8079)  │     │  飞腾派（下位机）    │
│  demo_data / event_spine  │ ──→ │  TVM/MNN 推理      │
│  inference_runner / ...   │     │  OpenAMP 控制面     │
└───────────────────────────┘     └────────────────────┘
```

### 4.2 关键设计决策

1. **Python 后端零改动**：前端通过 HTTP 调用 `127.0.0.1:8079` 的全部 API，保持原有 `server.py` 不变
2. **Electron Main Process 托管 Python 进程**：`child_process.spawn('python3', ['server.py'])`，窗口关闭时自动终止；解决"先启后端再启前端"的操作步骤
3. **API 类型安全**：根据 `server.py` 的路由与 `demo_data.build_snapshot()` 返回结构，生成 TypeScript 类型定义
4. **离线优先**：静态资源随 Electron 打包，GeoJSON 文件内嵌；不依赖外部 CDN 或在线瓦片

### 4.3 页面路由与功能映射

现有 Web demo 采用"四幕 + 首页 + 四个 Drawer"结构，迁移后映射为：

| 现有结构 | 新方案页面/组件 | 说明 |
|---|---|---|
| 首页 cockpitShell | **`/` — Dashboard** | 主仪表板：模式状态、关键指标、**世界地图主舞台**、快捷操作 |
| Session Drawer | **`/session`** 或 Dashboard 内 Drawer | 板卡接入、凭据管理、Job Manifest Gate |
| 第一幕 act1Panel | Dashboard 左侧面板 | 可信状态、里程碑时间线 |
| 第二幕 currentDrawer | **`/reconstruction`** | Current 重建进度、图像对比、实时日志 |
| 第三幕 compareDrawer | **`/comparison`** | Baseline vs Current 对比、性能口径、证据材料 |
| 第四幕 safetyDrawer | **`/safety`** | 故障注入、SAFE_STOP、事件时间线、黑匣子 |
| Qt TacticalView 世界地图 | Dashboard 中央区域 `WorldMapStage` | **从 Qt 迁移的 Canvas 世界地图 + 航电浮层** |
| 弱网控制台 sidebar | Dashboard 右侧面板 | 弱网场景对照、链路导演 |

---

## 五、UI 设计规范

### 5.1 设计语言：Mission Control Dark

整体视觉参考**航天任务指挥中心/航电座舱**风格，暗色为主：

- **主色调**：深海蓝底 `#060e1a` → `#0d1b2a`（与 Qt 地图底色一致），卡片背景 `#0c1e30`
- **强调色**：科技蓝 `#5ab7ff`（正常状态）、青 `#8fe6ff`（在线/通过）、琥珀 `#ffbf55`（告警/降级）、红 `#f85149`（故障/离线）
- **字体**：等宽数据用 `JetBrains Mono`；正文用系统默认无衬线字体
- **数据密度**：信息优先，大量使用 `Statistic`、`Badge`、`Tag` 组件展示实时数值
- **动效**：雷达扫描、航迹渐显、进度条平滑过渡、状态切换微动画、数字跳动（countUp 效果）

> 配色体系直接复用 Qt demo 的 `shellWindow` 主题 token（`accentCyan`、`accentBlue`、`accentAmber`、`textStrong`、`textSecondary`、`textMuted` 等），保证地图与其他面板的视觉一致性。

### 5.2 布局草案

```
┌──────────────────────────────────────────────────────────┐
│  [Logo] 飞腾多核弱网安全语义视觉回传系统   [模式] [时间] │  ← 顶栏
├────────┬──────────────────────────────────┬───────────────┤
│        │                                  │               │
│ 状态   │  ┌─ 世界地图主舞台 ──────────┐  │  弱网控制台   │
│ 面板   │  │ Canvas: 海洋 + 国界 + 航迹 │  │  链路导演     │
│        │  │ 浮层: 投影标签 / 场景焦点  │  │  安全镜像     │
│ 里程碑 │  │ 动画: 雷达扫描 / 航迹渐显  │  │               │
│ 时间线 │  └────────────────────────────┘  │  Operator     │
│        │                                  │  Cue 卡片     │
│ 关键   │     执行面板                      │               │
│ 指标   │     快捷操作按钮组               │               │
│        │     Current 重建进度             │               │
├────────┴──────────────────────────────────┴───────────────┤
│  [Session/Gate] [Current详情] [Compare/Evidence] [Safety] │  ← 底部导航
└──────────────────────────────────────────────────────────┘
```

---

## 六、核心组件清单

### 6.1 布局组件

| 组件 | 职责 | Ant Design 基础 |
|---|---|---|
| `AppShell` | 全局布局壳、侧边栏导航、顶栏 | `Layout`、`Menu` |
| `DashboardPage` | 主仪表板三栏布局 | `Row`、`Col` |
| `PageDrawer` | 可从底部或右侧拉出的详情面板 | `Drawer` |

### 6.2 世界地图组件（从 Qt 迁移）

| 组件 | 职责 | 技术 |
|---|---|---|
| **`WorldMapStage`** | **核心地图组件**：三层 Canvas 渲染 + 浮层面板 | HTML5 Canvas 2D + React |
| `WorldMapStage/BaseLayer` | 底图层：海洋渐变、径向光晕、经纬网、GeoJSON 国界绘制 | Canvas 2D |
| `WorldMapStage/TrackLayer` | 航迹层：航迹线分段渲染、当前位置标记、同心圆、航向线 | Canvas 2D |
| `WorldMapStage/SweepLayer` | 扫描层：雷达扇形扫描动画 | Canvas 2D + `requestAnimationFrame` |
| `WorldMapStage/StageBadge` | 左上角投影/模式标签浮层 | React + CSS |
| `WorldMapStage/ScenarioBadge` | 右上角场景焦点浮层 | React + CSS |
| `WorldMapStage/CommandBanner` | 底部/居中命令横幅（任务名、坐标、芯片组） | React + CSS |
| `WorldMapStage/PositionCallout` | 跟随当前位置的信息 callout | React + absolute 定位 |
| `WorldMapStage/InfoRail` | 底部信息栏（航迹/锚点/航向·定位） | React + CSS |
| `useGeoJson` | GeoJSON 异步加载 + 解析 Hook | `fetch` + `useState` |
| `useProjection` | 等距圆柱投影工具函数 | 纯 TS 函数 |

### 6.3 数据展示组件

| 组件 | 职责 | Ant Design 基础 |
|---|---|---|
| `StatusPanel` | 系统/板卡/模式状态概览 | `Descriptions`、`Badge`、`Tag` |
| `MetricCard` | 单个关键指标（如延迟、提升百分比） | `Statistic`、`Card` |
| `MilestoneTimeline` | P0 里程碑与 FIT 事件时间线 | `Timeline`、`Steps` |
| `PerformanceTable` | 性能指标表格（Current vs Baseline） | `ProTable` |
| `ProgressTracker` | 300 张图实时重建进度 | `Progress`、`Statistic` |
| `ImageCompare` | 参考图 vs 重建图对比查看器 | 自定义（滑动分屏） |
| `EventLog` | 事件流实时日志面板 | `List`、`Timeline` |

### 6.4 交互组件

| 组件 | 职责 | Ant Design 基础 |
|---|---|---|
| `CredentialForm` | 板卡 SSH 凭据录入 | `Form`、`Input`、`InputPassword` |
| `ActionDock` | 操作按钮组（探板、推理、SAFE_STOP 等） | `Space`、`Button`、`Popconfirm` |
| `FaultInjector` | 故障注入控制面板 | `Button`、`Alert`、`Modal` |
| `LinkDirector` | 链路导演档位切换 | `Radio`、`Select`、`Slider` |
| `WeakNetworkConsole` | 弱网场景对照与状态 | `Tabs`、`Descriptions` |

### 6.5 可视化组件

| 组件 | 职责 | 技术 |
|---|---|---|
| `PerformanceChart` | 性能对比柱状图/雷达图 | `echarts-for-react` |
| `LatencyTimeline` | 推理延迟时序图 | `echarts-for-react` |
| `BusStatusGrid` | 总线/子系统状态矩阵 | 自定义 SVG Grid |

---

## 七、API 对接层设计

### 7.1 TypeScript API Client

```typescript
// src/api/client.ts
const BASE_URL = 'http://127.0.0.1:8079';

export const api = {
  getSnapshot:          () => get<Snapshot>('/api/snapshot'),
  getSystemStatus:      () => get<SystemStatus>('/api/system-status'),
  getJobManifestGate:   () => get<JobManifestGate>('/api/job-manifest-gate'),
  getLinkDirector:      () => get<LinkDirector>('/api/link-director'),
  getAircraftPosition:  () => get<AircraftPosition>('/api/aircraft-position'),
  getEventSpine:        () => get<EventSpine>('/api/event-spine'),
  getHealth:            () => get<Health>('/api/health'),
  getArchiveSessions:   () => get<ArchiveSession[]>('/api/archive/sessions'),
  getInferenceProgress: (jobId: string) =>
    get<InferenceProgress>(`/api/inference-progress?job_id=${jobId}`),

  postBoardAccess:      (data: BoardAccessInput) => post('/api/session/board-access', data),
  postProbeBoard:       (data?: ProbeInput) => post('/api/probe-board', data),
  postRunInference:     (data: InferenceInput) => post('/api/run-inference', data),
  postRunBaseline:      (data: BaselineInput) => post('/api/run-baseline', data),
  postInjectFault:      (data: FaultInput) => post('/api/inject-fault', data),
  postRecover:          (data?: RecoverInput) => post('/api/recover', data),
  postLinkProfile:      (data: LinkProfileInput) => post('/api/link-director/profile', data),
  postManifestPreview:  (data?: ManifestPreviewInput) =>
    post('/api/job-manifest-gate/preview', data),
};
```

### 7.2 TanStack Query Hooks

```typescript
// src/hooks/useSnapshot.ts
export function useSnapshot() {
  return useQuery({
    queryKey: ['snapshot'],
    queryFn: api.getSnapshot,
    refetchInterval: 5000,
  });
}

export function useAircraftPosition() {
  return useQuery({
    queryKey: ['aircraft-position'],
    queryFn: api.getAircraftPosition,
    refetchInterval: 2000,  // 地图位置 2 秒刷新
  });
}

export function useInferenceProgress(jobId: string | null) {
  return useQuery({
    queryKey: ['inference-progress', jobId],
    queryFn: () => api.getInferenceProgress(jobId!),
    enabled: !!jobId,
    refetchInterval: 1000,
  });
}
```

---

## 八、项目目录结构

```
cockpit_desktop/                          # 新建顶层目录
├── README.md
├── package.json                          # 前端依赖
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── electron/                             # Electron 主进程
│   ├── main.ts                           # 窗口创建、spawn Python server
│   ├── preload.ts                        # 安全桥接
│   └── pythonManager.ts                  # Python 进程生命周期管理
├── src/                                  # React 前端
│   ├── main.tsx                          # 入口
│   ├── App.tsx                           # 路由 + 全局 Provider
│   ├── api/
│   │   ├── client.ts                     # HTTP 封装
│   │   └── types.ts                      # 从 Python API 推导的 TS 类型
│   ├── hooks/
│   │   ├── useSnapshot.ts
│   │   ├── useAircraftPosition.ts
│   │   ├── useInferenceProgress.ts
│   │   ├── useGeoJson.ts                 # GeoJSON 加载 hook
│   │   └── ...
│   ├── stores/
│   │   └── appStore.ts                   # Zustand 全局状态
│   ├── layouts/
│   │   └── AppShell.tsx
│   ├── pages/
│   │   ├── Dashboard/
│   │   │   ├── index.tsx
│   │   │   ├── StatusPanel.tsx
│   │   │   ├── ExecutionBoard.tsx
│   │   │   └── WeakNetworkSidebar.tsx
│   │   ├── Reconstruction/
│   │   │   ├── index.tsx
│   │   │   ├── ProgressTracker.tsx
│   │   │   └── ImageCompare.tsx
│   │   ├── Comparison/
│   │   │   ├── index.tsx
│   │   │   ├── PerformanceTable.tsx
│   │   │   └── CompareViewer.tsx
│   │   └── Safety/
│   │       ├── index.tsx
│   │       ├── FaultInjector.tsx
│   │       ├── EventTimeline.tsx
│   │       └── BlackboxPanel.tsx
│   ├── components/
│   │   ├── WorldMapStage/                # ★ 从 Qt 迁移的世界地图
│   │   │   ├── index.tsx                 # 主组件：Canvas 容器 + 浮层
│   │   │   ├── BaseLayer.ts              # 底图绘制（海洋/经纬网/国界）
│   │   │   ├── TrackLayer.ts             # 航迹 + 位置标记绘制
│   │   │   ├── SweepLayer.ts             # 雷达扫描动画
│   │   │   ├── projection.ts             # 等距圆柱投影函数
│   │   │   ├── geoRenderer.ts            # GeoJSON → Canvas 绘制
│   │   │   ├── continentPolygons.ts      # 内置大陆轮廓 fallback 数据
│   │   │   ├── theme.ts                  # 配色常量（复用 Qt token）
│   │   │   ├── StageBadge.tsx            # 左上角投影标签浮层
│   │   │   ├── ScenarioBadge.tsx         # 右上角场景焦点浮层
│   │   │   ├── CommandBanner.tsx         # 底部命令横幅
│   │   │   ├── PositionCallout.tsx       # 跟随位置的 callout
│   │   │   └── InfoRail.tsx              # 底部信息栏
│   │   ├── MetricCard.tsx
│   │   ├── MilestoneTimeline.tsx
│   │   ├── ActionDock.tsx
│   │   ├── CredentialForm.tsx
│   │   ├── PerformanceChart.tsx
│   │   └── ...
│   ├── theme/
│   │   └── antdTheme.ts                  # Ant Design 暗色主题 token
│   └── styles/
│       └── global.css                    # Tailwind 基础 + 航电风格
├── public/
│   └── geo/                              # GeoJSON 地理数据（从 Qt 迁移）
│       ├── world-countries-ne50m.geojson  # 世界国界（1.3MB）
│       ├── china-official.geojson         # 中国省界（620KB）
│       └── world-map-backdrop.svg         # SVG 底图备用（396KB）
└── scripts/
    └── generate-types.ts                 # 从 Python API 自动生成 TS 类型（可选）
```

---

## 九、实施路线图

### Phase 1：脚手架搭建（1 天）

- [ ] 使用 `electron-vite` 初始化项目（Electron + Vite + React + TypeScript）
- [ ] 安装依赖：`antd`、`@ant-design/pro-components`、`tailwindcss`、`zustand`、`@tanstack/react-query`、`echarts-for-react`、`react-router-dom`
- [ ] 配置 Ant Design 暗色主题 token（复用 Qt demo 色板）
- [ ] `electron/main.ts` 中 spawn Python `server.py`，窗口关闭时 kill
- [ ] 验证：Electron 窗口启动 → 能 fetch `/api/health` → 显示 "OK"

### Phase 2：世界地图迁移（2–3 天）★ 优先

- [ ] 拷贝 GeoJSON 资源到 `public/geo/`
- [ ] 实现 `projection.ts`（等距圆柱投影 + 中国战区模式）
- [ ] 实现 `BaseLayer.ts`：翻译 Qt `paintStaticMap` → Canvas 2D
- [ ] 实现 `geoRenderer.ts`：GeoJSON feature 遍历 + 多边形绘制
- [ ] 实现 `TrackLayer.ts`：翻译 Qt `drawTrack` + 位置标记
- [ ] 实现 `SweepLayer.ts`：翻译 Qt `paintSweepOverlay` + `requestAnimationFrame`
- [ ] 实现浮层组件：`StageBadge`、`ScenarioBadge`、`CommandBanner`、`PositionCallout`、`InfoRail`
- [ ] 对接 `/api/aircraft-position` 实时数据
- [ ] 视觉对比验证：新地图 vs Qt 截图，确保效果一致

### Phase 3：Dashboard 主页面（2 天）

- [ ] `AppShell` 布局（顶栏 + 三栏 + 底部导航）
- [ ] `StatusPanel`：系统状态、模式指示、板卡在线状态
- [ ] `MetricCard` 组：关键性能数字（加速比、延迟）
- [ ] 集成 `WorldMapStage` 到 Dashboard 中央区域
- [ ] `ExecutionBoard`：快捷操作按钮、Current 重建进度条、密码快捷录入
- [ ] `WeakNetworkSidebar`：弱网场景对照

### Phase 4：Current 重建详情页（1–2 天）

- [ ] `ProgressTracker`：300 张图实时进度（TanStack Query 1s 轮询）
- [ ] `ImageCompare`：滑动分屏对比原图/重建图
- [ ] 延迟计时板、质量指标展示
- [ ] 实时日志流面板

### Phase 5：Compare / Evidence 页（1–2 天）

- [ ] Baseline vs Current 双进度卡片
- [ ] `CompareViewer`：样例选择 + 双路对比
- [ ] `PerformanceTable`：正式口径指标表（ProTable）
- [ ] 证据材料入口链接

### Phase 6：Safety / Blackbox 页（1–2 天）

- [ ] `FaultInjector`：三种故障注入按钮 + SAFE_STOP
- [ ] `EventTimeline`：事件流时间线（Timeline 组件）
- [ ] `BlackboxPanel`：设备状态、任务队列、回传/重建状态矩阵

### Phase 7：Session 管理与收尾（1 天）

- [ ] `CredentialForm`：完整板卡会话接入表单
- [ ] Job Manifest Gate 展示
- [ ] 归档会话浏览与回放
- [ ] 全局 Toast 反馈、错误边界
- [ ] 打包测试（`electron-builder`）、README 文档

**总估时：9–13 天**（单人全职；地图迁移为重点耗时项）

---

## 十、关键风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| Qt Canvas 绘制逻辑翻译工作量 | 地图迁移耗时超预期 | Qt Canvas 2D API 与 HTML5 Canvas 2D API 同源，逻辑可以几乎 1:1 翻译；`WorldMapStageCanvas.qml` 约 700 行绘制代码，估计 2 天可完成 |
| GeoJSON 解析性能 | 1.3MB GeoJSON 首次加载卡顿 | 异步 `fetch` + Web Worker 解析；首帧先显示内置 `continentPolygons` 轮廓，GeoJSON 加载完毕后切换（与 Qt 行为一致） |
| Python server.py 的 CORS 限制 | Electron Renderer 请求被拒 | Electron 可配置 `webSecurity: false`（开发模式），或在 `server.py` 添加 `Access-Control-Allow-Origin: *` 头 |
| Ant Design 打包体积 | Electron 包进一步膨胀 | 按需导入 + Vite tree-shaking；Electron 本身已 150MB+，antd 增量（~1MB gzip）可忽略 |
| 团队不熟悉 React/TypeScript | 开发效率降低 | 组件库提供大量开箱即用组件，减少自定义代码量；提供模板和约定 |

---

## 十一、备选方案：若选 Tauri

如果后续包体积成为关注点（如发布到外部用户），切换 Tauri 差异仅在壳层：

```diff
- electron/main.ts         →  src-tauri/src/main.rs
- child_process.spawn()    →  Tauri sidecar 声明
- electron-builder.yml     →  tauri.conf.json
```

**前端代码（`src/` 目录）完全不变**，包括地图组件。

---

## 十二、与现有 Demo 的关系

| 方面 | 处理策略 |
|---|---|
| Web Demo (`openamp_control_plane_demo/`) | **保留**，作为轻量备用方案和 API 参考 |
| Qt Demo (`cockpit_native/`) | **保留**，其中 GeoJSON 资源和地图绘制逻辑被迁移到新方案 |
| Python 后端 (`server.py`) | **完全复用**，零改动（仅可能加 CORS 头） |
| 新桌面端 (`cockpit_desktop/`) | 独立顶层目录，不影响现有代码 |
| 启动方式 | Electron 一键启动（内部自动 spawn Python server + 打开窗口） |

---

## 十三、总结

本方案推荐 **Electron + React 18 + TypeScript + Ant Design 5.x** 技术栈，仅部署在上位机：

- **Electron** 提供桌面壳 + Chromium 硬件加速 Canvas，保证地图渲染性能
- **从 Qt 迁移世界地图**：复用 GeoJSON 资源 + 将 Qt Canvas 2D 绘制逻辑 1:1 翻译为 HTML5 Canvas，保留海洋渐变、国界轮廓、雷达扫描、航迹渲染等全部视觉效果
- **React + TypeScript** 提供类型安全的组件化开发体验
- **Ant Design** 提供开箱即用的企业级数据组件，大幅减少 UI 开发量
- **TanStack Query + Zustand** 解决数据轮询和状态管理

核心原则：**Python 后端零改动、Qt 地图视觉完整迁移、前端组件化重写、上位机一键部署**。预计 9–13 天可完成全部功能迁移并达到答辩演示品质。
