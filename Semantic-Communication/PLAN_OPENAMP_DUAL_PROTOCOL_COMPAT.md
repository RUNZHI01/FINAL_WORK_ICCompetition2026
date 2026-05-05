# OpenAMP 双协议兼容演进方案

## 结论摘要

**在当前源码基础上，老协议与新协议完全适合做成双轨并存方案。**

三个关键事实支撑这一判断：

1. **MessageType 空间已经天然分区**：老协议占 `0x01-0x10`（含签名准入 `0x0C-0x10` 和加密 `0x20`），新协议占 `0x60-0x62`（`LINK_HEALTH`、`MODE_DIRECTIVE`、`MODE_ACK`），两者在协议帧层面**零重叠**。
2. **guard.py 已经内建了双轨处理**：`handle()` 方法（L56-83）已经同时 dispatch 老协议消息（JOB_REQ、HEARTBEAT、STATUS_REQ 等）和新协议消息（LINK_HEALTH、MODE_ACK），内部的 inner mode state machine（L38-53, L365-484）与外部 guard state machine 完全正交。
3. **RPMsg bridge 对新帧类型透明容错**：`parse_frame()`（L306-370）用 if/elif 链分派已知类型，未知类型只保留 `payload_hex`，不会报错，也不会破坏已有帧的解析——未来添加新类型的解析只需增加 elif 分支。

**关键前提**：
- STATUS_RESP 的 6 字段二进制结构**绝对不改**——这是老协议 live contract 的刚性边界
- 新协议状态通过**独立通路**暴露，不污染老协议的任何已有字段或合同

**最大风险**：
- 当前 RTOS 固件不认识 `0x60-0x62` 帧，真机环境下发送 LINK_HEALTH 会被忽略（不会崩溃，但也不会触发 mode 切换）——这意味着新协议**首先只能在 mock 层和 server 层落地**，真机落地需要固件配合

---

## 1. 当前真实现状

### 1.1 老协议已落地到什么程度

| 维度 | 状态 | 证据 |
|---|---|---|
| 协议帧定义 | ✅ 稳定 | `protocol.py` L37-53 共 11 种老 MessageType |
| mock 层实现 | ✅ 完整 | `guard.py` + `orchestrator.py` 全链路 |
| 真机桥接 | ✅ 稳定 | `openamp_rpmsg_bridge.py` 2930 行，支持所有老帧的 binary 编解码 |
| 故障注入 | ✅ 收口 | `fault_injector.py` 支持 FIT-01/02/03，均真机 PASS |
| 证据包 | ✅ 正式 | `evidence_package_20260315/`，verdict = PASS |
| Electron 展示 | ✅ 稳定 | `CryptoStatusPanel` 展示 guard_state / fault_code / heartbeat / fault_count |
| 论文口径 | ✅ 写实 | 技术文档 3.3 节「五类控制消息 + 三项 FIT」 |

**老协议的 live contract 边界**：STATUS_RESP 返回 6 个 uint32 字段，通过 `STATUS_RESP_STRUCT = struct.Struct("<IIIIII")` 严格打包。这个二进制格式已经被：
- RTOS 固件的 C 代码写死
- `openamp_rpmsg_bridge.py` 的 `parse_status_resp_payload()` 写死
- `fault_injector.py` 的 `status_fields_from_response()` 写死
- `server.py` 的 `_control_plane_summary()` 消费

**这 4 层解析链是不可轻易动的硬边界。**

### 1.2 新协议已存在到什么程度

