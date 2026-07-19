# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T01:28:29+0800`
- run_id: `openamp_wrong_sha_fit_20260315_012403`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-003 | wrong expected_sha256 real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ARTIFACT_SHA_MISMATCH | `fit_report_FIT-01.md` |
| TC-004 | invalid input contract real-board denial | TODO | N/A | N/A | N/A | N/A | pending |
| TC-006 | heartbeat timeout real-board watchdog | TODO | N/A | N/A | N/A | N/A | pending |

## Covered This Round

FIT-01 is now backed by real-board evidence: pre-status clean `READY`, wrong-SHA `JOB_REQ` denied by firmware with `F001`, runner not started, and post-status stayed `READY/active_job_id=0`.

## Remaining High-Value Cases

Reuse the same bundle layout for FIT-02 (input contract violation) and FIT-03 (heartbeat timeout / watchdog semantics).
