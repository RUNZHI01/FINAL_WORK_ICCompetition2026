# OpenAMP 四幕答辩 / Demo Runbook

- package_date: `2026-03-15`
- mode: `offline-first`
- goal: `把已完成的 OpenAMP 真机证据转成一套可直接上台的飞腾多核弱网安全语义视觉回传系统 operator flow`
- hard_constraints:
  - `不要 reboot`
  - `不要在台上做新的远端实验`
  - `不要手工 stop/start remoteproc0`
  - `不要把 Act 3 写成 live 试错`
- positioning_guardrails:
  - `对外定位 = 飞腾多核弱网安全语义视觉回传系统`
  - `headline performance = 4-core Linux performance mode`
  - `OpenAMP live cue = 3-core Linux + RTOS demo mode`
  - `OpenAMP = control plane / safety，不是 speedup path`

## 0. 交付模式

推荐把演示分成三个 live 等级：

- `Red`：任何板级不确定性存在时，直接走零触板证据模式。这是默认安全模式。
- `Amber`：板在线但未做 presentation-day 彩排时，只允许展示板已在线的静态终端/截图，不做交互。
- `Green`：只有在**当天人工确认过板稳定、RPMsg 路径稳定、且窗口已预置**时，才允许在 `Act 1/2` 插入低扰动 live cue。

`Act 3` 默认不做 live 注入。`Act 4` 本身就是证据页，不依赖 live。

## 1. 上台前预置

建议预先打开这些页面或本地副本：

1. [summary_report.md](summary_report.md)
2. [coverage_matrix.md](coverage_matrix.md)
3. [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)
4. [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md)
5. [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md)
6. [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md)
7. [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md)
8. [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md)
9. [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md)
10. [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md)
11. [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)
12. [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md)
13. [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)
14. [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md)

如果要插入 live cue，额外要求：

- 板已经在线并保持空闲，不需要再 bring-up。
- live 窗口已经提前准备好；台上不做调试。
- 一旦现场有卡顿、状态不一致、或窗口内容异常，10 秒内切回 fallback，不解释、不排障。

## 2. 总时长建议

| Act | 目标 | 建议时长 |
|---|---|---|
| Act 1 | 建立“这是可信在线系统，不是 mock” | `1.5~2 min` |
| Act 2 | 展示最小控制闭环 | `2~3 min` |
| Act 3 | 展示正式 FIT 收口，尤其是 FIT-03 历史 | `3~4 min` |
| Act 4 | 说明性能价值与安全可靠定位 | `2~3 min` |

## 3. Act 1: Trusted Boot / Board-Online / Control-Plane Online

### 本幕目标

先把“系统是可信在线的”立住，但**不在现场重做冷启动**。

### 默认路径

1. 先打开 [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md)，用一句话把最近 live 状态定住：**8115 是当前唯一有效 demo 实例，current 已成功跑通，baseline 也已通过 signed sideband 进入真机执行，且两侧最新 live reconstruction 均完成 `300/300`。** 这也是当前 `TC-002` 的正式收口入口：live reconstruction `300/300` 已足以说明 payload / reconstruction 正常作业闭环，不再临时制造新的 `TC-002` 专用脚本。
2. 再打开 [summary_report.md](summary_report.md)，先报总判定：`P0 已板级闭环；P1 FIT-01 / FIT-02 / FIT-03 最终均为 PASS`。
3. 切到 [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md)，强调三个关键事实：
   - `remoteproc0=running`
   - `creating channel rpmsg-openamp-demo-channel`
   - `rpmsg-demo` 已真实 echo 到 `Hello World! No:100`
3. 再用 [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md) 中 `2026-03-15 02:40` 的 clean baseline 说明：当前 watchdog-fix live firmware 在 fresh boot 后可回到干净 `READY` 基线，适合作为演示起点。

### 可选 live cue

只有在 `Green` 模式下才做：

- 展示一块**已经在线**的终端或静态状态页，说明系统当前处于 clean `READY`。
- 只允许做“在线确认”，不允许 reboot、不允许重新 bring-up。

### fallback 材料

- [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md)
- [summary_report.md](summary_report.md)
- [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md)

### 推荐话术

