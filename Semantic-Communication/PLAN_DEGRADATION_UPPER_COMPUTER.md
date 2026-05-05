# 上位机退化保底方案（Codex 执行文档）

## 0. 一句话

退化决策在上位机完成，飞腾派 RTOS 固件和现有控制协议一行不改。上位机感知链路质量 → 自主决定发送策略（全图/ROI/告警）→ 飞腾派收到什么就处理什么。

---

## 1. 架构总览

```
上位机（笔记本 / 开发机）                                 飞腾派
┌────────────────────────────────────────┐              ┌──────────────────────────────┐
│                                        │              │  RTOS 从核                    │
│  USRP TX/RX 或 Simulator               │              │  ┌────────────────────────┐   │
│       │                                │              │  │ 已有 SafetyGuard 固件    │   │
│       ▼                                │   RPMsg/SSH  │  │ (准入/心跳/SAFE_STOP)   │   │
│  LinkHealthReport                      │  ─────────→  │  │ 完全不改               │   │
│       │                                │   现有协议    │  └────────────────────────┘   │
│       ▼                                │              │                              │
│  DegradationEngine（新模块）            │              │  Linux 主核                   │
│  ├─ _compute_target_mode()             │              │  ┌────────────────────────┐   │
│  ├─ 滞回防抖 (3窗口降/5窗口升)          │              │  │ TVM/MNN 推理管线        │   │
│  └─ 突发丢包紧急降级                    │              │  │ 收全图latent→整图重建   │   │
│       │                                │              │  │ 收ROI latent→局部重建   │   │
│       ▼ ServiceMode                    │              │  │ 收告警元数据→直接显示   │   │
│  编码策略选择器                          │   数据面传输  │  │                        │   │
│  ├─ FULL_FRAME → 发完整 latent         │  ─────────→  │  │ 按 payload 头部自适应   │   │
│  ├─ ROI_ONLY  → 发 ROI 裁剪 latent     │              │  └────────────────────────┘   │
│  └─ ALERT_ONLY → 只发告警元数据         │              │                              │
│       │                                │              └──────────────────────────────┘
│       ▼                                │
│  cockpit_native UI 展示当前降级状态     │
│                                        │
└────────────────────────────────────────┘
```

### 为什么这样设计

1. **链路质量数据产生在上位机**（USRP TX/RX 在上位机侧），退化决策天然应该在上位机做。
2. **退化影响的是"发什么"**，不是"收到之后怎么处理"——这是发送端策略，不是接收端安全逻辑。
3. **飞腾派 RTOS 从核只管安全停机**（作业准入、心跳监护、安全停机），这些已有逻辑完全不受影响。如果链路彻底断了，心跳自然超时，现有 SAFE_STOP 机制兜底。
4. **不需要改 `openamp_rpmsg_bridge.py`（2930行）**，不需要改 RTOS 固件，不需要新增 RPMsg 帧类型。

---

## 2. 需要新建的文件

### 2.1 `openamp_mock/degradation_engine.py`（核心模块）

从 `openamp_mock/guard.py` 的内层模式状态机中抽取退化决策逻辑，作为独立模块。

**要求：**

- 新建一个 `DegradationEngine` 类，**不依赖** `SafetyGuard`、`MockTransport`、`GuardState` 等任何与 RPMsg 控制面相关的类型。
- 只依赖 `openamp_mock/protocol.py` 中的 `ServiceMode` 枚举和 `openamp_mock/link_health.py` 中的 `LinkHealthReport`。
- 算法直接复用 `guard.py` 第 369-484 行的逻辑，但去掉所有 transport/guard 耦合。

**类接口设计：**

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .link_health import LinkHealthReport
from .protocol import ServiceMode


@dataclass
class ModeTransition:
    """记录一次模式切换。"""
    timestamp_ms: int
    from_mode: str
    to_mode: str
    reason: str


