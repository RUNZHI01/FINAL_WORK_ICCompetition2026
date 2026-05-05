# Phase 5 minimal `JOB_REQ/JOB_ACK` local implementation note

> Date: 2026-03-14  
> Scope: local code and patch artifacts only, no board deployment in this step.

## 1. Implemented artifacts

- Firmware incremental patch artifact:
  - `session_bootstrap/patches/phytium_openamp_for_linux_job_req_job_ack_extension_release_v1.4.0_2026-03-14.patch`
- Firmware patch note:
  - `session_bootstrap/patches/phytium_openamp_for_linux_job_req_job_ack_extension_release_v1.4.0_2026-03-14.md`
- Linux bridge update:
  - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 2. Wire shape used by the bridge and patch

Header remains unchanged:

- `magic`
- `version`
- `msg_type`
- `seq`
- `job_id`
- `payload_len`
- `header_crc32`

Minimal `JOB_REQ` payload is fixed-length `44` bytes:

- `expected_sha256[32]` as raw bytes, not hex text
- `deadline_ms` as `uint32`
- `expected_outputs` as `uint32`
- `flags` as `uint32`

Minimal `JOB_ACK` payload is fixed-length `12` bytes:

- `decision`
- `fault_code`
- `guard_state`

## 3. Concrete numeric mapping

- Guard states used now:
  - `1 = READY`
  - `2 = JOB_ACTIVE`
- Job flags:
  - `1 = payload`
  - `2 = reconstruction`
  - `3 = smoke`
- Fault codes used now:
  - `0 = NONE`
  - `1 = ARTIFACT_SHA_MISMATCH`
  - `8 = busy/not-ready reuse`
  - `9 = ILLEGAL_PARAM_RANGE`

## 4. Linux bridge behavior change

- `STATUS_REQ` path is preserved.
- In `--hook-stdin` mode, `JOB_REQ` is now encoded and sent as a real binary control frame.
- The bridge only admits execution when it receives a decodable firmware `JOB_ACK(ALLOW)`.
- Any timeout, echo, malformed `JOB_ACK`, unsupported decision value, or unsupported later phase is denied locally so the wrapper does not false-start the runner.

## 5. Post-ALLOW status semantics

The firmware extension is designed so that after a successful `JOB_ACK(ALLOW)`:

- `active_job_id = <job_id>`
- `guard_state = JOB_ACTIVE`
- `heartbeat_ok = 1` in the minimal status payload

That gives the next real `STATUS_REQ` a visible non-idle state without yet implementing heartbeat or job finalization.
