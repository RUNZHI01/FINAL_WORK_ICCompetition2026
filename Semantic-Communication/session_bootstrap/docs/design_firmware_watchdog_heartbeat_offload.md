# 设计文档：控制面心跳下沉到固件 Watchdog

> 状态：Draft  
> 日期：2026-03-16  
> 关联问题：Demo live heartbeat 导致 current 重建速度从 230ms 劣化到 350ms

---

## 1. 问题回顾

### 1.1 现状

当前 `run_openamp_demo.sh` → `server.py` → `LiveRemoteReconstructionJob` 的推理链路中，
`openamp_control_wrapper.py` 在 runner 执行期间以 **0.5s 间隔**持续发送 HEARTBEAT：

```
openamp_control_wrapper.py  主循环（每 0.2s poll 一次）
  │
  ├─ process.poll()           ← 检查 runner 是否结束
  ├─ if 0.5s elapsed:
  │    emit_event("HEARTBEAT", transport="hook")    ← 同步阻塞调用
  │      └─ subprocess.run(["bash", "-lc", hook_cmd])
  │           └─ openamp_remote_hook_proxy.py
  │                └─ subprocess.run(ssh_with_password.sh → SSH into board)
  │                     └─ 远端: mktemp → tar 解压 → sudo python3 rpmsg_bridge.py → cleanup
  │                          └─ /dev/rpmsg0 write(HEARTBEAT) + read(HEARTBEAT_ACK)
  └─ sleep(0.2)
```

### 1.2 性能影响

| 指标 | 值 | 说明 |
|---|---|---|
| `DEFAULT_HEARTBEAT_INTERVAL_SEC` | 0.5s | `inference_runner.py` L34 |
| 单次 hook 链路耗时 | ~1000–2000ms | SSH 握手 + fork + Python + rpmsg I/O |
| 300 张图 @230ms 无干扰基准 | ~69s | 推理总时长 |
| 实际受干扰后单张时间 | ~350ms | CPU 争抢 + I/O 争抢 |
| 300 张图 @350ms 受干扰 | ~105s | 推理总时长（+52%） |
| 推理期间 SSH 调用次数 | ~70–140 次 | 远端每次 fork sshd→bash→python3 |

**根因**：每次 heartbeat 在板端 fork 出进程链，4 核 Cortex-A72 的 CPU 时间片被推理进程和心跳进程反复争抢。

### 1.3 现有代码已知此问题

`inference_runner.py` 中已经有 `detect_current_live_slowdown()` 和相关常量（`HEAVY_HEARTBEAT_DURATION_MS = 1500`、`HEAVY_HEARTBEAT_COUNT = 8`），说明这个干扰在设计时已被预见但尚未解决。

---

## 2. 方案概览

将心跳超时检测从 **Linux 侧周期性 SSH 轮询** 下沉到 **从核 RTOS 固件内部的硬件 Timer**。
推理运行期间 Linux 侧不再发送任何 HEARTBEAT，整个链路仅在作业开始和结束时通过 SSH 通信。

### 2.1 架构对比

**当前（Linux 侧心跳）：**
```
Linux 主机                              飞腾派板卡
┌──────────────────────┐                ┌──────────────────────────────┐
│ wrapper 主循环       │  每 0.5s SSH   │ sshd → bash → python3       │
│   poll + heartbeat   │ ────────────→  │   → rpmsg_bridge.py         │
│   poll + heartbeat   │ ←────────────  │   → /dev/rpmsg0 write+read  │
│   poll + heartbeat   │  ~1500ms/次    │                              │
│   ...×70~140 次      │                │ 推理进程（CPU 被抢占）       │
└──────────────────────┘                └──────────────────────────────┘
SSH 调用次数：~100+
```