class DegradationEngine:
    """上位机侧退化决策引擎。

    消费 LinkHealthReport，输出当前 ServiceMode。
    不依赖任何 RPMsg/OpenAMP 控制面类型。
    """

    # 阈值常量（与 guard.py 保持一致）
    DEGRADE_THRESHOLD: int = 3        # 连续 N 个劣化窗口才降级
    UPGRADE_THRESHOLD: int = 5        # 连续 N 个恢复窗口才升级
    BURST_LOSS_EMERGENCY: int = 10    # 突发丢包阈值，跳过滞回
    SNR_ROI_THRESHOLD: int = 500      # SNR < 5dB → ROI
    PER_ROI_THRESHOLD: int = 50       # PER > 5% → ROI
    PER_ALERT_THRESHOLD: int = 200    # PER > 20% → ALERT

    def __init__(self) -> None:
        self.current_mode: ServiceMode = ServiceMode.FULL_FRAME
        self.mode_log: list[ModeTransition] = []
        self._degrade_window_count: int = 0
        self._upgrade_window_count: int = 0
        self._link_lost: bool = False

    @property
    def is_link_lost(self) -> bool:
        """链路是否已丢失（rx_locked=False）。"""
        return self._link_lost

    @property
    def payload_strategy(self) -> str:
        """返回当前数据面发送策略标签。

        - "full_latent": 完整 latent → TVM 定形重建
        - "roi_latent":  ROI 裁剪 latent → MNN 动态形重建
        - "alert_metadata": 仅告警元数据 → 无推理
        """
        if self.current_mode == ServiceMode.FULL_FRAME:
            return "full_latent"
        if self.current_mode == ServiceMode.ROI_ONLY:
            return "roi_latent"
        return "alert_metadata"

    def update(self, report: LinkHealthReport) -> ServiceMode:
        """接收一个 LinkHealthReport，更新模式并返回当前模式。

        这是唯一的输入接口。调用方只需要以固定节奏（建议 500ms）
        喂入报告即可。
        """
        now_ms = report.timestamp_ms or int(time.time() * 1000)

        # 1. 链路丢失 → 标记丢失（安全停机由飞腾派心跳超时兜底）
        if not report.rx_locked:
            self._link_lost = True
            if self.current_mode != ServiceMode.ALERT_ONLY:
                self._set_mode(ServiceMode.ALERT_ONLY, "link lost (rx_locked=false)", now_ms)
            return self.current_mode

        self._link_lost = False

        # 2. 计算目标模式
        target = self._compute_target_mode(report)

        # 3. 突发丢包紧急降级（跳过滞回）
        if report.burst_loss_max >= self.BURST_LOSS_EMERGENCY:
            if self.current_mode != ServiceMode.ALERT_ONLY:
                self._set_mode(ServiceMode.ALERT_ONLY, "burst loss emergency", now_ms)
                self._degrade_window_count = 0
                self._upgrade_window_count = 0
            return self.current_mode

        # 4. 滞回防抖
        if target.value > self.current_mode.value:
            self._degrade_window_count += 1
            self._upgrade_window_count = 0
            if self._degrade_window_count >= self.DEGRADE_THRESHOLD:
                self._set_mode(target, "sustained degradation", now_ms)
                self._degrade_window_count = 0
        elif target.value < self.current_mode.value:
            self._upgrade_window_count += 1
            self._degrade_window_count = 0
            if self._upgrade_window_count >= self.UPGRADE_THRESHOLD:
                self._set_mode(target, "sustained recovery", now_ms)
                self._upgrade_window_count = 0
        else:
            self._degrade_window_count = 0
            self._upgrade_window_count = 0

        return self.current_mode

    def reset(self) -> None:
        """重置到初始状态（任务结束或新任务开始时调用）。"""
        self.current_mode = ServiceMode.FULL_FRAME
        self._degrade_window_count = 0
        self._upgrade_window_count = 0
        self._link_lost = False

    def snapshot(self) -> dict[str, Any]:
        """返回当前状态快照（用于 API 暴露和 UI 展示）。"""
        return {
            "current_mode": self.current_mode.name,
            "current_mode_value": int(self.current_mode),
            "payload_strategy": self.payload_strategy,
            "is_link_lost": self._link_lost,
            "degrade_window_count": self._degrade_window_count,
            "upgrade_window_count": self._upgrade_window_count,
            "mode_transitions": len(self.mode_log),
            "last_transition": {
                "from_mode": self.mode_log[-1].from_mode,
                "to_mode": self.mode_log[-1].to_mode,
                "reason": self.mode_log[-1].reason,
                "timestamp_ms": self.mode_log[-1].timestamp_ms,
            } if self.mode_log else None,
        }

    def _compute_target_mode(self, report: LinkHealthReport) -> ServiceMode:
        if report.per_x1000 > self.PER_ALERT_THRESHOLD:
            return ServiceMode.ALERT_ONLY
        if (report.per_x1000 > self.PER_ROI_THRESHOLD
                or report.snr_est_db_x100 < self.SNR_ROI_THRESHOLD):
            return ServiceMode.ROI_ONLY
        return ServiceMode.FULL_FRAME

    def _set_mode(self, mode: ServiceMode, reason: str, now_ms: int) -> None:
        old = self.current_mode
        if old is mode:
            return
        self.current_mode = mode
        self.mode_log.append(ModeTransition(
            timestamp_ms=now_ms,
            from_mode=old.name,
            to_mode=mode.name,
            reason=reason,
        ))
