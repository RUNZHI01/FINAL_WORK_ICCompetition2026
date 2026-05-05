# 退化保底功能接入 Electron Demo — 实施方案

## 0. 背景与目标

将已在 `openamp_mock/degradation_engine.py` 实现并在 `cockpit_native` 验证过的**上位机退化保底状态**功能，延伸到 `cockpit_desktop`（Electron + React + TypeScript）demo 中，让 Electron 仪表盘也能实时展示退化模式、载荷策略、链路丢失标志和模式切换历史。

**一句话目标：** Electron dashboard 右侧面板新增一个退化保底状态卡片，数据通过现有后端轮询链路获取，不新建独立页面。

---

## 1. 当前已完成的基础能力（不重复规划）

| 已完成项 | 位置 |
|---|---|
| DegradationEngine 核心引擎 | `openamp_mock/degradation_engine.py` |
| 9 条单元测试全部通过 | `openamp_mock/tests/test_degradation_engine.py` |
| `__init__.py` 导出 | `openamp_mock/__init__.py` |
| cockpit_native UI 注入（退化模式行 + 只读动作卡） | `cockpit_native/adapter.py` |
| cockpit_native qt_app 透传 snapshot() | `cockpit_native/qt_app.py` |
| cockpit_native adapter 测试（2 条） | `cockpit_native/tests/test_adapter.py` |

---

## 2. Electron 侧现状判断

### 2.1 后端（server.py）是否已有退化数据？

**结论：没有。**

- 在 `session_bootstrap/demo/openamp_control_plane_demo/server.py`（6663 行）中搜索 `degradation`、`DegradationEngine`、`degradation_engine`，均为 **零匹配**。
- `DashboardState.__init__()` 没有实例化 `DegradationEngine`。
- `/api/crypto-status` 和 `/api/system-status` 返回的 JSON 中没有任何退化相关字段。

### 2.2 前端是否已有退化组件或类型？

**结论：没有。**

- 在 `cockpit_desktop/src/renderer/src/` 中搜索 `degradation`，**零匹配**。
- `api/types/crypto.ts` 中没有退化相关字段。
- 无 `DegradationPanel` 组件或相关 hook。

### 2.3 可复用的基础设施

| 基础设施 | 说明 |
|---|---|
| `/api/crypto-status` 接口 | 已有 2s 轮询，返回 ML-KEM + 控制面状态，可以扩展 |
| `useCryptoStatus` hook | 已接好 `@tanstack/react-query`，2s 自动刷新 |
| `CryptoStatusPanel` 组件模式 | 卡片式 `rowGrid` 布局 + 条件渲染 + tone 颜色映射 |
| `CryptoStatusPanel.module.css` | 完整的 `card` / `rowGrid` / `dot` / `mono` 样式体系 |
| `DashboardPageMinimal.tsx` 右侧面板 | 已有 `FlightPanel` → `MinimalStatusPanel` → `CryptoStatusPanel` 三层堆叠 |

---

## 3. 推荐接入方案

### 3.1 数据来源：扩展 `/api/crypto-status` 返回值

> **为什么不新建独立接口？**
>
> - 退化状态是"链路质量感知 → 传输策略调整"的全局状态，与 ML-KEM 安全信道同属**通信链路保障层**，语义上归属一致。
> - `CryptoStatusPanel` 已经展示了控制面 guard_state / fault / heartbeat 等字段（`control_*` 系列），退化模式是同一语义域的自然延伸。
> - 复用现有 2s 轮询链路，零额外网络开销。
> - 前端只需在 `useCryptoStatus` 返回的数据里读新字段，不需要新建 hook 或新建 query。

**后端最小改动：**

1. 在 `DashboardState.__init__()` 中实例化一个 `DegradationEngine`。
2. 在 `get_crypto_status()` 返回值中追加一个 `degradation` 字段，值为 `engine.snapshot()` 的 dict。
3. 引擎 `update()` 的时机：可以挂一个低频定时器（500ms）从 mock/simulated link health 喂入报告，也可以先以"纯展示初始状态"起步（即只看 snapshot 的静态值），后续再接真实 USRP 链路。

### 3.2 前端新增：独立的 `DegradationStatusPanel` 组件

> **为什么不直接往 CryptoStatusPanel 里加？**
>
> - `CryptoStatusPanel` 已经 315 行，内含 toggle 开关、test 按钮、benchmark 表格、多种状态分支——再加退化模式会让组件过长且职责不清。
> - 退化保底是**独立功能语义**（QoS 策略，非加密通道），独立面板更利于答辩展示和后续维护。
> - 但在**视觉风格**上完全复用 `CryptoStatusPanel.module.css` 的设计语言（卡片 + rowGrid + dot + mono），保持一致性。

