# release_v1.4.0 minimal `JOB_REQ/JOB_ACK` extension patch note

- Patch file: `session_bootstrap/patches/phytium_openamp_for_linux_job_req_job_ack_extension_release_v1.4.0_2026-03-14.patch`
- Patch prerequisite: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Target source path: `example/system/amp/openamp_for_linux/src/slaver_00_example.c`
- Target source shape: old `release_v1.4.0` callback flow with `FRpmsgEchoApp(...)`, `SHUTDOWN_MSG`, and the existing service name `rpmsg-openamp-demo-channel`

What this extension adds on top of the working STATUS patch:

- Parse a fixed 44-byte `JOB_REQ` payload:
  - `expected_sha256[32]`
  - `deadline_ms`
  - `expected_outputs`
  - `flags`
- Return a fixed 12-byte `JOB_ACK` payload:
  - `decision`
  - `fault_code`
  - `guard_state`
- Keep the outer entry path and service name unchanged.

Minimal local firmware checks:

- `ALLOW` only when:
  - `guard_state == READY`
  - `active_job_id == 0`
  - `expected_sha256` matches the built-in trusted current SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
  - `deadline_ms > 0`
  - `expected_outputs in {1, 300}`
  - `flags in {1=payload, 2=reconstruction, 3=smoke}`
- `DENY` fault code mapping:
  - `1` = trusted SHA mismatch
  - `8` = not ready / active job already present
  - `9` = illegal parameter range or unsupported flag

Observable status effect after `ALLOW`:

- `active_job_id` is set to the admitted `job_id`
- `guard_state` moves from `1=READY` to `2=JOB_ACTIVE`
- follow-up `STATUS_REQ` therefore reports a non-idle state instead of the old fixed idle payload

Implementation boundary kept intentionally minimal:

- no heartbeat watchdog
- no deadline stop action
- no `JOB_DONE`
- no `SAFE_STOP`
- no data-plane changes