**目标（固件 Watchdog）：**
```
Linux 主机                              飞腾派板卡
┌──────────────────────┐                ┌──────────────────────────────┐
│ wrapper              │  1× STATUS_REQ │                              │
│   发 JOB_REQ         │ ────────────→  │ sshd（仅 3~4 次连接）       │
│   (含 watchdog 配置) │                │   → rpmsg_bridge.py         │
│                      │  1× JOB_REQ   │                              │
│   等待 runner 完成   │ ────────────→  │ 从核 RTOS 固件:              │
│   （零 SSH 调用）    │                │   HW Timer 自主倒计时        │
│                      │  1× JOB_DONE  │   超时→自动 SAFE_STOP(F003)  │
│   发 JOB_DONE        │ ────────────→  │                              │
└──────────────────────┘                │ 推理进程（CPU 100% 可用）    │
SSH 调用次数：3~4                       └──────────────────────────────┘
```

---

## 3. 协议扩展

### 3.1 新增 `WatchdogMode` 枚举

```python
class WatchdogMode(IntEnum):
    DISABLED = 0               # 行为与当前完全一致（向后兼容）
    FIRMWARE_TIMER = 1         # 固件启动 HW Timer，超时自动 SAFE_STOP
    FIRMWARE_TIMER_WITH_PROBE = 2  # 在 mode 1 基础上，固件主动推送 STATUS_PROBE
```

### 3.2 新增消息类型

```python
class MessageType(IntEnum):
    # ...现有 0x01–0x10...
    STATUS_PROBE = 0x11      # Guard→Linux，固件主动推送状态（仅 mode 2）
    STATUS_PROBE_ACK = 0x12  # Linux→Guard，可选回复（仅 mode 2）
```

### 3.3 `JOB_REQ` payload 扩展

在现有 44 bytes 的基础上追加 12 bytes watchdog 配置：

```
偏移   大小   字段                         说明
───────────────────────────────────────────────────────
 0     32B   expected_sha256              现有
32      4B   deadline_ms                  现有
36      4B   expected_outputs             现有
40      4B   flags                        现有
─── 以下为新增字段（watchdog_mode > 0 时存在）───
44      4B   watchdog_mode                0=DISABLED, 1=FIRMWARE_TIMER, 2=WITH_PROBE
48      4B   watchdog_timeout_ms          固件 watchdog 超时阈值（建议 60000–120000ms）
52      4B   watchdog_probe_interval_ms   固件主动 probe 间隔（mode=2 时有效）
```

对应 C struct（RTOS 端）：

```c
typedef struct __attribute__((packed)) {
    uint8_t  expected_sha256[32];
    uint32_t deadline_ms;
    uint32_t expected_outputs;
    uint32_t flags;
    uint32_t watchdog_mode;              // 新增
    uint32_t watchdog_timeout_ms;        // 新增
    uint32_t watchdog_probe_interval_ms; // 新增
} job_req_payload_v2_t;  // 56 bytes
```

对应 Python bridge struct：

```python
JOB_REQ_V2_STRUCT = struct.Struct("<32sIIIIII")  # 56 bytes
```

**向后兼容**：固件收到 44B 的 JOB_REQ（`payload_len == 44`）时，视为 `watchdog_mode=0`（DISABLED），行为不变。

### 3.4 `STATUS_PROBE` payload（仅 mode 2）

```
偏移   大小   字段                         说明
───────────────────────────────────────────────────────
 0      4B   guard_state                  当前 guard 状态
 4      4B   active_job_id                当前活跃作业 ID
 8      4B   elapsed_since_job_start_ms   距作业开始的毫秒数
12      4B   watchdog_remaining_ms        距 watchdog 触发的剩余毫秒
```

```python
STATUS_PROBE_STRUCT = struct.Struct("<IIII")  # 16 bytes
```

### 3.5 协议变更总结

