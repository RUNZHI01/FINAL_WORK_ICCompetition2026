# Phytium OpenAMP signed-manifest patch plan

Date: 2026-03-16

Status:

- Design and mapping only.
- No firmware C patch is included in this batch.
- The implementation-ordered execution plan now lives in:
  `session_bootstrap/patches/phytium_openamp_signed_admission_release_v1.4.0_patch_execution_plan_2026-03-16.md`

## Target firmware baseline

This plan assumes the current working baseline in repo terms is:

- patch note: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- patch file: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- target source: `example/system/amp/openamp_for_linux/src/slaver_00_example.c`

## Current code path to replace

Current SHA-only admission is centered on these firmware constructs from the existing patch:

- `ScTrustedArtifactEntry`
- `sc_trusted_artifact_allowlist[]`
- `sc_ctrl_is_trusted_artifact_sha(...)`
- `sc_ctrl_handle_job_req(...)`

Current decision path:

1. Parse `ScJobReqV1`
2. Read `request.expected_sha256`
3. Call `sc_ctrl_is_trusted_artifact_sha(request.expected_sha256, ...)`
4. Allow or deny

## Intended replacement architecture

Replace static per-artifact SHA admission with:

1. Firmware-embedded public-key table
2. Staged manifest buffer keyed by `manifest_sha256`
3. Detached signature staging
4. Manifest signature verification
5. Manifest parsing into the same execution contract fields currently extracted from `JOB_REQ`

The important shift is:

- `expected_sha256` stops being the policy root
- the signed manifest becomes the policy root
- `artifact.sha256` becomes one field inside that signed policy object

## Concrete patch plan by firmware area

### 1. Data structures

Add new structs near the current control message structs:

- `ScManifestChunk`
- `ScManifestSig`
- `ScManifestAck`
- `ScJobReqV2`
- `ScManifestStage`
- `ScPublicKeySlot`

Recommended new global/static state:

- `static ScManifestStage sc_manifest_stage;`
- `static const ScPublicKeySlot sc_public_key_slots[] = { ... };`

`ScManifestStage` should hold at least:

- `manifest_sha256[32]`
- `total_len`
- `received_len`
- `signature_len`
- `signature_algorithm`
- `key_slot`
- `manifest_ready`
- `signature_ready`
- `manifest_buf[...]`
- `signature_buf[...]`

### 2. Remove artifact allowlist as the admission gate

Delete the policy role of:

- `ScTrustedArtifactEntry`
- `sc_trusted_artifact_allowlist[]`
- `sc_ctrl_is_trusted_artifact_sha(...)`

It is acceptable to leave the old helper in place temporarily only for `ScJobReqV1` backward compatibility, but it should no longer be the admission path for `ScJobReqV2`.

### 3. Add public-key verification helpers

Introduce helpers such as:

- `sc_ctrl_lookup_public_key_slot(uint8_t key_slot, const ScPublicKeySlot **out_slot)`
- `sc_ctrl_verify_manifest_signature(...)`
- `sc_ctrl_sha256_manifest_bytes(...)`

Expected implementation detail:

- Use SHA-256 over the exact staged canonical manifest bytes
- Verify detached `ecdsa-p256-sha256` signature against the selected public key slot
- Prefer a small, well-understood crypto library already accepted by the firmware build

Likely practical choice:

- mbedTLS or PSA Crypto if already available in the standalone SDK

If the SDK does not already include a usable ECC verify path, the next step is to choose the smallest acceptable verifier and prove it builds in `pe2204_aarch64_phytiumpi_openamp_core0`.

### 4. Add manifest staging handlers

Extend the control callback switch to handle:

- `SC_MSG_MANIFEST_CHUNK`
- `SC_MSG_MANIFEST_SIG`
- `SC_MSG_MANIFEST_ACK`

Required checks:

- size bounds
- CRC32 of each chunk/signature payload
- consistent `manifest_sha256`
- in-order or explicitly offset-tracked staging
- stage reset on mismatch or overflow

### 5. Add `JOB_REQ_V2` parsing

Update `sc_ctrl_handle_job_req(...)` to:

- keep `payload_len == 44` as `ScJobReqV1`
- add `payload_len == 56` as `ScJobReqV2`

For `ScJobReqV2` with `admission_type == signed_manifest_v1`:

1. Ensure the staged manifest and signature are ready
2. Ensure `manifest_sha256` in `JOB_REQ_V2` matches the staged object
3. Verify the detached signature against the indicated public key slot
4. Parse the manifest JSON
5. Extract:
   - `artifact.sha256`
   - `job.deadline_ms`
   - `job.expected_outputs`
   - `job.job_flags`
   - `input_contract`
6. Enforce those values instead of trusting unsigned host-side duplicates
7. Transition guard state exactly as the current allow path does

### 6. JSON parsing boundary

Do not implement a large generic JSON parser. Keep the parser narrow:

- accept only the manifest schema used in `session_bootstrap/scripts/openamp_signed_manifest.py`
- parse only the fields needed for admission
- deny on extra complexity rather than trying to support arbitrary JSON

A practical implementation pattern is:

- scan for the required keys in the staged canonical JSON bytes
- or use a small token parser with tight field whitelisting

The parser must not silently fall back to defaults for required fields.

### 7. New deny/fault paths

Add new deny/fault codes for the signed path:

- `MANIFEST_NOT_STAGED`
- `MANIFEST_DIGEST_MISMATCH`
- `MANIFEST_PARSE_ERROR`
- `SIGNATURE_INVALID`
- `KEY_SLOT_UNKNOWN`
- `MANIFEST_CONTRACT_MISMATCH`

These should map to `JOB_ACK(DENY, fault_code=...)` in the same style as the current `F001/F002/...` path.

## Host-side files that will need follow-up changes once firmware is ready

- `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
  - add `MANIFEST_CHUNK`, `MANIFEST_SIG`, `MANIFEST_ACK`, and `JOB_REQ_V2` encoding/parsing
- `session_bootstrap/scripts/openamp_control_wrapper.py`
  - stop using the legacy `expected_sha256` mirror when the firmware path is ready
  - send staged manifest/signature before `JOB_REQ_V2`

## Minimum acceptance criteria for the firmware patch

1. `ScJobReqV1` still works for compatibility.
2. `ScJobReqV2` only allows when:
   - manifest staged
   - signature staged
   - key slot exists
   - signature verifies
   - manifest parses
   - manifest contract is valid
3. A tampered manifest is denied.
4. A tampered signature is denied.
5. An unknown `key_slot` is denied.
6. `STATUS_REQ` exposes the post-deny fault code.
7. `HEARTBEAT`, `SAFE_STOP`, and `JOB_DONE` still behave exactly as they do after a successful admit.

## Recommended next execution step after this repo batch

Patch `session_bootstrap/scripts/openamp_rpmsg_bridge.py` and the firmware C source together in one branch so the first board test can exercise the full staged-manifest flow instead of only local JSON scaffolding.
