# OpenAMP Phase 5 FIT-02 输入契约破坏真机验证成功记录

> 日期：2026-03-15  
> 目标：把 P1 第二个正式 fault-injection test（输入契约/参数范围破坏）推进到真实飞腾派板级证据。
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_fit01_wrong_sha_success_2026-03-15.md`
> - `session_bootstrap/reports/openamp_input_contract_fit_20260315_014542/`

## 1. 本轮结论

`FIT-02` 已在飞腾派真机上验证成功。对 `JOB_REQ.expected_outputs` 注入非法值 `2`（当前允许集合仅 `(1, 300)`）后：

1. pre `STATUS_REQ` 返回干净 `READY / active_job_id=0 / last_fault=NONE / total_fault_count=0`；
2. wrapper 通过 board-local hook 发出真实二进制 `JOB_REQ(expected_outputs=2)`；
3. firmware 返回真实 `JOB_ACK(DENY)`，并明确给出 `fault_code=9 / ILLEGAL_PARAM_RANGE`；
4. wrapper 收敛为 `result=denied_by_control_hook`，未启动 runner；
5. post `STATUS_REQ` 仍为 `READY / active_job_id=0`，同时 `last_fault_code=9 / ILLEGAL_PARAM_RANGE / total_fault_count=1`。

这说明当前控制面已经能把“参数范围不合法”的输入契约错误在 admission gate 边界直接拒绝，并留下可观测 fault。

## 2. 关键参数

- board host: `100.121.87.73`
- transport: `/dev/rpmsg0` + `/dev/rpmsg_ctrl0`
- job_id: `9302`
- trusted current SHA: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- injected invalid field: `expected_outputs=2`
- remote working root: `/tmp/openamp_wrong_sha_fit/project`
- bundle root: `session_bootstrap/reports/openamp_input_contract_fit_20260315_014542/`

## 3. 关键证据

### pre-status
- `guard_state = READY`
- `active_job_id = 0`
- `last_fault_name = NONE`
- `total_fault_count = 0`

### JOB_REQ denial
- `decision = DENY`
- `fault_code = 9`
- `fault_name = ILLEGAL_PARAM_RANGE`
- `guard_state = READY`
- `source = firmware_job_ack`

### wrapper 行为
- `result = denied_by_control_hook`
- `runner_exit_code = null`
- 远端 `runner_should_not_run.txt` 未生成

### post-status
- `guard_state = READY`
- `active_job_id = 0`
- `last_fault_name = ILLEGAL_PARAM_RANGE`
- `total_fault_count = 1`

## 4. 结论判定

因此这轮可以正式记为：**FIT-02 input-contract board proof = PASS**。

## 5. 下一步

下一项高价值 FIT 为：`FIT-03` 心跳超时 / watchdog 语义。
