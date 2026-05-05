# OpenAMP Phase 5 FIT-03 心跳超时 / watchdog 语义缺口确认

> 日期：2026-03-15  
> 目标：验证当前 live firmware 是否已具备“停发 heartbeat 后自动 fault / stop”的真实板级语义。
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_fit01_wrong_sha_success_2026-03-15.md`
> - `session_bootstrap/reports/openamp_phase5_fit02_input_contract_success_2026-03-15.md`
> - `session_bootstrap/reports/openamp_heartbeat_timeout_fit_20260315_015841/`

## 1. 本轮结论

本轮没有证明 watchdog 成功，反而正式确认了**当前 live firmware 还没有自动 heartbeat-timeout 语义**。

真实板级探针顺序为：

1. pre `STATUS_REQ`：`READY / active_job_id=0 / last_fault=0 / heartbeat_ok=0`；
2. `JOB_REQ(ALLOW)`：作业进入 `JOB_ACTIVE`；
3. `HEARTBEAT_ACK(heartbeat_ok=1)`：运行中心跳路径正常；
4. 故意停发 heartbeat `5.0 s`；
5. follow-up `STATUS_REQ`：**仍然**返回 `JOB_ACTIVE / active_job_id=9303 / last_fault=0 / heartbeat_ok=1 / total_fault_count=0`；
6. 为了把板子带回安全状态，额外发送一次 `SAFE_STOP` 做清理；
7. cleanup 后 `STATUS_RESP` 才回到 `READY / active_job_id=0 / last_fault=MANUAL_SAFE_STOP / total_fault_count=1`。

因此，当前能确认的真实边界是：

- `JOB_REQ/JOB_ACK`：已打通
- `HEARTBEAT/HEARTBEAT_ACK`：已打通
- **heartbeat timeout 自动 fault / stop：未实现或未接入当前 live firmware**

## 2. 为什么这个结果重要

这不是一次“没跑成”的失败，而是一条很有价值的正式系统结论：

> 当前控制面已经能做 admission、参数拒绝、错误 SHA 拒绝、心跳打点、手工 SAFE_STOP、JOB_DONE；
> 但“停发 heartbeat 后自动转异常态”这条安全监护语义还缺最后一环。

也就是说，P1 的前三个 FIT 里：

- `FIT-01`：PASS
- `FIT-02`：PASS
- `FIT-03`：**真实跑出了缺口，而不是停留在猜测**

## 3. 关键证据

来自 `remote_probe.json`：

- pre-status: `READY / active_job_id=0 / last_fault=0 / heartbeat_ok=0`
- after `JOB_REQ`: `ALLOW`
- after `HEARTBEAT`: `heartbeat_ok=1`
- after `5s` no-heartbeat: `JOB_ACTIVE / active_job_id=9303 / last_fault=0 / heartbeat_ok=1 / total_fault_count=0`
- after manual cleanup `SAFE_STOP`: `READY / active_job_id=0 / last_fault=10 / total_fault_count=1`

## 4. 下一步

下一步已经非常明确：

1. 在 firmware 里补 heartbeat watchdog / timeout fault 逻辑；
2. 保持现有 FIT-03 探针顺序不变重新真机复跑；
3. 目标是把第 5 步的状态从
   - `JOB_ACTIVE / fault=0`
   变成
   - `READY or fault-latched / last_fault=HEARTBEAT_TIMEOUT (F003)`。

## 5. 2026-03-15 本地修复准备

同日已在本地 `release_v1.4.0` firmware patch artifact 里补上最小 watchdog 语义，方向保持为 firmware 侧、协议不变：

- 记录最近一次被接受 `HEARTBEAT` 的 generic-timer tick；
- 在下一次入站控制流量（包括 `STATUS_REQ`）时 lazy 检查是否已经超过 `5000 ms`；
- 若超时，则把可观察状态收敛到：
  - `READY`
  - `active_job_id = 0`
  - `last_fault = HEARTBEAT_TIMEOUT (F003)`
  - `heartbeat_ok = 0`
  - `total_fault_count += 1`

关联本地产物：

- `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- `session_bootstrap/reports/openamp_phase5_minimal_heartbeat_timeout_impl_2026-03-15.md`