| 消息类型 | Code | 方向 | 现有大小 | 变更 |
|---|---|---|---|---|
| `JOB_REQ` | 0x01 | Linux→Guard | 44B payload | 可选扩展到 56B（+12B watchdog config） |
| `JOB_ACK` | 0x02 | Guard→Linux | 12B | 不变 |
| `HEARTBEAT` | 0x03 | Linux→Guard | 16B | **mode 1/2 下不再需要发送** |
| `HEARTBEAT_ACK` | 0x04 | Guard→Linux | 8B | **mode 1/2 下不再产生** |
| `STATUS_PROBE` | **0x11** | Guard→Linux | 不存在 | **新增**，仅 mode 2，16B |
| `STATUS_PROBE_ACK` | **0x12** | Linux→Guard | 不存在 | **新增**，可选回复，0B payload |
| `FAULT_REPORT` | 0x06 | Guard→Linux | 不变 | watchdog 超时时由固件**主动推送** |

---

## 4. 固件侧设计（RTOS C 代码）

### 4.1 状态机修改

```
                     ┌────────────────────────────────────────────────────┐
                     │           SafetyGuard State Machine               │
                     │                                                    │
BOOT ──→ READY ──JOB_REQ(ALLOW)──→ JOB_ACTIVE                           │
                                       │                                  │
                  watchdog_mode=0:     │     watchdog_mode=1/2:           │
                  等待 Linux HEARTBEAT │     启动 HW Timer                │
                  超时→SAFE_STOP      │     Timer ISR 递减 countdown     │
                                       │     countdown==0→SAFE_STOP(F003)│
                                       │                                  │
                  收到 JOB_DONE ──→ READY   收到 JOB_DONE→停止 Timer→READY│
                     │                                                    │
                     └────────────────────────────────────────────────────┘
```

### 4.2 核心 C 伪代码

```c
/* ──── 全局变量 ──── */
static TimerHandle_t g_watchdog_timer = NULL;
static uint32_t g_watchdog_timeout_ms = 0;
static uint8_t  g_watchdog_mode = 0;  /* 0=DISABLED, 1=FIRMWARE_TIMER, 2=WITH_PROBE */

/* ──── Timer 到期回调 ──── */
void watchdog_expired_callback(TimerHandle_t timer)
{
    /* 在 Timer ISR 或 deferred handler 中执行 */
    trigger_safe_stop(FAULT_HEARTBEAT_TIMEOUT, "firmware watchdog expired");

    /* 通过 rpmsg 主动通知 Linux 侧 */
    send_fault_report(FAULT_HEARTBEAT_TIMEOUT);
}

/* ──── JOB_REQ 处理 ──── */
void handle_job_req(job_req_payload_v2_t *req, uint32_t payload_len)
{
    /* ...现有准入检查（SHA, input contract 等）... */

    /* 解析 watchdog 配置（仅当 payload 足够长时） */
    if (payload_len >= sizeof(job_req_payload_v2_t)) {
        g_watchdog_mode = req->watchdog_mode;
        g_watchdog_timeout_ms = req->watchdog_timeout_ms;
    } else {
        g_watchdog_mode = 0;  /* 向后兼容：旧 44B payload 等同 DISABLED */
        g_watchdog_timeout_ms = 0;
    }

    if (g_watchdog_mode >= 1 && g_watchdog_timeout_ms > 0) {
        /* 启动单次硬件定时器 */
        if (g_watchdog_timer == NULL) {
            g_watchdog_timer = xTimerCreate(
                "wdt",
                pdMS_TO_TICKS(g_watchdog_timeout_ms),
                pdFALSE,          /* 单次触发，不自动重载 */
                NULL,
                watchdog_expired_callback
            );
        } else {
            xTimerChangePeriod(
                g_watchdog_timer,
                pdMS_TO_TICKS(g_watchdog_timeout_ms),
                0
            );
        }
        xTimerStart(g_watchdog_timer, 0);
    }

    /* 发送 JOB_ACK(ALLOW) */
    send_job_ack(DECISION_ALLOW, FAULT_NONE, GUARD_JOB_ACTIVE);
}

/* ──── JOB_DONE 处理 ──── */
void handle_job_done(job_done_payload_t *done)
{
    /* 正常结束，取消 watchdog */
    if (g_watchdog_timer != NULL) {
        xTimerStop(g_watchdog_timer, 0);
    }
    g_watchdog_mode = 0;

    /* ...现有 JOB_DONE 逻辑... */
}

/* ──── HEARTBEAT 处理 ──── */
void handle_heartbeat(heartbeat_payload_t *hb)
{
    if (g_watchdog_mode >= 1) {
        /* 固件 watchdog 模式下，收到 HEARTBEAT 可选择重置 Timer（喂狗） */
        if (g_watchdog_timer != NULL) {
            xTimerReset(g_watchdog_timer, 0);
        }
    }
    /* 原有 HEARTBEAT 处理保持不变 */
    last_heartbeat_ms = get_tick_ms();
}
```

