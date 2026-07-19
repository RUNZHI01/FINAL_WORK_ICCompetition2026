# 故障排除 - 极简界面

## 黑屏问题 ✅ 已修复

### 问题原因
使用了不存在的图标组件：
- `Icons.Slash` → 改为 `Icons.XCircle`
- `Icons.Terminal` → 改为 `Icons.Settings`

### 解决方案
已修复所有图标引用。现在刷新浏览器即可。

---

## 查看新界面

### 方法1: 直接访问
```
http://localhost:5173/#/
```

### 方法2: 强制刷新
```
Ctrl + Shift + R (Windows/Linux)
Cmd + Shift + R (Mac)
```

### 方法3: 清除缓存
1. 打开开发者工具 (F12)
2. 右键点击刷新按钮
3. 选择"清空缓存并硬性重新加载"

---

## 切换界面

### 新极简界面
```
http://localhost:5173/#/
```

### 旧三栏界面（保留）
```
http://localhost:5173/#/legacy
```

---

## 预期效果

新界面应该显示：
```
┌─────────────────────────────────────────┐
│   OpenAMP Cockpit                        │ ← Header
├─────────────────────────────────────────┤
│   130.2 ← 72px白色超大数字              │
│   milliseconds                           │
│            ↓                             │
│        [TrendingUp]                      │
│            ↓                             │
│   1846.9 ← 56px灰色数字                 │
│   milliseconds                           │
│                                         │
│    [93% faster]                          │ ← 徽章
│                                         │
│─────────────────────────────────────────│
│ PSNR: 32.5 dB │ SSIM: 0.9456 │ ...     │ ← 次要指标
├─────────────────────────────────────────┤
│ [System Status Panel] │ [Execute]       │
│  - Connection: Online    │ [Probe Board] │
│  - Safe State: ARMED     │ [Run Inference]
│  - Last Fault: None      │ [Run Baseline]│
│  - Board: 52°C           │               │
│                                         │
│ [Fault Injection]        │               │
│  - Wrong SHA              │               │
│  - Heartbeat Timeout      │               │
│  - Invalid Params         │               │
└─────────────────────────────────────────┘
```

---

## 如果仍然黑屏

### 检查控制台错误
1. 按 F12 打开开发者工具
2. 查看 Console 标签
3. 截图所有红色错误

### 检查网络请求
1. 开发者工具 → Network 标签
2. 刷新页面
3. 检查是否有 404 错误

### 重启开发服务器
```bash
# 停止服务器 (Ctrl+C)
# 重新启动
cd cockpit_desktop
npm run dev
```

### 检查文件是否创建
```bash
ls -la src/renderer/src/components/dashboard/HeroMetrics/
ls -la src/renderer/src/components/dashboard/MinimalStatusPanel/
ls -la src/renderer/src/pages/DashboardPageMinimal.*
```

---

## 常见问题

### Q: 为什么纯黑背景？
A: 这是设计选择。纯黑(#000000)比深蓝更有科技感，符合极简美学。

### Q: 字体是否太大？
A: 72px的Hero数字是**故意的**，创造视觉冲击力。这是Apple Keynote风格。

### Q: 地图去哪了？
A: 地图占据大量空间但信息密度低。新布局聚焦于**性能数据**和**系统状态**。

### Q: 如何恢复旧界面？
A: 访问 `/#/legacy` 或修改 `App.tsx` 中的路由配置。

---

## 性能对比

### 旧界面
- 10+ 碎片化卡片
- 三栏拥挤布局
- 性能数字淹没在细节中
- 第一眼：复杂

### 新界面
- 3 核心模块
- 两栏宽松布局
- 72px Hero数字
- 第一眼："130ms！"

---

## 下一步

1. ✅ 修复图标错误
2. ✅ 刷新浏览器
3. 📸 截图新界面
4. 🎨 准备演示脚本
5. 📊 收集反馈

---

**Created**: 2026-03-30
**Status**: 图标问题已修复，准备使用