> 今天不在台上重做冷启动，因为 cold boot 和官方 RPMsg demo 路径已经在真机落证。  
> live 如果出现，只代表“系统现在仍然在线且干净”；系统是否成立，以这里的板级证据为准。

### 本幕允许主张

- `release_v1.4.0` 路线已经通过板级 cold boot + RPMsg demo 门禁。
- 当前最终 live 基线是 watchdog-fix 路线，fresh boot 后可回到 clean `READY`。

### 本幕不要主张

- 不要说“当前台上的 live 状态等于又完成了一次 fresh reboot 验证”。
- 不要说“已证明与板原始官方固件 byte-identical”。

## 4. Act 2: Minimal Control-Loop Capability

### 本幕目标

说明 OpenAMP 已经不是 demo echo，而是一个能影响 runner 放行与作业状态的最小控制闭环。

### 默认路径

1. 打开 [coverage_matrix.md](coverage_matrix.md)，指出 P0 已覆盖：
   - `STATUS_REQ/RESP`
   - `JOB_REQ/JOB_ACK`
   - `HEARTBEAT/HEARTBEAT_ACK`
   - wrapper-backed board smoke
   - `SAFE_STOP`
   - `JOB_DONE`
2. 先用 [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md) 讲“准入”：
   - `source=firmware_job_ack`
   - `decision=ALLOW`
   - `runner_exit_code=0`
3. 再用 [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md) 讲“闭环”：
   - `JOB_REQ(ALLOW)` 后进入 `JOB_ACTIVE`
   - `HEARTBEAT_ACK(heartbeat_ok=1)` 说明运行中监护在
   - `JOB_DONE(success)` 后返回 `READY / active_job_id=0 / last_fault_code=0`
4. 如果评委追问“停止路径”，补一页 [../openamp_phase5_safe_stop_success_2026-03-14.md](../openamp_phase5_safe_stop_success_2026-03-14.md)，说明 `SAFE_STOP` 会回到 `READY` 且留下 `MANUAL_SAFE_STOP(10)` 证据。

### 可选 live cue

只有在 `Green` 模式下才做，并且只做一项：

- 展示一个已预演过的低扰动在线确认，例如当前 `READY` 状态页或一次已预置的最小状态切换展示。

不建议现场执行：

- live wrapper smoke
- live `SAFE_STOP`
- live `JOB_DONE`
- 任何需要重新 bring-up 或清理板状态的操作

### fallback 材料

- [coverage_matrix.md](coverage_matrix.md)
- [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md)
- [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md)
- [../openamp_phase5_safe_stop_success_2026-03-14.md](../openamp_phase5_safe_stop_success_2026-03-14.md)

### 推荐话术

> 这里的关键不是“消息发通了”，而是 firmware 的真实 `JOB_ACK(ALLOW)` 会改变可观测状态，并驱动 wrapper 真正放行 runner。  
> 作业结束后，系统又能回到 clean `READY`；如果需要人工停止，也有 `SAFE_STOP` 的板级证据。

### 本幕允许主张

- 这是一条板级最小控制闭环，不是 mock echo。
- wrapper 不是本地自判，它吃到的是 `source=firmware_job_ack` 的真实决定。

### 本幕不要主张

- 不要说已经做完完整 fault recovery 系统。
- 不要把 `SAFE_STOP` 或 `JOB_DONE` 说成 deadline enforcement。

## 5. Act 3: Formal FIT Evidence

### 本幕目标

把“安全性不是口头承诺”讲成正式 FIT 证据，尤其要保留 `FIT-03` 的 fail -> fix -> pass 历史。

### 默认路径

1. 先用 [coverage_matrix.md](coverage_matrix.md) 打总表，说明 P1 的最终正式状态：
   - `FIT-01 PASS`
   - `FIT-02 PASS`
   - `FIT-03 PASS`
2. 展示 `FIT-01`：
   - 打开 [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md)
   - 重点说 `JOB_ACK(DENY, ARTIFACT_SHA_MISMATCH)`、wrapper `denied_by_control_hook`、runner 未启动
3. 展示 `FIT-02`：
   - 打开 [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md)
   - 重点说 `JOB_ACK(DENY, ILLEGAL_PARAM_RANGE)`、post 状态仍为 `READY`