### 3.3 页面放置：右侧面板，在 `CryptoStatusPanel` 之后

```
右侧面板 (38%)
├── FlightPanel          ← 战术地图
├── MinimalStatusPanel   ← 板卡遥测
├── CryptoStatusPanel    ← ML-KEM 安全信道
└── DegradationStatusPanel ← 【新增】退化保底状态
```

这样的顺序是有逻辑的：从宏观（飞行态势）→ 硬件（板卡遥测）→ 通信安全（加密信道）→ 通信质量（退化策略），逐层递进。

---

## 4. 精确改动点

### 4.1 后端（Python）

#### [MODIFY] [server.py](file:///home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/server.py)

**改动 1：import 和实例化**

在文件头部 import 区域添加：

```python
from openamp_mock.degradation_engine import DegradationEngine
```

在 `DashboardState.__init__()` 末尾（约 L1960 前）添加：

```python
self._degradation_engine = DegradationEngine()
```

**改动 2：在 `get_crypto_status()` 返回值中追加退化字段**

在 `get_crypto_status()` 方法的每个 return 路径中，追加：

```python
"degradation": self._degradation_engine.snapshot(),
```

需要在以下位置分别添加：
- L2859 `_disabled` dict 中
- L2865 toggle OFF 的 return 中
- L2874 缓存命中的 return dict 中
- L2887 board_not_configured 的 return dict 中
- L2921 成功获取远端 status 后的 data dict 中
- L2937 fallback dict 中
- L2953 cold start dict 中

> [!TIP]
> 更优雅的做法：在方法最终 return 前统一注入，而不是每个分支都加。可以把 `get_crypto_status` 重构为先计算 payload 再统一追加 degradation 后 return。但考虑到这个文件已经 6663 行且改动要最小化，**推荐将 `get_crypto_status()` 包装一个内部 helper** `_get_crypto_status_core()`，然后 `get_crypto_status()` 调用它并追加 degradation 字段。这样只需改动一处 return。

**不需要新建路由，不需要新建 HTTP handler。**

---

### 4.2 前端（TypeScript / React）

#### [MODIFY] [crypto.ts](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/api/types/crypto.ts)

在 `CryptoStatusResponse` 类型中追加退化相关字段：

```typescript
/** Upper-computer degradation engine snapshot */
degradation?: DegradationSnapshot | null
```

并在同文件中新增类型定义：

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

---

#### [NEW] DegradationStatusPanel 组件

新建目录和文件：

```
cockpit_desktop/src/renderer/src/components/dashboard/DegradationStatusPanel/
├── DegradationStatusPanel.tsx
├── DegradationStatusPanel.module.css
└── index.ts
```

##### DegradationStatusPanel.tsx

组件设计要点：

- 从 `useCryptoStatus()` hook 获取数据（复用现有轮询），读取 `data.degradation`
- 如果 `degradation` 为 null/undefined，显示"未接入"占位
- 正常状态下用 `rowGrid` 布局展示：
  - 当前模式（带 tone 色彩的 dot + 文字）
  - 载荷策略（full_latent / roi_latent / alert_metadata）
  - 链路状态（正常 / 丢失）
  - 降级窗口计数 / 升级窗口计数
  - 模式切换次数
  - 最近一次切换（from → to，原因）
- 模式到 tone 的映射：
  - `FULL_FRAME` → 绿色 (`dotOk`)
  - `ROI_ONLY` → 金色 (`dotWarn`)
  - `ALERT_ONLY` → 红色（用 `fail` 色）
  - 链路丢失 → 红色闪烁

##### DegradationStatusPanel.module.css

**直接复用 CryptoStatusPanel.module.css 的设计 token**（`card`, `titleRow`, `title`, `rowGrid`, `label`, `mono`, `dot`, `dotOk`, `dotWarn`, `dotOff`, `muted` 等），保持视觉一致。只需额外增加：

- `.dotDanger` — 红色 dot 样式（用于 ALERT_ONLY）
- `.modeBadge` — 可选的 mode 标签底色

##### index.ts

```typescript
export { DegradationStatusPanel } from './DegradationStatusPanel'
```

---

#### [MODIFY] [DashboardPageMinimal.tsx](file:///home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx)

在右侧面板（`rightPanel`）、`CryptoStatusPanel` 之后添加：

