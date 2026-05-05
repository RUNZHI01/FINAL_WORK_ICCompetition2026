# release_v1.4.0 STATUS_REQ/RESP + JOB_REQ/JOB_ACK + HEARTBEAT + HEARTBEAT_TIMEOUT + SAFE_STOP + JOB_DONE patch note

- Patch file: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Target source path: `example/system/amp/openamp_for_linux/src/slaver_00_example.c`
- Target source shape: old `release_v1.4.0` callback flow with `FRpmsgEchoApp(...)`, `SHUTDOWN_MSG`, and direct `temp_data` echo behavior
- Artifact integrity: the patch file has been regenerated as a canonical unified diff from the untouched old-source copy at `.codex_tmp/release_v1_4_0_patch_repair/apply_check_safe_stop_20260314_1/example/system/amp/openamp_for_linux/src/slaver_00_example.c` to the locally extended `JOB_DONE + heartbeat-timeout` copy at `.codex_tmp/release_v1_4_0_patch_repair/apply_verify_job_done_20260315_1/example/system/amp/openamp_for_linux/src/slaver_00_example.c`

Structural differences from `phytium_openamp_for_linux_status_req_resp_2026-03-14.patch`:

- This adaptation still hooks the old `rpmsg_endpoint_cb(...)` echo path directly instead of the newer `ProtocolData` parser/switch path.
- `FRpmsgEchoApp(...)`, the top-level entry path, and the service name `rpmsg-openamp-demo-channel` stay unchanged.
- `SHUTDOWN_MSG` handling is still preserved before control-frame parsing.

Implemented behavior:

- Keep the existing control header shape: `magic/version/msg_type/seq/job_id/payload_len/header_crc32`.
- Accept `STATUS_REQ (0x08)` with `payload_len == 0` and reply with a stateful `STATUS_RESP (0x09)` carrying:
  - `guard_state`
  - `active_job_id`
  - `last_fault_code`
  - `heartbeat_ok`
  - `sticky_fault=0`
  - `total_fault_count`
- Accept `JOB_REQ (0x01)` with a fixed 44-byte payload:
  - `expected_sha256[32]`
  - `deadline_ms`
  - `expected_outputs`
  - `flags`
- Reply with `JOB_ACK (0x02)` carrying:
  - `decision`
  - `fault_code`
  - `guard_state`
- Accept `HEARTBEAT (0x03)` with a fixed 16-byte payload:
  - `runtime_state`
  - `elapsed_ms`
  - `completed_outputs`
  - `progress_x100`
- Reply with `HEARTBEAT_ACK (0x04)` carrying:
  - `guard_state`
  - `heartbeat_ok`
- Keep the wire protocol stable for timeout handling:
  - no new timeout frame is introduced
  - timeout becomes observable through the existing `STATUS_RESP`
- Accept `SAFE_STOP (0x07)` with `payload_len == 0`
- Reply to `SAFE_STOP` with `STATUS_RESP (0x09)` as the minimal result frame:
  - no dedicated `SAFE_STOP_ACK` is added
  - the returned `STATUS_RESP` carries the post-stop runtime state
- Accept `JOB_DONE (0x05)` with a fixed 16-byte payload:
  - `result_code`
  - `output_count`
  - `result_crc32`
  - `reserved`
- Reply to `JOB_DONE` with `STATUS_RESP (0x09)` as the minimal result frame:
  - no dedicated `JOB_DONE_ACK` is added
  - the returned `STATUS_RESP` carries the post-done runtime state

Minimal admission checks in the patch:

- Guard must be `READY` and `active_job_id` must be `0`.
- `expected_sha256` must match any enabled entry in the built-in trusted-artifact allowlist
  - `baseline`: `85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849`
  - `current`: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- `deadline_ms > 0`
- `expected_outputs` must be `1` or `300`
- `flags` must be one of the known wire values `1/2/3`

State behavior:

- Before entering `FRpmsgEchoApp(...)`, the patch now explicitly resets:
  - `sc_guard_state`
  - `sc_active_job_id`
  - `sc_last_fault_code`
  - `sc_total_fault_count`
  - `sc_heartbeat_seen`
- This avoids relying on startup-time static initialization for a fresh remoteproc/app start.
- On `ALLOW`, the patch sets:
  - `active_job_id = <request job_id>`
  - `guard_state = JOB_ACTIVE`
  - `last_fault_code = 0`
  - `sc_expected_outputs = <request expected_outputs>`
- On `ALLOW`, the patch also clears the per-job heartbeat bit:
  - `heartbeat_ok = 0` in follow-up `STATUS_RESP` until the first accepted `HEARTBEAT`
- On accepted `HEARTBEAT`, the patch:
  - requires `guard_state == JOB_ACTIVE`
  - requires `active_job_id != 0`
  - requires `job_id == active_job_id`
  - sends `HEARTBEAT_ACK(guard_state=<current>, heartbeat_ok=1)`
  - updates the minimal per-job state so follow-up `STATUS_REQ` reports `heartbeat_ok = 1`