| 维度 | 状态 | 位置 |
|---|---|---|
| MessageType 定义 | ✅ 已有 | `protocol.py` L55-58：`LINK_HEALTH=0x60`, `MODE_DIRECTIVE=0x61`, `MODE_ACK=0x62` |
| FaultCode 扩展 | ✅ 已有 | `protocol.py` L84-86：`LINK_DEGRADED=17`, `LINK_LOST=18` |
| ServiceMode 枚举 | ✅ 已有 | `protocol.py` L24-34：`FULL_FRAME=0`, `ROI_ONLY=1`, `ALERT_ONLY=2` |
| guard 侧消费 | ✅ 已实现 | `guard.py` L79-83 dispatch + L369-484 完整内部状态机 |
| orchestrator 侧跟踪 | ✅ 已实现 | `orchestrator.py` L31-33 + L247-260 `_handle_mode_directive()` |
| bridge 侧帧编解码 | ❌ 未实现 | `openamp_rpmsg_bridge.py` 无 LINK_HEALTH/MODE_DIRECTIVE 的 struct 定义和解析 |
| fault_injector 侧驱动 | ❌ 未实现 | `fault_injector.py` 无发送 LINK_HEALTH 的流程 |
| server 侧暴露 | ❌ 未实现 | `server.py` 不消费 guard 的 `allowed_mode`/`current_mode` |
| Electron 侧展示 | ❌ 未实现 | 前端无 service mode 展示 |
| RTOS 固件 | ❌ 不认识 | 固件不解析 0x60-0x62 帧 |
| 论文 / 证据 | ❌ 未纳入 | 不在当前答辩 claim 范围内 |

**结论**：新协议在 `protocol.py` / `guard.py` / `orchestrator.py` 层已经是**功能完整的 mock 实现**，但在 bridge → fault_injector → server → Electron 这条 "live 暴露链" 上是**完全断裂的**。

### 1.3 demo 当前真实能看到什么

| 能看到 | 看不到 |
|---|---|
| guard_state（READY / JOB_ACTIVE / FAULT_LATCHED 等） | current_mode（FULL_FRAME / ROI_ONLY / ALERT_ONLY） |
| last_fault_code（NONE / HEARTBEAT_TIMEOUT / ARTIFACT_SHA_MISMATCH 等） | allowed_mode |
| heartbeat_ok / sticky_fault / total_fault_count | mode_log / mode_history |
| SAFE_STOP 事件 | MODE_DIRECTIVE 事件 |
| event spine 的老协议事件计数 | 任何与 ServiceMode 相关的信息 |

---

## 2. 推荐演进路线

### 推荐方案：STATUS_RESP 不动 + 独立 mode snapshot 通路

```
┌──────────────────────────────────────────┐
│ protocol.py / guard.py / orchestrator.py │
│  (已有双轨逻辑，不改)                      │
└───────┬──────────────────────┬───────────┘
        │ 老协议                │ 新协议
        │ STATUS_RESP          │ guard.allowed_mode
        │ 6 字段不变            │ guard.current_mode
        ▼                      │ guard.mode_log
┌───────────────┐              ▼
│ bridge 层      │     ┌───────────────────┐
│ 不改           │     │ server.py          │
│ 继续解析老帧   │     │ 新增: mock 层读取    │
└───────┬───────┘     │ guard.current_mode │
        │              │ / orchestrator    │
        │              │ .current_service  │
        ▼              │ _mode             │
┌───────────────┐     └────────┬──────────┘
│ /api/crypto-  │              │
│ status        │              ▼
│ 老字段不变     │     ┌───────────────────┐
│ + service_    │     │ 新增嵌套对象:       │
│   mode{}      │     │ "service_mode": {  │
│               │     │   mode, strategy,  │
│               │     │   transitions...   │
│               │     │ }                  │
└───────┬───────┘     └────────┬──────────┘
        │                      │
        ▼                      ▼
┌───────────────┐     ┌───────────────────┐
│ CryptoStatus  │     │ ServiceMode       │
│ Panel         │     │ Panel (新增)       │
│ 老控制面状态   │     │ 服务模式状态       │
└───────────────┘     └───────────────────┘
```

### 为什么不选其他方案

