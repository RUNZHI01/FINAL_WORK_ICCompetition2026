# OpenAMP signed-manifest admission design

Date: 2026-03-16

Status:

- First implementation batch in repo only.
- Host-side scaffolding is added in this batch.
- Board firmware does not support this yet.
- The implementation-ready wire refinement now lives in:
  `session_bootstrap/runbooks/openamp_signed_admission_transport_v1_2026-03-16.md`

## Current protocol baseline

This design is anchored to the current repo state:

- Firmware patch note: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.md`
- Firmware patch file: `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_release_v1.4.0_2026-03-14.patch`
- Linux bridge: `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
- Control wrapper: `session_bootstrap/scripts/openamp_control_wrapper.py`

The current `JOB_REQ` wire payload is a fixed 44-byte struct:

```c
struct ScJobReqV1 {
    uint8_t expected_sha256[32];
    uint32_t deadline_ms;
    uint32_t expected_outputs;
    uint32_t flags;
};
```

Current admission behavior in firmware:

- `sc_ctrl_handle_job_req(...)` parses the 44-byte payload.
- `sc_ctrl_is_trusted_artifact_sha(...)` checks `expected_sha256` against a built-in allowlist.
- The allowlist is compiled into firmware as static SHA-256 constants.

That works for a short list of demo artifacts, but it does not scale. Every new artifact requires a firmware edit, rebuild, redeploy, and keying mistakes are easy because the policy is just a hard-coded hash table.

## Product direction captured in this design

- Firmware stores public keys, not per-artifact SHA allowlists.
- Publishing/build infrastructure holds the private key.
- Admission is centered on a signed manifest, not only a raw `.so` byte signature.
- Current behavior remains available as the legacy path until the new firmware lands.

## Chosen crypto profile

This repo batch standardizes the host-side draft on:

- Signature algorithm: `ecdsa-p256-sha256`
- Manifest digest: `sha256(canonical_manifest_json_utf8)`
- Signature encoding in the signed bundle JSON: base64 of ASN.1 DER ECDSA signature bytes

Why this profile:

- It is easy to produce and verify today with the local `openssl` tool.
- It maps cleanly to likely firmware-side libraries such as mbedTLS or PSA Crypto.
- It avoids committing new Python crypto dependencies just to start the rollout.

## Manifest schema

Unsigned manifest schema id:

- `openamp_artifact_manifest/v1`

Signed bundle schema id:

- `openamp_signed_manifest_bundle/v1`

Unsigned manifest fields:

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `schema` | string | yes | Must equal `openamp_artifact_manifest/v1` |
| `manifest_version` | int | yes | Must equal `1` |
| `artifact.path` | string | yes | Human/audit path to the built `.so` |
| `artifact.sha256` | hex string | yes | Artifact integrity anchor |
| `artifact.size_bytes` | int | yes | Sanity check and audit metadata |
| `artifact.format` | string | yes | Example: `tvm-module-shared-object` |
| `artifact.variant` | string | yes | Example: `current`, `baseline` |
| `job.deadline_ms` | int | yes | Admission-time execution contract |
| `job.expected_outputs` | int | yes | Admission-time execution contract |
| `job.job_flags` | string | yes | Existing logical job marker |
| `input_contract.shape` | list[int, int, int, int] | yes | Expected input shape |
| `input_contract.dtype` | string | yes | Expected input dtype |
| `publisher.key_id` | string | yes | Selects the firmware public key slot |
| `publisher.channel` | string | yes | Provenance label for release lane |
| `provenance.created_at` | string | yes | Manifest creation time |
| `provenance.builder` | string | yes | Tooling identity |
| `provenance.source_repo` | string | yes | Repo identity |
| `provenance.source_git_commit` | string | no | Build provenance |
| `provenance.note` | string | no | Human note |

Example unsigned manifest:

- `session_bootstrap/examples/openamp_signed_manifest.example.json`

Signed bundle shape:

```json
{
  "schema": "openamp_signed_manifest_bundle/v1",
  "bundle_version": 1,
  "manifest_sha256": "<sha256 of canonical manifest bytes>",
  "manifest": {
    "...": "unsigned manifest object"
  },
  "signature": {
    "algorithm": "ecdsa-p256-sha256",
    "key_id": "dev-local-20260316",
    "encoding": "base64",
    "value": "<base64 DER signature>"
  }
}
```

