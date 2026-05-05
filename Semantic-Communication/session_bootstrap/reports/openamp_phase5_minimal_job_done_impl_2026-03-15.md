# Phase 5 minimal JOB_DONE local implementation note

> Date: 2026-03-15  
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

- `JOB_DONE (0x05)` is sent by the Linux bridge in hook mode with:
  - `job_id` in the control header
  - fixed 16-byte payload:
    - `result_code`
    - `output_count`
    - `result_crc32`
    - `reserved`
- Firmware replies with `STATUS_RESP (0x09)` as the minimal result frame:
  - no new `JOB_DONE_ACK` type is introduced
  - the bridge treats the completion report as acknowledged only when the returned status matches the reported result:
    - success path: `READY`, `active_job_id=0`, `heartbeat_ok=0`, `last_fault_code=NONE`
    - failure path: `READY`, `active_job_id=0`, `heartbeat_ok=0`, `last_fault_code=OUTPUT_INCOMPLETE`

## Minimal state effect

- Accepted `JOB_DONE` only applies to the currently admitted `job_id`.
- On accepted `JOB_DONE(result_code=0)`, firmware:
  - clears `active_job_id`
  - clears the per-job heartbeat bit
  - clears stored `expected_outputs`
  - returns to `READY`
  - keeps `last_fault_code = NONE`
- On accepted `JOB_DONE(result_code!=0)`, firmware:
  - records `OUTPUT_INCOMPLETE (F005)`
  - increments `total_fault_count`
  - clears `active_job_id`
  - clears the per-job heartbeat bit
  - clears stored `expected_outputs`
  - returns to `READY`
- If `JOB_DONE` is mismatched or malformed, firmware still returns a `STATUS_RESP`, but the bridge marks the completion report as not applied.

## Boundary kept for next round

- `output_count/result_crc32/reserved` are carried on the wire, but not yet enforced in firmware
- No `FAULT_REPORT` is emitted for `JOB_DONE` failure yet
- No `FAULT_LATCHED` / `RESET_REQ` dependency is introduced just to consume minimal completion reports
- Wrapper behavior remains unchanged; existing hook-mode `JOB_DONE` events are now bridge/firmware-backed
