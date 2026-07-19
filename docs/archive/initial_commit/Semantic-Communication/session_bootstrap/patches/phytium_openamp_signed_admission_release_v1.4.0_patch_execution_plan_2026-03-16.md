# Phytium OpenAMP signed-admission release_v1.4.0 patch execution plan

Date: 2026-03-16

Status:

- Firmware implementation plan only.
- Concrete enough for the next coding step in `slaver_00_example.c`.
- Leaves the legacy SHA-only path intact.

## Target baseline

This plan assumes the firmware file already contains the current control patch shape described in:

- `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`

Target C file:

- `example/system/amp/openamp_for_linux/src/slaver_00_example.c`

Current relevant functions from that baseline:

- `sc_ctrl_reset_runtime_state()`
- `sc_ctrl_clear_active_job()`
- `sc_ctrl_handle_job_req(...)`
- `sc_ctrl_handle_heartbeat(...)`
- `sc_ctrl_handle_job_done(...)`
- `sc_ctrl_handle_safe_stop(...)`
- `sc_ctrl_send_job_ack(...)`
- `sc_ctrl_send_status_resp(...)`
- `rpmsg_endpoint_cb(...)`

## Execution objective

Add firmware support for:

1. staging canonical manifest bytes
2. staging detached signature bytes
3. verifying the signature against a firmware public-key slot
4. parsing the narrow manifest schema
5. cross-checking that signed contract against the existing 44-byte `JOB_REQ`

Do not rewrite:

- the RPMsg service name
- the existing control header
- the existing `JOB_REQ` payload
- the existing `HEARTBEAT`, `SAFE_STOP`, or `JOB_DONE` wire contracts

## Concrete patch order

Apply the firmware work in this order. Each step maps to a small, reviewable edit in the current file.

### 1. Extend constants and fault codes

Near the current `SC_MSG_*` and `SC_FAULT_*` definitions, add:

```c
#define SC_MSG_SIGNED_ADMISSION_BEGIN      0x000CU
#define SC_MSG_SIGNED_ADMISSION_CHUNK      0x000DU
#define SC_MSG_SIGNED_ADMISSION_SIGNATURE  0x000EU
#define SC_MSG_SIGNED_ADMISSION_COMMIT     0x000FU
#define SC_MSG_SIGNED_ADMISSION_ACK        0x0010U

#define SC_FAULT_MANIFEST_NOT_STAGED       11U
#define SC_FAULT_MANIFEST_DIGEST_MISMATCH  12U
#define SC_FAULT_MANIFEST_PARSE_ERROR      13U
#define SC_FAULT_SIGNATURE_INVALID         14U
#define SC_FAULT_KEY_SLOT_UNKNOWN          15U
#define SC_FAULT_MANIFEST_CONTRACT_MISMATCH 16U

#define SC_ADMISSION_TYPE_SIGNED_MANIFEST_V1 1U
#define SC_SIGALG_ECDSA_P256_SHA256_DER      1U

#define SC_SIGNED_MANIFEST_MAX_LEN          1536U
#define SC_SIGNED_SIGNATURE_MAX_LEN         96U
#define SC_SIGNED_MANIFEST_CHUNK_MAX        160U

#define SC_SIGNED_STAGE_BEGIN               1U
#define SC_SIGNED_STAGE_CHUNK               2U
#define SC_SIGNED_STAGE_SIGNATURE           3U
#define SC_SIGNED_STAGE_COMMIT              4U

#define SC_SIGNED_ACK_ACCEPTED              0U
#define SC_SIGNED_ACK_DUPLICATE             1U
#define SC_SIGNED_ACK_OUT_OF_RANGE          2U
#define SC_SIGNED_ACK_CRC_ERROR             3U
#define SC_SIGNED_ACK_TOO_LARGE             4U
#define SC_SIGNED_ACK_READY                 5U
```

Do not remove existing `SC_FAULT_ARTIFACT_SHA`, `SC_FAULT_PARAM_RANGE`, or `SC_FAULT_DUPLICATE_JOB`.

### 2. Add new structs beside the existing control structs

Immediately after the current `ScStatusRespFrame` and before the allowlist struct area, add:

```c
typedef struct {
    uint8_t admission_type;
    uint8_t key_slot;
    uint16_t signature_algorithm;
    uint8_t manifest_sha256[32];
    uint32_t manifest_len;
    uint32_t signature_len;
    uint32_t chunk_size;
} ScSignedAdmissionBeginV1;

typedef struct {
    uint8_t manifest_sha256[32];
    uint32_t offset;
    uint32_t chunk_len;
    uint32_t chunk_crc32;
} ScSignedAdmissionChunkHdrV1;

typedef struct {
    uint8_t manifest_sha256[32];
    uint32_t signature_len;
    uint32_t signature_crc32;
} ScSignedAdmissionSignatureHdrV1;

typedef struct {
    uint8_t manifest_sha256[32];
    uint32_t manifest_crc32;
    uint32_t signature_crc32;
    uint32_t manifest_len;
    uint32_t signature_len;
} ScSignedAdmissionCommitV1;

typedef struct {
    uint8_t manifest_sha256[32];
    uint32_t stage;
    uint32_t status;
    uint32_t offset;
    uint32_t accepted_len;
} ScSignedAdmissionAckV1;

typedef struct {
    ScCtrlHdr header;
    ScSignedAdmissionAckV1 payload;
} ScSignedAdmissionAckFrame;

typedef struct {
    uint32_t job_id;
    uint8_t key_slot;
    uint16_t signature_algorithm;
    uint8_t manifest_sha256[32];
    uint32_t manifest_len;
    uint32_t received_manifest_len;
    uint32_t signature_len;
    uint32_t received_signature_len;
    uint32_t chunk_size;
    uint32_t ready_for_job_req;
    uint8_t manifest_buf[SC_SIGNED_MANIFEST_MAX_LEN];
    uint8_t signature_buf[SC_SIGNED_SIGNATURE_MAX_LEN];
} ScSignedAdmissionStage;

typedef struct {
    uint8_t slot_id;
    const char *key_id;
    uint8_t public_key_uncompressed[65];
} ScPublicKeySlot;

typedef struct {
    uint8_t artifact_sha256[32];
    uint32_t deadline_ms;
    uint32_t expected_outputs;
    uint32_t flags;
} ScManifestContract;
```

Why `public_key_uncompressed[65]`:

- it is a direct `0x04 || X || Y` P-256 point
- it avoids PEM parsing in the firmware patch
- it maps cleanly to mbedTLS point-loading helpers

### 3. Add new global state after the current runtime variables

Add:

```c
static ScSignedAdmissionStage sc_signed_stage;
static const ScPublicKeySlot sc_public_key_slots[] = {
    /* slot 1: populate from the chosen publishing public key */
};
```

Also extend reset helpers:

- `sc_ctrl_clear_active_job()` must not clear signed staging by itself
- `sc_ctrl_reset_runtime_state()` must call `sc_ctrl_clear_signed_stage()`
- `SAFE_STOP`, `JOB_DONE`, and watchdog timeout paths must clear signed staging after clearing the active job

### 4. Add small helpers before `sc_ctrl_handle_job_req(...)`

Implement these helpers in the same style as the existing C file:

- `sc_ctrl_clear_signed_stage(void)`
- `sc_ctrl_lookup_public_key_slot(uint8_t key_slot, const ScPublicKeySlot **out_slot)`
- `sc_ctrl_send_signed_admission_ack(...)`
- `sc_ctrl_handle_signed_admission_begin(...)`
- `sc_ctrl_handle_signed_admission_chunk(...)`
- `sc_ctrl_handle_signed_admission_signature(...)`
- `sc_ctrl_handle_signed_admission_commit(...)`
- `sc_ctrl_parse_manifest_contract(...)`
- `sc_ctrl_verify_signed_manifest_for_job_req(...)`

Required helper behavior:

`sc_ctrl_clear_signed_stage(void)`

- `memset(&sc_signed_stage, 0, sizeof(sc_signed_stage))`

`sc_ctrl_lookup_public_key_slot(...)`

- linear scan over `sc_public_key_slots[]`
- return `0/1` style success

`sc_ctrl_send_signed_admission_ack(...)`

- reply with `SC_MSG_SIGNED_ADMISSION_ACK`
- mirror `seq` and `job_id`
- fill `manifest_sha256`, `stage`, `status`, `offset`, `accepted_len`

`sc_ctrl_handle_signed_admission_begin(...)`

- require payload size `sizeof(ScSignedAdmissionBeginV1)`
- validate size limits
- validate `admission_type == SC_ADMISSION_TYPE_SIGNED_MANIFEST_V1`
- validate `signature_algorithm == SC_SIGALG_ECDSA_P256_SHA256_DER`
- clear old stage
- record `job_id`, lengths, slot, algorithm, and `manifest_sha256`
- send `ACK(stage=BEGIN,status=ACCEPTED)`

`sc_ctrl_handle_signed_admission_chunk(...)`

- require at least `sizeof(ScSignedAdmissionChunkHdrV1)` bytes
- require stage `job_id` match
- require manifest SHA match
- require `offset == received_manifest_len` in v1
- require `offset + chunk_len <= manifest_len`
- verify `chunk_crc32`
- append bytes to `manifest_buf`
- update `received_manifest_len`
- send `ACK(stage=CHUNK,status=ACCEPTED,offset=<offset>,accepted_len=<chunk_len>)`

`sc_ctrl_handle_signed_admission_signature(...)`

- require stage exists and `job_id` matches
- require manifest SHA match
- require `signature_len <= SC_SIGNED_SIGNATURE_MAX_LEN`
- verify signature CRC
- copy bytes into `signature_buf`
- set `received_signature_len`
- send `ACK(stage=SIGNATURE,status=ACCEPTED,accepted_len=<signature_len>)`