| 备选方案 | 为什么不选 |
|---|---|
| **A. 扩展 STATUS_RESP 结构** | `STATUS_RESP_STRUCT = struct.Struct("<IIIIII")` 是 6 × uint32 固定格式。改成 8 个字段意味着：①RTOS 固件 C 代码必须同步改，②bridge 的 parse 必须改，③所有已有 evidence 的帧格式都变了。撼动老协议 live contract 的成本太高，收益不相称。 |
| **B. 新建 STATUS_EX_REQ/RESP (0x70/0x71)** | 技术上可行，但需要 RTOS 固件支持新帧类型。当前固件不认识 0x6x 更别说 0x7x。而且纯 mock 场景下完全不需要新帧——guard 的 `current_mode` 本身就是 Python 属性，直读即可。 |
| **C. 新建独立 HTTP 路由 `/api/service-mode`** | 可行但没必要。service mode 与控制面是同一个 guard 实例的两面，挂到 `/api/crypto-status` 的新嵌套对象里更符合 "一次轮询拿到全量状态" 的前端模式。 |

---

## 3. 备选路线对比

### 备选 A：扩展 STATUS_RESP

```
STATUS_RESP (v2) = | guard_state | job_id | fault_code | heartbeat_ok | sticky | fault_cnt | allowed_mode | mode_transitions |
```

| 优点 | 缺点 |
|---|---|
| 帧级集成，无需独立状态通路 | 破坏 bridge `STATUS_RESP_STRUCT` 的 6×u32 固定格式 |
| 将来真机天然可用 | RTOS 固件必须改 C struct，重新编译部署 |
| | 已有 evidence 的帧格式全部失效 |
| | fault_injector 的 `status_fields_from_response()` 必须兼容新旧格式 |

**trade-off**：最终方案如果要推到真机 live，确实需要在 STATUS_RESP 中增加 mode 字段。但当前阶段（初赛答辩前）不应动这一步，应该先在 mock/server 层把展示链路通了，等固件侧准备好再切。

### 备选 B：保留 STATUS_RESP 不变 + 新增 mode snapshot（推荐）

| 优点 | 缺点 |
|---|---|
| 老协议零回归风险 | mock 与 live 的 service mode 来源不同（demo 模式直读 Python 对象，live 模式需新帧） |
| 不改 bridge / 不改固件 / 不改 evidence | 将来推真机时还是要扩帧 |
| server 侧改动最小 | |
| 前端可立即展示 | |

### 备选 C：server 层纯派生（从老字段推断 mode）

| 优点 | 缺点 |
|---|---|
| 完全不碰 mock 层 | 不诚实：从 guard_state+fault_code 推断 FULL_FRAME/ROI_ONLY 是在假装有能力 |
| | 推断逻辑与真实 mode 状态机无关 |
| | 在答辩中经不起追问 |

**否决理由**：方案 C 在上一版分析中已经被提出过作为 "最诚实的替代"，但现在重新审视需求后发现——guard.py 里已经有了完整的 inner mode state machine，问题不在于"没有状态机"而在于"状态没暴露"，那就把暴露链路补上，不需要用推断来冒充。

---

## 4. 协议兼容性分析

### 4.1 MessageType 共存

```
老协议区间: 0x01-0x10 (JOB, HEARTBEAT, STATUS, SAFE_STOP, RESET, SIGNED_ADMISSION)
加密扩展:   0x20      (ENCRYPTED_CTRL)
新协议区间: 0x60-0x62 (LINK_HEALTH, MODE_DIRECTIVE, MODE_ACK)
```

**完全不重叠。** guard.py 的 `handle()` 方法通过逐一匹配 `msg_type` 来 dispatch，新帧只是 elif 链的额外分支，不影响老分支的任何逻辑。

### 4.2 guard 状态机双层正交性

```
外层 FSM（老协议）:
  BOOT → READY → JOB_ACTIVE → (WAIT_DONE | FAULT_LATCHED) → READY

内层 FSM（新协议）:
  FULL_FRAME ↔ ROI_ONLY ↔ ALERT_ONLY
  仅在 外层 == JOB_ACTIVE 时活跃
  作业结束时自动 reset 到 FULL_FRAME
```

两层之间的唯一耦合点：
- `handle_link_health()` 检查 `self.state is not GuardState.JOB_ACTIVE`，如果不在 JOB_ACTIVE 就直接 return（L380-381）
- `_clear_active_job()` 将 mode 重置为 FULL_FRAME（L360-363）
- link lost 触发 `_trigger_safe_stop()`，内层 mode 通过外层 SAFE_STOP 间接与老协议产生关联（L384-391）

