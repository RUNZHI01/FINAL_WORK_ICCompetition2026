# Cockpit Desktop UI 重设计方案

> **版本：** v1.0 — 2026-03-30  
> **状态：** 待执行  
> **审阅人：** 项目负责人

---

## 〇、代码审查总结：当前 Demo 存在的核心问题

我已逐文件审阅了 `cockpit_desktop/` 下的全部 UI 代码（约 40 个文件）。以下是**按严重程度排序**的问题清单：

### 问题 A — 布局架构崩坏（严重）

| 问题 | 位置 | 说明 |
|---|---|---|
| **无三栏 Dashboard 布局** | `DashboardPage.tsx` | 迁移计划明确要求「左状态面板 / 中央地图 / 右弱网控制台」三栏布局，但实际实现为 **上下两段**（上：地图+侧栏 grid 5:2；下：Tabs），完全丧失了专业座舱仪表盘的空间利用率 |
| **底部 Tabs 堆砌** | `DashboardPage.tsx:70-127` | 整个「推理面板」和「操作面板」被塞进 antd `Tabs` 的两个 tab 里，导致：① 推理面板内所有卡片竖向单列排列，严重浪费横向空间；② 操作按钮被隐藏在第二个 tab 中，用户需要切换 tab 才能看到核心操作 |
| **MissionStagePanel 全部单列** | `MissionStagePanel/index.tsx` | 5 张数据卡（执行模式 / 板卡遥测 / 快照统计 / 推理进度 / 对比表）垂直排列，`flex-direction: column`，在 1280px 宽的桌面窗口中极度浪费空间 |
| **地图与遥测比例失调** | `FlightPanel/index.tsx` | 地图和遥测卡片用 `flex-direction: column` 堆叠，遥测卡片（6 个 Descriptions 项）无固定高度，在窗口变化时与地图抢空间 |
| **缺少全局导航** | `MissionShell.tsx` | 计划中有底部导航栏切换 Session/Current/Compare/Safety 四个子页面，当前实现只有一个 Dashboard 页面，Header 也只有标题和健康状态 |

### 问题 B — 设计 Token 混乱与冗余（严重）

| 问题 | 位置 | 说明 |
|---|---|---|
| **三套重复的 Token 系统** | `index.css` + `tokens.ts` + `main.tsx` | 同一套颜色值（如 `#7dd8f5`、`rgba(56,139,200,0.12)` 等）在三个地方各定义一遍：CSS 变量、TypeScript 对象、antd ConfigProvider。修改一处其他两处不会同步 |
| **inline style 泛滥** | 几乎所有组件 | `PanelCard` 的 `headStyle`/`bodyStyle`、`ToneTag` 和 `IOSTag` 的全部样式、每个卡片 title 的图标容器——全部通过内联 `style={}` 写死。无法复用、无法统一调整、无法响应主题切换 |
| **IOSTag / ToneTag 功能重复** | `ToneTag.tsx` + `IOSTag.tsx` | 两个组件做的事情完全一样（给 antd Tag 加语义色），只是 API 略有不同。整个代码库中两者混用，没有统一规范 |

### 问题 C — 字体与排版欠佳（中等）

| 问题 | 位置 | 说明 |
|---|---|---|
| **全局基础字号过小** | `main.tsx:43` | `fontSize: 12` 作为 antd 全局 token。对于桌面应用（非移动端），12px 正文字号过小，信息密度高但可读性差 |
| **字体加载依赖 CDN** | `index.html:12` | Inter / JetBrains Mono / Noto Sans SC 从 Google Fonts CDN 加载。Electron 是桌面应用，CSP 策略虽已放行 `fonts.googleapis.com`，但**离线环境下字体会 fallback 到系统默认字体，视觉效果不一致** |
| **排版层级扁平** | 全局 | 除 `text-display` 到 `text-caption` 定义了 6 级字号外，实际使用中所有卡片 title 都是 12px/600，所有正文都是 11px/400，**缺少明确的视觉层级** |
| **标题样式全靠内联** | 每个卡片组件 | 所有卡片标题都是 `<div style={{ display:'flex', alignItems:'center', gap:6 }}><Icon size={14} style={{color:'#7dd8f5'}}/><span>标题</span></div>` 这一段复制粘贴，写了 12 遍 |

### 问题 D — 控件质量与交互（中等）

