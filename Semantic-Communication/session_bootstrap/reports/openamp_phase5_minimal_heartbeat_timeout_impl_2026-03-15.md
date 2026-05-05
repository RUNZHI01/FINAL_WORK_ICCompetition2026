# Phase 5 minimal HEARTBEAT timeout local implementation note

> Date: 2026-03-15  
> Scope: local firmware patch artifacts only; no board deployment in this step.

## Implemented pieces

- Firmware patch artifact updated:
  - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Firmware patch note updated:
  - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- FIT-03 gap report updated with the predeploy fix expectation:
  - `session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md`

## Chosen minimal watchdog semantics

- Keep the existing control wire protocol unchanged.
- After the first accepted `HEARTBEAT` for the active `job_id`, firmware stores the last heartbeat tick from the Arm generic counter.
- Before serving inbound control traffic, firmware lazily checks whether the quiet window has reached `5000 ms`.
- On expiry, firmware:
  - records `HEARTBEAT_TIMEOUT (F003)`
  - increments `total_fault_count`
  - clears `active_job_id`
  - clears `heartbeat_ok`
  - returns the observable state to `READY`

## Expected FIT-03 result after deployment

- `JOB_REQ(ALLOW)` still succeeds for the trusted current payload.
- The first valid `HEARTBEAT` still returns `HEARTBEAT_ACK(heartbeat_ok=1)`.
- A follow-up `STATUS_REQ` after the tested `5 s` no-heartbeat window should report:
  - `guard_state = READY`
  - `active_job_id = 0`
  - `last_fault_code = 3 (HEARTBEAT_TIMEOUT / F003)`
  - `heartbeat_ok = 0`
  - `total_fault_count` incremented by `1`

## Boundaries kept

- No wrapper or bridge behavior was changed.
- No new control message type was added.
- No periodic ISR/task watchdog was introduced; timeout becomes observable on the next inbound control frame.
- FIT-01 and FIT-02 admission/deny semantics are intended to remain unchanged.