**这些耦合都是单向的（外层约束内层），不可能让内层状态机污染外层状态机的行为。** 老协议的 guard_state、fault_code、heartbeat_ok 完全不受新协议影响。

### 4.3 bridge 容错性

`parse_frame()` 在 elif 链末尾没有 else raise，未知帧类型直接滑过，`result["is_protocol_frame"] = True` 且 `result["payload_hex"]` 保留原始数据。所以：
- 如果新帧从板子发出（将来固件支持 MODE_DIRECTIVE），bridge 不会崩溃，只是不解析 payload
- 将来添加解析只需加 elif + struct 定义，不改任何已有逻辑

### 4.4 FaultCode 兼容性

新增的 `LINK_DEGRADED=17` 和 `LINK_LOST=18` 不与任何已有 fault code 冲突（最大已有值 `MANIFEST_CONTRACT_MISMATCH=16`）。`safe_fault_name()` 通过 `FaultCode(value).name` 做枚举查找，新 code 自动有名字。

---

## 5. STATUS_RESP 的边界判断

### 明确结论：STATUS_RESP 当前不应该改

理由：

1. **二进制结构刚性**：`struct.Struct("<IIIIII")` 是精确 24 字节。RTOS 固件 C 侧也是 24 字节 packed struct。改成 28 或 32 字节意味着固件重编译+重部署+重验证。

2. **证据链完整性**：evidence package 里所有 STATUS_RESP 帧的 hex 都是 24 字节。如果改了格式，需要重新跑一遍所有 FIT 测试并重写证据包。

3. **解析链太长**：bridge → fault_injector → server → frontend，4 层都硬编码了 6 字段的解析逻辑。

4. **将来可以安全扩展**：等固件侧真正支持 mode 时，可以定义 `STATUS_RESP_V2 = 0x19` 作为新帧类型（而不是复用 `0x09`），或者通过 `version` 字段区分。但这不是当前要做的事。

### 新协议状态的暴露方式

在 **demo/mock 模式**下：

```python
# server.py 中直接从 mock 层读取
def _service_mode_snapshot(self) -> dict[str, Any]:
    """从 mock guard/orchestrator 直读 inner mode state。"""
    # 如果有 mock guard 实例（demo 模式下使用 DegradationEngine 或直接用 guard 内部状态）
    return {
        "current_mode": self._guard.current_mode.name if self._guard else "UNKNOWN",
        "allowed_mode": self._guard.allowed_mode.name if self._guard else "UNKNOWN",
        "payload_strategy": ...,
        "mode_transitions": len(self._guard.mode_log) if self._guard else 0,
        "last_transition": ...,
        "source": "mock_guard_internal",  # 诚实标注来源
    }
```

在 **live/真机模式**下（将来）：

```python
# 通过新的 bridge 帧类型（将来实现）或 STATUS_RESP_V2 获取
# 当前返回 "source": "not_available_on_live"
```

---

## 6. server / API 层承接方案

### 在 `/api/crypto-status` 中新增嵌套对象

```json
{
  // 老控制面状态 —— 保持原样不动
  "control_guard_state": "READY",
  "control_last_fault_code": "NONE",
  "control_heartbeat_ok": 1,
  "control_total_fault_count": 0,
  // ... 所有已有 control_ 前缀字段 ...

  // 新协议状态 —— 独立嵌套对象
  "service_mode": {
    "current_mode": "FULL_FRAME",
    "current_mode_value": 0,
    "allowed_mode": "FULL_FRAME",
    "payload_strategy": "full_latent",
    "mode_transitions": 0,
    "last_transition": null,
    "source": "mock_guard_internal"
  }
}
```

**为什么是嵌套对象而非平铺字段**：
- 避免命名空间冲突（`control_*` vs `service_mode.*`）
- 前端可以用一个 TypeScript type 整体接收
- 将来 source 从 `mock_guard_internal` 切到 `live_bridge` 时，只改内部实现不改接口结构