| 问题 | 位置 | 说明 |
|---|---|---|
| **iOS 组件名不副实** | `ios/` 目录 | `IOSSwitch`、`IOSProgress`、`IOSTag` 名为 iOS 风格，但只是给 antd 原生组件加了几行内联样式，既不像 iOS，也不像座舱风格，与整体暗色主题**色调冲突**（如 `IOSProgress` 使用 `#007AFF` 等 iOS 蓝色系列，而主题强调色是 `#7dd8f5` / `#4090e0`） |
| **操作按钮缺乏层级** | `DashboardPage.tsx:92-122` | 探板、推理(current)、推理(baseline)、故障注入 4 个按钮平铺在一个 `flex-wrap` 行中，无分组、无视觉优先级区分。已有的 `ActionToolbar` 组件（有分隔线和分组逻辑）完全未被使用 |
| **动画组件全部闲置** | `animations/PageTransition.tsx` | 定义了 `PageTransition`、`StaggeredList`、`AnimatedListItem`、`ScaleIn`、`SlideFrom` 五个动画组件，**没有一个被实际使用**。页面切换无过渡，卡片加载无动效 |
| **ProComponents 基本未用** | `package.json` | 安装了 `@ant-design/pro-components`，但只用了 `ProCard`。`ProTable`、`StatisticCard`、`ProDescriptions` 等计划中应该使用的组件完全未出现 |
| **大量 `any` 类型** | 所有数据组件 | `system: any`、`snapshot: any`、`aircraft: any`——丧失了 TypeScript 的类型安全优势 |

### 问题 E — 视觉效果与细节（一般）

| 问题 | 位置 | 说明 |
|---|---|---|
| **Header 过于简陋** | `MissionShell.tsx` | 48px 高的 header 只有左侧标题 + 右侧时钟和健康标签。没有 logo/图标、没有导航 tab、没有系统级操作（设置/全屏/最小化） |
| **间距节奏单一** | `DashboardPage.module.css` | 所有 gap 几乎都是 8-10px，卡片、面板、区域之间缺乏呼吸感，信息密度高但显得拥挤 |
| **无视觉焦点** | 全局 | 所有 `PanelCard` 样式完全相同——同样的背景渐变、同样的边框、同样的阴影。没有「主要/次要」的视觉权重区分 |
| **Tailwind CSS 未安装** | `package.json` | 迁移计划推荐 Tailwind CSS 4 + Ant Design Token 方案，但 **package.json 中没有 tailwindcss 依赖**，项目中也没有 tailwind 配置文件 |
| **ScrollBar 只在部分区域生效** | `DashboardPage.module.css` | 自定义 scrollbar 样式只在 `.statusArea` 和 `.bottomSection` 上，其他可滚动区域仍是系统默认滚动条，不协调 |

---

## 一、总体重设计方向

### 1.1 设计理念调整

当前实现的问题根源是**把桌面应用当成了移动端卡片流来做**——所有信息纵向堆叠、字号偏小、控件偏紧凑。

应该转向 **「Mission Control Console」风格**：

- **空间利用率优先**：1280×800 的桌面窗口，应该用 grid 把信息铺满，而不是纵向滚动
- **一屏完整展示**：关键决策信息必须在一屏内全部可见，不需要切 tab 或滚动
- **数据密度与可读性平衡**：通过字号层级、色彩权重、间距节奏来引导视线
- **状态感知一目了然**：系统在线/离线、推理中/空闲、正常/告警——这些状态要通过颜色、动效立刻传达

### 1.2 设计参考

- SpaceX Mission Control 地面站界面
- Bloomberg Terminal 暗色数据面板
- Grafana Dashboard 多 panel 布局
- F-35 座舱 MFD（Multi-Function Display）

---

## 二、布局重构方案

### 2.1 新 Dashboard 布局

放弃当前的「上下两段 + Tabs」结构，改为**三列 + Header + 底部操作栏**一屏布局：

