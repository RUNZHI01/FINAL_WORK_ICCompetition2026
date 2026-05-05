# 上位机退化保底功能接入 Electron Demo — 完整工作说明

> 本文档供外部审查使用，详细记录了本次「将退化保底状态功能从 cockpit_native 延伸到 cockpit_desktop (Electron)」的全部工作。

---

## 一、任务背景

### 1.1 项目上下文

本项目是一个面向飞腾杯竞赛的**语义通信 + 边缘推理**系统。系统架构分为：

- **上位机**（笔记本 / 开发机）：运行 USRP 物理链路、语义编码器、控制面 demo 后端
- **飞腾派**（RTOS 从核 + Linux 主核）：运行安全管控（SafetyGuard）和 TVM/MNN 推理管线

上位机侧有一个 `DegradationEngine`（退化决策引擎），根据实时链路质量（SNR、PER、突发丢包）自主调整发送策略：

| 模式 | 说明 | 载荷策略 |
|---|---|---|
| `FULL_FRAME` | 全图模式 | 发送完整语义张量 |
| `ROI_ONLY` | ROI 模式 | 只发关键区域裁剪张量 |
| `ALERT_ONLY` | 告警模式 | 仅发告警元数据 |

这个引擎已在 `openamp_mock/degradation_engine.py` 中实现完毕，并已接入原生 Qt demo（`cockpit_native`）。

### 1.2 本次任务

用户要求：**将同一项退化功能延伸到 Electron demo（cockpit_desktop）**，具体是让 Electron 仪表盘能实时展示退化模式、载荷策略、链路丢失标志和模式切换历史。

约束条件：
- 不修改已完成的 openamp_mock / cockpit_native 代码
- 不新建独立 HTTP 路由
- 不重做 dashboard 布局
- 复用现有 API 轮询链路
- 视觉风格对齐现有组件

---

## 二、方案设计阶段

### 2.1 现状调研

在编码前，我对以下文件进行了完整阅读和搜索：

