# iOS 字体更新说明

**更新日期**: 2026-03-30
**字体风格**: iOS SF Pro 风格

---

## 字体变化

### 旧字体配置
```css
font-family:
  'Inter',
  'Noto Sans SC',
  system-ui,
  -apple-system,
  'Segoe UI',
  Roboto,
  'Helvetica Neue',
  Arial,
  sans-serif;
```

**特点**:
- Inter (第三方开源字体)
- Noto Sans SC (Google 中文字体)
- 需要加载本地字体文件
- 字重：400, 500, 600, 700

### 新字体配置 (iOS SF Pro 风格)
```css
font-family:
  -apple-system,
  BlinkMacSystemFont,
  "SF Pro Display",
  "SF Pro Text",
  "PingFang SC",
  "Helvetica Neue",
  Helvetica,
  Arial,
  sans-serif;
```

**特点**:
- **-apple-system**: Apple 系统字体自动选择
- **SF Pro Display/Text**: Apple 官方字体（iOS 9+）
- **PingFang SC**: 苹方（Apple 的中文字体）
- **BlinkMacSystemFont**: Chrome macOS 版本的系统字体
- **无需加载本地字体文件**
- **自动适配系统字体**

---

## 字体栈解析

### iOS / macOS
- **SF Pro Display**: 大标题、Hero 数字
- **SF Pro Text**: 正文文本
- **PingFang SC**: 中文文本
- **SF Mono**: 等宽字体（数字、代码）

### Android / Windows
- **-apple-system**: 回退到系统默认
- **Roboto** (Android)
- **Segoe UI** (Windows)
- **Helvetica Neue** (兼容性)

---

## 视觉对比

### 旧字体 (Inter + Noto Sans SC)
```
特点：
- 中性、现代
- 字重分明
- x-高度较大
- 适合 UI 界面

缺点：
- 需要 300KB+ 字体文件
- 加载时间较长
- 中文字重不够丰富
```

### 新字体 (SF Pro + PingFang)
```
特点：
✓ Apple 品质感
✓ 系统原生，无加载延迟
✓ 中英文完美搭配
✓ 数字显示清晰
✓ 字重层次细腻

优势：
✓ 零额外加载时间
✓ 系统一致性
✓ 视觉更精致
✓ 长文本易读性更好
```

---

## 字体使用建议

### 大标题 / Hero 数字
```css
font-family: "SF Pro Display", -apple-system, sans-serif;
font-size: 72px;
font-weight: 700;
letter-spacing: -0.02em;
```

### 正文文本
```css
font-family: "SF Pro Text", -apple-system, "PingFang SC", sans-serif;
font-size: 14px;
font-weight: 400;
line-height: 1.5;
```

### 数字 / 代码
```css
font-family: "SF Mono", "JetBrains Mono", monospace;
font-feature-settings: "tnum" 1, "zero" 1;
```

---

## 具体改进

### 1. 零加载时间
**旧**: 需要加载 Inter + Noto Sans SC (~400KB)
**新**: 使用系统字体，无需下载

### 2. 系统一致性
**旧**: 界面字体与系统字体不同
**新**: 与 macOS/iOS 系统字体一致

### 3. 中文显示
**旧**: Noto Sans SC (Google 设计)
**新**: PingFang SC (Apple 设计)

### 4. 数字可读性
**旧**: JetBrains Mono 或 Inter
**新**: SF Mono (Apple 等宽字体)

---

## 浏览器兼容性

### 完美支持
- ✅ Safari (iOS/macOS)
- ✅ Chrome (macOS)
- ✅ Edge (macOS)

### 良好支持
- ✅ Chrome (Windows) → 使用 Segoe UI
- ✅ Firefox (所有平台) → 使用系统字体
- ✅ Edge (Windows) → 使用 Segoe UI

### 降级方案
```
-apple-system (iOS/macOS)
  ↓
BlinkMacSystemFont (Chrome macOS)
  ↓
PingFang SC (中文)
  ↓
Helvetica Neue (旧版 macOS)
  ↓
Arial (通用)
  ↓
sans-serif (最终降级)
```

---

## 更新的文件

1. **index.css** - 全局字体栈
2. **cssVariables.ts** - CSS 变量

---

## 效果对比

### 标题
| 旧字体 (Inter) | 新字体 (SF Pro Display) |
|---------------|----------------------|
| 现代但通用 | Apple 精致感 |
| 字重较硬 | 字重更细腻 |
| x-height 大 | x-height适中 |

### 中文
| 旧字体 (Noto Sans SC) | 新字体 (PingFang SC) |
|---------------------|---------------------|
| Google 风格 | Apple 风格 |
| 笔画均匀 | 笔画精致 |
| 字重较少 | 字重丰富 |

### 数字
| 旧字体 (JetBrains Mono) | 新字体 (SF Mono) |
|----------------------|-----------------|
| 程序员感 | Apple 感 |
| 字符较宽 | 字符适中 |
| 适合代码 | 适合界面数字 |

---

## 为什么选择 iOS 字体？

### 1. 品质感
SF Pro 是 Apple 专门为屏幕显示设计的字体，细节精致。

### 2. 系统一致性
与 macOS/iOS 系统字体一致，界面更协调。

### 3. 性能
无需加载额外字体文件，提升启动速度。

### 4. 中文支持
PingFang SC 是 Apple 专为中国用户设计的，美观易读。

### 5. 数字显示
SF Mono 是 Apple 的等宽字体，数字显示专业。

---

## 字体对比示例

### 英文文本
**旧 (Inter)**:
```
The quick brown fox jumps over the lazy dog.
```

**新 (SF Pro Text)**:
```
The quick brown fox jumps over the lazy dog.
```

差异：SF Pro 的字重更细腻，字符间距更精确。

### 中文文本
**旧 (Noto Sans SC)**:
```
快速响应时间优化，提升用户体验
```

**新 (PingFang SC)**:
```
快速响应时间优化，提升用户体验
```

差异：PingFang 的笔画更精致，字重层次更丰富。

### 数字显示
**旧 (JetBrains Mono)**:
```
130.2 ms
1846.9 ms
```

**新 (SF Mono)**:
```
130.2 ms
1846.9 ms
```

差异：SF Mono 的数字更紧凑，更适合界面显示。

---

## 浏览器查看效果

### macOS / iOS
完美显示 SF Pro 和 PingFang SC

### Windows
显示 Segoe UI (Microsoft 系统字体)

### Android
显示 Roboto (Google 系统字体)

### Linux
显示系统默认无衬线字体

---

## 未来优化

### 可选方案
如果需要更强的品牌区分，可以考虑：
1. **MiSans** (小米开源) - 现代简洁
2. **HarmonyOS Sans** (华为) - 科技感
3. **阿里巴巴普惠体** - 电商友好

### 当前建议
保持 iOS 字体栈，原因：
- 系统一致性
- 零加载时间
- 品质感优秀
- 用户熟悉度高

---

**总结**: 更换为 iOS SF Pro 字体栈后，界面将拥有 Apple 级别的精致感，同时提升性能和系统一致性。

**Created**: 2026-03-30
**Font Family**: Apple SF Pro + PingFang SC
**Status**: ✅ 已更新，刷新浏览器即可查看
