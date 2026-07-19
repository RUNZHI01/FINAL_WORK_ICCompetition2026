# OpenAMP wrapper-backed board smoke 成功记录

> 日期：2026-03-14  
> 目标：记录一次真正的 `openamp_control_wrapper.py --transport hook` 板级 smoke，证明 wrapper 能通过 bridge 吃到真实 firmware `JOB_ACK(ALLOW)`，并在收到显式 `ALLOW` 后放行 runner。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_wrapper_hook_admission_validation_2026-03-14.md`
> - `session_bootstrap/scripts/openamp_control_wrapper.py`
> - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 1. 本轮结论

这次不是本地 replay，也不是裸 `/dev/rpmsg0` 探测，而是一次真正的 wrapper-backed board smoke：

1. 板上当前 live firmware 仍为已经打通 `JOB_REQ/JOB_ACK` 的 patched `release_v1.4.0` 路线。
2. 板上 wrapper 通过 `--transport hook` 调用 board-local bridge。
3. bridge 发出真实二进制 `JOB_REQ`，并收到真实 firmware `JOB_ACK(ALLOW)`。
4. `openamp_control_wrapper.py` 收到显式 `ALLOW` 后，真实放行 runner。
5. wrapper 产出了 `JOB_DONE(success)`，runner 退出码为 `0`。

因此，当前最准确的工程结论应更新为：

**OpenAMP 的最小作业授权闭环不只是“协议层能通”，而是已经完成了 wrapper × bridge × firmware × board 的真实串接。**

## 2. 这次 smoke 的关键事实

本轮运行：

- `job_id = 9205`
- `job_flags = smoke`
- `expected_sha256 = 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- `deadline_ms = 60000`
- `expected_outputs = 1`

wrapper summary 的关键结果：

- `result = success`
- `runner_exit_code = 0`

这说明这次不是“收到 ACK 但 Linux 没敢放行”，而是：

> **wrapper 已经真的把 runner 跑起来并正常收尾。**

## 3. 真实 firmware-backed `JOB_ACK`

本轮 `JOB_REQ` 对应的 bridge summary 已明确记录：

- `decision = ALLOW`
- `fault_code = 0`
- `fault_name = NONE`
- `guard_state = 2`
- `guard_state_name = JOB_ACTIVE`
- `source = firmware_job_ack`
- `transport_status = job_ack_received`
- `protocol_semantics = implemented`

这是最关键的边界证据，因为它证明：

1. 不是 wrapper 自己本地伪造 `ALLOW`
2. 不是 bridge 本地 skeleton ACK
3. 而是：
   - **bridge 真实收到了 firmware `JOB_ACK(ALLOW)`**
   - wrapper 再基于这条真实 decision 放行 runner

## 4. 为什么这次结果比前面的 probe 更强

之前我们已经分别证明：

- `STATUS_REQ/RESP` 真机通了
- `JOB_REQ/JOB_ACK(ALLOW)` 真机通了
- wrapper hook 逻辑已修成 fail-closed

但这些都还可以被视为“组件级成功”。

本轮更强的地方在于：

- 同一条链路里同时包含：
  - wrapper
  - hook
  - bridge
  - 板上 `/dev/rpmsg0`
  - firmware `JOB_ACK(ALLOW)`
  - runner 放行与完成

所以这次成功意味着：

> **最小 admission gate 已经从“可分段验证”升级为“真实端到端串接成功”。**

## 5. 结论边界

这次成功仍然需要边界清晰：

1. 已完成的是最小 admission smoke：
   - `STATUS_REQ`（板上状态路径已知可用）
   - `JOB_REQ -> JOB_ACK(ALLOW)`
   - wrapper 放行 runner
   - `JOB_DONE(success)`
2. 当前还没有扩到：
   - `HEARTBEAT watchdog`
   - `SAFE_STOP`
   - `JOB_DONE` 由 firmware 主动驱动
   - deadline 超时控制
3. 但这已经足以说明：
   - **OpenAMP 控制面已不再只是实验性协议，而是已经开始具备对 runner 的真实 admission control 能力。**

## 6. 下一步建议

最自然的下一步已经非常清楚：

1. `HEARTBEAT`
2. `SAFE_STOP`
3. firmware 侧 `JOB_DONE`
4. 再把当前 smoke 风格收敛成更正式的 wrapper-runbook / evidence bundle

一句话总结：

> 现在我们已经不只是“协议消息能收发”，而是已经完成了一次真实的 wrapper-backed board smoke：firmware 给出 `JOB_ACK(ALLOW)`，wrapper 吃到它并成功放行 runner。