4. 展示 `FIT-03`：
   - 先打开 [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md)，明确 old live firmware 在停发 heartbeat `5.0 s` 后仍停在 `JOB_ACTIVE`
   - 再打开 [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)，说明相同探针顺序在 watchdog-fix live firmware 上已变成 `READY + HEARTBEAT_TIMEOUT(F003)`

### 可选 live cue

不推荐。默认禁止。

如果评委坚持“为什么不现场打 fault”，标准回答是：

> 这三项 fault injection 已经有正式板级 evidence bundle；现场再打一次只会把答辩变成新的实验，而且可能扰动当前 clean baseline。  
> 我们保留的是证据完整性，尤其是 FIT-03 的历史完整性，而不是舞台效果。

### fallback 材料

- [coverage_matrix.md](coverage_matrix.md)
- [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md)
- [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md)
- [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md)
- [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md)

### 推荐话术

> 这三项 FIT 的价值不只是“最后都 PASS”，而是边界非常清楚。  
> 错误 SHA 会被 admission gate 拒绝，非法参数会被 contract gate 拒绝，heartbeat watchdog 则经历了真实 FAIL、真实修复、再真实 PASS 的完整链路。

### 本幕允许主张

- `FIT-01/02/03` 已有正式板级证据。
- `FIT-03` 历史完整保留，没有掩盖旧固件缺口。

### 本幕不要主张

- 不要把 `FIT-03 PASS` 讲成“系统已具备完整实时监护框架”。
- 不要说 `FIT-04/05` 已完成。

## 6. Act 4: Performance + Safe Reliable System Positioning

### 本幕目标

把 OpenAMP 控制面放到整机价值里：它不是单独追求协议花哨，而是为高性能 trusted current 提供 admission、contract 与 heartbeat safety envelope。

### 默认路径

1. 先报 trusted current artifact SHA：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`。
2. 打开 [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md)，说明 payload 口径：
   - baseline `1846.9 ms`
   - current `130.219 ms`
   - improvement `92.95%`
3. 打开 [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)，说明真实端到端口径：
   - baseline `1850.0 ms/image`
   - current `230.339 ms/image`
   - improvement `87.55%`
4. 把性能结果与控制面连接起来：
   - `FIT-01` 证明错误 SHA 进不来
   - `FIT-02` 证明非法输入契约进不来
   - `FIT-03` 证明运行中 heartbeat 丢失已能收敛到 `HEARTBEAT_TIMEOUT`
5. 最后强调边界：当前定位是“高性能 current artifact 的安全可靠执行入口”，不是“已完成全部 fault-recovery 子系统”。
   - `TC-010` 对应的 `RESET_REQ/ACK` / sticky fault reset 仍属于后续协议扩展，不在本轮正式 claim。

### 可选 live cue

不需要。建议全程用证据页。

### fallback 材料

- [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md)
- [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md)
- [coverage_matrix.md](coverage_matrix.md)

### 推荐话术

> 我们不是为了做一个“能收发消息”的 OpenAMP demo，而是为了给已经证明更快的 trusted current 提供可审计的执行边界。  
> 同一个 trusted SHA 既对应性能结论，也被 admission gate 和 watchdog 保护；性能数字引用 4-core Linux performance mode，而当前 OpenAMP live cue 明确属于 3-core Linux + RTOS demo mode，这才是这套系统的工程价值。

### 本幕允许主张

- trusted current 在 payload 与真实端到端口径下都明显优于 baseline。
- OpenAMP 当前价值是“安全可靠执行入口”，而不是孤立的协议演示。

### 本幕不要主张

- 不要把 TVM 性能结论说成由 OpenAMP 直接带来的。
- 不要把 current artifact 的性能结论与 out-of-scope FIT 混在一起。
- 不要把 `TC-002` 的 `300/300` 收口延伸成 `TC-010` 已完成。

## 7. 结尾一句话

> 这套 demo 的核心不是“现场把板折腾一遍”，而是用已经完成的真机证据证明：  
> 我们有一个可在线、可准入、可拒绝、可监护、且能服务于高性能 trusted current 的最小 OpenAMP 控制面。
