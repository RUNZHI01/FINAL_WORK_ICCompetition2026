# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T01:09:03+0800`
- run_id: `openamp_wrong_sha_fit_20260315_010828`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-003 | wrong expected_sha256 real-board denial | BLOCKED | N/A | BLOCKED_REMOTE_ACCESS | N/A | N/A | `fit_report_FIT-01.md` |
| TC-004 | invalid input contract real-board denial | TODO | N/A | N/A | N/A | N/A | pending |
| TC-006 | heartbeat timeout real-board watchdog | TODO | N/A | N/A | N/A | N/A | pending |

## Covered This Round

None; FIT-01 blocked before board execution.

## Remaining High-Value Cases

FIT-01 needs a real-board rerun when SSH works; FIT-02 and FIT-03 can reuse the same bundle layout.