```
┌──────────────────────────────────────────────────────────────────┐
│  ● 飞腾弱网语义回传 · Cockpit    [Nav Tabs]    LINK OK  14:32:07│  ← 56px Header
├──────────┬──────────────────────────────────┬────────────────────┤
│          │                                  │                    │
│  链路导演 │    ┌──── 世界地图 ─────────┐     │   执行模式 ▪ 状态  │
│  状态卡片 │    │                       │     │                    │
│          │    │  Canvas 三层渲染       │     │   板卡遥测         │
│  安全面板 │    │  + 浮层信息           │     │   在线 ● ONLINE    │
│          │    │                       │     │   guard / fault    │
│  操作员   │    └───────────────────────┘     │                    │
│  引导     │                                  │   推理进度         │
│          │    ┌─ 快照统计 ─┐┌─ 对比表 ──┐   │   ████████ 72%     │
│  任务票   │    │ Payload   ││ Metric   │   │                    │
│  闸机     │    │ E2E       ││ Table    │   │   证据包快照        │
│          │    │ Gauge     ││          │   │   Gauge × 2        │
│  事件脊   │    └───────────┘└──────────┘   │                    │
├──────────┴──────────────────────────────────┴────────────────────┤
│ [探板] [▶ 推理 current] [推理 baseline] │ [故障注入 ▾] │ [收口]  │  ← 52px 操作栏
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 具体 Grid 规格

```css
.dashboard {
  display: grid;
  grid-template-columns: 260px 1fr 300px;
  grid-template-rows: 1fr auto;
  gap: 12px;
  height: calc(100vh - 56px);     /* 减去 header */
  padding: 12px;
}

.leftPanel   { grid-row: 1; grid-column: 1; overflow-y: auto; }
.centerArea  { grid-row: 1; grid-column: 2; display: grid; grid-template-rows: 3fr 2fr; gap: 12px; }
.rightPanel  { grid-row: 1; grid-column: 3; overflow-y: auto; }
.actionBar   { grid-row: 2; grid-column: 1 / -1; }  /* 横跨三列 */
```

### 2.3 各区域内容分配

| 区域 | 包含的卡片 | 说明 |
|---|---|---|
| **左面板 (260px)** | 链路导演 → 安全面板 → 操作员引导 → 任务票闸机 → 事件脊 | 当前的 SidebarPanel，纵向可滚动 |
| **中央上部 (flex)** | WorldMapStage（含遥测数据浮层） | 地图占据中央最大面积，遥测数据不再独立卡片，改为地图底部的 Overlay Bar |
| **中央下部 (flex)** | 快照统计（含 Gauge）+ 对比表 | 两个卡片横向并排 `grid-template-columns: 1fr 1fr` |
| **右面板 (300px)** | 执行模式 → 板卡遥测 → 推理进度 → 推理时间线 | 当前的 MissionStagePanel，纵向可滚动 |
| **底部操作栏 (52px)** | 已有的 `ActionToolbar` 组件 | **启用**当前闲置的 ActionToolbar，固定在底部 |

### 2.4 响应式策略

```css
/* 窄屏：左面板收起为图标导航 */
@media (max-width: 1200px) {
  .dashboard {
    grid-template-columns: 48px 1fr 280px;
  }
  .leftPanel { /* 折叠为图标栏，hover 展开 */ }
}

/* 更窄：右面板也收起 */
@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }
}
```

---

## 三、设计 Token 统一方案

### 3.1 消除三重定义，建立单一来源

**保留 `tokens.ts` 作为唯一真相源**，CSS 变量和 antd ConfigProvider 从它派生：

```typescript
// theme/tokens.ts — 唯一来源
export const T = { ... }  // 保持现有

// theme/cssVariables.ts — 新建，自动生成 CSS 变量注入
export function injectCSSVariables() {
  const root = document.documentElement.style
  root.setProperty('--color-bg-primary', T.bgPrimary)
  root.setProperty('--color-text-primary', T.textPrimary)
  // ... 自动映射所有 token
}

