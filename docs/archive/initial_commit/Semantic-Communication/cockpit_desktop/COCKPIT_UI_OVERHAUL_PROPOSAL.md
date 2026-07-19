# Cockpit Desktop UI 全面改造方案

> **日期**: 2026-03-31  
> **版本**: v1.0  
> **定位**: 从"深黑科技风"走向"温润科技精品"——一份从主题、布局到交互的系统级改造方案

---

## 一、现状诊断：当前 Demo 到底差在哪

### 1.1 主题问题——"太重"的深黑

当前主题 `tokens.ts` 完整照搬了 **Google Cloud Console Dark** 的配色逻辑：

| 问题 | 具体表现 |
|------|---------|
| 背景过深 | `bgPrimary: #0f1117`，几乎纯黑，压迫感强 |
| 对比度断裂 | 卡片 `#1a1d26` 与背景 `#0f1117` 色差仅 ΔE≈4，层级模糊 |
| 蓝光主导 | 所有强调色集中在 `#60a5fa` 冷蓝色系，观感冰冷单调 |
| 装饰过度 | glass 效果、glow 发光、多层阴影叠加，显得繁杂 |
| 中文排版粗糙 | Noto Sans SC 与 Inter 的行高/字重配比未做精调，中英混排不和谐 |

### 1.2 布局问题——信息密度失衡

```
当前结构：
┌──────────────── Header (56px) ──────────────────┐
├─────── Hero Metrics (25vh，很大却信息稀疏) ──────┤
├──── Left Panel (1fr) ──┬──── Right Panel (1fr) ──┤
│ MinimalStatusPanel     │ FlightPanel（地图）      │
│ Success/Error Card     │ ActionSection（按钮墙）  │
│ ProgressCard           │                          │
│ PasswordCard           │                          │
└────────────────────────┴──────────────────────────┘
```

**核心痛点**：
1. **Hero 区占了 25vh 但只有 2 个数字**——空间浪费严重
2. **左栏是松散的卡片堆叠**——ProgressCard、PasswordCard、StatusPanel 毫无视觉关联
3. **右栏地图太大、按钮区太密**——地图在 demo 中并非高频查看，却占了最大面积；操作按钮 8 个挤成 2 列网格，没有主次之分
4. **缺少全局节奏**——从 Hero 到 Content 没有呼吸感，所有信息同等权重平铺

### 1.3 交互问题

- 页面切换无过渡感（虽有 `PageTransition` 但效果微弱）
- 按钮状态反馈不足（仅 opacity 变化，缺少 loading spinner）
- 卡片没有层级动画（hover 仅微调阴影，缺乏引导性）
- 无空状态 / 成功状态的精致设计（`successCard` 和 `errorCard` 只是简单的 flex 行）

---

## 二、设计理念：我们要走向什么风格

### 2.1 为什么不要纯白，也不要深黑？

