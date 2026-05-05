# OpenAMP FIT Report

- generated_at: `2026-03-15T02:00:46+0800`
- fit_id: `FIT-03`
- run_id: `openamp_heartbeat_timeout_fit_20260315_015841`
- scenario: `heartbeat timeout / watchdog semantics on real board path`
- tc_id: `TC-006`

## Fault Injection

- injected_fault: Admit a real job, send one accepted `HEARTBEAT`, then deliberately stop sending heartbeat for `5.0 s`.
- risk_item: runaway active job due to missing heartbeat timeout watchdog

## Expected

After the no-heartbeat window, firmware should leave `JOB_ACTIVE`, latch `HEARTBEAT_TIMEOUT (F003)`, and expose that abnormal state through follow-up `STATUS_RESP`.

## Actual

FIT-03 currently **fails as a watchdog test**: after `5.0 s` without heartbeat, the board still reported `guard_state=JOB_ACTIVE`, `active_job_id=9303`, `last_fault_code=0`, `heartbeat_ok=1`, `total_fault_count=0`. The board only returned to `READY` after an explicit cleanup `SAFE_STOP`, which then set `last_fault_code=MANUAL_SAFE_STOP (10)`.

## Evidence Bundle

`run_manifest.json`, `remote_probe.json`, `pre_status/status_snapshot.json`, `timeout_status/status_snapshot.json`, `cleanup_safe_stop/status_snapshot.json`, `final_status/status_snapshot.json`, `fit_summary.json`, `coverage_matrix.md`