// theme/antdTheme.ts — 新建，从 T 派生 antd config
export const antdThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: T.accentBlue,
    colorBgLayout: T.bgPrimary,
    colorBgContainer: T.bgCard,
    colorText: T.textPrimary,
    // ... 所有值从 T 读取
  }
}
```

### 3.2 `index.css` 精简

删除 `index.css` 中所有的 `:root` CSS 变量定义和重复的颜色值。只保留：
- Reset 样式
- 动画 `@keyframes`（shimmer、status-pulse、icon-spin 等）
- 工具 class（`.skeleton`、`.font-mono` 等）
- 全局滚动条样式

颜色值全部改为 `var(--xxx)` 引用，由 `injectCSSVariables()` 注入。

---

## 四、字体方案重建

### 4.1 字体文件本地化

**Electron 是桌面应用，不应依赖 CDN。** 将字体文件下载到项目中：

```
src/renderer/src/assets/fonts/
├── Inter-Regular.woff2
├── Inter-Medium.woff2
├── Inter-SemiBold.woff2
├── Inter-Bold.woff2
├── JetBrainsMono-Regular.woff2
├── JetBrainsMono-Medium.woff2
├── JetBrainsMono-SemiBold.woff2
├── NotoSansSC-Regular.woff2
├── NotoSansSC-Medium.woff2
├── NotoSansSC-SemiBold.woff2
└── NotoSansSC-Bold.woff2
```

在 CSS 中用 `@font-face` 声明：

```css
@font-face {
  font-family: 'Inter';
  src: url('./assets/fonts/Inter-Regular.woff2') format('woff2');
  font-weight: 400;
  font-display: swap;
}
/* ... 其余字重 */
```

删除 `index.html` 中的 Google Fonts `<link>` 标签。

### 4.2 字号体系调整

桌面应用基础字号应从 12px 上调到 **13-14px**，重建层级：

| 级别 | 用途 | 字号 | 字重 | 行高 | 字体 |
|---|---|---|---|---|---|
| Display | 页面大标题 | 28px | 700 | 1.15 | Inter |
| H1 | 区域标题（面板名称） | 18px | 600 | 1.3 | Inter |
| H2 | 卡片标题 | 15px | 600 | 1.35 | Inter |
| H3 | 子标题 / Tag 文字 | 13px | 600 | 1.4 | Inter |
| Body | 正文 / 描述 | 14px | 400 | 1.6 | Inter / Noto Sans SC |
| Caption | 辅助说明 | 12px | 400 | 1.5 | Inter |
| Overline | 面板分区标签 | 11px | 600 | 1.5 | Inter, letter-spacing: 0.08em |
| Number | 数值数据 | 14-24px | 500-600 | 1.2 | JetBrains Mono |

**关键修改点：**
- `main.tsx` 中 antd `fontSize` 改为 `14`
- antd `Button.fontSize` 改为 `13`
- antd `Table.fontSize` 改为 `13`
- 所有卡片内正文从 `11px` 上调到 `13-14px`
- 所有卡片 title 从 `12px` 上调到 `15px`

---

## 五、组件质量提升

### 5.1 消除 inline style，改用 CSS Modules

**原则：** 所有可复用的视觉样式必须写在 `.module.css` 文件中，组件内 `style={}` 仅用于动态计算值（如 `width: ${percent}%`）。

**重点改造文件：**

| 组件 | 当前问题 | 改造方式 |
|---|---|---|
| `PanelCard.tsx` | `headStyle` / `bodyStyle` / `style` 全部内联 | 新建 `PanelCard.module.css`，通过 `className` 传递。提供 `variant` prop 支持 `default` / `highlight` / `glass` 三种视觉权重 |
| `ToneTag.tsx` | 纯内联样式 | 改为 CSS Module + `data-tone` 属性选择器 |
| `IOSTag.tsx` | 与 ToneTag 功能重复 | **删除**，统一使用 `ToneTag` |
| `IOSProgress.tsx` | iOS 色系与主题冲突 | **重写**为 `CockpitProgress`，使用主题色系渐变 |
| `IOSSwitch.tsx` | 简单包装无特色 | **重写**为 `CockpitSwitch`，增加座舱风格（如开关两侧有 ON/OFF 标签、开启时带辉光） |
| 12 个卡片组件的 title | 每个都复制粘贴 `<div style={{display:'flex'...}}>` | 统一由 `PanelCard` 的 `icon` prop 处理，title 传字符串即可 |

### 5.2 PanelCard 重构

当前 `PanelCard` 是最核心的复用组件，但缺乏视觉层级。重构方案：

```typescript
interface PanelCardProps {
  title: string
  icon?: React.ComponentType<{ size?: number }>  // lucide icon
  extra?: ReactNode
  children: ReactNode
  variant?: 'default' | 'highlight' | 'glass'    // 新增视觉权重
  size?: 'compact' | 'normal'                     // 新增尺寸
  collapsible?: boolean
  defaultCollapsed?: boolean
}
```

三种 variant 的视觉区别：
- `default`：当前的 card-premium 样式，用于一般信息卡
- `highlight`：左侧带 3px 强调色竖线，卡片微微发光，用于关键状态卡（如推理进度、安全面板）
- `glass`：毛玻璃效果 + 更高透明度，用于浮层/覆盖场景

### 5.3 统一标签组件

删除 `IOSTag`，保留并增强 `ToneTag`：

```typescript
interface ToneTagProps {
  tone: 'online' | 'success' | 'warning' | 'error' | 'neutral' | 'idle'
  children: ReactNode          // 允许自定义内容，不仅是 label 字符串
  size?: 'sm' | 'md'          // sm: 10px, md: 12px
  dot?: boolean                // 是否显示前面的状态圆点
  pulse?: boolean              // 是否闪烁（用于活跃状态）
}
```

### 5.4 安装并使用 Tailwind CSS

当前项目 `package.json` 中没有 Tailwind CSS。应该安装并配置：

```bash
npm install tailwindcss @tailwindcss/vite
```

在 `vite` renderer 配置中加入 Tailwind 插件。用 Tailwind 的 utility class 替换大量手写的 flex/grid 布局和间距样式，减少 CSS Module 的样式碎片化。

将 `tokens.ts` 中的颜色注册为 Tailwind 的 `theme.extend.colors`，实现 class 名即语义色：

```html
<span class="text-tone-online">ONLINE</span>
<div class="bg-card border-border-base rounded-md">...</div>
```

---

## 六、组件具体改造清单

### 6.1 Header 重构 — `MissionShell.tsx`

**目标：** 从简陋状态条升级为功能完整的顶部导航栏。

```
┌─●─飞腾弱网回传 Cockpit────[仪表盘│Session│对比│安全]────── LINK OK  14:32:07─┐
```

改造要点：
- 高度从 48px 增加到 **56px**
- 左侧增加项目 Logo 图标（可用 lucide 的 `Radar` 或 `Crosshair` 图标替代）
- 中央增加导航 Tab（Dashboard / Session / Comparison / Safety），为后续多页面做准备
- 右侧保留时钟和健康状态，增加全屏按钮
- 标题字号从 13px 增加到 **15px**

### 6.2 FlightPanel 重构 — 地图遥测一体化

**目标：** 遥测数据不再单独成卡片，改为地图底部的 Overlay Bar。

当前问题：`TelemetryCard` 作为独立卡片竖向排列 6 行 Descriptions，挤压地图高度。

改为：
```
┌──── 世界地图 Canvas ──────────────────────────────┐
│                                                    │
│           (三层 Canvas 渲染区域)                    │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ 源:sim │ 经纬:39.9,116.4 │ 航向:42.3° │ ...  │  │  ← 半透明 Overlay Bar
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