`sc_ctrl_handle_signed_admission_commit(...)`

- require stage exists and `job_id` matches
- require manifest SHA match
- require `received_manifest_len == manifest_len`
- require `received_signature_len == signature_len`
- verify full-buffer CRCs
- set `ready_for_job_req = 1`
- send `ACK(stage=COMMIT,status=READY,accepted_len=<manifest_len>)`

### 5. Implement signature verification with a single chosen crypto path

Inside `sc_ctrl_verify_signed_manifest_for_job_req(...)`, do this in order:

1. ensure `sc_signed_stage.ready_for_job_req != 0`
2. ensure `sc_signed_stage.job_id == request_header->job_id`
3. recompute SHA-256 of `manifest_buf[0:manifest_len]`
4. compare to `sc_signed_stage.manifest_sha256`
5. look up `key_slot`
6. verify ECDSA signature over the exact staged manifest bytes
7. parse the manifest into `ScManifestContract`
8. compare that contract to the incoming `ScJobReq`

Use only one crypto backend in the first patch. Preferred order:

1. mbedTLS if already available in the standalone SDK build
2. PSA Crypto if that is the accepted project path on this board support package

Do not implement hand-written ECC math.

### 6. Keep manifest parsing narrow

The parser only needs to accept the exact schema already produced by:

- `session_bootstrap/scripts/openamp_signed_manifest.py`

The parser only needs these fields:

- `artifact.sha256`
- `job.deadline_ms`
- `job.expected_outputs`
- `job.job_flags`

Optional but recommended fields for later diagnostics:

- `publisher.key_id`
- `publisher.channel`
- `input_contract.shape`
- `input_contract.dtype`

If a required field is missing or malformed, return `SC_FAULT_MANIFEST_PARSE_ERROR`.

Do not silently default values.

### 7. Modify `sc_ctrl_handle_job_req(...)`, not the `JOB_REQ` struct

Keep the current `ScJobReq` definition and `payload_len == sizeof(ScJobReq)` check.

Replace the current allowlist-only branch with:

1. duplicate/guard checks exactly as today
2. if `sc_signed_stage.job_id == request_header->job_id`:
   - call `sc_ctrl_verify_signed_manifest_for_job_req(...)`
   - on success, allow
   - on failure, deny with `F011..F016`
3. else:
   - keep the current legacy SHA allowlist behavior unchanged

This is the key compatibility point:

- old host path still works
- new host path can stage a signed manifest first and then reuse the existing `JOB_REQ`

### 8. Extend `rpmsg_endpoint_cb(...)`

In the current `switch (header.msg_type)`, add cases before `SC_MSG_JOB_REQ`:

- `SC_MSG_SIGNED_ADMISSION_BEGIN`
- `SC_MSG_SIGNED_ADMISSION_CHUNK`
- `SC_MSG_SIGNED_ADMISSION_SIGNATURE`
- `SC_MSG_SIGNED_ADMISSION_COMMIT`

Each case should call its helper and return `RPMSG_SUCCESS` after transmitting the ack.

`SC_MSG_SIGNED_ADMISSION_ACK` is firmware-to-host only and does not need a receive handler.

### 9. Clear signed staging anywhere a job lifecycle ends

Update these paths:

- watchdog timeout path
- `SAFE_STOP` success path
- `JOB_DONE` success path
- `JOB_DONE` failure path
- `JOB_REQ` signed-path deny after verification failure
- top-level app reset before `FRpmsgEchoApp(...)`

Reason:

- stale signed staging must never survive into a new job

## Initial public-key population step

The repo now contains a committed public-key fixture:

- `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`

The next firmware coding step should convert the chosen public key into one `public_key_uncompressed[65]` array and place it in `sc_public_key_slots[]` as `slot_id = 1`.

Do not add any private key material to firmware or repo.

## First board-side acceptance run

Use the committed example artifacts as the first integration target:

- bundle:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.bundle.json`
- transport plan:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.transport.json`

Required first board acceptance criteria:

1. each sideband staging message receives `SIGNED_ADMISSION_ACK`
2. `COMMIT` returns `status = READY`
3. the follow-up unchanged `JOB_REQ` returns `JOB_ACK(ALLOW)`
4. a tampered chunk CRC returns `SIGNED_ADMISSION_ACK(CRC_ERROR)`
5. a tampered signature returns `JOB_ACK(DENY, F014)`
6. a mismatched `deadline_ms` or `expected_outputs` in `JOB_REQ` returns `JOB_ACK(DENY, F016)`

## Exact next coding step

The next firmware-side coding step is:

Implement the new sideband structs, staging state, four `SIGNED_ADMISSION_*` handlers, and the signed-branch inside `sc_ctrl_handle_job_req(...)` in `example/system/amp/openamp_for_linux/src/slaver_00_example.c`, using the committed transport fixture as the byte-level reference.
