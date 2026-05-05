# 退化路径状态接入 Electron Demo — 基于 OpenAMP 控制面的诚实方案

## 结论摘要

**在不改 OpenAMP 控制源码的前提下，无法诚实地展示真正的 FULL_FRAME / ROI_ONLY / ALERT_ONLY 退化路径状态。**

原因：现有 STATUS_RESP 帧中**不包含 `allowed_mode` / `current_mode` / `service_mode` 字段**。guard.py 内部虽然维护了 `self.allowed_mode` 和 `self.current_mode`（L39-40），但这一内部状态**从未在 `_send_status()` 方法（L209-224）中暴露给上位机**。上位机通过 RPMsg bridge 拿到的 STATUS_RESP 只有 6 个字段：`guard_state`、`active_job_id`、`last_fault_code`、`heartbeat_ok`、`sticky_fault`、`total_fault_count`。

因此，本方案采用**方案 C**：在 server.py / Electron 侧增加一层派生逻辑，基于现有可观测的控制面信号映射出一个"推断退化态势"，并在 UI 中**诚实标注其为推断值而非板端回报**。

---

## 1. 背景与目标

### 目标

在 Electron demo 的仪表盘中展示「当前系统退化成什么样子」，仅做**状态展示**，不触发任何自动动作。

### 这不是什么

- 不是真正的退化路径控制（不改 payload 发送行为）
- 不是真正的 FULL_FRAME → ROI_ONLY 自动切换
- 不是 USRP 物理链路感知
- 不是新协议设计

---

## 2. 当前真实边界

### 2.1 不能动的文件（硬约束）

| 文件 | 行数 | 根本原因 |
|---|---|---|
| `openamp_mock/protocol.py` | 237 | 协议帧定义，不改 |
| `openamp_mock/guard.py` | 485 | SafetyGuard 状态机，不改 |
| `openamp_mock/orchestrator.py` | — | 编排器，不改 |
| `scripts/openamp_rpmsg_bridge.py` | 2930 | 真机桥接，不改 |
| RTOS / 固件代码 | — | 完全不涉及 |
| 现有控制协议帧定义 | — | 不新增消息类型 |

### 2.2 可以动的文件

| 文件 | 改动范围 |
|---|---|
| `server.py` | 增加派生逻辑 |
| `cockpit_desktop/src/renderer/src/api/types/crypto.ts` | 增加类型 |
| `cockpit_desktop/src/renderer/src/components/dashboard/DegradationStatusPanel/*` | 新建或修改组件 |
| `cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx` | 放置组件 |

### 2.3 不引入的东西

- ❌ `/tmp/usrp_link_health.json` 或任何文件轮询
- ❌ USRP / link_health 作为输入源
- ❌ 独立于 OpenAMP 控制面的新状态机
- ❌ Tailscale 作为业务状态源
- ❌ 新的 HTTP 路由

---

## 3. 现有 OpenAMP 控制逻辑中已经可观测的状态

### 3.1 通过 STATUS_RESP 帧可获得的字段

