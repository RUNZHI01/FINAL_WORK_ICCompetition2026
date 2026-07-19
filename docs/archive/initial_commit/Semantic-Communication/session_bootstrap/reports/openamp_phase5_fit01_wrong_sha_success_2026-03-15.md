# OpenAMP Phase 5 FIT-01 wrong-SHA 真机验证成功记录

> 日期：2026-03-15  
> 目标：把 P1 第一个正式 fault-injection test（错误 SHA）从“计划/blocked”推进到真实飞腾派板级证据。
> 关联前置：
> - `session_bootstrap/reports/openamp_fit_wrong_sha_board_prep_2026-03-15.md`
> - `session_bootstrap/reports/openamp_wrapper_hook_board_smoke_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_wrong_sha_fit_20260315_012403/`

## 1. 本轮结论

`FIT-01` 已在飞腾派真机上验证成功。对 `JOB_REQ.expected_sha256` 注入一个合法长度但错误的 SHA-256 后：

1. pre `STATUS_REQ` 返回干净 `READY / active_job_id=0 / last_fault=NONE / total_fault_count=0`；
2. wrapper 通过 board-local hook 发出真实二进制 `JOB_REQ`；
3. firmware 返回真实 `JOB_ACK(DENY)`，并明确给出 `fault_code=1 / ARTIFACT_SHA_MISMATCH`；
4. wrapper 收敛为 `result=denied_by_control_hook`，未启动 runner；
5. post `STATUS_REQ` 仍为 `READY / active_job_id=0`，同时 `last_fault_code=1 / ARTIFACT_SHA_MISMATCH / total_fault_count=1`。

这说明当前控制面已经不只是“能 allow 正常作业”，而且能在 board-backed admission gate 上对不受信任 artifact 做显式拒绝并保留可观测 fault 证据。

## 2. 本轮关键参数

- board host: `100.121.87.73`
- transport: `/dev/rpmsg0` + `/dev/rpmsg_ctrl0`
- job_id: `9301`
- trusted current SHA: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- injected wrong SHA: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0`
- remote working root: `/tmp/openamp_wrong_sha_fit/project`
- bundle root: `session_bootstrap/reports/openamp_wrong_sha_fit_20260315_012403/`

## 3. 关键证据

### pre-status

来自 `pre_status/bridge_summary.json`：

- `guard_state = READY`
- `active_job_id = 0`
- `last_fault_name = NONE`
- `total_fault_count = 0`

### JOB_REQ denial

来自 `hook/job_req/bridge_summary.json`：

- `decision = DENY`
- `fault_code = 1`
- `fault_name = ARTIFACT_SHA_MISMATCH`
- `guard_state = READY`
- `source = firmware_job_ack`
- `transport_status = job_ack_received`

### wrapper 行为

来自 `wrapper/wrapper_summary.json` 与 `wrapper/control_trace.jsonl`：

- `result = denied_by_control_hook`
- `runner_exit_code = null`
- wrapper trace 中已记录 `JOB_ACK(DENY, ARTIFACT_SHA_MISMATCH)`
- 远端 `runner_should_not_run.txt` 未生成，说明 runner 未被放行

### post-status

来自 `post_status/bridge_summary.json`：

- `guard_state = READY`
- `active_job_id = 0`
- `last_fault_name = ARTIFACT_SHA_MISMATCH`
- `total_fault_count = 1`

## 4. 结论判定

按照 `openamp_fit_wrong_sha_board_prep_2026-03-15.md` 里定义的最小判定标准，这次 `FIT-01` 满足：

- [x] 发出的确是错误 SHA，而不是空值/格式错误；
- [x] firmware 返回真实 `JOB_ACK(DENY)`；
- [x] fault 被解析为 `ARTIFACT_SHA_MISMATCH (F001)`；
- [x] guard 未进入 active；
- [x] wrapper 未启动 runner；
- [x] follow-up `STATUS_RESP` 仍保持 `READY / active_job_id=0`。

因此这轮可以正式记为：**FIT-01 wrong-SHA board proof = PASS**。

## 5. 下一步

按既定顺序，下一批高价值 FIT 应继续推进：

1. `FIT-02`：输入契约破坏（如 `expected_outputs` 非法值或 `deadline_ms=0`）；
2. `FIT-03`：心跳超时 / watchdog 语义；
3. 把 `FIT-01/02/03` 与已完成的 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE` 汇总到统一 coverage matrix / FIT summary。
