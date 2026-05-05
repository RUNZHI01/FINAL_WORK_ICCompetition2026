# 极简科技风格重构说明

**日期**: 2026-03-30
**风格**: Apple-inspired Minimalist Tech
**核心原则**: 大量留白 + 超大关键数字 + 一眼看全

## 设计理念

### 问题诊断
用户反馈的核心问题：
1. 三栏布局太拥挤，信息密度过高
2. 卡片太多太碎，找不到重点
3. 信息组织不符合工作流程
4. 主题不够独特，缺乏记忆点

### 设计方向
**Apple-inspired Minimalist Tech**: 像iPhone发布会那样，用超大数字和大量留白突出关键指标。

## 关键改动

### 1. 主题配色 (tokens.ts)

**从** SaaS专业风格 **到** Apple极简风格

```typescript
// 深色背景 - 纯黑而非深蓝
bgPrimary: '#000000'  // 之前是 #0a0e1a
bgCard: '#0d0d0d'     // 之前是 rgba(15, 20, 35, 0.85)

// 高对比度文字
textPrimary: '#ffffff'  // 更高的对比度
textSecondary: '#a1a1aa' // Apple灰色

// 状态色 - 更鲜艳
toneOnline: '#00ff9c'   // 亮绿青色
toneError: '#ff453a'    // iOS红色
toneWarning: '#ffb020'  // iOS橙色

// 超大字体
fontSize3Xl: 48   // 大标题
fontSize4Xl: 72   // Hero数字（130ms显示72px）

// 大量留白
gapLg: 32   // 之前是18
gapXl: 48   // 之前是28
gap2Xl: 64  // 之前是36

// 极小圆角
radiusMd: 6  // 之前是8
radiusLg: 8  // 之前是12
```

### 2. 全新布局架构

**之前**: 三栏拥挤布局
```
[280px Sidebar] [Map Area] [320px Mission]
      ↓              ↓            ↓
  太多卡片      地图太大      碎片化信息
```

**现在**: 极简两栏 + Hero区域
```
┌─────────────────────────────────────┐
│    HERO METRICS (超大数字区域)       │
│   130ms  →  1846ms  │  93% faster  │
├─────────────────────────────────────┤
│ [Status Panel]    │   [Actions]    │
│  - System Status  │  - Probe Board │
│  - Active Job     │  - Run Inf     │
│  - Quick Actions  │  - Fault Test  │
└─────────────────────────────────────┘
```

**优势**:
- ✅ 一眼看全所有关键信息
- ✅ 超大的性能数字（72px）视觉冲击力强
- ✅ 左侧状态面板信息密度适中
- ✅ 右侧操作区域清晰集中

### 3. Hero Metrics 组件

**新增文件**: `HeroMetrics.tsx` + `HeroMetrics.module.css`

**特点**:
- 超大数字显示（72px for current, 56px for baseline）
- 清晰的"93% faster"徽章
- 次要指标（PSNR/SSIM/Total）横向排列
- 大量留白（48px padding）

**视觉层级**:
```
PRIMARY: 130ms (72px, 白色, 粗体)
SECONDARY: 1846ms (56px, 灰色)
ACCENT: 93% faster (徽章, iOS蓝)
TERTIARY: PSNR/SSIM/Total (小字, 底部)
```

### 4. MinimalStatusPanel 组件

**新增文件**: `MinimalStatusPanel.tsx` + `.module.css`

**整合内容**:
- System Status（在线/离线、安全状态、最后故障、板子温度）
- Active Job（当前推理任务）
- Quick Actions（快速操作）

**设计特点**:
- 2x2网格布局
- 每项信息一行，无冗余
- 最小化视觉装饰
- 功能性优先

### 5. 全新Dashboard页面

**新增文件**: `DashboardPageMinimal.tsx` + `.module.css`

**布局**:
```
┌──────────────────────────────────┐
│     HeroMetrics (顶部固定)         │
├──────────────────────────────────┤
│ [380px Status]  │  [Actions]    │
│                  │  (居中对齐)    │
└──────────────────────────────────┘
```

**响应式设计**:
- >1400px: 380px + 自适应
- 1200-1400px: 320px + 自适应
- <1200px: 垂直堆叠
- <900px: 移动优化

### 6. Header更新

**改动**:
- 更大的间距（32px gap）
- 更高的header（56px）
- 更简洁的样式
- 移除模糊效果（backdrop-filter）
- 纯黑背景

## 文件清单

### 新增文件
```
src/renderer/src/
├── components/dashboard/
│   ├── HeroMetrics/
│   │   ├── HeroMetrics.tsx
│   │   ├── HeroMetrics.module.css
│   │   └── index.ts
│   └── MinimalStatusPanel/
│       ├── MinimalStatusPanel.tsx
│       ├── MinimalStatusPanel.module.css
│       └── index.ts
├── pages/
│   ├── DashboardPageMinimal.tsx
│   └── DashboardPageMinimal.module.css
```

