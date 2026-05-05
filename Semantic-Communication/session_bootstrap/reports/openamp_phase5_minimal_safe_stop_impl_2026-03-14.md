# Phase 5 minimal SAFE_STOP local implementation note

> Date: 2026-03-14  
> Scope: local bridge and firmware patch artifacts only; no board deployment in this step.

## Implemented pieces

- Firmware patch artifact updated:
  - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Firmware patch note updated:
  - `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- Linux bridge updated:
  - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
- Focused bridge tests updated:
  - `openamp_mock/tests/test_rpmsg_bridge.py`

## Chosen minimal wire semantics

- `SAFE_STOP (0x07)` is sent by the Linux bridge in hook mode with:
  - `job_id` in the control header
  - `payload_len = 0`
- Firmware replies with `STATUS_RESP (0x09)` as the minimal result frame:
  - no new `SAFE_STOP_ACK` type is introduced
  - bridge treats the stop as acknowledged only when the returned status shows:
    - `guard_state = READY`
    - `active_job_id = 0`
    - `heartbeat_ok = 0`
    - `last_fault_code = MANUAL_SAFE_STOP`

## Minimal state effect

- Accepted `SAFE_STOP` only applies to the currently admitted `job_id`.
- On acceptance, firmware:
  - records `MANUAL_SAFE_STOP (F010)`
  - increments `total_fault_count`
  - clears `active_job_id`
  - clears the per-job heartbeat bit
  - returns to `READY`
- If `SAFE_STOP` is mismatched, idle, or malformed, firmware still returns a `STATUS_RESP`, but the bridge marks the stop as not applied.

## Boundary kept for next round

- No heartbeat watchdog-triggered outbound `SAFE_STOP` yet
- No `RESET_REQ/ACK`-gated fault latch
- Wrapper behavior unchanged; existing `SAFE_STOP` hook events can now hit the bridge/firmware path directly