Overlay Bar 用 `position: absolute; bottom: 0;` 叠在地图上，半透明背景 + blur。数据用紧凑的 inline 展示（`key: value` 间隔排列），不占额外纵向空间。

### 6.3 ActionToolbar — 启用已有组件

当前 `ActionToolbar` 组件已经写好（分组+分隔线+ScaleOnHover），但 `DashboardPage` 没有使用它，而是自己在 Tabs 里放了一排裸 Button。

**直接启用 `ActionToolbar`**，固定在 Dashboard 底部作为 actionBar。

改造要点：
- 从 Tabs 中移出
- 改为全宽 bar 横跨三列
- 按钮增加文字说明 tooltip
- 「推理 (current)」按钮增大尺寸和视觉权重（加 glow / pulsing border）
- 危险操作（故障注入、SAFE_STOP 收口）用红色系，且加 Popconfirm 二次确认

### 6.4 中央下半部分 — 快照+对比并排

当前 `SnapshotStatsCard` 和 `ComparisonCard` 堆叠在 MissionStagePanel 的长列表中。将它们移到中央区域下半部分，横向并排：

```css
.centerBottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
```

- `SnapshotStatsCard`：保留 Statistic 数字 + PerformanceGauge 双表盘
- `ComparisonCard`：保留 Table，但改进样式——当前 antd Table 在暗色下辨识度低，应增加行交替色 + 数值高亮

### 6.5 右面板 — 纵向信息流

将执行模式、板卡遥测、推理进度、推理时间线（InferenceTimeline）放入右面板，纵向排列，可滚动。

