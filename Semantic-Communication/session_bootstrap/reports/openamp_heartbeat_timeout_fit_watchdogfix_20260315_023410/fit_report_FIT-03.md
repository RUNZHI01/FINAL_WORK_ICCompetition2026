# OpenAMP FIT Report

- generated_at: `2026-03-15T02:36:22+0800`
- fit_id: `FIT-03`
- run_id: `openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410`
- scenario: `heartbeat timeout / watchdog semantics on real board path after watchdog fix`
- tc_id: `TC-006`

## Fault Injection

- injected_fault: Admit a real job, send one accepted `HEARTBEAT`, then deliberately stop sending heartbeat for `5.0 s`.
- risk_item: runaway active job due to missing heartbeat timeout watchdog

## Expected

A follow-up `STATUS_REQ` after the quiet window should expose `HEARTBEAT_TIMEOUT(F003)` and return the observable state to `READY`.

## Actual

Board-backed FIT-03 passed after the firmware watchdog fix: after `5.0 s` without heartbeat, the board reported `guard_state=READY`, `active_job_id=0`, `last_fault_code=3 (HEARTBEAT_TIMEOUT)`, `heartbeat_ok=0`, and `total_fault_count=1`. No manual stop was required to trigger the timeout fault.

## Evidence Bundle

`run_manifest.json`, `remote_probe.json`, `pre_status/status_snapshot.json`, `timeout_status/status_snapshot.json`, `cleanup_safe_stop/status_snapshot.json`, `final_status/status_snapshot.json`, `fit_summary.json`, `coverage_matrix.md`