| 风格 | 问题 |
|------|------|
| **纯白 (#FFFFFF)** | 长时间注视刺眼，在 demo 演示环境（投影/大屏）下反光严重，且显得过于"办公软件" |
| **深黑 (#0f1117)** | 压迫感强，层级难以区分，在明亮环境下屏幕像"黑洞"，不适合展示类场景 |

### 2.2 目标风格：**Warm Neutral Tonal（温润中性色调）**

借鉴三个顶级参考：

#### 参考 1: Google Material Design 3 Expressive (2025–2026)
- **核心思想**：从"严格色板"走向"情感驱动 UX"
- **我们借鉴**：Tonal Palette（色调梯度系统）——不是 grey 而是带温度的 warm stone 色系
- **关键特征**：动态圆角（不同组件不同曲率）、35 种形状 token、波浪进度条

#### 参考 2: 腾讯 TDesign (2026 最新版)
- **核心思想**：跨端一致、模块化、暗色模式不等于冷色模式
- **我们借鉴**：Dashboard Starter 的信息层级处理——清晰的 Section > Card > Item 三层结构
- **关键特征**：8px 网格系统、4 级阴影梯度、组件圆角统一收敛

#### 参考 3: 2026 年 SaaS Dashboard 设计趋势
- **核心共识**：Warm Neutrals（暖中性色）正在取代 Cool Greys，研究表明暖中性色在"舒适感"测试中比冷灰高 **34%**
- **我们借鉴**：用 Sand / Stone / Clay 色系替代传统灰色

### 2.3 设计关键词

```
温润 · 克制 · 呼吸感 · 专业不冰冷 · 科技不压迫
```

---

## 三、主题系统改造（tokens.ts 重构）

### 3.1 色板对比：旧 → 新

#### 背景系统

```
                    旧 (Cold Dark)         新 (Warm Neutral)
                    ─────────────          ─────────────────
页面背景              #0f1117               #F7F5F2
                    (近纯黑)               (暖米白，带微黄调)

卡片背景              #1a1d26               #FFFFFF
                    (深蓝灰)               (纯白，靠阴影分层)

次级面                #161921               #F0EDE8
                    (比背景稍亮)            (暖石灰，用于 section 分区)

Header               #161921               #FAFAF7
                    (深灰)                 (接近纯白但带暖调)
```

#### 文字系统

```
                    旧                      新
                    ─────                   ─────
主文字                #e8eaed               #1A1A1A
                    (冷白)                 (暖黑，非纯黑)

次文字                #9aa0a6               #6B6560
                    (冷灰)                 (暖石色)

标签/辅助              #80868b               #9C9590
                    (冷灰)                 (暖灰棕)

高亮                  #8ab4f8               #2563EB
                    (淡蓝)                 (深蓝，暖底色上更醒目)
```

#### 强调色系

```
                    旧                      新
                    ─────                   ─────
主强调色              #60a5fa (冷蓝400)      #2563EB (蓝700，沉稳饱和)
主强调容器            #1e3a5f               #EFF6FF (蓝色浅底)

成功色                #34d399 (翡翠绿)       #059669 (绿色，暖底上更和谐)
成功容器              #064e3b               #ECFDF5

警告色                #fbbf24 (亮琥珀)       #D97706 (深琥珀)
警告容器              —                     #FFFBEB

错误色                #f87171 (红400)        #DC2626 (红600)
错误容器              #5c1d1d               #FEF2F2
```

#### 边框 & 阴影

```
旧：靠边框线分层 → border: 1px solid #2d3139
新：靠阴影分层   → box-shadow 为主，边框极少使用

新阴影体系（暖色投影，非纯黑）:
  elevation-0: none
  elevation-1: 0 1px 3px rgba(140,130,115,0.08), 0 1px 2px rgba(140,130,115,0.04)
  elevation-2: 0 4px 12px rgba(140,130,115,0.10), 0 2px 4px rgba(140,130,115,0.06)
  elevation-3: 0 12px 32px rgba(140,130,115,0.12), 0 4px 8px rgba(140,130,115,0.08)
```

### 3.2 新 tokens.ts 核心结构

```typescript
export const T = {
  // ── 背景 ──
  bgPrimary:     '#F7F5F2',   // 页面底色：暖米白
  bgCard:        '#FFFFFF',   // 卡片：纯白，靠阴影浮起
  bgCardHover:   '#FAFAF7',   // 卡片 hover
  bgHeader:      '#FAFAF7',   // Header
  bgSection:     '#F0EDE8',   // 分区底色（暖石灰）
  bgOverlay:     'rgba(26,24,20,0.4)', // 遮罩层

  // ── 边框（极少使用）──
  borderBase:    '#E8E4DE',   // 仅在需要明确分隔时使用
  borderLight:   '#F0EDE8',   // 微弱分隔
  borderAccent:  '#2563EB',   // 蓝色强调线

  // ── 文字 ──
  textPrimary:   '#1A1A1A',   // 主文字：暖黑
  textSecondary: '#6B6560',   // 次文字：暖石色
  textLabel:     '#9C9590',   // 标签：暖灰棕
  textAccent:    '#2563EB',   // 链接/强调
  textMuted:     '#C4BEB8',   // 禁用态

  // ── 语义色 ──
  toneOnline:    '#059669',
  toneWarning:   '#D97706',
  toneError:     '#DC2626',
  toneSuccess:   '#059669',

  // ── 强调色（Tonal Palette）──
  accentBlue:    '#2563EB',
  accentCyan:    '#0891B2',
  accentIndigo:  '#7C3AED',
  accentTeal:    '#0D9488',

  // ── 圆角（Material 3 Expressive 风格，不同层级不同曲率）──
  radiusSm:    8,    // 小组件：Tag, Badge
  radiusMd:    12,   // 中组件：Button, Input
  radiusLg:    16,   // 大组件：Card
  radiusXl:    24,   // 超大组件：Modal, 地图容器
  radiusFull:  9999, // 圆形

  // ── 阴影（暖色调阴影）──
  elevation1: '0 1px 3px rgba(140,130,115,0.08), 0 1px 2px rgba(140,130,115,0.04)',
  elevation2: '0 4px 12px rgba(140,130,115,0.10), 0 2px 4px rgba(140,130,115,0.06)',
  elevation3: '0 12px 32px rgba(140,130,115,0.12), 0 4px 8px rgba(140,130,115,0.08)',

  // ── 间距 (8px 基准) ──
  gapXs: 4, gapSm: 8, gapMd: 16, gapLg: 24, gapXl: 32, gap2xl: 48,
}
```

### 3.3 排版系统升级

```
当前问题：
  - Inter + Noto Sans SC 的行高不匹配
  - 中文 14px 偏小，英文 14px 正好 → 混排不协调
  - 数字字体（JetBrains Mono）与正文反差太大

改造方案：
  主字体栈:   'Inter Variable', 'Noto Sans SC', system-ui, sans-serif
  数字字体:   'Geist Mono', 'JetBrains Mono', monospace  (Geist 更柔和)
  
  中英混排行高规则:
    Body (14px):  line-height: 1.7  (24px，给中文留空间)
    Title (20px): line-height: 1.5  (30px)
    Hero (32px):  line-height: 1.3  (42px)
    
  字重简化（只用 3 档，减少视觉噪音）:
    Regular (400):  正文、次要信息
    Medium (500):   标题、标签
    Semibold (600): Hero 数字、重要操作
```

---

## 四、布局架构改造

### 4.1 现有布局的问题

```
当前：
┌─────────── Header 56px ───────────┐
├─── Hero (25vh，数字展示) ──────────┤   ← 过高，信息稀疏
├── Left 1fr ─┬── Right 1fr ────────┤
│ 松散卡片堆叠 │ 地图(巨大)+按钮(密集) │  ← 左右失衡
└──────────────┴────────────────────┘
```

### 4.2 新布局方案：**三段式 + 黄金比例分栏**

```
新方案：
┌──────────────── Header 52px ─────────────────────┐
│ Logo · 标题   [仪表盘] [Session]   ●在线  12:30  │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─ 状态概览条 (Metrics Bar) ─────────────────┐  │
│  │  🟢 系统在线    ⚡ ARMED    ⏱ 130.2ms     │  │  ← 一行式关键指标
│  │  📊 PSNR 32.5dB   🔄 0/300   📡 弱网正常   │  │     (替代 25vh Hero)
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌─ Primary (62%) ───┬── Secondary (38%) ────┐  │
│  │                    │                       │  │
│  │   Progress         │    World Map          │  │  ← 左主右辅
│  │   Section          │    (带遥测叠加)        │  │     黄金比例分栏
│  │   ─────────        │                       │  │
│  │   Action           │    ─────────          │  │
│  │   Section          │    Quick Actions      │  │
│  │   ─────────        │    (折叠式)            │  │
│  │   Board Access     │                       │  │
│  │                    │                       │  │
│  └────────────────────┴───────────────────────┘  │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 4.3 各区域详细设计

#### A. Header (52px)

**改造重点**：更轻、更透气

```
旧：56px 高度 · 深灰背景 · 1px 实线底边 · 紧凑布局
新：52px 高度 · 暖白背景 · 无底边(靠阴影分层) · 宽松布局

具体改动：
  - 背景: #FAFAF7，无 border-bottom，改用 elevation-1 底部投影
  - Logo 图标: 从 Radar 改为更精致的自定义 SVG 或保留但用 #2563EB 色
  - 标题字号: 14px → 15px，font-weight: 500
  - Nav Tabs: 
      旧 → 圆角胶囊按钮 (border-radius: 9999px, 蓝色容器背景)
      新 → 底部指示线风格 (Google 风格下划线 tab，更轻盈)
           active 状态: 2px 蓝色底线 + 文字变色，无背景色
  - 右侧状态:
      旧 → 带边框的健康指示器 + 带边框的时钟 + 带边框的全屏按钮
      新 → 去掉所有边框容器，状态点+文字即可，时钟直接显示
  - 全屏按钮: 44px → 36px，去掉边框，hover 时显示浅灰圆形背景
```

#### B. Metrics Bar (状态概览条)

**替代旧的 25vh Hero 区**——用一行高密度展示替代大面积留白

```
设计：
  - 高度: 固定 64px（而非 25vh）
  - 背景: #FFFFFF，elevation-1 阴影
  - 布局: 水平 flex，均匀分布 5-6 个 Metric Item
  - 每个 Metric Item:
      ┌──────────────┐
      │ 标签   值     │    ← 标签左对齐，值右对齐，同一行
      │ Payload  130.2ms │    
      └──────────────┘
      或者更紧凑：
      标签（灰色小字）
      值（大字 + 单位小字）

  - 指标项之间用 1px 竖线分隔 (border-right: 1px solid #F0EDE8)
  - 核心指标（Payload）用主强调色 #2563EB 显示数值
  - 次要指标用默认文字色

Metric Items:
  1. 系统状态:  ●在线 / ●离线（绿/红点 + 文字）
  2. Guard State: ARMED / SAFE_STOP（带 Badge 色）
  3. Current Payload: 130.2 ms（蓝色高亮）
  4. Baseline: 1846.9 ms
  5. 加速比: 93.0% faster（成功色 Badge）
  6. 推理进度: 0 / 300（如果正在运行）
```

**为什么这样做**：
- 旧 Hero 区 25vh 只放了 2 个大数字 → 浪费了 ≈200px 高度
- Metrics Bar 仅 64px，同时展示 6 项关键信息
- 节省的空间给到下方核心操作区，让地图和进度条都能更从容

#### C. Primary Panel (左侧 62%)

**三个逻辑分区，用 Section 标题分隔，不用独立卡片包裹**

```
Section 1: 推理进度
  ┌───────────────────────────────────────┐
  │  Current 重建进度          [运行中]    │  ← 标题行 + 状态 Badge
  │                                       │
  │  ████████████░░░░░░░░░░  45 / 300    │  ← 进度条 + 计数
  │                                       │
  │  当前阶段: tvm_compile                │  ← 阶段信息
  │  预计剩余: ~8 分钟                     │  ← 估算（如有）
  └───────────────────────────────────────┘

  设计：
    - 白色卡片，elevation-1，radius-lg (16px)
    - 进度条: 6px 高，圆角，主蓝色填充，灰色轨道
    - 运行中 Badge: 小圆点脉冲动画 + "运行中" 文字
    - 内间距: 24px


Section 2: 执行操作
  ┌───────────────────────────────────────┐
  │  执行操作                              │
  │                                       │
  │  ┌─────────────────────────────────┐  │
  │  │  ▶  启动 Current 重建（300张图）  │  │  ← 主操作：全宽大按钮
  │  └─────────────────────────────────┘  │
  │                                       │
  │  ┌──────────┐ ┌──────────┐ ┌──────┐  │
  │  │ 探测板卡  │ │票据预检   │ │PyTorch│  │  ← 次要操作：3 列等宽
  │  └──────────┘ └──────────┘ └──────┘  │
  │                                       │
  │  ▸ 故障注入与恢复                 [展开]│  ← 折叠区域（默认收起）
  │    ┌────────┐ ┌────────┐ ┌────────┐   │
  │    │错误SHA  │ │心跳超时  │ │非法参数 │   │
  │    └────────┘ └────────┘ └────────┘   │
  │    ┌─────────────────────────────┐    │
  │    │  SAFE_STOP 收口               │    │
  │    └─────────────────────────────┘    │
  └───────────────────────────────────────┘

  设计：
    - 主操作按钮: 全宽，48px 高，#2563EB 实底，白色文字，elevation-1
    - 次要操作: 透明底 + border，hover 时显示浅蓝背景
    - 故障注入区域: 默认折叠，用 Disclosure/Collapse 组件
      → 避免 8 个按钮同时露出导致视觉负担
    - 危险操作: 红色文字 + 红色边框（而非红色背景），降低视觉攻击性


Section 3: 板卡密码
  ┌───────────────────────────────────────┐
  │  板卡连接设置                          │
  │                                       │
  │  [密码输入框...................] [保存]  │
  └───────────────────────────────────────┘

  设计：
    - 最简形式，一行搞定
    - Input: 40px 高，暖灰背景 #F7F5F2，无边框（focus 时出现蓝色底线）
    - Button: 与 Input 等高，蓝色实底
```

#### D. Secondary Panel (右侧 38%)

```
Section 1: 世界地图 (占右栏 ~70% 高度)
  ┌───────────────────────────┐
  │                           │
  │        World Map          │  ← 圆角容器，overflow: hidden
  │        (Canvas)           │
  │                           │
  │  ┌─遥测数据叠加─────────┐  │
  │  │ 源:GPS  经纬:39.9,116.4│  ← 底部半透明条
  │  │ 航向:45.2° 高度:500m │  │
  │  └───────────────────────┘  │
  │              [中国战区 ◉]   │  ← 右上角开关
  └───────────────────────────┘

  地图主题改造：
    旧: 深黑海洋 + 深灰陆地 (太暗)
    新: 暖米色海洋 #F0EDE8 + 浅石色陆地 #E2DDD5 + 蓝色航迹
    → 与整体暖色调一致

Section 2: 系统详情 (占右栏 ~30% 高度)
  ┌───────────────────────────┐
  │  系统详情                  │
  │                           │
  │  Connection   ● Online    │
  │  Guard State  ARMED       │
  │  Last Fault   None        │
  │  Target       phytium     │
  └───────────────────────────┘

  设计：
    - 紧凑的 key-value 列表，不用 2x2 网格
    - 改为垂直列表，每行: 标签(左) + 值(右)
    - 标签用 #9C9590 小字，值用 #1A1A1A 正文
```

### 4.4 响应式策略

```
≥ 1440px:  左 62% + 右 38%，Metrics Bar 6 项一行
1200-1440: 左 55% + 右 45%，Metrics Bar 6 项一行（缩小间距）
900-1200:  单栏，地图移到顶部，Metrics Bar 换行为 2 行×3 列
< 900:     移动布局，Metrics Bar 变为垂直堆叠
```

---

## 五、组件级改造清单

### 5.1 MissionShell（Header + Layout Shell）

| 改动项 | 旧 | 新 |
|--------|-----|-----|
| 高度 | 56px | 52px |
| 背景 | `#161921` + `border-bottom` | `#FAFAF7` + `elevation-1` 阴影 |
| Nav Tabs | 胶囊按钮 (pill) | 底部指示线 (underline tab) |
| 状态指示器 | 带边框卡片包裹 | 裸露的点+文字 |
| 系统时钟 | 带边框容器 | 无边框，直接显示 |
| 全屏按钮 | 44px 带边框正方形 | 36px 无边框圆角，hover 显示灰底 |

### 5.2 HeroMetrics → MetricsBar

| 改动项 | 旧 | 新 |
|--------|-----|-----|
| 定位 | 独立区域，25vh | 嵌入式条，64px 固定 |
| 布局 | 居中大数字 + 分隔线 + Badge | 横向均匀分布的 Metric Items |
| 数字大小 | 32px / 24px | 24px / 20px（因为同行展示更多信息） |
| 信息密度 | 2 组数字 + 3 项次要 | 6 项同级展示 |
| 背景 | 与页面同色 | 白色卡片 + 阴影浮起 |

### 5.3 DashboardPageMinimal → DashboardPage（重构）

| 改动项 | 旧 | 新 |
|--------|-----|-----|
| 布局 | `1fr 1fr` 等分双栏 | `62% 38%` 黄金比例 |
| 卡片间距 | `gap: 24px` | `gap: 20px`（更紧凑但更有节奏） |
| 进度卡 | 独立卡片，满填充 | Section 式，白底卡片 |
| 操作区 | 平铺 8 个按钮 | 主操作突出 + 次要操作分组 + 危险操作折叠 |
| 密码区 | 独立大卡片 | 紧凑一行式 |
| 成功/错误提示 | 内嵌卡片 | 顶部 Toast 通知（3 秒自动消失） |

### 5.4 MinimalStatusPanel → SystemDetailList

| 改动项 | 旧 | 新 |
|--------|-----|-----|
| 位置 | 左栏第一项 | 右栏底部（地图下方） |
| 布局 | 2×2 网格 + 带背景的 statusItem | 垂直 key-value 列表 |
| 包含内容 | Status + Job + Quick Actions | 仅 Status（Job 和 Actions 已在其他区域） |
| Quick Actions | 此处重复 | 移除（合并到左栏 Action Section） |

### 5.5 FlightPanel（地图面板）

| 改动项 | 旧 | 新 |
|--------|-----|-----|
| 占比 | 右栏 ~75% 高度 | 右栏 ~65% 高度 |
| 圆角 | `radius-lg (16px)` | `radius-xl (24px)`（更 expressive） |
| 地图配色 | 深黑海洋 + 深灰陆地 | 暖米海洋 + 浅石陆地 |
| 遥测条 | `glass-intense` 毛玻璃 | 半透明白底 `rgba(255,255,255,0.85)` |
| 控件 | iOS 风格 Switch | 简洁 Toggle，暖色调 |

### 5.6 按钮系统重构

```
旧的按钮层级（4 种，区分不清晰）：
  primaryAction   → #60a5fa 实底
  secondaryAction → 透明 + border
  dangerAction    → 透明 + 红色 border
  recoverAction   → #1a1d26 暗底

新的按钮层级（3 种，清晰分明）：

  ┌───────────────────────────────────────────┐
  │  Filled (实底)                             │
  │  用途: 页面唯一主操作                       │
  │  样式: #2563EB 底，白色文字，elevation-1    │
  │  Hover: #1D4ED8，elevation-2               │
  │  圆角: 12px                                │
  │  高度: 48px（主操作）/ 40px（标准）          │
  ├───────────────────────────────────────────┤
  │  Tonal (色调)                              │
  │  用途: 次要操作                             │
  │  样式: #EFF6FF 底 (蓝色浅底)，#2563EB 文字  │
  │  Hover: #DBEAFE 底                         │
  │  圆角: 12px                                │
  │  高度: 40px                                │
  ├───────────────────────────────────────────┤
  │  Outlined (描边)                            │
  │  用途: 危险操作 / 可选操作                   │
  │  样式: 透明底，#E8E4DE 边框，#6B6560 文字    │
  │  危险变体: #DC2626 文字，#FEF2F2 hover 底   │
  │  圆角: 12px                                │
  │  高度: 40px                                │
  └───────────────────────────────────────────┘
```

### 5.7 卡片系统重构

```
旧：所有卡片靠 border + 微弱阴影 → 层级模糊
新：用阴影梯度建立层级，极少用 border

  Level 0 (背景面):  #F7F5F2，无阴影
  Level 1 (内容卡片): #FFFFFF，elevation-1
  Level 2 (浮动面板): #FFFFFF，elevation-2
  Level 3 (弹窗/抽屉): #FFFFFF，elevation-3

卡片间距规则（8px 网格）：
  - 卡片内 padding: 24px
  - 卡片间 gap: 20px
  - 区域间 gap: 32px
```

---

## 六、交互与动效改造

### 6.1 微交互升级

| 场景 | 旧 | 新 |
|------|-----|-----|
| 卡片 hover | `box-shadow` 微调 | `translateY(-1px)` + elevation 提升 + 200ms ease |
| 按钮点击 | 无反馈 | `scale(0.98)` 按压 + 释放弹回，100ms |
| 按钮 loading | `opacity: 0.38` | Spinner 图标替换原图标 + 文字变"处理中..." |
| 进度条更新 | 直接跳变 | `width` 过渡 500ms + 填充色脉冲发光效果 |
| 状态切换 | 无 | 状态点的颜色渐变 + 文字淡入淡出 |
| Toast 通知 | 内嵌卡片 | 右上角弹出，slideIn + fadeOut，3s 自动消失 |

### 6.2 页面过渡

```
当前：framer-motion PageTransition，但效果不明显

改造：
  - 整页切换: opacity 0→1 + translateY(8px→0)，duration 300ms
  - 卡片入场: staggerChildren 50ms，每张卡片 opacity+translateY
  - Metrics Bar: 数字 countUp 动画（从 0 滚动到实际值）
```

### 6.3 空状态设计

```
当前：显示 "等待数据" 文字
改造：精致空状态插画 + 引导文案

  ┌─────────────────────────┐
  │                         │
  │      ◇ (线条图标)       │
  │                         │
  │    暂无推理数据          │
  │    点击"启动重建"       │
  │    开始首次推理          │
  │                         │
  └─────────────────────────┘
```

---

## 七、地图主题改造（WorldMapStage/theme.ts）

### 7.1 配色对比

```typescript
// 旧 (深黑)
oceanTop: '#0a0d14',
oceanBottom: '#0f1219',
landFill: '#1e2430',
coastline: '#3a4255',

// 新 (暖中性)
oceanTop: '#F0EDE8',      // 暖灰
oceanBottom: '#E8E4DE',    // 稍深暖灰
landFill: '#E2DDD5',       // 浅石色
landFillBright: '#D9D3CA', // 高亮地块
coastline: '#C4BEB8',      // 暖灰棕海岸线
gridMajor: 'rgba(37,99,235,0.08)',  // 蓝色经纬线（微弱）
trackLine: '#2563EB',      // 航迹蓝色（不变）
statusOnline: '#059669',
statusOffline: '#DC2626',
```

### 7.2 航迹样式

```
旧: 发光蓝线 + 大面积 beam/haze 效果 → 花哨
新: 2px 实线蓝色 + 末端渐隐 → 干净
    当前位置: 8px 蓝色实心圆 + 2px 白色描边
    历史轨迹: 蓝色渐变透明度（越旧越淡）
```

---

## 八、Ant Design 主题适配（antdTheme.ts）

```typescript
export const antdThemeConfig = {
  algorithm: theme.defaultAlgorithm,  // 从 darkAlgorithm → defaultAlgorithm
  token: {
    colorPrimary: '#2563EB',
    colorInfo: '#2563EB',
    colorWarning: '#D97706',
    colorError: '#DC2626',
    colorSuccess: '#059669',
    colorBgLayout: '#F7F5F2',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBorder: '#E8E4DE',
    colorBorderSecondary: '#F0EDE8',
    colorText: '#1A1A1A',
    colorTextSecondary: '#6B6560',
    colorTextTertiary: '#9C9590',
    borderRadius: 12,
    fontFamily: "'Inter Variable', 'Noto Sans SC', system-ui, sans-serif",
    fontSize: 14,
    lineHeight: 1.7,
  },
  components: {
    Button: { borderRadius: 12, controlHeight: 40 },
    Progress: { remainingColor: '#F0EDE8' },
    Tag: { borderRadiusSM: 6 },
  },
}
```

---

## 九、ECharts 主题适配

```
关键改动：
  - 背景: transparent（继承卡片白色）
  - 文字: #6B6560（暖石色）
  - 分割线: #F0EDE8（极淡暖灰）
  - Tooltip: 白底 + elevation-2 阴影 + 12px 圆角
  - 配色序列: ['#2563EB', '#7C3AED', '#059669', '#D97706', '#DC2626', '#0891B2']
```

---

## 十、CSS 全局变量改造（index.css）

### 10.1 滚动条

```css
/* 旧：白色半透明滚动条（暗色主题）*/
/* 新：暖灰色滚动条 */
*::-webkit-scrollbar-thumb { background: rgba(156,149,144,0.3); }
*::-webkit-scrollbar-thumb:hover { background: rgba(156,149,144,0.5); }
```

### 10.2 选区

```css
/* 旧：蓝色半透明选区 */
/* 新：暖蓝选区 */
::selection {
  background: rgba(37,99,235,0.15);
  color: #1A1A1A;
}
```

### 10.3 Skeleton 加载态

```css
/* 旧：白色闪烁（深色背景上的白条纹）*/
/* 新：暖灰色闪烁 */
.skeleton {
  background: linear-gradient(90deg, #F0EDE8 0%, #E8E4DE 50%, #F0EDE8 100%);
  background-size: 400px 100%;
  animation: shimmer 2s infinite linear;
}
```

---

## 十一、实施路线图

### Phase 1: 主题层（预计 2-3 小时）
- [ ] 重写 `tokens.ts`（新色板、间距、阴影）
- [ ] 重写 `cssVariables.ts`（注入新 CSS 变量）
- [ ] 重写 `antdTheme.ts`（切换到 defaultAlgorithm）
- [ ] 重写 `echarts-theme.ts`（适配暖色调）
- [ ] 更新 `index.css`（全局样式适配）
- [ ] 更新 `WorldMapStage/theme.ts`（地图暖色调）

### Phase 2: 布局层（预计 3-4 小时）
- [ ] 重构 `MissionShell.tsx` + `.module.css`（Header 改造）
- [ ] 新建 `MetricsBar` 组件（替代 HeroMetrics）
- [ ] 重构 `DashboardPageMinimal.tsx` + `.module.css`（新布局）
- [ ] 重构 `MinimalStatusPanel` → `SystemDetailList`（右下角）

### Phase 3: 组件层（预计 2-3 小时）
- [ ] 按钮系统重构（Filled / Tonal / Outlined 三级）
- [ ] 进度卡重构（Section 式）
- [ ] 操作区重构（主操作突出 + 折叠式危险区）
- [ ] 密码区简化（一行式）
- [ ] Toast 通知组件（替代内嵌成功/错误卡片）

### Phase 4: 交互层（预计 1-2 小时）
- [ ] 卡片入场动画（stagger）
- [ ] 数字 countUp 动画
- [ ] 按钮 loading 状态
- [ ] 空状态设计
- [ ] 微交互打磨（hover/press/focus）

### 总预估：8-12 小时

---

## 十二、视觉模拟对比

### Before（当前深黑主题）

```
┌─────────────────────────────────────────┐
│██████████████ DARK HEADER ██████████████│  ← 深灰，压迫
├─────────────────────────────────────────┤
│                                         │
│       130.2          →        1846.9    │  ← 大数字，但只有 2 个
│    CURRENT PAYLOAD        BASELINE      │
│                                         │
│         [ 93% faster ]                  │  ← 蓝色 Badge
│                                         │
│─── PSNR: 32.5 ── SSIM: 0.9456 ────────│
├────────────────┬────────────────────────┤
│ ▓▓▓▓▓▓▓▓▓▓▓▓  │  ░░░░░░░░░░░░░░░░░░   │
│ 深色卡片堆叠    │  深色地图（黑洞感）     │
│ 深色卡片堆叠    │                        │
│ 深色卡片堆叠    │  [btn][btn][btn][btn]  │  ← 按钮密集排列
│ 深色卡片堆叠    │  [btn][btn][btn][btn]  │
└────────────────┴────────────────────────┘
整体观感：沉重 · 冷硬 · 层级模糊 · "黑洞"
```

### After（暖中性主题）

```
┌─────────────────────────────────────────┐
│ ◇ 座舱演示   仪表盘  Session   ●在线 12:30│  ← 暖白 Header，轻盈
├─────────────────────────────────────────┤
│ ●在线 │ ARMED │ 130.2ms │ 1846ms │ 93% │  ← 64px Metrics Bar
├───────────────────┬─────────────────────┤
│                   │                     │
│  Current 重建进度  │  ┌───────────────┐  │
│  ████████░░ 45/300│  │  World Map     │  │  ← 暖色地图
│                   │  │  (暖色调)      │  │
│  ┌──────────────┐ │  │               │  │
│  │▶ 启动重建    │ │  │  经纬 航向 高度 │  │
│  └──────────────┘ │  └───────────────┘  │
│  [探测] [预检] [PT]│                     │
│                   │  Connection  Online  │
│  ▸ 故障注入 [展开] │  Guard      ARMED   │  ← 折叠的危险区
│                   │  Last Fault  None    │
│  [密码....] [保存] │                     │
└───────────────────┴─────────────────────┘
整体观感：温润 · 透气 · 层级清晰 · "精品感"
```

---

## 十三、补充：暗色模式的可选方案

如果未来需要暗色模式，建议不是回到"冷黑"，而是走 **Warm Dark** 路线：

```
页面背景:  #1C1917  (暖深褐，而非 #0f1117 冷黑)
卡片背景:  #292524  (暖炭色)
文字:      #F5F5F4  (暖白)
标签:      #A8A29E  (暖灰)
阴影:      rgba(12,10,9,0.3)  (暖色阴影)
```

这样即使切换暗色，也保持"温润"的整体基调，避免回到冰冷的感觉。

---

## 十四、总结

| 维度 | 当前 | 改造后 |
|------|------|--------|
| **主题** | Cold Dark（冷黑科技） | Warm Neutral（温润科技精品） |
| **背景** | #0f1117 近纯黑 | #F7F5F2 暖米白 |
| **强调色** | #60a5fa 冷蓝 | #2563EB 沉稳蓝 |
| **层级系统** | border 分层（模糊） | shadow 分层（清晰） |
| **Header** | 56px 深灰胶囊 Tab | 52px 暖白下划线 Tab |
| **Hero 区** | 25vh 大面积留白 | 64px 紧凑 Metrics Bar |
| **布局** | 1:1 等分双栏 | 62:38 黄金比例 |
| **按钮** | 4 种混乱层级 | 3 种清晰层级（Filled/Tonal/Outlined） |
| **危险操作** | 与常规按钮平铺 | 折叠收起，需展开才可见 |
| **消息提示** | 内嵌卡片 | Toast 通知 |
| **地图** | 深黑海洋 | 暖米色海洋 |
| **圆角** | 统一 8-16px | 分级 8/12/16/24px |
| **动效** | 基本无 | 入场/hover/loading/countUp |
| **设计参考** | Google Cloud Console Dark | MD3 Expressive + TDesign + Warm Neutral 2026 趋势 |

**一句话总结**：从"深空科幻"转向"温润精品"，用暖中性色调消除压迫感，用阴影层级替代边框噪音，用信息密度优化替代大面积留白，打造一个**既有科技质感又让人舒服的** demo 界面。

---

*本方案基于对 Material Design 3 Expressive、腾讯 TDesign 2026、以及 2026 年 SaaS Dashboard 暖中性色趋势的综合研究而制定。*