- After the first accepted `HEARTBEAT`, the patch arms a lazy watchdog:
  - last accepted heartbeat timestamp is recorded from the Arm generic counter
  - timeout threshold is fixed at `5000 ms`
  - no new interrupt/task loop is introduced
- Before serving inbound control traffic (`STATUS_REQ`, `JOB_REQ`, `HEARTBEAT`, `SAFE_STOP`, `JOB_DONE`), the patch lazily checks whether the active job has exceeded that heartbeat window
- On watchdog expiry, the patch:
  - records `last_fault_code = 3 (HEARTBEAT_TIMEOUT / F003)`
  - increments `total_fault_count`
  - clears `active_job_id`
  - clears the per-job heartbeat bit
  - returns the observable state to `guard_state = READY`
  - lets the current or follow-up `STATUS_RESP` expose the timeout without adding a new wire message
- On ignored or mismatched `HEARTBEAT`, the patch still returns a minimal `HEARTBEAT_ACK`, but with `heartbeat_ok = 0`
- On accepted `SAFE_STOP`, the patch:
  - requires `payload_len == 0`
  - requires an admitted active job
  - requires `job_id == active_job_id`
  - records `last_fault_code = 10 (MANUAL_SAFE_STOP)`
  - increments `total_fault_count`
  - clears `active_job_id`
  - clears the per-job heartbeat bit
  - moves the observable state back to `guard_state = READY`
  - returns a `STATUS_RESP` that reflects this post-stop state
- On ignored or mismatched `SAFE_STOP`, the patch still returns a `STATUS_RESP`, but with the current state unchanged
- On accepted `JOB_DONE`, the patch:
  - requires `payload_len == 16`
  - requires an admitted active job
  - requires `job_id == active_job_id`
  - uses `result_code` as the minimal completion decision bit in this revision
  - on `result_code == 0`, clears the active job and returns `STATUS_RESP(READY, active_job_id=0, last_fault_code=0, heartbeat_ok=0)`
  - on `result_code != 0`, records `last_fault_code = 5 (OUTPUT_INCOMPLETE)`, increments `total_fault_count`, clears the active job, and returns `STATUS_RESP(READY, active_job_id=0, last_fault_code=5, heartbeat_ok=0)`
  - accepts `output_count/result_crc32/reserved` on the wire, but does not yet enforce them in this minimal old-source firmware path
- On ignored or mismatched `JOB_DONE`, the patch still returns a `STATUS_RESP`, but with the current state unchanged
- On `DENY`, the patch updates `last_fault_code`, increments `total_fault_count`, and normalizes any non-admitted state back to:
  - `guard_state = READY`
  - `active_job_id = 0`
  - `heartbeat_ok = 0`
- Unsupported control messages are still ignored conservatively after logging.

Deliberate boundary kept in this revision:

- The timeout watchdog is lazy and inbound-control-driven; there is still no separate periodic timer ISR/task just for guard polling
- `JOB_DONE` failure is reflected as `READY + last_fault_code=OUTPUT_INCOMPLETE`, not `FAULT_LATCHED`
- No `FAULT_REPORT` is emitted yet
- No `RESET_REQ/ACK` dependency is introduced just to consume a minimal completion report

State-consistency hypothesis fixed in this revision:

- The HEARTBEAT-era inconsistency is most plausibly caused by stale file-scope state surviving into a new app session because the patch relied on static initialization only.
- Once stale `guard_state=JOB_ACTIVE` and `active_job_id=<old job>` are present, a fresh `JOB_REQ` can be denied as duplicate while a follow-up `HEARTBEAT` for that same stale `job_id` is still acknowledged.
- The local fix is therefore:
  - explicit runtime-state reset at app entry
  - heartbeat gating on a nonzero admitted `active_job_id`
  - normalization of non-active state before deny/status reporting

Local artifact checks performed on 2026-03-15:

- `diff -u --label a/example/system/amp/openamp_for_linux/src/slaver_00_example.c --label b/example/system/amp/openamp_for_linux/src/slaver_00_example.c .codex_tmp/release_v1_4_0_patch_repair/apply_check_safe_stop_20260314_1/example/system/amp/openamp_for_linux/src/slaver_00_example.c .codex_tmp/release_v1_4_0_patch_repair/apply_verify_job_done_20260315_1/example/system/amp/openamp_for_linux/src/slaver_00_example.c > session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- `git diff --check -- session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md session_bootstrap/reports/openamp_phase5_minimal_heartbeat_impl_2026-03-14.md session_bootstrap/reports/openamp_phase5_minimal_heartbeat_timeout_impl_2026-03-15.md session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md`
- No firmware build, remote deployment, or board rerun was performed from Codex in this step
