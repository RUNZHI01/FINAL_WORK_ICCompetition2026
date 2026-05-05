# OpenAMP FIT Report

- generated_at: `2026-03-13T22:52:54`
- fit_id: `FIT-01`
- run_id: `openamp_mock_smoke_20260313_p0p1`
- scenario: `deny_sha`
- tc_id: `TC-003`

## Fault Injection

- injected_fault: 提交与 trusted current 不一致的 expected_sha256。
- risk_item: 未知 artifact 执行风险

## Expected

收到 JOB_ACK(DENY, F001)，不进入 TVM 执行。

## Actual

decision=DENY, orchestrator=DENIED, guard=READY, last_fault=F001

## Evidence Bundle

deny_sha/job_manifest_1002.json, deny_sha/fault_log.jsonl, deny_sha/guard_state_log.jsonl
