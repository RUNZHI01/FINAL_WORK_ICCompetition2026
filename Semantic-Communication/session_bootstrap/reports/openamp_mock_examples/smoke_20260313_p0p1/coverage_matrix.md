# OpenAMP Coverage Matrix

- generated_at: `2026-03-13T22:52:54`
- run_id: `openamp_mock_smoke_20260313_p0p1`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-001 | allow | PASS | ALLOW | DONE | READY | F000 | `allow/job_manifest_1001.json` |
| TC-003 | deny_sha | PASS | DENY | DENIED | READY | F001 | `deny_sha/job_manifest_1002.json` |
| TC-004 | deny_input | PASS | DENY | DENIED | READY | F002 | `deny_input/job_manifest_1003.json` |
| TC-006 | timeout | PASS | ALLOW | SAFE_STOPPED | FAULT_LATCHED | F003 | `timeout/job_manifest_1004.json` |

## Covered This Round

TC-001, TC-003, TC-004, TC-006

## Remaining High-Value Cases

TC-002, TC-005, TC-007, TC-008, TC-009, TC-010, TC-011, TC-012