### 4.3 Mode 2 主动 Probe（可选增强）

```c
static TimerHandle_t g_probe_timer = NULL;

void probe_timer_callback(TimerHandle_t timer)
{
    /* 固件每隔 probe_interval_ms 主动向 Linux 推送 STATUS_PROBE */
    status_probe_payload_t probe = {
        .guard_state = current_guard_state,
        .active_job_id = active_job_id,
        .elapsed_since_job_start_ms = get_tick_ms() - job_start_ms,
        .watchdog_remaining_ms = xTimerGetExpiryTime(g_watchdog_timer) - xTaskGetTickCount(),
    };
    send_rpmsg_frame(MSG_STATUS_PROBE, &probe, sizeof(probe));
}
```

Linux 侧被动接收 STATUS_PROBE（零开销 `select()` 监听）：

```python
# Linux 侧可选的 passive listener（在已有 SSH session 内运行）
def passive_probe_listener(rpmsg_fd, probe_callback):
    """JOB_ACTIVE 期间被动收集 STATUS_PROBE，不主动发送任何东西"""
    while True:
        readable, _, _ = select.select([rpmsg_fd], [], [], 30.0)
        if not readable:
            break
        data = os.read(rpmsg_fd, 4096)
        frame = parse_frame(data)
        if frame.get("msg_type") == int(MessageType.STATUS_PROBE):
            probe_callback(frame)  # 更新 UI 进度等
```

---

## 5. Linux 侧改造

### 5.1 `openamp_control_wrapper.py` — 删除心跳循环

当前核心循环（约 L668–L705）：

```python
# BEFORE: 每 0.2s poll + 每 0.5s emit heartbeat（同步阻塞 SSH）
last_heartbeat = start_time
while True:
    return_code = process.poll()
    elapsed = time.monotonic() - start_time
    if return_code is not None:
        break
    if args.runner_timeout_sec > 0 and elapsed > args.runner_timeout_sec:
        # ...timeout handling...
        break
    if time.monotonic() - last_heartbeat >= args.heartbeat_interval_sec:
        emit_event(
            trace_path=trace_path,
            phase="HEARTBEAT",
            payload={...},
            transport=args.transport,
            hook_cmd=args.control_hook_cmd,
            hook_timeout_sec=args.control_hook_timeout_sec,
        )
        last_heartbeat = time.monotonic()
    time.sleep(0.2)
```

改为：

```python
# AFTER: 直接 wait，推理期间零控制面开销
if args.watchdog_mode > 0:
    # 固件 watchdog 模式：不发送 heartbeat，直接等 runner 完成
    try:
        timeout = args.runner_timeout_sec if args.runner_timeout_sec > 0 else None
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        time.sleep(1.0)
        if process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return_code = process.wait(timeout=5)
else:
    # 旧模式: 保留原有 heartbeat 循环（向后兼容）
    last_heartbeat = start_time
    while True:
        return_code = process.poll()
        # ...原有逻辑不变...
```

新增命令行参数：

```python
parser.add_argument(
    "--watchdog-mode",
    type=int,
    choices=[0, 1, 2],
    default=0,
    help="0=legacy heartbeat, 1=firmware timer, 2=firmware timer with probe.",
)
parser.add_argument(
    "--watchdog-timeout-ms",
    type=int,
    default=120000,
    help="Firmware watchdog timeout in ms (mode 1/2 only).",
)
parser.add_argument(
    "--watchdog-probe-interval-ms",
    type=int,
    default=10000,
    help="Firmware probe interval in ms (mode 2 only).",
)
```