**为什么不新开路由**：
- `useCryptoStatus` hook 已经以 2s 间隔轮询 `/api/crypto-status`
- React Query 的 cache sharing 让多个 Panel 共享同一次请求
- 加一个字段比加一个路由+一个 hook 简单得多

---

## 7. 双协议在 demo 中的呈现建议

### 7.1 两个独立 Panel，明确命名区分

```
右侧面板（rightPanel）
├── FlightPanel           — 战术地图
├── MinimalStatusPanel    — 板卡遥测
├── CryptoStatusPanel     — 控制面状态（老协议）      ← 已有，不改
│     title: "OpenAMP 控制面"
│     展示: guard_state, fault_code, heartbeat, fault_count
│
└── ServiceModePanel      — 服务模式状态（新协议）    ← 新增
      title: "服务模式"
      展示: current_mode, payload_strategy, mode_transitions
```

### 7.2 为什么必须分开

1. **语义层次不同**：
   - `guard_state=READY` → "RTOS 从核的安全守卫处于就绪态"（安全管控层）
   - `service_mode=FULL_FRAME` → "当前数据面采用全图发送策略"（业务 QoS 层）
   - 这两者完全正交——guard 可以在 READY 状态下 mode 也在 FULL_FRAME，也可以在 JOB_ACTIVE 状态下 mode 变为 ROI_ONLY

2. **时间线不同**：
   - guard_state 随作业生命周期变化：READY → JOB_ACTIVE → READY
   - service_mode 随链路质量变化：FULL_FRAME → ROI_ONLY → ALERT_ONLY
   - 两者变化节奏和触发条件完全不同

3. **答辩表述清晰**：
   - "上面这块是安全控制面——准入、心跳、安全停机，这是 RTOS 从核负责的"
   - "下面这块是服务模式——全图、ROI、告警，这是链路质量驱动的 QoS 策略"

### 7.3 如何解释给评委

> "我们的控制面有两层：
>
> **安全控制层**（老协议）——RTOS 从核通过 STATUS/JOB/HEARTBEAT/SAFE_STOP 五类消息管理作业准入、心跳监护和安全停机。这一层的状态机保障系统'可控、可停、可恢复'。
>
> **服务模式层**（新协议）——在安全控制面基础上，系统根据链路质量动态调整数据面发送策略：全图模式（完整语义张量）、ROI 模式（局部区域推理）、告警模式（仅元信息）。这一层的状态机保障系统在弱网退化时仍能维持有效服务。
>
> 两层职责正交：安全控制管'能不能跑'，服务模式管'以什么质量跑'。"

---

## 8. ROI_ONLY 的真实工程语义

### 8.1 现状诚实评估

| 路线 | 推理引擎 | 输入约束 | 当前状态 |
|---|---|---|---|
| FULL_FRAME | TVM | 固定 `(1,32,32,32)` | ✅ 已通过 300 张真机验证，230ms/张 |
| ROI_ONLY | MNN | 动态形状 | ✅ MNN 已通过 300 张不同分辨率验证，327ms/张 |
| ALERT_ONLY | 无推理 | 仅元数据 | ⚪ 纯控制面状态，无推理负载 |

### 8.2 ROI_ONLY 的推荐工程定义

不要继续使用旧文案"只传 ROI latent"——这暗示上位机发送行为的改变，但当前上位机语义编码流程是固定的。

更准确的定义：

> **ROI_ONLY = 板端局部区域推理模式**
>
> - 利用 MNN 的动态形状输入能力，只对感兴趣的局部区域做推理
> - 上位机负责：裁切或标注 ROI → 只编码局部区域的 latent → 发送到板端
> - 板端负责：MNN 接收动态形状的 latent → 局部重建
> - 带宽收益：从全图 `(1,32,32,32)` ≈ 128KB 降到例如 `(1,32,16,16)` ≈ 32KB
> - 推理收益：MNN 计算量与输入分辨率成正比，小区域更快

### 8.3 与当前 MNN 能力的对齐

