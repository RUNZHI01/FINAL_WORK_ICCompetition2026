# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T03:20:00+0800`
- package_id: `openamp_control_plane_evidence_package_20260315`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- final_live_firmware_sha: `2c4240e03deedd2cc6bbd1c7c34abee852aa8f7927a5187a5131659c4ce7878a`
- note: `P0` = 已完成的最小板级控制闭环；`P1` = 设计矩阵里已正式收口的 FIT 项

## Test Coverage

| Stage | Coverage Item | Mapped ID | Status | Key Proof Point | Evidence |
|---|---|---|---|---|---|
| P0 | `STATUS_REQ/RESP` | `TC-011` | PASS | 真机返回结构化 `STATUS_RESP`，不是 demo echo。 | [summary](../openamp_phase5_release_v1.4.0_status_req_resp_success_2026-03-14.md) / [probe](../openamp_status_req_resp_real_probe_20260314_001.json) |
| P0 | `JOB_REQ/JOB_ACK` | `TC-001` | PASS | 真机返回 `JOB_ACK(ALLOW)`，follow-up `STATUS_RESP` 进入 `JOB_ACTIVE` 且 `active_job_id=9001`。 | [summary](../openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md) / [probe](../openamp_job_req_job_ack_real_probe_20260314_001.json) |
| P0 | `HEARTBEAT/HEARTBEAT_ACK` | `TC-005` | PASS | 真机返回 `HEARTBEAT_ACK(heartbeat_ok=1)`，follow-up 状态保持 `JOB_ACTIVE` 且 `heartbeat_ok=1`。 | [probe log](../openamp_heartbeat_v14_trial_20260314/phase3_probe.log) / [history summary](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) |
| P0 | wrapper-backed board smoke | `TC-001 wrapper path` | PASS | `source=firmware_job_ack`，wrapper 因真实 `ALLOW` 放行 runner，`runner_exit_code=0`。 | [summary](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md) / [wrapper summary](../openamp_wrapper_hook_board_smoke_20260314_005.wrapper_summary.json) |
| P0 | `SAFE_STOP` | `manual stop milestone` | PASS | 真机 stop 后状态回到 `READY`，`last_fault_code=MANUAL_SAFE_STOP(10)`，且 follow-up 状态保持一致。 | [summary](../openamp_phase5_safe_stop_success_2026-03-14.md) / [probe](../openamp_safe_stop_real_probe_20260314_001.json) |
| P0 | `JOB_DONE` | `TC-001 completion` | PASS | 真机 `JOB_DONE(success)` 后状态回到干净 `READY`，`last_fault_code=0`。 | [summary](../openamp_phase5_job_done_success_2026-03-15.md) / [probe](../openamp_job_done_real_probe_20260315_001.json) |
| P1 | wrong-SHA denial | `TC-003 / FIT-01` | PASS | `JOB_ACK(DENY, ARTIFACT_SHA_MISMATCH)`，wrapper `denied_by_control_hook`，runner 未启动，post-state 仍为 `READY`。 | [summary](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md) / [fit](../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md) |
| P1 | input contract violation denial | `TC-004 / FIT-02` | PASS | `JOB_ACK(DENY, ILLEGAL_PARAM_RANGE)`，wrapper `denied_by_control_hook`，runner 未启动，post-state 仍为 `READY`。 | [summary](../openamp_phase5_fit02_input_contract_success_2026-03-15.md) / [fit](../openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md) / [case card](../openamp_fit02_batch_contract_case_card_2026-04-03.md) |
| P1 | heartbeat timeout / watchdog on old live firmware | `TC-006 / FIT-03` | FAIL (historical) | 停发 heartbeat `5.0 s` 后板子仍停在 `JOB_ACTIVE`；只有额外 `SAFE_STOP` 清理后才回 `READY`。 | [summary](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) / [fit](../openamp_heartbeat_timeout_fit_20260315_015841/fit_report_FIT-03.md) |
| P1 | heartbeat timeout / watchdog after fix | `TC-006 / FIT-03` | PASS (final) | 部署 watchdog-fix firmware 后，同一探针顺序返回 `READY + HEARTBEAT_TIMEOUT(F003)`，且无需手工 stop 才能观察超时。 | [summary](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) / [fit](../openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410/fit_report_FIT-03.md) |

## Covered This Package

- P0 里当前已经对外主张的最小板级控制闭环，现都能对应到一份明确的 summary evidence 和一份原始 probe / wrapper evidence。
- P1 的正式最终状态为：`FIT-01 PASS`、`FIT-02 PASS`、`FIT-03 PASS`。
- `FIT-03` 的旧固件 FAIL 没有被覆盖掉，而是以单独历史行保留在矩阵里。

## Remaining Out Of Scope

- `FIT-04` 参数 / 帧篡改
- `FIT-05` 结果不完整
- `RESET_REQ/ACK`
- deadline timeout / sticky fault reset