### 修改文件
```
src/renderer/src/
├── App.tsx                        # 添加新路由
├── theme/tokens.ts                # 极简主题配色
├── layouts/MissionShell.module.css # Header样式更新
└── index.css                      # 全局样式简化
```

## 设计对比

### Before (SaaS风格)
```
❌ 三栏拥挤布局
❌ 信息碎片化（10+卡片）
❌ 地图占据中心但信息量低
❌ 中等字体大小
❌ 装饰性元素（渐变、发光、玻璃态）
```

### After (极简科技)
```
✅ 两栏宽松布局
✅ 信息整合（3个核心模块）
✅ Hero数字区域视觉冲击
✅ 超大关键指标（72px）
✅ 极简装饰（纯色、细线）
```

## 关键指标展示

### 性能对比（Hero Metrics）
```
┌─────────────────────────────────────────┐
│ CURRENT PAYLOAD                         │
│          130.2                          │ ← 72px白色粗体
│     milliseconds                        │
│            ↓                            │
│        [TrendingUp]                     │
│            ↓                            │
│ BASELINE                               │
│         1846.9                          │ ← 56px灰色
│     milliseconds                        │
│                                         │
│    [93% faster]                         │ ← 徽章
│                                         │
│─────────────────────────────────────────│
│ PSNR: 32.5 dB │ SSIM: 0.9456 │ ...    │ ← 次要指标
└─────────────────────────────────────────┘
```

### 系统状态（MinimalStatusPanel）
```
┌────────────────────────────┐
│ System Status              │
│ ┌──────────┬──────────┐    │
│ │Connection│  Online  │    │ ← 2x2网格
│ ├──────────┼──────────┤    │
│ │Safe State│   ARMED  │    │
│ ├──────────┼──────────┤    │
│ │Last Fault│   None   │    │
│ ├──────────┼──────────┤    │
│ │   Board  │   52°C   │    │
│ └──────────┴──────────┘    │
│                            │
│ Active Job                 │
│ ┌──────────────────────┐  │
│ │ abc12345  [Running]  │  │
│ │ Progress: 67%        │  │
│ │ Payload: 128.3 ms    │  │
│ └──────────────────────┘  │
│                            │
│ Quick Actions              │
│ ┌──────────┬──────────┐    │
│ │ Recover  │Inject    │    │
│ └──────────┴──────────┘    │
└────────────────────────────┘
```

## 测试清单

- [ ] 运行 `npm run dev` 查看新界面
- [ ] 验证Hero Metrics数字显示正确
- [ ] 测试Status Panel各项信息
- [ ] 测试操作按钮功能
- [ ] 响应式布局测试（1400/1200/900px）
- [ ] 检查色彩对比度（accessibility）
- [ ] 验证动画流畅度

## 路由说明

```typescript
/           → DashboardPageMinimal (新极简界面)
/legacy     → DashboardPage (旧三栏界面，保留)
```

如需切换回旧界面，访问 `#/legacy`

## 设计哲学

### "Less but Better" - Dieter Rams

这次重构遵循Apple的设计哲学：
1. **去除不必要的元素** - 地图、碎卡片、装饰效果
2. **突出核心信息** - 130ms vs 1846ms，这就是故事
3. **大量留白** - 让关键信息呼吸
4. **超大数字** - 视觉冲击力，评委一眼记住

### 视觉层级

```
Level 1 (Hero): 72px 数字 - 130ms
Level 2 (Badge): 32px 数字 - 93% faster
Level 3 (Labels): 13-16px - 标签文字
Level 4 (Metadata): 11-12px - 次要信息
```

## 后续优化建议

1. **动画增强**: 数字变化时的counting动画
2. **空状态设计**: 无数据时的优雅提示
3. **微交互**: 按钮hover的微妙反馈
4. **深色模式优化**: 真正的纯黑（#000000）在OLED屏上的优势
5. **打印样式**: 为评委准备材料时的打印布局

## 总结

这次重构不是简单的"美化"，而是**彻底重新思考信息架构**：

**之前**: 展示所有功能（信息过载）
**现在**: 突出核心价值（性能提升）

**之前**: 三栏拥挤布局
**现在**: 两栏宽松布局 + Hero区域

**之前**: 装饰性设计
**现在**: 功能性极简

结果是一个**令人印象深刻的、一眼看全的、高科技感的demo界面**。

---

**Created with**: Claude Code Frontend Design Skill
**Inspired by**: Apple Keynote Presentations, iOS Design, SpaceX Interfaces