```

**关键约束：**
- 这个类**完全无副作用**——不发消息、不操作文件、不触发网络。
- 调用方只需要 `engine.update(report)` 然后读 `engine.current_mode` 或 `engine.payload_strategy`。
- 阈值常量必须与 `guard.py` 第 46-52 行的值完全一致。

### 2.2 `openamp_mock/tests/test_degradation_engine.py`（测试文件）

**要求：**

用 `unittest` 编写，覆盖以下场景（与 `demo.py` 中 FIT-04~FIT-07 对标）：

| 测试用例 | 对标 | 验证内容 |
|---|---|---|
| `test_full_to_roi` | FIT-04 | 3 个连续 degraded 窗口后模式变为 `ROI_ONLY` |
| `test_roi_to_alert` | FIT-05 | 从 ROI 再 3 个 severe 窗口后变为 `ALERT_ONLY` |
| `test_burst_loss_emergency` | FIT-06 | 单个 burst_loss_max>=10 窗口直接跳到 `ALERT_ONLY` |
| `test_recovery_roi_to_full` | FIT-07 | 降级到 ROI 后 5 个 normal 窗口恢复为 `FULL_FRAME` |
| `test_link_lost` | 新增 | `rx_locked=False` → `is_link_lost=True`，模式切为 `ALERT_ONLY` |
| `test_hysteresis_no_flap` | 新增 | 2 个 degraded + 1 个 normal + 2 个 degraded 不触发降级（防抖验证） |
| `test_payload_strategy` | 新增 | 三种模式下 `payload_strategy` 返回正确的字符串 |
| `test_snapshot` | 新增 | `snapshot()` 返回的字典包含所有预期字段 |
| `test_reset` | 新增 | `reset()` 后状态回到 `FULL_FRAME`，计数器清零 |

使用 `openamp_mock/link_health.py` 中已有的 `LinkHealthSimulator` 和预定义 profile（`PROFILE_NORMAL`、`PROFILE_DEGRADED`、`PROFILE_SEVERE`、`PROFILE_BURST_LOSS`、`PROFILE_LOST`）来构造输入。

---

## 3. 需要修改的文件

### 3.1 `cockpit_native/adapter.py` — 退化状态注入 UI 数据

**目标：** 让 cockpit_native 的 UI 数据层能展示当前的退化保底状态。

**修改位置：** `DemoRepoAdapter._build_ui_state()` 方法（大约第 348 行起）。

**具体做法：**

1. 在 `_build_ui_state` 方法中，新增一个 `degradation_status` 参数（可选，默认 `None`），类型为 `dict` （来自 `DegradationEngine.snapshot()`）。

2. 在 `left_panel["rows"]` 列表中，在"链路档位"这一行之后，插入一行新的退化模式行：

```python
{
    "label": "退化模式",
    "value": degradation_status.get("current_mode", "FULL_FRAME") if degradation_status else "未接入",
    "tone": _degradation_tone(degradation_status),
},
```

3. 新增一个辅助函数 `_degradation_tone()`：

```python
def _degradation_tone(status: dict | None) -> str:
    if status is None:
        return "neutral"
    mode = status.get("current_mode", "FULL_FRAME")
    if mode == "ALERT_ONLY":
        return "warning"
    if mode == "ROI_ONLY":
        return "degraded"
    return "online"
