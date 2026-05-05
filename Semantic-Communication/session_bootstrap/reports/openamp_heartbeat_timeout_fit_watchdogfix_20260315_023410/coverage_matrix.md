# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T02:36:22+0800`
- run_id: `openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-003 | wrong expected_sha256 real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ARTIFACT_SHA_MISMATCH | `../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md` |
| TC-004 | invalid input contract real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ILLEGAL_PARAM_RANGE | `../openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md` |
| TC-006 | heartbeat timeout real-board watchdog | PASS | ALLOW | WATCHDOG_TIMEOUT_OBSERVED | READY | HEARTBEAT_TIMEOUT | `fit_report_FIT-03.md` |

## Covered This Round

FIT-03 is now backed by real-board evidence: after one valid heartbeat and a `5.0 s` no-heartbeat window, follow-up `STATUS_REQ` exposes `HEARTBEAT_TIMEOUT(F003)` and the board returns to `READY`.

## Remaining High-Value Cases

Unify FIT-01/02/03 and the already finished SAFE_STOP/JOB_DONE traces into one summary package / defense-facing matrix.
