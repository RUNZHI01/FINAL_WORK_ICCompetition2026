# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T01:47:41+0800`
- run_id: `openamp_input_contract_fit_20260315_014542`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-003 | wrong expected_sha256 real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ARTIFACT_SHA_MISMATCH | `../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md` |
| TC-004 | invalid input contract real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ILLEGAL_PARAM_RANGE | `fit_report_FIT-02.md` |
| TC-006 | heartbeat timeout real-board watchdog | TODO | N/A | N/A | N/A | N/A | pending |

## Covered This Round

FIT-02 is now backed by real-board evidence: pre-status clean `READY`, illegal `expected_outputs=2` denied by firmware with `F009`, runner not started, and post-status stayed `READY/active_job_id=0`.

## Remaining High-Value Cases

Proceed to FIT-03 heartbeat timeout / watchdog semantics on the real board.