```

其中 `"degraded"` 是 `WeakNetworkPanel.qml` 第 79 行已经支持的 tone 值（映射到金色 `#ffbf52`），不需要新增 QML 代码。

4. 在 `bottom_actions["actions"]` 列表中最后追加一个只读动作卡，用于展示退化引擎摘要：

```python
{
    "action_id": "degradation_status",
    "label": "退化保底状态",
    "tone": _degradation_tone(degradation_status),
    "enabled": False,
    "interactive": False,
    "note": _degradation_summary_text(degradation_status),
    "runtime_state": "只读",
},
```

5. 新增辅助函数 `_degradation_summary_text()`：

```python
def _degradation_summary_text(status: dict | None) -> str:
    if status is None:
        return "退化引擎未接入。"
    mode = status.get("current_mode", "FULL_FRAME")
    strategy = status.get("payload_strategy", "full_latent")
    transitions = status.get("mode_transitions", 0)
    lost = status.get("is_link_lost", False)
    if lost:
        return f"链路丢失，当前模式 {mode}（仅告警），已发生 {transitions} 次模式切换。"
    return f"当前模式 {mode}，发送策略 {strategy}，已发生 {transitions} 次模式切换。"
```

**不需要修改的文件：**
- `cockpit_native/qml/components/StatusPanel.qml` — 它通过 `rows` 数组动态渲染，新增的"退化模式"行会自动出现，带正确的 tone 颜色。
- `cockpit_native/qml/components/WeakNetworkPanel.qml` — 已支持 `"degraded"` tone。
- `cockpit_native/qml/components/ActionStrip.qml` — 它通过 `actions` 数组动态渲染，新增的动作卡会自动出现。

### 3.2 `cockpit_native/qt_app.py` — 传递退化状态

**目标：** 让 `qt_app.py` 在构建 UI 数据时能接收并传递退化状态。

**修改位置：** `load_contract_bundle()` 的调用链。

**具体做法：**

1. 在 `DemoRepoAdapter.load_contract_bundle()` 方法中新增可选参数 `degradation_status: dict | None = None`。
2. 将该参数传递给 `_build_ui_state()`。
3. `qt_app.py` 调用 `load_contract_bundle()` 时，如果环境中有 `DegradationEngine` 实例就传入 `engine.snapshot()`，否则传 `None`。

### 3.3 `openamp_mock/__init__.py` — 导出新模块

在 `openamp_mock/__init__.py` 中确保 `DegradationEngine` 可被外部 import。如果当前 `__init__.py` 为空或只有 pass，就加上：

```python
from .degradation_engine import DegradationEngine, ModeTransition
```

---

## 4. 不需要修改的文件（明确声明）

以下文件**必须保持原样不动**：

| 文件 | 原因 |
|---|---|
| `scripts/openamp_rpmsg_bridge.py` (2930行) | 真机桥接代码，退化逻辑不走 RPMsg |
| `scripts/openamp_control_wrapper.py` (897行) | 控制面包装器，与退化无关 |
| `openamp_mock/guard.py` | 已有的 SafetyGuard 不删不改，保留原有 FIT-01~FIT-07 测试兼容 |
| `openamp_mock/orchestrator.py` | 已有的 Orchestrator 不删不改 |
| `openamp_mock/protocol.py` | 不新增消息类型，`ServiceMode` 枚举已经定义好了直接用 |
| `openamp_mock/link_health.py` | 不改，直接复用 `LinkHealthReport` 和 `LinkHealthSimulator` |
| `openamp_mock/transport.py` | 不改 |
| `openamp_mock/demo.py` | 不改，已有的 FIT 测试继续跑 |
| `session_bootstrap/demo/openamp_control_plane_demo/server.py` (6600+行) | 本阶段不改 server，先把核心引擎和 UI 做通 |
| RTOS 固件（任何 C/裸机代码） | 完全不涉及 |