### 5.2 `JOB_REQ` payload 扩展

`build_job_req_payload` 新增 watchdog 字段（仅 `watchdog_mode > 0` 时）：

```python
payload = {
    "job_id": job_id,
    "expected_sha256": expected_sha256,
    "deadline_ms": deadline_ms,
    "expected_outputs": expected_outputs,
    "job_flags": job_flags,
    "runner_cmd": runner_cmd,
}
if watchdog_mode > 0:
    payload["watchdog_mode"] = watchdog_mode
    payload["watchdog_timeout_ms"] = watchdog_timeout_ms
    payload["watchdog_probe_interval_ms"] = watchdog_probe_interval_ms
```

### 5.3 `openamp_rpmsg_bridge.py` — V2 struct 序列化

```python
JOB_REQ_V2_STRUCT = struct.Struct("<32sIIIIII")  # 56 bytes

def build_job_req_payload_from_hook(hook_event):
    payload = hook_event["payload"]
    expected_sha256 = decode_sha256_hex(payload["expected_sha256"])
    deadline_ms = int(payload["deadline_ms"])
    expected_outputs = int(payload["expected_outputs"])
    flags = map_job_flags(payload.get("job_flags", payload.get("flags")))
    watchdog_mode = int(payload.get("watchdog_mode", 0))

    if watchdog_mode > 0:
        return JOB_REQ_V2_STRUCT.pack(
            expected_sha256, deadline_ms, expected_outputs, flags,
            watchdog_mode,
            int(payload.get("watchdog_timeout_ms", 0)),
            int(payload.get("watchdog_probe_interval_ms", 0)),
        )
    return JOB_REQ_STRUCT.pack(expected_sha256, deadline_ms, expected_outputs, flags)
```

### 5.4 `inference_runner.py` — 适配

```python
DEFAULT_HEARTBEAT_INTERVAL_SEC = 5.0   # 旧模式也提高到 5s（止血）
DEFAULT_WATCHDOG_MODE = 1              # 新增：默认使用固件 watchdog
DEFAULT_WATCHDOG_TIMEOUT_MS = 120000   # 新增：2 分钟超时

class LiveRemoteReconstructionJob:
    def __init__(self, access, *, variant, ...,
                 watchdog_mode=DEFAULT_WATCHDOG_MODE,
                 watchdog_timeout_ms=DEFAULT_WATCHDOG_TIMEOUT_MS):
        # ...
        command = [
            "python3", str(OPENAMP_CONTROL_WRAPPER_SCRIPT),
            # ...现有参数...
            "--watchdog-mode", str(watchdog_mode),
            "--watchdog-timeout-ms", str(watchdog_timeout_ms),
        ]
        if watchdog_mode > 0:
            # 固件 watchdog 模式下不需要高频 heartbeat
            command.extend(["--heartbeat-interval-sec", "999999"])
```

---

## 6. Mock 层改造（用于单元测试）

### 6.1 `protocol.py`

```python
class WatchdogMode(IntEnum):
    DISABLED = 0
    FIRMWARE_TIMER = 1
    FIRMWARE_TIMER_WITH_PROBE = 2

class MessageType(IntEnum):
    # ...现有...
    STATUS_PROBE = 0x11
    STATUS_PROBE_ACK = 0x12
```

### 6.2 `guard.py`

`SafetyGuard.__init__` 新增：

```python
self._watchdog_mode = WatchdogMode.DISABLED
self._watchdog_deadline_ms: int | None = None
self._watchdog_probe_interval_ms: int | None = None
self._last_probe_ms: int | None = None
self._job_start_ms: int | None = None
```

`_handle_job_req` 新增 watchdog 配置解析：

