# OpenAMP FIT Report

- generated_at: `2026-03-13T22:52:54`
- fit_id: `FIT-02`
- run_id: `openamp_mock_smoke_20260313_p0p1`
- scenario: `deny_input`
- tc_id: `TC-004`

## Fault Injection

- injected_fault: 构造 batch=4，触发固定 batch=1 契约拒绝。
- risk_item: 输入契约违规风险

## Expected

收到 JOB_ACK(DENY, F002)，guard 记录输入契约故障。

## Actual

decision=DENY, orchestrator=DENIED, guard=READY, last_fault=F002

## Evidence Bundle

deny_input/job_manifest_1003.json, deny_input/fault_log.jsonl, deny_input/guard_state_log.jsonl