---

## 5. 集成演示流程（验证标准）

实现完成后，应能支持以下演示流程：

```python
from openamp_mock.degradation_engine import DegradationEngine
from openamp_mock.link_health import LinkHealthSimulator

engine = DegradationEngine()
sim = LinkHealthSimulator()

# 正常链路
for _ in range(3):
    engine.update(sim.normal())
assert engine.current_mode.name == "FULL_FRAME"
assert engine.payload_strategy == "full_latent"

# 持续劣化 → 降级到 ROI
for _ in range(3):
    engine.update(sim.degraded())
assert engine.current_mode.name == "ROI_ONLY"
assert engine.payload_strategy == "roi_latent"

# 继续恶化 → 降级到 ALERT
for _ in range(3):
    engine.update(sim.severe())
assert engine.current_mode.name == "ALERT_ONLY"
assert engine.payload_strategy == "alert_metadata"

# 链路恢复 → 5 窗口后回到 FULL
engine.reset()  # 模拟新任务
for _ in range(3):
    engine.update(sim.degraded())  # 先降到 ROI
for _ in range(5):
    engine.update(sim.normal())   # 5 窗口恢复
assert engine.current_mode.name == "FULL_FRAME"

# snapshot 可用于 API 和 UI
status = engine.snapshot()
assert "current_mode" in status
assert "payload_strategy" in status
assert "is_link_lost" in status
```

---

## 6. 答辩叙事（供文档使用）

接入后可以在答辩中这样讲：

> "我们的退化保底机制采用上位机智能感知 + 飞腾派安全兜底的双层架构：
>
> - **上位机（语义编码侧）** 实时监测信道质量（SNR、PER、突发丢包），通过带防抖滞回的三级退化状态机（FULL_FRAME → ROI_ONLY → ALERT_ONLY）自主调整语义编码发送策略——信道好时发完整语义张量，信道劣化时只发关键 ROI 区域，信道极端恶化时只发告警摘要。
>
> - **飞腾派（安全管控侧）** 的 RTOS 从核专注于作业准入、心跳监护和安全停机。如果链路彻底中断，心跳超时机制自动触发安全停机（SAFE_STOP），保证系统在任何极端场景下都能安全收口。
>
> 两层职责正交：退化是 QoS 策略，安全停机是硬保障。"

---

## 7. 执行检查清单

- [ ] 新建 `openamp_mock/degradation_engine.py`，实现 `DegradationEngine` 类
- [ ] 新建 `openamp_mock/tests/test_degradation_engine.py`，9 个测试用例全部通过
- [ ] 修改 `openamp_mock/__init__.py`，导出 `DegradationEngine`
- [ ] 修改 `cockpit_native/adapter.py`，在 `_build_ui_state` 中注入退化状态行和动作卡
- [ ] 修改 `cockpit_native/adapter.py`，新增 `_degradation_tone()` 和 `_degradation_summary_text()` 辅助函数
- [ ] 修改 `cockpit_native/qt_app.py`（如果需要传递 degradation_status 参数）
- [ ] 运行已有的 `openamp_mock` 测试，确认 FIT-01~FIT-07 全部仍然通过（不回归）
- [ ] 运行新的 `test_degradation_engine.py`，确认 9 个用例全部通过
- [ ] 确认 `scripts/openamp_rpmsg_bridge.py` 没有被修改（`git diff` 验证）

---

## 8. 文件影响汇总

| 操作 | 文件路径 |
|---|---|
| **新建** | `openamp_mock/degradation_engine.py` |
| **新建** | `openamp_mock/tests/test_degradation_engine.py` |
| **修改** | `openamp_mock/__init__.py` |
| **修改** | `cockpit_native/adapter.py` |
| **可能修改** | `cockpit_native/qt_app.py` |
| **不改** | 其余所有文件 |