Canonicalization rule used in this repo batch:

- Serialize the `manifest` object only
- UTF-8
- `json.dumps(..., sort_keys=True, separators=(",", ":"), allow_nan=False)`
- Signature covers those exact bytes

This is good enough for the first repo batch because:

- host-side tools can generate and verify it today
- the firmware patch can verify the exact received canonical bytes without having to reformat JSON

## Admission flow proposal

### Phase 0: current legacy path

Keep the current path unchanged:

1. Wrapper resolves `expected_sha256`
2. Bridge emits the current 44-byte `JOB_REQ`
3. Firmware checks the static SHA allowlist

### Phase 1: signed-manifest path

The refined execution-batch choice is now:

1. Host stages the canonical manifest JSON bytes to firmware.
2. Host stages the detached signature bytes to firmware.
3. Host sends the existing 44-byte `JOB_REQ`.
4. Firmware verifies the staged signed data and cross-checks it against that existing `JOB_REQ`.
5. Firmware admits or denies the job.

That keeps the current `JOB_REQ` semantics intact while adding signed admission alongside them.

## Proposed protocol extension

### New message types

Proposed additions adjacent to `JOB_REQ`:

- `SC_MSG_MANIFEST_CHUNK = 0x000C`
- `SC_MSG_MANIFEST_SIG = 0x000D`
- `SC_MSG_MANIFEST_ACK = 0x000E`

These are draft-only in this batch. They are documented here but not emitted by the current bridge yet.

### `MANIFEST_CHUNK` payload

```c
struct ScManifestChunk {
    uint8_t manifest_sha256[32];
    uint32_t total_len;
    uint32_t offset;
    uint32_t chunk_len;
    uint32_t chunk_crc32;
    uint8_t data[chunk_len];
};
```

Notes:

- `manifest_sha256` is the SHA-256 of the full canonical manifest bytes.
- `chunk_crc32` is transport integrity only.
- Firmware stores chunks in a per-job staging buffer keyed by `manifest_sha256`.

### `MANIFEST_SIG` payload

```c
struct ScManifestSig {
    uint8_t manifest_sha256[32];
    uint16_t signature_algorithm; /* 1 = ECDSA_P256_SHA256_DER */
    uint16_t key_slot;
    uint32_t sig_len;
    uint32_t sig_crc32;
    uint8_t signature[sig_len];
};
```

Notes:

- `key_slot` indexes the firmware public-key table.
- Detached signature bytes avoid forcing firmware to base64-decode a transport blob.

### `MANIFEST_ACK` payload

```c
struct ScManifestAck {
    uint8_t manifest_sha256[32];
    uint32_t stage;        /* chunk, signature, complete */
    uint32_t status;       /* accepted, duplicate, invalid_crc, invalid_sig, etc */
    uint32_t received_len;
    uint32_t expected_len;
};
```

### `JOB_REQ_V2` payload

```c
struct ScJobReqV2 {
    uint8_t admission_type;        /* 0 = sha_allowlist_v1, 1 = signed_manifest_v1 */
    uint8_t key_slot;
    uint16_t signature_algorithm;  /* 1 = ECDSA_P256_SHA256_DER */
    uint8_t manifest_sha256[32];
    uint32_t deadline_ms;
    uint32_t expected_outputs;
    uint32_t flags;
    uint32_t manifest_len;
    uint32_t reserved;
};
```

Behavior:

- `payload_len == 44` continues to mean the current `ScJobReqV1`
- `payload_len == 56` means `ScJobReqV2`
- `admission_type == 0` preserves the old SHA path
- `admission_type == 1` means:
  - do not consult static artifact SHA allowlists
  - require a previously staged manifest and signature
  - verify against the configured public key slot
  - parse the manifest and enforce `artifact.sha256`, `job.deadline_ms`, `job.expected_outputs`, `job.job_flags`, and `input_contract`

## Proposed firmware deny reasons

Legacy `F001 ARTIFACT_SHA_MISMATCH` remains for the old path.