技术文档 4.2 节已经证实：

> "MNN 动态尺寸路线支持 300 张不同分辨率图像的直接处理，端到端总耗时 98.2 秒（平均 327.3 ms/张）"

这说明 MNN 已经具备处理非标准尺寸输入的能力。ROI_ONLY 模式可以自然地映射到：
- 上位机裁切 ROI 区域 → 生成小尺寸 latent
- MNN 接收动态形状 latent → 完成局部重建

### 8.4 需要哪些数据面前提 vs 先控制面表达

| 维度 | 控制面（先做） | 数据面（后做） |
|---|---|---|
| 模式声明 | ✅ guard 下发 MODE_DIRECTIVE(ROI_ONLY) | — |
| ROI 坐标传递 | — | 需在 JOB_REQ 或单独帧中携带 ROI bbox |
| 上位机裁切 | — | Encoder 需支持可变输入尺寸或 ROI 裁切 |
| MNN 调用 | — | 已具备动态输入能力，需在 runner 中增加路由 |
| 板端结果拼接 | — | 将局部重建结果贴回全图坐标 |

**本轮只做控制面表达**（让 demo 能展示 "当前模式是 ROI_ONLY"），数据面落地留后续。

---

## 9. 精确改动点

### 9.1 本轮改动的文件

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `server.py` | **修改** | 新增 `_service_mode_snapshot()` 方法；在 `get_crypto_status()` 返回值中注入 `"service_mode"` 嵌套对象 |
| `crypto.ts` | **修改** | 新增 `ServiceModeSnapshot` TypeScript 类型；在 `CryptoStatusResponse` 中增加 `service_mode?` 字段 |
| `ServiceModePanel/` | **新建** | 新组件：展示 current_mode、payload_strategy、mode_transitions |
| `DashboardPageMinimal.tsx` | **修改** | 导入并放置 `ServiceModePanel` |

### 9.2 本轮不改的文件

| 文件 | 原因 |
|---|---|
| `protocol.py` | 新 MessageType 和 ServiceMode 已经存在，不需要改 |
| `guard.py` | inner mode state machine 已完整实现，不改 |
| `orchestrator.py` | MODE_DIRECTIVE 处理已实现，不改 |
| `openamp_rpmsg_bridge.py` | 不在本轮添加新帧解析，将来推真机时再改 |
| `fault_injector.py` | 不在本轮添加 LINK_HEALTH 注入流程 |
| `CryptoStatusPanel/` | 老控制面面板保持原样 |
| RTOS 固件 | 完全不涉及 |

### 9.3 高风险接口（标注但不改）

| 接口 | 风险 | 当前处理 |
|---|---|---|
| `STATUS_RESP_STRUCT` (bridge L25) | 改了就破老合同 | **不改** |
| `status_fields_from_response()` (fault_injector L70) | 改了影响 FIT 测试 | **不改** |
| `_control_plane_summary()` (server L3010) | 老字段的唯一入口 | **不改**，service_mode 走独立方法 |

---

## 10. 兼容性与迁移策略

### 10.1 老 demo / 老 evidence 是否受影响

**不受影响。**

- `CryptoStatusPanel` 继续读 `data.control_guard_state` 等老字段，这些字段的值和生成逻辑完全不变
- evidence package 的所有帧 hex、FIT 报告、STATUS_RESP 格式全部保持原样
- bridge / fault_injector 不改，老测试路径零回归

### 10.2 版本协商策略

当前不需要版本协商——新协议状态完全在 server Python 层内部读取（从 mock guard 的 Python 属性直读），不过 RPMsg 线路。

将来推真机时，建议采用 **feature flag** 模式：

```python
# server.py
SERVICE_MODE_SOURCE = os.environ.get("OPENAMP_SERVICE_MODE_SOURCE", "mock")

def _service_mode_snapshot(self):
    if SERVICE_MODE_SOURCE == "mock" and self._mock_guard:
        return self._mock_guard_mode_snapshot()
    elif SERVICE_MODE_SOURCE == "live":
        return self._live_guard_mode_snapshot()  # 将来从 bridge 新帧获取
    else:
        return {"source": "unavailable", "current_mode": "UNKNOWN"}
```