```python
watchdog_mode = int(message.payload.get("watchdog_mode", 0))
self._watchdog_mode = WatchdogMode(watchdog_mode)
if self._watchdog_mode >= WatchdogMode.FIRMWARE_TIMER:
    watchdog_timeout_ms = int(message.payload.get("watchdog_timeout_ms", 0))
    self._watchdog_deadline_ms = now_ms + (watchdog_timeout_ms or int(message.payload["deadline_ms"]))
    self._job_start_ms = now_ms
    if self._watchdog_mode == WatchdogMode.FIRMWARE_TIMER_WITH_PROBE:
        self._watchdog_probe_interval_ms = int(message.payload.get("watchdog_probe_interval_ms", 10000))
        self._last_probe_ms = now_ms
```

`check_timeouts` 新增固件 watchdog 分支：

```python
if self._watchdog_mode >= WatchdogMode.FIRMWARE_TIMER:
    if self._watchdog_deadline_ms is not None and now_ms > self._watchdog_deadline_ms:
        self._trigger_safe_stop(FaultCode.HEARTBEAT_TIMEOUT, "firmware watchdog expired", ...)
        return
    if (self._watchdog_mode == WatchdogMode.FIRMWARE_TIMER_WITH_PROBE
            and self._last_probe_ms is not None
            and now_ms - self._last_probe_ms >= self._watchdog_probe_interval_ms):
        self._send_status_probe(now_ms, transport)
        self._last_probe_ms = now_ms
    return
# else: 走原有 Linux heartbeat 超时逻辑
```

`_clear_active_job` 新增清理：

```python
self._watchdog_mode = WatchdogMode.DISABLED
self._watchdog_deadline_ms = None
self._watchdog_probe_interval_ms = None
self._last_probe_ms = None
self._job_start_ms = None
```

新增 `_send_status_probe` 方法：

```python
def _send_status_probe(self, now_ms, transport):
    elapsed = now_ms - self._job_start_ms if self._job_start_ms else 0
    remaining = max(0, self._watchdog_deadline_ms - now_ms) if self._watchdog_deadline_ms else 0
    self._send(
        transport=transport, now_ms=now_ms,
        msg_type=MessageType.STATUS_PROBE,
        job_id=self.active_job_id,
        payload={
            "guard_state": self.state.value,
            "active_job_id": self.active_job_id,
            "elapsed_since_job_start_ms": elapsed,
            "watchdog_remaining_ms": remaining,
        },
    )
```

---

## 7. 时序对比

### 7.1 当前（300 张 @~350ms）

```
T=0.0s    STATUS_REQ ──SSH──→ 板  ←── STATUS_RESP
T=0.5s    JOB_REQ   ──SSH──→ 板  ←── JOB_ACK(ALLOW)
T=1.0s    runner starts
T=1.5s    HEARTBEAT ──SSH──→ 板  ←── HEARTBEAT_ACK   ← CPU 被抢
T=3.0s    HEARTBEAT ──SSH──→ 板  ←── HEARTBEAT_ACK   ← CPU 被抢
...       （反复 ~70–140 次）
T=105s    runner done
T=106s    JOB_DONE  ──SSH──→ 板

总推理时间:  ~105s (300 × 350ms)
SSH 调用:    ~100+
```

### 7.2 方案三（300 张 @~230ms）

```
T=0.0s    STATUS_REQ ──SSH──→ 板  ←── STATUS_RESP
T=0.5s    JOB_REQ(watchdog_mode=1, timeout=120s) ──SSH──→ 板  ←── JOB_ACK(ALLOW)
T=1.0s    runner starts
          （零 SSH 调用，固件 HW Timer 自主倒计时 120s）
          （板端 CPU 100% 给推理）
T=70s     runner done (300 × 230ms ≈ 69s)
T=70.5s   JOB_DONE  ──SSH──→ 板  （固件取消 watchdog timer）

总推理时间:  ~69s (300 × 230ms，回到无干扰基准)
SSH 调用:    3–4
时间节约:    ~36s（34%）
```

---

## 8. 安全性分析

