# OpenAMP Coverage Matrix

- generated_at: `2026-03-15T02:00:46+0800`
- run_id: `openamp_heartbeat_timeout_fit_20260315_015841`
- trusted_current_sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

## Test Coverage

| TC ID | Scenario | Status | Decision | Orchestrator Final State | Guard Final State | Last Fault | Evidence |
|---|---|---|---|---|---|---|---|
| TC-003 | wrong expected_sha256 real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ARTIFACT_SHA_MISMATCH | `../openamp_wrong_sha_fit_20260315_012403/fit_report_FIT-01.md` |
| TC-004 | invalid input contract real-board denial | PASS | DENY | DENIED_BY_CONTROL_HOOK | READY | ILLEGAL_PARAM_RANGE | `../openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md` |
| TC-006 | heartbeat timeout real-board watchdog | FAIL | ALLOW | MANUAL_SAFE_STOP_CLEANUP | JOB_ACTIVE after 5s no-heartbeat | NONE during timeout window | `fit_report_FIT-03.md` |

## Covered This Round

FIT-03 now has real-board boundary evidence: admission and heartbeat work, but the tested 5s no-heartbeat window did **not** trigger an automatic watchdog stop or `F003` fault.

## Remaining High-Value Cases

Implement or wire up firmware-side heartbeat timeout / watchdog semantics, then rerun FIT-03 to convert this row from FAIL to PASS.
