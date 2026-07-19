# Phase 5 minimal HEARTBEAT local implementation note

> Date: 2026-03-14  
> Scope: local bridge and firmware patch artifacts only; no board deployment in this step.
>
> Update 2026-03-15: the missing timeout/watchdog piece from this note is now implemented in `session_bootstrap/reports/openamp_phase5_minimal_heartbeat_timeout_impl_2026-03-15.md`. The "No heartbeat watchdog yet" boundary below is historical for the 2026-03-14 step only.

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

- `HEARTBEAT (0x03)` uses a fixed 16-byte payload:
  - `runtime_state`
  - `elapsed_ms`
  - `completed_outputs`
  - `progress_x100`
- `HEARTBEAT_ACK (0x04)` uses a fixed 8-byte payload:
  - `guard_state`
  - `heartbeat_ok`

## Minimal state effect

- After `JOB_ACK(ALLOW)`, firmware keeps `guard_state = JOB_ACTIVE` and clears the per-job heartbeat bit.
- The first accepted `HEARTBEAT` for the active `job_id` sets that bit and returns `HEARTBEAT_ACK(..., heartbeat_ok=1)`.
- Follow-up `STATUS_REQ` then reports `heartbeat_ok = 1`.
- A mismatched or otherwise ignored `HEARTBEAT` still gets a minimal `HEARTBEAT_ACK`, but with `heartbeat_ok = 0`.

## Boundary kept for next round

- No heartbeat watchdog yet
- No `SAFE_STOP`
- No firmware-driven `JOB_DONE`
- Wrapper behavior unchanged beyond consuming bridge hook output sanely