改造要点：
- `ExecutionModeCard`：增加视觉权重，状态标签更大
- `BoardTelemetryCard`：遥测指标用 grid 布局代替 Descriptions（Descriptions 在窄面板中 label 和 content 容易换行错乱）
- `InferenceProgressCard`：进度条增加百分比数字叠加显示，阶段文字更突出
- `InferenceTimeline` 图表：固定高度 160px，轴标签字号从 10px 调到 12px

---

## 七、动效系统启用

当前 `animations/` 目录下有完整的动画组件但全部闲置。启用方案：

| 动画组件 | 应用场景 |
|---|---|
| `PageTransition` | 包裹 `DashboardPage` 根元素，首次加载有 fade-in |
| `StaggeredList` + `AnimatedListItem` | 左/右面板的卡片列表，依次交错进入 |
| `ScaleOnHover` | 所有 PanelCard 增加 hover 微缩放（已在 ActionToolbar 中使用） |
| `SlideFrom` | 侧面板折叠/展开动画 |
| `ScaleIn` | Modal / Drawer 打开动画 |

**新增动效：**
- 数值跳动（countUp）：关键 Statistic 数字变化时的过渡动画
- 状态变化 transition：PanelCard 的 `variant` 切换时背景色平滑过渡
- 推理进度 pulse：进度条在推理运行中增加 stripe 动画（当前 `progress-animated` class 已定义但未使用）

---

## 八、ECharts 图表改进

### 8.1 PerformanceGauge

当前问题：两个 Gauge 挤在 180px 高的容器中，指针细节不清楚。

改进：
- 高度增加到 200-220px
- 双 Gauge 之间增加中央分隔标签
- 指针颜色根据值动态变化（绿 → 黄 → 红）
- 增加「目标线」标记（如 1000ms 标准线）

### 8.2 InferenceTimeline

当前问题：只有一条折线 + 区域填充，数据点少时图表空旷。

改进：
- 增加 markLine 标注关键阈值
- 增加 markPoint 标注最大/最小值
- tooltip 增加与 baseline 的对比信息
- Y 轴增加 min/max 范围，避免单点时 Y 轴刻度不合理

---

## 九、类型安全修复

所有组件 props 中的 `any` 类型应该替换为 `api/types.ts` 中定义的正确类型：

```typescript
// 当前
interface SidebarPanelProps {
  system: any              // ← 
}

// 应该改为
import type { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatus } from '../../api/types'

interface SidebarPanelProps {
  system: UseQueryResult<SystemStatus>
}
```

对 `api/types.ts` 进行补全，从 Python `server.py` 的返回结构推导完整 TypeScript 类型定义。

---

## 十、文件变更清单（按优先级排序）

### P0 — 必须完成（解决布局崩坏）

| # | 文件 | 操作 | 说明 |
|---|---|---|---|
| 1 | `pages/DashboardPage.tsx` | **重写** | 三列 grid 布局 + 底部操作栏 |
| 2 | `pages/DashboardPage.module.css` | **重写** | 新 grid 系统 |
| 3 | `layouts/MissionShell.tsx` | **改写** | Header 升级：增加导航 tab、logo |
| 4 | `layouts/MissionShell.module.css` | **改写** | Header 56px + 增加导航样式 |
| 5 | `components/dashboard/FlightPanel/index.tsx` | **改写** | 遥测改为 Overlay Bar |
| 6 | `components/dashboard/FlightPanel/TelemetryCard.tsx` | **改写** → `TelemetryOverlay.tsx` | 从独立卡片改为浮层 |

### P1 — 重要改进（设计系统统一）

| # | 文件 | 操作 | 说明 |
|---|---|---|---|
| 7 | `theme/tokens.ts` | **保留**为唯一源 | 无需大改 |
| 8 | **新建** `theme/cssVariables.ts` | **新建** | 从 T 生成 CSS 变量 |
| 9 | **新建** `theme/antdTheme.ts` | **新建** | 从 T 派生 antd 配置 |
| 10 | `index.css` | **精简** | 删除重复的颜色定义 |
| 11 | `main.tsx` | **改写** | ConfigProvider 从 antdTheme.ts 导入，字号调整 |
| 12 | `index.html` | **改写** | 删除 Google Fonts link，字体本地化 |
| 13 | **新建** `assets/fonts/*.woff2` | **新建** | 下载字体文件 |
| 14 | **新建** `styles/fonts.css` | **新建** | @font-face 声明 |

### P2 — 质量提升（组件重构）

