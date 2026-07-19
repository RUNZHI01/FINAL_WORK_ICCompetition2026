# OpenAMP signed-admission transport v1

Date: 2026-03-16

Status:

- Execution-batch protocol definition.
- Refines the first-batch signed-manifest design into an implementation-ready wire contract.
- Keeps the existing 44-byte `JOB_REQ` as the final admission trigger.

## Baseline this extends

This protocol is anchored to the current working control path:

- current firmware patch note:
  `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- current firmware patch file:
  `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- current bridge:
  `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
- first-batch signed-manifest design:
  `session_bootstrap/runbooks/openamp_signed_manifest_admission_design_2026-03-16.md`

The signed-admission transport is intentionally an extension around the current path, not a replacement:

1. Host still sends the existing binary `JOB_REQ`.
2. Signed manifest data is staged first over new sideband message types.
3. Firmware uses the staged signed data to validate the existing `JOB_REQ` fields.
4. If no signed staging exists for that `job_id`, firmware can still take the legacy SHA-only path.

That preserves backward compatibility and keeps the wrapper contract stable.

## Existing unchanged frame header

The wire header stays exactly as it is today:

```c
struct ScCtrlHdr {
    uint32_t magic;        /* 0x53434F4D */
    uint16_t version;      /* 1 */
    uint16_t msg_type;
    uint32_t seq;
    uint32_t job_id;
    uint32_t payload_len;
    uint32_t header_crc32;
};
```

Header CRC remains:

- little-endian packed bytes of `magic/version/msg_type/seq/job_id/payload_len`
- polynomial implementation identical to current firmware patch and current Linux bridge

## Existing unchanged `JOB_REQ`

The final admission trigger remains the current 44-byte payload:

```c
struct ScJobReq {
    uint8_t expected_sha256[32];
    uint32_t deadline_ms;
    uint32_t expected_outputs;
    uint32_t flags;
};
```

Signed admission does not replace these fields. Instead, firmware cross-checks them against the staged manifest:

- `expected_sha256` must equal `manifest.artifact.sha256`
- `deadline_ms` must equal `manifest.job.deadline_ms`
- `expected_outputs` must equal `manifest.job.expected_outputs`
- `flags` must equal the wire mapping of `manifest.job.job_flags`

Wire flag mapping remains:

- `1 = payload`
- `2 = reconstruction`
- `3 = smoke`

## New sideband message types

These values extend the current message map:

| Name | Value | Purpose |
| --- | ---: | --- |
| `SIGNED_ADMISSION_BEGIN` | `0x000C` | Bind a signed-manifest staging session to `header.job_id` |
| `SIGNED_ADMISSION_CHUNK` | `0x000D` | Transmit canonical manifest JSON bytes |
| `SIGNED_ADMISSION_SIGNATURE` | `0x000E` | Transmit detached ECDSA signature bytes |
| `SIGNED_ADMISSION_COMMIT` | `0x000F` | Mark staging complete and ready for `JOB_REQ` |
| `SIGNED_ADMISSION_ACK` | `0x0010` | Acknowledge begin/chunk/signature/commit |

## Fixed constants for v1

These are intentionally concrete so the next firmware step can implement them directly:

- `admission_type = 1` means `signed_manifest_v1`
- `signature_algorithm = 1` means `ecdsa-p256-sha256-der`
- `manifest_max_len = 1536`
- `signature_max_len = 96`
- `chunk_data_max = 160`
- `max_chunk_count = 10`

Why these limits:

- they comfortably cover the current manifest schema
- each chunk frame stays below the current informal `<256B` control-frame target
- the staging buffer cost is explicit and small enough for the current firmware file-scope model

## Sideband payloads

### `SIGNED_ADMISSION_BEGIN`

Payload size: 48 bytes

```c
struct ScSignedAdmissionBeginV1 {
    uint8_t admission_type;        /* 1 = signed_manifest_v1 */
    uint8_t key_slot;              /* firmware public-key slot index */
    uint16_t signature_algorithm;  /* 1 = ecdsa-p256-sha256-der */
    uint8_t manifest_sha256[32];
    uint32_t manifest_len;
    uint32_t signature_len;
    uint32_t chunk_size;
};
```

Rules:

- `header.job_id` binds the staging session to the future `JOB_REQ`
- `manifest_len <= 1536`
- `signature_len <= 96`
- `chunk_size <= 160`
- firmware clears any older signed-admission stage for the same `job_id` before accepting a new begin

### `SIGNED_ADMISSION_CHUNK`

Payload size: 44 bytes of header plus `chunk_len`

```c
struct ScSignedAdmissionChunkV1 {
    uint8_t manifest_sha256[32];
    uint32_t offset;
    uint32_t chunk_len;
    uint32_t chunk_crc32;
    uint8_t data[chunk_len];
};
```

Rules:

- `offset + chunk_len <= manifest_len`
- `chunk_len > 0`
- `chunk_len <= chunk_size` from `SIGNED_ADMISSION_BEGIN`
- `chunk_crc32` is CRC-32 of `data`
- v1 host sends chunks strictly in ascending offset order
- v1 firmware may reject out-of-order chunks rather than supporting sparse assembly

### `SIGNED_ADMISSION_SIGNATURE`

Payload size: 40 bytes of header plus `signature_len`

```c
struct ScSignedAdmissionSignatureV1 {
    uint8_t manifest_sha256[32];
    uint32_t signature_len;
    uint32_t signature_crc32;
    uint8_t signature[signature_len];
};
```

Rules:

- detached signature bytes are the raw ASN.1 DER ECDSA signature
- `signature_crc32` is CRC-32 of the signature bytes
- base64 exists only inside the host-side bundle JSON, not on the firmware wire

### `SIGNED_ADMISSION_COMMIT`

Payload size: 48 bytes

```c
struct ScSignedAdmissionCommitV1 {
    uint8_t manifest_sha256[32];
    uint32_t manifest_crc32;
    uint32_t signature_crc32;
    uint32_t manifest_len;
    uint32_t signature_len;
};
```

Rules:

- firmware verifies received lengths match the begin record
- firmware verifies CRC-32 of the fully assembled manifest buffer
- firmware verifies CRC-32 of the staged signature buffer
- on success firmware marks the stage `ready_for_job_req = 1`

### `SIGNED_ADMISSION_ACK`

Payload size: 48 bytes

```c
struct ScSignedAdmissionAckV1 {
    uint8_t manifest_sha256[32];
    uint32_t stage;        /* 1=BEGIN, 2=CHUNK, 3=SIGNATURE, 4=COMMIT */
    uint32_t status;       /* see table below */
    uint32_t offset;       /* chunk offset or 0 */
    uint32_t accepted_len; /* chunk_len, signature_len, or total_len */
};
```

Status codes:

| Status | Value | Meaning |
| --- | ---: | --- |
| `ACCEPTED` | `0` | stage accepted |
| `DUPLICATE` | `1` | same begin/chunk/signature already present |
| `OUT_OF_RANGE` | `2` | offset/length mismatch |
| `CRC_ERROR` | `3` | chunk/signature/commit CRC mismatch |
| `TOO_LARGE` | `4` | declared lengths exceed v1 limits |
| `READY` | `5` | commit succeeded; signed admission is ready for `JOB_REQ` |

## Required host sequence

For `admission_mode = signed_manifest_v1`, the host sequence is:

1. `SIGNED_ADMISSION_BEGIN`
2. one or more `SIGNED_ADMISSION_CHUNK`
3. `SIGNED_ADMISSION_SIGNATURE`
4. `SIGNED_ADMISSION_COMMIT`
5. existing `JOB_REQ`

The same `header.job_id` is used for all five messages.

The host must wait for `SIGNED_ADMISSION_ACK` after each sideband message in v1. That keeps the firmware implementation simple and makes board-side failure reasons observable before `JOB_REQ`.

## Required firmware behavior on `JOB_REQ`

When firmware receives the unchanged 44-byte `JOB_REQ`, it chooses the path below:

### Path A: no staged signed admission for `job_id`

- current legacy allowlist path
- exact behavior stays unchanged

### Path B: staged signed admission is `ready_for_job_req`

Firmware must:

1. verify the staged manifest SHA matches the staged bytes
2. look up `key_slot`
3. verify the detached ECDSA signature over the exact staged canonical manifest bytes
4. parse only the required manifest fields
5. cross-check the existing `JOB_REQ` fields against the signed manifest
6. allow only if every check passes

Required extracted manifest fields:

- `artifact.sha256`
- `job.deadline_ms`
- `job.expected_outputs`
- `job.job_flags`
- `publisher.key_id`
- `publisher.channel`
- `input_contract.shape`
- `input_contract.dtype`

The firmware does not need a general JSON feature set. It only needs a strict parser for this schema.

## New deny codes for the signed path

These extend the current fault-code range:

| Code | Name | Meaning |
| --- | --- | --- |
| `F011` | `MANIFEST_NOT_STAGED` | `JOB_REQ` arrived before commit succeeded |
| `F012` | `MANIFEST_DIGEST_MISMATCH` | staged bytes do not match declared manifest SHA |
| `F013` | `MANIFEST_PARSE_ERROR` | required manifest fields cannot be parsed |
| `F014` | `SIGNATURE_INVALID` | ECDSA verification failed |
| `F015` | `KEY_SLOT_UNKNOWN` | `key_slot` has no firmware public key |
| `F016` | `MANIFEST_CONTRACT_MISMATCH` | signed manifest disagrees with `JOB_REQ` |

## Stage lifetime and cleanup

The signed-admission stage must be cleared:

- when a new `SIGNED_ADMISSION_BEGIN` arrives for the same `job_id`
- after a successful `JOB_REQ(ALLOW)`
- after a signed-path `JOB_REQ(DENY)`
- when `SAFE_STOP` clears the active job
- when `JOB_DONE` clears the active job
- when the watchdog clears the active job
- during top-level runtime reset at app start

This keeps stale signed state from leaking across jobs.

## Host mapping from current wrapper output

The current wrapper already exposes all required metadata in hook payloads:

- `payload.expected_sha256`
- `payload.deadline_ms`
- `payload.expected_outputs`
- `payload.job_flags`
- `payload.signed_manifest.*`

The bridge only needs one new behavior:

1. read the full signed bundle JSON locally
2. canonicalize `bundle.manifest`
3. send the four sideband staging messages
4. send the existing 44-byte `JOB_REQ`

No wrapper schema change is required for this.

## Concrete example fixtures in repo

These fixtures were generated from the current tool output and are committed for firmware bring-up:

- artifact:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.artifact.so`
- public key:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`
- signed bundle:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.bundle.json`
- transport plan:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.transport.json`

The transport fixture uses:

- `job_id = 7301`
- `key_slot = 1`
- `chunk_size = 160`

The committed transport plan is the exact reference for the first firmware implementation step.

## Why this transport is the chosen v1 refinement

The first-batch design left room for a `JOB_REQ_V2` descriptor. This execution batch refines that choice:

- keep `JOB_REQ` unchanged
- stage signed data alongside it
- let firmware cross-check, not reinterpret, the existing job contract

That is the lowest-churn path from the currently deployed `release_v1.4.0` control patch to firmware-backed signed admission.