```tsx
import { DegradationStatusPanel } from '../components/dashboard/DegradationStatusPanel'

// ... 在 rightPanel 中：
<CryptoStatusPanel />
<DegradationStatusPanel />
```

这是约 2 行的改动。

---

### 4.3 不需要改的文件

| 文件 | 原因 |
|---|---|
| `openamp_mock/degradation_engine.py` | 已完成，不改 |
| `openamp_mock/tests/test_degradation_engine.py` | 已完成，不改 |
| `openamp_mock/__init__.py` | 已完成，不改 |
| `cockpit_native/adapter.py` | 已完成 native 侧集成，不改 |
| `cockpit_native/qt_app.py` | 已完成 native 侧，不改 |
| `cockpit_desktop/src/renderer/src/hooks/useCryptoStatus.ts` | 复用现有 hook 即可，不改 |
| `cockpit_desktop/src/renderer/src/api/client.ts` | `getCryptoStatus()` 已有，不改 |
| `cockpit_desktop/src/renderer/src/components/dashboard/CryptoStatusPanel/` | 不往里面加内容 |
| `cockpit_desktop/src/renderer/src/components/dashboard/MinimalStatusPanel/` | 不改 |
| `scripts/openamp_rpmsg_bridge.py` | 不改 |
| 所有 RTOS / 固件代码 | 不改 |

---

## 5. 数据流

```
                             后端 (Python)
                        ┌─────────────────────────┐
                        │ DashboardState           │
                        │   ._degradation_engine   │
                        │     .snapshot()           │
                        │         ↓                 │
                        │ get_crypto_status()       │
                        │   return {                │
                        │     ...existing fields,   │
                        │     "degradation": {...}  │
                        │   }                       │
                        └──────────┬──────────────┘
                                   │ HTTP GET /api/crypto-status
                                   │ (每 2 秒)
                        ┌──────────▼──────────────┐
                        │ 前端                      │
                        │                          │
                        │ useCryptoStatus() hook   │
                        │   → data.degradation     │
                        │         ↓                │
                        │ DegradationStatusPanel   │
                        │   读 data.degradation    │
                        │   渲染退化状态卡片        │
                        └──────────────────────────┘
```

## 6. 组件流

```
DashboardPageMinimal.tsx
  └─ rightPanel
       ├─ FlightPanel
       ├─ MinimalStatusPanel
       ├─ CryptoStatusPanel       ← useCryptoStatus() (2s 轮询)
       └─ DegradationStatusPanel  ← 同一个 useCryptoStatus() hook
                                     读取 data.degradation 子字段
```

> [!IMPORTANT]
> `DegradationStatusPanel` 内部直接调用 `useCryptoStatus()`——React Query 会自动复用同一个 `['crypto-status']` query key 的缓存，**不会产生重复请求**。这是 React Query 的标准 cache sharing 机制。

---

## 7. 关键设计决策回答

| 问题 | 回答 |
|---|---|
| 退化状态放在哪个面板/区域？ | 右侧面板底部，在 CryptoStatusPanel 之后，独立卡片 |
| 复用 CryptoStatusPanel 还是独立？ | **独立组件**，但视觉风格完全对齐（共用设计 token） |
| 前端轮询挂在哪个 hook？ | 复用 `useCryptoStatus`，不新建 hook |
| 后端补字段到哪个接口？ | `/api/crypto-status`（`get_crypto_status()` 返回值追加 `degradation` 字段） |
| 为什么选这个接口？ | 已有 2s 轮询；退化与加密通道同属通信链路保障语义层 |
| 需要哪些前端类型？ | `DegradationSnapshot` 类型定义，加入 `crypto.ts` |
| 需要哪些 API client 改动？ | 无——`getCryptoStatus()` 已有，类型自动包含新字段 |
| 需要组件测试或页面测试？ | 当前 Electron 侧无测试文件先例；如需要可后补 vitest 组件测试 |

---

## 8. 测试与验收方式

### 8.1 后端验证

```bash
# 确保 DegradationEngine 单测仍通过
cd /home/tianxing/tvm_metaschedule_execution_project
python3 -m unittest openamp_mock.tests.test_degradation_engine

# 启动后端，验证接口返回含 degradation 字段
python3 session_bootstrap/demo/openamp_control_plane_demo/server.py --port 8079 &
curl -s http://127.0.0.1:8079/api/crypto-status | python3 -m json.tool | grep -A 15 '"degradation"'
```

预期输出应包含：