来源：[guard.py `_send_status()` L209-224](file:///home/tianxing/tvm_metaschedule_execution_project/openamp_mock/guard.py#L209-L224)

```python
payload={
    "guard_state": guard_state,           # BOOT | READY | JOB_ACTIVE | WAIT_DONE | DENY_PENDING | FAULT_LATCHED
    "active_job_id": self.active_job_id,  # 0 或正整数
    "last_fault_code": int(self.last_fault_code),  # FaultCode 枚举值
    "heartbeat_ok": int(self.state is GuardState.JOB_ACTIVE),  # 0 或 1
    "sticky_fault": int(self.sticky_fault),  # 0 或 1
    "total_fault_count": self.total_fault_count,  # 累计故障计数
}
```

这 6 个字段通过 `fault_injector.py` → `status_fields_from_response()` 解析，存储在 `server.py` 的 `self._last_control_status` 中，最终通过 `_control_plane_summary()` 注入到 `/api/crypto-status` 返回值。

### 3.2 通过 event spine 可获得的事件计数

来源：[server.py `_control_plane_summary()` L3020-3035](file:///home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/server.py#L3020-L3035)

- `HEARTBEAT_OK` / `HEARTBEAT_LOST` 事件计数
- `SAFE_STOP_TRIGGERED` / `SAFE_STOP_CLEARED` 事件计数
- `JOB_SUBMITTED` / `JOB_ADMITTED` / `JOB_REJECTED` 事件计数
- soft recover 尝试记录

### 3.3 通过 FaultCode 枚举可区分的故障类型

来源：[protocol.py L66-86](file:///home/tianxing/tvm_metaschedule_execution_project/openamp_mock/protocol.py#L66-L86)

其中与退化有关的：
- `FaultCode.LINK_DEGRADED = 17`（信息性：链路质量低于阈值）
- `FaultCode.LINK_LOST = 18`（严重：RX 失锁，触发 SAFE_STOP）
- `FaultCode.HEARTBEAT_TIMEOUT = 3`（心跳超时）

### 3.4 guard.py 内部**有但未暴露**的状态

| 字段 | 位置 | 描述 | 是否在 STATUS_RESP 中暴露 |
|---|---|---|---|
| `self.allowed_mode` | L39 | 守卫允许的服务模式 | ❌ **不暴露** |
| `self.current_mode` | L40 | 当前服务模式 | ❌ **不暴露** |
| `self.mode_log` | L41 | 模式切换日志 | ❌ **不暴露** |
| `self._degrade_window_count` | L42 | 降级滞回计数 | ❌ **不暴露** |
| `self._upgrade_window_count` | L43 | 升级滞回计数 | ❌ **不暴露** |

**这是核心问题**：guard.py 的 `_send_status()` 方法（L209-224）只发送了 6 个字段，完全没有包含任何 `ServiceMode` 相关信息。即使 guard.py 内部的 inner mode state machine 已经维护了完整的退化逻辑（L365-484），但这些状态**对上位机是不可见的**。

---

## 4. 核心判断：现有状态是否足以支撑退化展示

### 4.1 能否诚实展示 FULL_FRAME / ROI_ONLY / ALERT_ONLY？

**不能。**

理由：
1. STATUS_RESP 不含 `allowed_mode` / `current_mode` — 上位机**无法从板端拿到当前服务模式**
2. `_handle_link_health_msg()` 和 MODE_DIRECTIVE 消息（L430-484）是 guard → linux 的方向，但上位机侧的 `server.py` / `fault_injector.py` **从未发送 LINK_HEALTH 消息**，也**从未解析 MODE_DIRECTIVE**
3. `status_fields_from_response()`（fault_injector.py L70-81）只解析 6 个字段，不含 mode

所以在当前实现中，**整条 "LINK_HEALTH → guard 内部模式切换 → MODE_DIRECTIVE" 链路对 Electron demo 来说是完全不可达的**。即使 guard.py 已经有了完整的退化逻辑，server.py 也看不到。

### 4.2 能推断出什么？

基于已有状态，可以做的**诚实推断**：

| 现有可观测信号 | 可推断的"退化态势" |
|---|---|
| `guard_state=READY`, `last_fault_code=NONE`, `heartbeat_ok=1` | 全功能（正常运行） |
| `guard_state=READY`, `last_fault_code=LINK_DEGRADED(17)` | 曾出现链路退化（但已恢复） |
| `guard_state=FAULT_LATCHED`, `last_fault_code=HEARTBEAT_TIMEOUT(3)` | 心跳超时 → 安全停机 |
| `guard_state=FAULT_LATCHED`, `last_fault_code=LINK_LOST(18)` | 链路丢失 → 安全停机 |
| `SAFE_STOP_TRIGGERED` 事件计数 > 0 | 系统经历过紧急停机 |
| `sticky_fault=1` | 故障锁定未清除 |

**关键区别**：这些推断给出的是**「系统处于什么安全状态」**（正常 / 故障锁定 / 已恢复），而不是**「数据面正在用什么发送策略」**（FULL_FRAME / ROI_ONLY / ALERT_ONLY）。

---

## 5. 最诚实的替代展示方案

### 5.1 核心理念：展示"控制面健康态势"而非"发送模式"

既然无法从板端获取真实的 `ServiceMode`，就**不要假装能展示它**。改为展示"基于现有控制面信号推断的系统健康态势"，这是一个**诚实的派生视图**。

### 5.2 三级态势映射

在 `server.py` 中（**不改 guard.py**），基于 `_last_control_status` 和 event spine 事件推导一个三级态势：

```
Level 0: NOMINAL（标称运行）
  条件：guard_state ∈ {READY, JOB_ACTIVE}
        且 last_fault_code = NONE 或 FaultCode ≤ 16（非退化相关）
        且 sticky_fault = 0

Level 1: DEGRADED（退化告警）
  条件：last_fault_code = LINK_DEGRADED(17)
        或 heartbeat_lost_count > 0 且 guard 未锁定
        或 total_fault_count > 0 且 guard 已恢复到 READY

Level 2: CRITICAL（严重/安全停机）
  条件：guard_state = FAULT_LATCHED
        或 last_fault_code = LINK_LOST(18)
        或 last_fault_code = HEARTBEAT_TIMEOUT(3) 且 sticky_fault = 1
        或 safe_stop_triggered_count > safe_stop_cleared_count
```

### 5.3 为什么不直接复用 DegradationEngine

之前的 `DegradationEngine`（`openamp_mock/degradation_engine.py`）是一个**独立状态机**，需要 `LinkHealthReport` 作为输入。但在当前约束下：
- 不允许引入 USRP/link_health 文件轮询
- 不允许引入新的链路源

没有任何东西喂给 `DegradationEngine.update()`，所以它永远停在 `FULL_FRAME` 初始状态——这不是错误，但**展示一个永远不变的初始值没有信息量**。

**诚实的做法**是：不用 `DegradationEngine`，而是从现有控制面状态派生。

---

## 6. 精确改动点

### 6.1 后端：server.py

在 `DashboardState` 中新增一个方法：

```python
def _inferred_degradation_posture(self) -> dict[str, Any]:
    """从已有控制面状态推断退化态势（无需改 guard.py）。"""
```

逻辑：
1. 读取 `_last_control_status` 中的 `guard_state`、`last_fault_code`、`sticky_fault`、`total_fault_count`
2. 读取 event spine 中的 `HEARTBEAT_LOST`、`SAFE_STOP_TRIGGERED`、`SAFE_STOP_CLEARED` 计数
3. 按 5.2 的规则输出三级态势

返回值结构：
```python
{
    "posture": "NOMINAL" | "DEGRADED" | "CRITICAL",
    "posture_label": "标称运行" | "退化告警" | "安全停机",
    "source": "inferred_from_control_plane",  # 诚实标注来源
    "basis": {
        "guard_state": "...",
        "last_fault_code": "...",
        "sticky_fault": 0 | 1,
        "heartbeat_lost_count": N,
        "safe_stop_triggered": N,
        "safe_stop_cleared": N,
        "total_fault_count": N,
    },
}
```

注入方式：在 `get_crypto_status()` 返回值中追加 `"degradation_posture": self._inferred_degradation_posture()`。

> [!IMPORTANT]
> 字段名故意用 `degradation_posture` 而非 `degradation`，以区别于之前直接用 `DegradationEngine.snapshot()` 的方案。`posture` 一词明确表达"这是一个推断的态势评估，不是板端回报的真实模式"。

### 6.2 前端：TypeScript 类型

在 `crypto.ts` 中：

```typescript
export type DegradationPosture = {
  /** System posture level: NOMINAL | DEGRADED | CRITICAL */
  posture: 'NOMINAL' | 'DEGRADED' | 'CRITICAL'
  /** Chinese display label */
  posture_label: string
  /** Data source marker: always "inferred_from_control_plane" */
  source: string
  /** Observable basis signals used for inference */
  basis: {
    guard_state: string
    last_fault_code: string
    sticky_fault: number
    heartbeat_lost_count: number
    safe_stop_triggered: number
    safe_stop_cleared: number
    total_fault_count: number
  }
}
```

在 `CryptoStatusResponse` 中追加：
```typescript
degradation_posture?: DegradationPosture | null
```

### 6.3 前端：DegradationStatusPanel 组件

修改现有的 `DegradationStatusPanel` 组件（或重建），使其展示**三级态势**而非三级服务模式：

```
┌─────────────────────────────────────────┐
│ 退化态势                   ● 标称运行     │  ← NOMINAL: 绿色
│─────────────────────────────────────────│
│ 守卫状态    READY                        │
│ 最近故障    NONE                         │
│ 故障锁定    否                           │
│ 心跳丢失    0 次                         │
│ 安全停机    0 次                         │
│ 累计故障    0                            │
│─────────────────────────────────────────│
│ ⓘ 基于控制面信号推断，非板端模式回报       │  ← 诚实标注
└─────────────────────────────────────────┘
```

三种态势的视觉：

| 态势 | 标签 | 颜色 | dot 样式 |
|---|---|---|---|
| NOMINAL | 标称运行 | 绿色 `--color-success` | `dotOk` |
| DEGRADED | 退化告警 | 金色 `#D97706` | `dotWarn` |
| CRITICAL | 安全停机 | 红色 `--color-error` | `dotDanger` + pulse |

底部用灰色小字注明数据来源：「基于控制面信号推断，非板端模式回报」。

### 6.4 不改的文件

| 文件 | 理由 |
|---|---|
| `openamp_mock/protocol.py` | 不改 |
| `openamp_mock/guard.py` | 不改 |
| `openamp_mock/orchestrator.py` | 不改 |
| `openamp_mock/degradation_engine.py` | 保留，但本方案不使用它 |
| `scripts/openamp_rpmsg_bridge.py` | 不改 |
| `cockpit_desktop/src/renderer/src/hooks/useCryptoStatus.ts` | 复用 |
| `cockpit_desktop/src/renderer/src/api/client.ts` | 复用 |
| `CryptoStatusPanel/` | 不改 |
| `MinimalStatusPanel/` | 不改 |

---

## 7. Electron 页面落点

### 放在 CryptoStatusPanel 附近是否合理？

**合理。** 退化态势属于"通信链路保障"语义域，与 ML-KEM 加密通道、控制面守卫状态是同层信息。放在右侧面板 CryptoStatusPanel 之后是逻辑递进。

### 独立 panel 还是并入？

**独立 panel。** 理由：
1. CryptoStatusPanel 已 315 行，职责已满
2. 态势评估是独立功能语义（系统健康评估 vs 加密通道状态）
3. 答辩时可单独展示和讲解
4. 视觉风格对齐但逻辑独立

---

## 8. 与之前方案的差异

| 维度 | 之前方案（已实现但有问题） | 本方案 |
|---|---|---|
| 数据来源 | `DegradationEngine.snapshot()`（独立状态机，需 LinkHealthReport 输入） | 现有控制面 STATUS_RESP + event spine（已有数据） |
| 展示内容 | FULL_FRAME / ROI_ONLY / ALERT_ONLY 三级模式 | NOMINAL / DEGRADED / CRITICAL 三级态势 |
| 诚实程度 | **不诚实** — DegradationEngine 没有输入就永远显示 FULL_FRAME | **诚实** — 基于实际可观测的控制面状态推断 |
| 依赖 | 依赖 `openamp_mock/degradation_engine.py` | 只依赖 `_last_control_status` + event spine |
| 需要新输入源 | 需要 LinkHealthReport（但无来源） | 不需要（复用已有轮询） |

---

## 9. 测试与验收方式

### 9.1 后端验证

```bash
# 不需要独立单测（不新建状态机），但可以验证推断逻辑
curl -s http://127.0.0.1:8079/api/crypto-status | python3 -m json.tool | grep -A 12 '"degradation_posture"'
```

预期：当板子未连接时

```json
"degradation_posture": {
    "posture": "NOMINAL",
    "posture_label": "标称运行",
    "source": "inferred_from_control_plane",
    "basis": {
        "guard_state": "UNKNOWN",
        "last_fault_code": "UNKNOWN",
        ...
    }
}
```

当触发故障注入（如 heartbeat_timeout）后：

```json
"degradation_posture": {
    "posture": "CRITICAL",
    "posture_label": "安全停机",
    ...
}
```

### 9.2 前端验证

1. `npx tsc --noEmit` 零类型错误
2. `npm run dev` 正常渲染
3. 右侧面板底部显示「退化态势」卡片，默认绿色「标称运行」
4. 执行故障注入后，卡片自动变色

### 9.3 回归确认

```bash
python3 -m unittest openamp_mock.tests.test_degradation_engine  # 原单测不受影响
```

---

## 10. 非目标（明确声明）

- ❌ **不做自动切换动作** — 只展示态势，不触发 payload 策略变更
- ❌ **不改 OpenAMP 源码** — `protocol.py`、`guard.py`、`orchestrator.py` 一行不动
- ❌ **不引入新链路源** — 不引入 USRP file polling、link_health JSON、独立状态机
- ❌ **不接 USRP file polling** — 不引入 `/tmp/usrp_link_health.json`
- ❌ **不假装能展示 FULL_FRAME / ROI_ONLY / ALERT_ONLY** — 因为板端 STATUS_RESP 并不包含这些字段
- ❌ **不改 Tailscale 配置** — Tailscale 只是连接路径
- ❌ **不新建 HTTP 路由** — 复用 `/api/crypto-status`
- ❌ **不大改 dashboard 整体布局**

---

## 11. 对之前已实现代码的处理建议

之前已在 server.py 中集成了 `DegradationEngine`，在前端创建了 `DegradationStatusPanel` 展示 FULL_FRAME/ROI_ONLY/ALERT_ONLY。

> [!WARNING]
> 这些代码在技术上是正确的（TypeScript 编译通过、组件能渲染），但在语义上是空洞的——`DegradationEngine` 没有输入源，永远显示初始态 `FULL_FRAME`，这不是在展示系统真实状态，而是在展示一个空壳。

建议：
1. **保留** `openamp_mock/degradation_engine.py` 和其 9 条单测——它是退化决策逻辑的正确实现，将来接 USRP 时可以直接复用
2. **移除** server.py 中对 `DegradationEngine` 的 import 和实例化
3. **重写** `DegradationStatusPanel` 组件为基于 `degradation_posture` 的态势展示
4. **替换** `crypto.ts` 中的 `DegradationSnapshot` 为 `DegradationPosture`

---

## 12. 答辩叙事

接入后可以在答辩中这样讲：

> "我们的 Electron 仪表盘基于 OpenAMP 控制面的真实状态——守卫状态、故障码、心跳丢失计数、安全停机事件——推断出系统当前的退化态势（标称运行 / 退化告警 / 安全停机）。这个态势评估完全建立在已有控制协议暴露的字段之上，不引入任何独立于 OpenAMP 的新输入源。
>
> 当链路质量下降触发心跳丢失或故障码变为 LINK_DEGRADED 时，态势自动变为黄色'退化告警'；当 SAFE_STOP 被触发或链路彻底丢失时，态势变为红色'安全停机'。这与飞腾派 RTOS 从核的安全管控逻辑是一致的、互补的。"
