# release_v1.4.0 signed-admission scaffold patch note

- Patch file:
  `session_bootstrap/patches/phytium_openamp_for_linux_signed_admission_scaffold_release_v1.4.0_2026-03-16.patch`
- Patch prerequisite:
  `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Target source path:
  `example/system/amp/openamp_for_linux/src/slaver_00_example.c`
- Related transport/doc baseline:
  `session_bootstrap/runbooks/openamp_signed_admission_transport_v1_2026-03-16.md`
- Related execution plan:
  `session_bootstrap/patches/phytium_openamp_signed_admission_release_v1.4.0_patch_execution_plan_2026-03-16.md`

Status:

- Repo-side firmware scaffold only.
- Board firmware does not support signed admission yet.
- Legacy `JOB_REQ` SHA allowlist behavior remains intact when no signed stage exists for the `job_id`.

What this scaffold adds in repo terms:

- New sideband message IDs in the `release_v1.4.0` control-path patch:
  - `SIGNED_ADMISSION_BEGIN = 0x000C`
  - `SIGNED_ADMISSION_CHUNK = 0x000D`
  - `SIGNED_ADMISSION_SIGNATURE = 0x000E`
  - `SIGNED_ADMISSION_COMMIT = 0x000F`
  - `SIGNED_ADMISSION_ACK = 0x0010`
- New signed-path fault codes:
  - `F011` `MANIFEST_NOT_STAGED`
  - `F012` `MANIFEST_DIGEST_MISMATCH`
  - `F013` `MANIFEST_PARSE_ERROR`
  - `F014` `SIGNATURE_INVALID`
  - `F015` `KEY_SLOT_UNKNOWN`
  - `F016` `MANIFEST_CONTRACT_MISMATCH`
- Concrete `slaver_00_example.c` scaffold shapes for:
  - sideband payload structs
  - signed staging buffers and limits
  - `SIGNED_ADMISSION_ACK` send path
  - four firmware handlers:
    - `sc_ctrl_handle_signed_admission_begin(...)`
    - `sc_ctrl_handle_signed_admission_chunk(...)`
    - `sc_ctrl_handle_signed_admission_signature(...)`
    - `sc_ctrl_handle_signed_admission_commit(...)`
  - signed-path `JOB_REQ` branch hook:
    - `sc_ctrl_verify_signed_manifest_for_job_req(...)`
- Cleanup hooks so staged signed state is cleared on:
  - top-level runtime reset
  - watchdog timeout
  - `JOB_DONE`
  - `SAFE_STOP`
  - signed-path deny

What is intentionally still placeholder in this scaffold:

- `sc_public_key_slots[]` contains a placeholder slot-1 record and placeholder key bytes only.
- `sc_ctrl_verify_manifest_signature(...)` is a deny-by-default stub.
- `sc_ctrl_parse_manifest_contract(...)` is a deny-by-default stub.

Why that placeholder behavior is intentional:

- It makes the sideband control plumbing concrete now.
- It avoids falsely claiming that firmware already verifies signatures.
- It preserves the old host/runtime path when signed staging is not used.

Resulting runtime posture if this scaffold were applied as-is:

- `SIGNED_ADMISSION_BEGIN/CHUNK/SIGNATURE/COMMIT` can be staged and acknowledged.
- `COMMIT` can mark the stage `READY` once buffers and CRCs line up.
- The follow-up signed-path `JOB_REQ` still denies, because the real verifier/parser are not filled in yet.
- The legacy `JOB_REQ` path still behaves as before for non-signed jobs.

Committed byte-level references for the next firmware coding step:

- signed bundle:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.bundle.json`
- transport plan:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.transport.json`
- public key fixture:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`

Exact next firmware coding step:

1. Replace the placeholder `sc_public_key_slots[0].public_key_uncompressed` bytes with the chosen uncompressed P-256 public key for slot `1`.
2. Replace `sc_ctrl_verify_manifest_signature(...)` with the actual SHA-256 + ECDSA-P256 verification path using the accepted standalone-SDK crypto backend.
3. Replace `sc_ctrl_parse_manifest_contract(...)` with a strict parser for:
   - `artifact.sha256`
   - `job.deadline_ms`
   - `job.expected_outputs`
   - `job.job_flags`
4. Re-run the existing unchanged 44-byte `JOB_REQ` against the committed fixture transport plan and only then flip the signed path from deny-by-default to allow-on-success.