```json
"degradation": {
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

### 8.2 前端验证

```bash
cd /home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop
npm run dev
```

在浏览器/Electron 窗口中验证：
1. 右侧面板底部出现「退化保底状态」卡片
2. 显示当前模式 `FULL_FRAME`（绿色 dot）
3. 显示载荷策略 `full_latent`
4. 链路状态显示「正常」
5. 卡片每 2 秒自动刷新（观察网络面板 `/api/crypto-status` 请求，response 中含 `degradation`）

### 8.3 TypeScript 编译

```bash
cd /home/tianxing/tvm_metaschedule_execution_project/cockpit_desktop
npx tsc --noEmit
```

确认零类型错误。

---

## 9. 明确的非目标（Scope Boundary）

以下内容**不在本方案范围内**，避免 scope creep：

- ❌ 不重新设计退化引擎算法
- ❌ 不修改 openamp_mock 已有代码
- ❌ 不修改 cockpit_native 已有代码
- ❌ 不新建独立 HTTP 路由（复用 `/api/crypto-status`）
- ❌ 不做 USRP 真实链路对接（引擎初始化为默认 FULL_FRAME 静态状态）
- ❌ 不涉及飞腾派连接、SSH、板端部署
- ❌ 不重做 dashboard 整体布局
- ❌ 不改 DashboardPageMinimal 已有的左侧面板
- ❌ 不给退化面板加交互按钮（只读展示）
- ❌ 不新建前端路由或页面

---

## 10. 风险与注意事项

| 风险 | 缓解措施 |
|---|---|
| server.py import `openamp_mock` 时 PYTHONPATH 不对 | Electron 启动后端时已有 `PYTHONPATH` 设置逻辑（`pythonManager.ts`）；如需补充，在 Electron 主进程 spawn 时追加项目根目录到 `PYTHONPATH` |
| `DegradationEngine` 依赖 `openamp_mock.link_health` 和 `openamp_mock.protocol` | 这些模块已存在且无外部依赖（纯 Python），不需要额外安装包 |
| server.py 已有 6663 行，改动需谨慎 | 所有改动限制在 2 处：`__init__` 加一行 + `get_crypto_status` 加字段；不重构 |
| 当前 degradation engine 处于初始状态（FULL_FRAME），没有真实链路驱动 | 这是预期行为——展示"初始全功能状态"本身就是正确的；后续接 USRP 后自动进入动态退化 |
| Electron 侧当前无前端测试先例 | 不强制补测试，但建议后续补 vitest 组件渲染测试 |

---

## 11. 文件影响汇总

| 操作 | 文件路径 |
|---|---|
| **修改** | `session_bootstrap/demo/openamp_control_plane_demo/server.py`（2 处：import + get_crypto_status） |
| **修改** | `cockpit_desktop/src/renderer/src/api/types/crypto.ts`（追加 `DegradationSnapshot` 类型 + `CryptoStatusResponse.degradation` 字段） |
| **修改** | `cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx`（右侧面板追加 `DegradationStatusPanel`，约 2 行） |
| **新增** | `cockpit_desktop/src/renderer/src/components/dashboard/DegradationStatusPanel/DegradationStatusPanel.tsx` |
| **新增** | `cockpit_desktop/src/renderer/src/components/dashboard/DegradationStatusPanel/DegradationStatusPanel.module.css` |
| **新增** | `cockpit_desktop/src/renderer/src/components/dashboard/DegradationStatusPanel/index.ts` |
| **不改** | 其余所有文件 |

---

## 12. 执行检查清单

- [ ] server.py：import `DegradationEngine`
- [ ] server.py：`DashboardState.__init__` 中 `self._degradation_engine = DegradationEngine()`
- [ ] server.py：`get_crypto_status()` 返回值追加 `"degradation": self._degradation_engine.snapshot()`
- [ ] crypto.ts：新增 `DegradationSnapshot` 类型
- [ ] crypto.ts：`CryptoStatusResponse` 追加 `degradation?: DegradationSnapshot | null`
- [ ] 新建 `DegradationStatusPanel/DegradationStatusPanel.tsx`
- [ ] 新建 `DegradationStatusPanel/DegradationStatusPanel.module.css`
- [ ] 新建 `DegradationStatusPanel/index.ts`
- [ ] DashboardPageMinimal.tsx：import 并放置 `DegradationStatusPanel`
- [ ] `curl /api/crypto-status` 验证返回值含 `degradation` 字段
- [ ] `npm run dev` 验证前端渲染正确
- [ ] `npx tsc --noEmit` 零类型错误
- [ ] 确认 `openamp_mock` 全量测试不回归