| # | 文件 | 操作 | 说明 |
|---|---|---|---|
| 15 | `components/shared/PanelCard.tsx` | **重构** | 新增 `icon` / `variant` / `size` prop，消除内联样式 |
| 16 | **新建** `components/shared/PanelCard.module.css` | **新建** | PanelCard 样式外部化 |
| 17 | `components/shared/ToneTag.tsx` | **增强** | 新增 `dot` / `pulse` / `size` / `children` |
| 18 | `components/ios/IOSTag.tsx` | **删除** | 统一用 ToneTag |
| 19 | `components/ios/IOSProgress.tsx` | **重写** → `CockpitProgress.tsx` | 使用主题色系 |
| 20 | `components/ios/IOSSwitch.tsx` | **重写** → `CockpitSwitch.tsx` | 座舱风格开关 |
| 21 | 12 个卡片组件 | **改写 title 部分** | 统一由 PanelCard icon prop 处理 |

### P3 — 锦上添花（动效 / 类型安全）

| # | 文件 | 操作 | 说明 |
|---|---|---|---|
| 22 | `pages/DashboardPage.tsx` | **增加动效** | PageTransition 包裹 + StaggeredList |
| 23 | 所有 `interface XXXProps { system: any }` | **修复类型** | 替换为正确的 TS 类型 |
| 24 | `api/types.ts` | **补全** | 完整的 API 响应类型定义 |
| 25 | `package.json` | **增加依赖** | `tailwindcss`、`@tailwindcss/vite` |
| 26 | **新建** Tailwind 配置 | **新建** | theme.extend 注册 tokens |

---

## 十一、视觉规范快速参考

### 颜色权重

| 用途 | 颜色 | 说明 |
|---|---|---|
| 主背景 | `#050b14` | 最深色，全局底色 |
| 卡片背景 | `rgba(8,18,32,0.92)` | 微透明，与底色有区分 |
| 高亮卡片 | `rgba(12,26,44,0.95)` + 左侧强调线 | 关键信息卡 |
| 主强调 | `#4090e0` → `#7dd8f5` | 按钮、链接、活跃状态 |
| 正常 / 在线 | `#40c870` | 绿色系 |
| 告警 / 降级 | `#f0a840` | 琥珀色系 |
| 错误 / 离线 | `#f06050` | 红色系 |
| 正文 | `#e8f4ff` / `#7a9bb8` | 主/次文字 |
| 标签 | `#5a7d99` | 低权重描述文字 |

### 间距节奏

| 级别 | 值 | 用途 |
|---|---|---|
| xs | 4px | 紧凑元素间（icon 与文字） |
| sm | 8px | 同一卡片内小元素间 |
| md | 12px | 卡片内区块间 / 三列 grid gap |
| lg | 16px | 面板内 padding |
| xl | 24px | 区域间的大间距 |

### 圆角

| 级别 | 值 | 用途 |
|---|---|---|
| sm | 6px | Tag / Badge / 小按钮 |
| md | 10px | 卡片 / 输入框 |
| lg | 14px | 面板 / 浮层 |
| full | 9999px | 圆形 Tag / 状态点 |

---

## 十二、执行建议

### 建议执行顺序

1. **先做 P0 布局重构**（1 天）：把 DashboardPage 改成三列，把 ActionToolbar 接上，遥测改 Overlay。这一步完成后整体观感会有质的飞跃
2. **再做 P1 设计系统**（0.5 天）：Token 统一 + 字体本地化 + 字号调整。这一步让所有文字和颜色变得专业
3. **然后做 P2 组件**（1-2 天）：PanelCard 重构 + 消灭 IOSTag + 进度条重写。这一步让细节经得起推敲
4. **最后做 P3 锦上添花**（0.5-1 天）：动效 + 类型安全 + Tailwind

### 注意事项

- **不要改 Python 后端**：所有改动限于 `cockpit_desktop/src/renderer/` 下的前端代码
- **不要改 WorldMapStage 渲染逻辑**：地图 Canvas 绘制代码质量尚可，只需要调整它在布局中的位置和尺寸
- **不要改 hooks / stores / api**：数据层代码结构合理，只需改 UI 层
- **先在 1280×800 窗口下调好**：这是 `electron/main.ts` 中定义的默认窗口尺寸
- **保持一屏展示**：Dashboard 页面不应该出现纵向滚动条（左右面板内部可以滚动）