New signed-manifest deny/fault codes should be added when the firmware patch is implemented:

- `F011 MANIFEST_NOT_STAGED`
- `F012 MANIFEST_DIGEST_MISMATCH`
- `F013 MANIFEST_PARSE_ERROR`
- `F014 SIGNATURE_INVALID`
- `F015 KEY_SLOT_UNKNOWN`
- `F016 MANIFEST_CONTRACT_MISMATCH`

These are design-only in this batch. No code in repo consumes them yet.

## Host-side workflow in this repo

New tool added in this batch:

- `session_bootstrap/scripts/openamp_signed_manifest.py`

Supported local workflow:

1. Build an unsigned manifest from an artifact:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py build \
  --artifact build/current/optimized_model.so \
  --output /tmp/openamp_manifest.json \
  --variant current \
  --key-id dev-local-20260316 \
  --publisher-channel openamp-dev
```

2. Sign it with a private key kept outside the repo:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py sign \
  --manifest /tmp/openamp_manifest.json \
  --private-key /secure/openamp/dev-local-20260316.pem \
  --output /tmp/openamp_manifest.signed.json
```

3. Verify it locally with a public key:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py verify \
  --signed-manifest /tmp/openamp_manifest.signed.json \
  --public-key /secure/openamp/dev-local-20260316.pub.pem \
  --artifact build/current/optimized_model.so
```

4. Build and sign in one command:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py bundle \
  --artifact build/current/optimized_model.so \
  --private-key /secure/openamp/dev-local-20260316.pem \
  --output /tmp/openamp_manifest.signed.json \
  --variant current \
  --key-id dev-local-20260316 \
  --publisher-channel openamp-dev
```

5. Emit the staged signed-admission transport plan that precedes the unchanged `JOB_REQ`:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py transport-plan \
  --signed-manifest /tmp/openamp_manifest.signed.json \
  --job-id 7301 \
  --key-slot 1 \
  --output /tmp/openamp_manifest.transport.json
```

Wrapper support added in this batch:

- `session_bootstrap/scripts/openamp_control_wrapper.py`

New wrapper flags:

- `--admission-mode legacy_sha|signed_manifest_v1`
- `--signed-manifest-file <bundle.json>`
- `--signed-manifest-public-key <pubkey.pem>`

Current behavior of the wrapper in signed mode:

- It loads the signed manifest bundle.
- It optionally verifies the bundle locally with the supplied public key.
- It derives `expected_sha256`, `deadline_ms`, `expected_outputs`, `job_flags`, and `variant` from the signed manifest.
- It still emits the existing `expected_sha256` mirror so the current bridge and current firmware behavior stay backward-compatible.
- It appends signed-manifest metadata to local manifests and control traces as a draft protocol sidecar.

What it does not do yet:

- It does not send `SIGNED_ADMISSION_BEGIN/CHUNK/SIGNATURE/COMMIT` on the real bridge yet.
- It does not change the current bridge binary wire format.

## Key handling expectations

- Private keys must stay outside this repo.
- The signer script only consumes a private key path; it does not generate or store keys in repo.
- Public keys should be exported as PEM for host-side verification and as DER or static byte arrays for firmware embedding.
- `publisher.key_id` and `signature.key_id` must match the firmware key slot naming.
- Rotation model:
  - add new public key slot in firmware
  - start signing new manifests with the new private key and `key_id`
  - keep the old key slot until old manifests no longer need admission

Recommended local key commands:

```bash
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out /secure/openamp/dev-local-20260316.pem
openssl pkey -in /secure/openamp/dev-local-20260316.pem -pubout -out /secure/openamp/dev-local-20260316.pub.pem
```

Do not commit the private key output.

## Next firmware step

The next real firmware step is to replace the static `sc_trusted_artifact_allowlist[]` check in `sc_ctrl_handle_job_req(...)` with a staged-manifest plus public-key verification flow. The concrete file/function patch plan is captured in:

- `session_bootstrap/patches/phytium_openamp_signed_manifest_patch_plan_2026-03-16.md`
- `session_bootstrap/patches/phytium_openamp_signed_admission_release_v1.4.0_patch_execution_plan_2026-03-16.md`