### 10.3 真机迁移最小路径（将来）

1. RTOS 固件增加 `0x60`/`0x61`/`0x62` 的 C 处理代码
2. bridge 增加 `LINK_HEALTH_STRUCT` / `MODE_DIRECTIVE_STRUCT` 的打包和解析
3. fault_injector 增加发送 LINK_HEALTH 的 phase
4. server 切换 SERVICE_MODE_SOURCE 到 "live"
5. 重跑 FIT-04/05/06/07 并产出新 evidence

---

## 11. 测试与验收清单

### 11.1 老协议回归

```bash
# 已有 mock 单测
python3 -m unittest openamp_mock.tests.test_degradation_engine

# 确认老协议 FIT 路径不受影响
# (不改 guard/orchestrator/protocol，所以天然不回归)
```

### 11.2 新协议路径

```bash
# 验证 service_mode 出现在 /api/crypto-status
curl -s http://127.0.0.1:8079/api/crypto-status | python3 -c "
import json, sys
data = json.load(sys.stdin)
sm = data.get('service_mode')
assert sm is not None, 'service_mode missing'
assert sm['current_mode'] in ('FULL_FRAME', 'ROI_ONLY', 'ALERT_ONLY')
print('OK:', sm)
"
```

### 11.3 TypeScript 编译

```bash
cd cockpit_desktop && npx tsc --noEmit
```

### 11.4 双协议共存 UI 验证

- `npm run dev` 启动后，右侧面板应显示两个独立卡片:
  - "OpenAMP 控制面" / "ML-KEM 安全信道" — 显示 guard_state 等老字段
  - "服务模式" — 显示 current_mode、payload_strategy

### 11.5 无新协议输入时的降级行为

当 mock guard 没有收到 LINK_HEALTH 输入时：
- `current_mode` 应为 `FULL_FRAME`（初始态）
- `mode_transitions` 应为 `0`
- 这是**正确行为**，不是 bug

---

## 12. 板端可落地性分析

### 12.1 只在 mock / server / demo 的改动

- server.py 的 `_service_mode_snapshot()`
- 前端 TypeScript 类型和 Panel 组件
- demo 页面布局

### 12.2 最终一定涉及固件侧的改动

- RTOS 增加对 `LINK_HEALTH(0x60)` 帧的解析
- RTOS 实现 inner mode state machine 的 C 版本
- RTOS 增加 `MODE_DIRECTIVE(0x61)` 的发送
- bridge 增加新帧 struct 定义和编解码

### 12.3 可先做成"源码级兼容预留"的部分

- `protocol.py` 已经做好了（MessageType + ServiceMode + FaultCode 都已定义）
- `guard.py` 已经做好了（handle_link_health + _compute_target_mode + _set_service_mode 全部实现）
- `orchestrator.py` 已经做好了（_handle_mode_directive + current_service_mode 跟踪）

**这三个文件就是最好的"源码级兼容预留"——mock 层已经完整实现了新协议的全部语义，将来固件跟上后 bridge 只需要把帧翻译成 mock 已有的接口。**

---

## 13. 非目标

- ❌ **不重写整个 dashboard**
- ❌ **不推翻老协议** — STATUS_RESP 6 字段结构绝对不改
- ❌ **不把新协议强行塞成老协议字段** — 不在 `control_guard_state` 里混入 mode 信息
- ❌ **不脱离现有 OpenAMP 控制主线另起炉灶** — service mode 建立在 guard.py 已有内部状态机之上
- ❌ **不修改 bridge 或 fault_injector** — 将来推真机时再改
- ❌ **不修改 RTOS 固件**
- ❌ **不引入 USRP file polling 或独立于 OpenAMP 的新状态源**
- ❌ **不在本轮实现 ROI_ONLY 的数据面落地** — 只做控制面状态表达
- ❌ **不污染已有 evidence package**
- ❌ **不改变论文已有口径**