| 风险场景 | 当前方案 | 方案三 |
|---|---|---|
| Linux 主机崩溃 | 心跳停发 → 固件无 watchdog（FIT-03 已确认缺失） | 固件 Timer 到期 → `SAFE_STOP(F003)` ✓ |
| SSH 网络中断 | 心跳 hook 超时但固件无反应 | 固件 Timer 不依赖网络，照常触发 ✓ |
| 推理进程挂死 | 心跳仍在发（误报存活） | wrapper 本地 `runner_timeout_sec` 兜底 + 固件 deadline 兜底 ✓ |
| 固件 Timer 硬件故障 | N/A | wrapper 保留 `runner_timeout_sec` 作为二级保护 ✓ |
| 接收到旧版本 JOB_REQ（44B） | 正常工作 | `payload_len < 56` → `watchdog_mode=0`，完全向后兼容 ✓ |

**结论**：方案三比当前方案**更安全**，因为它填补了 FIT-03 确认的"固件缺少心跳超时 watchdog"缺口。

---

## 9. 涉及文件清单

| 文件 | 改动类型 | 改动量估算 | 备注 |
|---|---|---|---|
| `openamp_mock/protocol.py` | 新增枚举 | +10 行 | `WatchdogMode`、`STATUS_PROBE` |
| `openamp_mock/guard.py` | 逻辑分支 | +60 行 | watchdog 配置解析 + `check_timeouts` 分支 + `_send_status_probe` |
| `session_bootstrap/scripts/openamp_rpmsg_bridge.py` | struct 扩展 | +30 行 | `JOB_REQ_V2_STRUCT`、`STATUS_PROBE_STRUCT` |
| `session_bootstrap/scripts/openamp_control_wrapper.py` | 主循环重构 | +20/−15 行 | watchdog 模式下用 `process.wait()` 替代心跳循环 |
| `session_bootstrap/demo/.../inference_runner.py` | 参数透传 | +15 行 | `watchdog_mode` 参数加入 command 构建 |
| `session_bootstrap/demo/.../openamp_remote_hook_proxy.py` | 无改动 | 0 | hook proxy 按原有方式路由，调用次数自然降到 3–4 |
| **RTOS 固件 C 代码** | **Timer 逻辑** | **~100 行 C** | **需在板上编译烧录，不在本仓库内** |

---

## 10. 实施路线

| 阶段 | 工作项 | 依赖 | 可并行 |
|---|---|---|---|
| **Phase A** | Mock 层：`protocol.py` + `guard.py` 新增 `WatchdogMode` 和固件 watchdog 逻辑 | 无 | ✓ |
| **Phase B** | Bridge 层：`openamp_rpmsg_bridge.py` 新增 `JOB_REQ_V2_STRUCT` 序列化/反序列化 | Phase A | ✓ |
| **Phase C** | Wrapper 层：`openamp_control_wrapper.py` 新增 `--watchdog-mode` 参数 + `process.wait()` 分支 | Phase B | ✓ |
| **Phase D** | RTOS 固件：在 `handle_job_req` 中启动 `xTimerCreate`，`handle_job_done` 中 `xTimerStop` | Phase A | 与 B/C 并行 |
| **Phase E** | 真机验证：FIT-03 重跑，验证固件 watchdog PASS | Phase D | — |
| **Phase F** | `inference_runner.py` 参数适配 + 性能回测 | Phase C + D | — |

> Phase A–C 可以在 mock + Linux 侧全部完成并通过单测，**不需要等板子**。
> Phase D 是固件改动，需要在飞腾派上编译烧录。
> Phase A–C 与 Phase D 可以并行开发。

---

## 11. 快速止血方案（可立即执行）

如果不想等方案三完整落地，**改一行代码**即可降低干扰约 10 倍：

```python
# inference_runner.py L34
# 将 0.5 改为 5.0（与 wrapper 自身 CLI 默认值对齐）
DEFAULT_HEARTBEAT_INTERVAL_SEC = 5.0
```

效果：心跳从 ~140 次降到 ~14 次，板端 CPU 干扰降 10x，预计单张时间从 350ms 回落到 240–250ms 区间。

此改动与方案三完全兼容——方案三落地后 `watchdog_mode=1` 会绕过整个心跳循环，该默认值仅作为旧模式的兜底。
