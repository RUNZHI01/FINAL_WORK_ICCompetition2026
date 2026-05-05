# OpenAMP FIT Report

- generated_at: `2026-03-13T22:52:54`
- fit_id: `FIT-03`
- run_id: `openamp_mock_smoke_20260313_p0p1`
- scenario: `timeout`
- tc_id: `TC-006`

## Fault Injection

- injected_fault: 合法作业启动后故意停止 heartbeat。
- risk_item: 主控失活风险

## Expected

guard 触发 SAFE_STOP(F003) 并进入 FAULT_LATCHED。

## Actual

decision=ALLOW, orchestrator=SAFE_STOPPED, guard=FAULT_LATCHED, last_fault=F003

## Evidence Bundle

timeout/job_manifest_1004.json, timeout/fault_log.jsonl, timeout/guard_state_log.jsonl