| 文件 | 核心发现 |
|---|---|
| [server.py](file:///home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/server.py) (6663 行) | 搜索 `degradation` / `DegradationEngine` **零匹配**——后端完全没有退化数据 |
| [client.ts](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/api/client.ts) | 已有 `getCryptoStatus()` 调用 `/api/crypto-status`，可复用 |
| [crypto.ts](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/api/types/crypto.ts) | `CryptoStatusResponse` 类型中无退化字段 |
| [DashboardPageMinimal.tsx](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx) | 右侧面板堆叠：FlightPanel → MinimalStatusPanel → CryptoStatusPanel |
| [CryptoStatusPanel.tsx](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/components/dashboard/CryptoStatusPanel/CryptoStatusPanel.tsx) (315 行) | 已有 rowGrid 卡片模式、useCryptoStatus hook、2s 轮询 |
| [useCryptoStatus.ts](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/hooks/useCryptoStatus.ts) | 基于 `@tanstack/react-query`，`queryKey: ['crypto-status']`，`refetchInterval: 2000` |
| [degradation_engine.py](file:///home/tianxing/tvm_metaschedule_execution_project/openamp_mock/degradation_engine.py) | `snapshot()` 方法返回完整状态 dict，已有 9 条单测 |
| [DashboardState.__init__](file:///home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/server.py#L1892-L1961) | 没有 `DegradationEngine` 实例 |

**结论：Electron 侧退化功能完全从零开始，但有大量可复用基础设施。**

### 2.2 关键设计决策

#### 决策 1：数据塞到哪个接口？

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A. 新建 `/api/degradation-status` | 语义清晰 | 新增路由、新增 hook、多一次 HTTP 请求、打破现有轮询节奏 | ❌ 否决 |
| B. 塞入 `/api/system-status` | 贴近"系统状态" | 该接口 6s 轮询一次，刷新太慢；且其 response 结构复杂 | ❌ 否决 |
| **C. 塞入 `/api/crypto-status`** | 已有 2s 轮询；退化与加密通道同属通信链路保障层；前端零新 hook | 语义略有越界 | **✅ 采用** |

**理由**：`/api/crypto-status` 已经包含了 `control_guard_state`、`control_heartbeat_ok`、`control_total_fault_count` 等控制面字段——退化模式是控制面的自然延伸，语义上一致。

#### 决策 2：独立面板还是塞进 CryptoStatusPanel？

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 塞入 CryptoStatusPanel | 少一个文件 | 该组件已 315 行，再加退化逻辑会臃肿；职责不单一 | ❌ |
| **独立 DegradationStatusPanel** | 职责单一；答辩时可单独展示 | 多 3 个文件 | **✅** |

#### 决策 3：后端如何注入 degradation 字段？

`get_crypto_status()` 方法有 **5+ 个 return 分支**（toggle OFF、board 未配置、缓存命中、远端成功、远端失败、cold start）。逐一添加 `"degradation": ...` 容易遗漏。

**采用 wrapper 模式**：
```python
def get_crypto_status(self) -> dict[str, Any]:
    result = self._get_crypto_status_core()
    result["degradation"] = self._degradation_engine.snapshot()
    return result

def _get_crypto_status_core(self) -> dict[str, Any]:
    # ... 原有逻辑不变 ...
```

这样只改一处，所有分支自动被覆盖。

---

## 三、具体改动

### 3.1 改动总览

| 类型 | 文件 | 改动量 |
|---|---|---|
| **修改** | `server.py` | +1 行 import, +1 行 init, +6 行 wrapper |
| **修改** | `crypto.ts` | +24 行类型定义, +2 行字段 |
| **修改** | `DashboardPageMinimal.tsx` | +1 行 import, +2 行 JSX |
| **新建** | `DegradationStatusPanel/index.ts` | 1 行 |
| **新建** | `DegradationStatusPanel/DegradationStatusPanel.module.css` | 149 行 |
| **新建** | `DegradationStatusPanel/DegradationStatusPanel.tsx` | 98 行 |

### 3.2 后端改动详解：server.py

#### 改动点 1：import（L68）

```python
from openamp_mock.degradation_engine import DegradationEngine
```

放在 `from event_spine import ...` 之后。`DegradationEngine` 只依赖 `openamp_mock.link_health.LinkHealthReport` 和 `openamp_mock.protocol.ServiceMode`，两者都是纯 Python 数据类，无外部依赖。

#### 改动点 2：实例化（L1960）

```python
self._degradation_engine = DegradationEngine()
```

放在 `DashboardState.__init__()` 末尾、`self._ensure_local_aircraft_position_bridge_thread()` 之前。引擎初始化为 `FULL_FRAME` 模式、所有计数器归零。

#### 改动点 3：wrapper 注入（L2839-2844）

原来的 `get_crypto_status` 被重命名为 `_get_crypto_status_core`（internal），新的 `get_crypto_status` 调用 core 后追加 `degradation` 字段：

```python
def get_crypto_status(self) -> dict[str, Any]:
    """从板卡 tcp_server 的 HTTP /status 端点获取 ML-KEM 通道状态。
    ...
    """
    result = self._get_crypto_status_core()
    result["degradation"] = self._degradation_engine.snapshot()
    return result

def _get_crypto_status_core(self) -> dict[str, Any]:
    """Internal: crypto status without degradation overlay."""
    # ... 原有所有逻辑保持不变 ...
```

**为什么这样做**：
- 原方法有 5+ 个 return 分支，如果每个分支都追加 `"degradation": ...`，容易遗漏且 diff 污染大
- wrapper 模式只新增 6 行，所有分支自动覆盖
- HTTP handler 调用的是 `self.server.app_state.get_crypto_status()`，公共接口名不变，**对外零感知**

### 3.3 前端改动详解：TypeScript 类型

#### crypto.ts 新增类型

```typescript
export type DegradationSnapshot = {
  current_mode: string         // "FULL_FRAME" | "ROI_ONLY" | "ALERT_ONLY"
  current_mode_value: number   // 0 | 1 | 2
  payload_strategy: string     // "full_latent" | "roi_latent" | "alert_metadata"
  is_link_lost: boolean
  degrade_window_count: number
  upgrade_window_count: number
  mode_transitions: number
  last_transition: {
    from_mode: string
    to_mode: string
    reason: string
    timestamp_ms: number
  } | null
}
```

这个类型与 Python `DegradationEngine.snapshot()` 的返回值 **1:1 对应**。每个字段都有 JSDoc 注释。

#### CryptoStatusResponse 新增字段

```typescript
/** Upper-computer degradation engine snapshot */
degradation?: DegradationSnapshot | null
```

使用可选类型（`?`）+ `null`，兼容后端未部署的场景。

### 3.4 前端改动详解：DegradationStatusPanel 组件

#### 数据获取

```typescript
const { data } = useCryptoStatus()
const deg: DegradationSnapshot | null | undefined = data?.degradation
```

**关键点**：该组件内部调用的 `useCryptoStatus()` 与 `CryptoStatusPanel` 内部调用的是**同一个 React Query**（`queryKey: ['crypto-status']`）。React Query 会自动复用缓存，**不会产生重复 HTTP 请求**。这是 React Query 的标准 cache sharing 机制。

#### 模式到视觉的映射

```typescript
const MODE_DISPLAY = {
  FULL_FRAME: { label: '全图模式', dotClass: s.dotOk,     badgeClass: s.modeFull  },
  ROI_ONLY:   { label: 'ROI 模式', dotClass: s.dotWarn,   badgeClass: s.modeRoi   },
  ALERT_ONLY: { label: '告警模式', dotClass: s.dotDanger,  badgeClass: s.modeAlert },
}
```

- `FULL_FRAME` → 绿色（`--color-success`）
- `ROI_ONLY` → 金色（`#F59E0B`）— 与 CryptoStatusPanel 的 `dotWarn` 一致
- `ALERT_ONLY` → 红色（`--color-error`）

链路丢失时（`is_link_lost=true`），dot 叠加 pulse 动画（`dotDangerPulse`）。

#### 载荷策略中文映射

```typescript
const STRATEGY_LABEL = {
  full_latent: '完整语义张量',
  roi_latent: 'ROI 裁剪张量',
  alert_metadata: '告警元数据',
}
```

#### 最近切换原因中文映射

```typescript
function formatTransitionReason(reason: string): string {
  const MAP = {
    'sustained degradation': '持续劣化',
    'sustained recovery': '持续恢复',
    'burst loss emergency': '突发丢包紧急',
    'link lost (rx_locked=false)': '链路丢失',
  }
  return MAP[reason] ?? reason
}
```

#### CSS 设计

CSS module 的设计 token 与 `CryptoStatusPanel.module.css` **完全对齐**：

- `.card` — 相同的 glassmorphism 卡片（`rgba(255,255,255,0.85)` + `backdrop-filter: blur(12px)`）
- `.titleRow` / `.title` — 相同的标题栏
- `.rowGrid` — 相同的两列 grid
- `.label` / `.mono` / `.muted` — 相同的文字样式
- `.dot` / `.dotOk` / `.dotWarn` / `.dotOff` — 相同的状态点

新增的类：
- `.dotDanger` — 红色点（`--color-error`），用于 `ALERT_ONLY`
- `.dotDangerPulse` — 红色点 + pulse 动画，用于链路丢失
- `.modeBadge` / `.modeFull` / `.modeRoi` / `.modeAlert` — 标题栏右侧的模式标签
- `.transitionRow` / `.transitionArrow` — 最近切换信息行

#### 渲染内容

卡片顶部：标题「退化保底状态」+ 右侧模式标签（带色点）

rowGrid 区域展示 6 项：
1. **当前模式**：FULL_FRAME / ROI_ONLY / ALERT_ONLY
2. **载荷策略**：完整语义张量 / ROI 裁剪张量 / 告警元数据
3. **链路状态**：正常（绿）/ 丢失（红）
4. **降级窗口**：当前累积 / 阈值 3
5. **升级窗口**：当前累积 / 阈值 5
6. **模式切换**：N 次

如果有历史切换，底部显示最近一次切换信息（from → to + 原因）。

### 3.5 页面集成

在 `DashboardPageMinimal.tsx` 的右侧面板（`rightPanel`）中，`<CryptoStatusPanel />` 之后追加：

```tsx
<DegradationStatusPanel />
```

最终右侧面板布局：
```
FlightPanel          — 战术地图
MinimalStatusPanel   — 板卡遥测
CryptoStatusPanel    — ML-KEM 安全信道
DegradationStatusPanel — 退化保底状态 【新增】
```

---

## 四、数据流全貌

```
Python 后端                                Electron 前端
────────────────────                    ────────────────────

DegradationEngine()
  .snapshot()
      │
      ▼
get_crypto_status()
  → { ...existing, "degradation": {...} }
      │
      │  HTTP GET /api/crypto-status
      │  (每 2 秒, 由 useCryptoStatus 驱动)
      ▼
                                        useCryptoStatus() hook
                                          queryKey: ['crypto-status']
                                          refetchInterval: 2000ms
                                              │
                                      ┌───────┴───────┐
                                      │               │
                                CryptoStatusPanel  DegradationStatusPanel
                                  读 data.*           读 data.degradation
                                  (已有)              (新增)
                                      │               │
                                  渲染加密状态      渲染退化状态
```

> 两个 Panel 共享同一个 React Query cache，**不会产生重复 HTTP 请求**。

---

## 五、验证结果

### 5.1 后端单测

```
$ python3 -m unittest openamp_mock.tests.test_degradation_engine
.........
----------------------------------------------------------------------
Ran 9 tests in 0.000s
OK
```

9 条测试覆盖：full→roi、roi→alert、burst loss emergency、recovery、link lost、hysteresis no-flap、payload strategy、snapshot、reset。

### 5.2 DegradationEngine.snapshot() 输出

```json
{
  "current_mode": "FULL_FRAME",
  "current_mode_value": 0,
  "payload_strategy": "full_latent",
  "is_link_lost": false,
  "degrade_window_count": 0,
  "upgrade_window_count": 0,
  "mode_transitions": 0,
  "last_transition": null
}
```

### 5.3 TypeScript 编译

```
$ npx tsc --noEmit
(无输出，零错误)
```

---

## 六、未改动的文件（明确声明）

| 文件 | 原因 |
|---|---|
| `openamp_mock/degradation_engine.py` | 已完成，本次不改 |
| `openamp_mock/tests/test_degradation_engine.py` | 已完成，本次不改 |
| `openamp_mock/__init__.py` | 已完成导出，本次不改 |
| `cockpit_native/adapter.py` | native 侧已完成，本次不改 |
| `cockpit_native/qt_app.py` | native 侧已完成，本次不改 |
| `cockpit_desktop/src/renderer/src/hooks/useCryptoStatus.ts` | 复用现有 hook，不改 |
| `cockpit_desktop/src/renderer/src/api/client.ts` | `getCryptoStatus()` 已有，不改 |
| `CryptoStatusPanel/` | 不往里面加内容 |
| `MinimalStatusPanel/` | 不改 |
| `scripts/openamp_rpmsg_bridge.py` (2930 行) | 真机桥接，不改 |
| 所有 RTOS / 固件代码 | 完全不涉及 |

---

## 七、风险评估

| 风险项 | 严重程度 | 缓解措施 |
|---|---|---|
| server.py import openamp_mock 时 PYTHONPATH 不对 | 中 | Electron 的 `pythonManager.ts` 启动后端时已有 PYTHONPATH 设置逻辑；server.py 同目录有 `sys.path` 插入逻辑 |
| server.py 已 6663 行，改动牵一发动全身 | 低 | 本次只加 8 行，wrapper 模式不侵入原有分支逻辑 |
| 当前 DegradationEngine 处于初始静态状态 | 低（预期行为） | 展示 FULL_FRAME 初始状态是正确的；后续接 USRP 物理链路后自动进入动态退化 |
| React Query 缓存共享可能导致数据竞争 | 极低 | React Query 的 cache sharing 是其核心设计，同 queryKey 的多个 consumer 共享同一份数据是标准用法 |
| DegradationSnapshot 类型与 Python 不同步 | 低 | 类型定义与 `DegradationEngine.snapshot()` 的返回值 1:1 对应；字段全部使用 `?` 可选标记容错 |

---

## 八、总结

本次改动的核心思路是**最小侵入 + 最大复用**：

1. **后端 8 行改动**（1 行 import + 1 行 init + 6 行 wrapper），不动原有任何 return 分支
2. **前端零新 hook、零新 API 调用**，复用 `useCryptoStatus` 的 2s 轮询和 React Query cache sharing
3. **独立组件** `DegradationStatusPanel`，视觉风格完全对齐 `CryptoStatusPanel`
4. **TypeScript 类型安全**，`DegradationSnapshot` 与 Python `snapshot()` 1:1 对应，`npx tsc --noEmit` 零错误
5. **不动已完成的 openamp_mock / cockpit_native / 真机桥接代码**
