# OpenAMP Signed Admission Real-Board Success Package

Date captured: 2026-03-16 20:38 +0800

## Purpose

This package records the now-confirmed real-board signed-admission success in a
durable repo location.

It is intentionally explicit about evidence quality:

- `Committed fixture evidence`: byte-level transport/manifest/public-key artifacts already in the repo.
- `Recovered local transient evidence`: board-build/install lineage recovered from
  local session transcripts and `/tmp` helper files at packaging time.
- `Session-confirmed final facts`: the operator-confirmed success facts handed
  into this task, where the raw final `140e...` frame dump was not persisted in
  the repo or in the local archived transcript.

No claim below is invented beyond those sources.

## Executive Summary

The final session-confirmed state is:

- Live board firmware is `140e2e8ca22d951d518907ab92a3ec910969fba6830481fc3d397193ac1712f1`.
- That firmware survives cold-start.
- The real-board signed sideband flow succeeded:
  - `SIGNED_ADMISSION_BEGIN` ACKed
  - `SIGNED_ADMISSION_CHUNK` ACKed
  - `SIGNED_ADMISSION_SIGNATURE` ACKed
  - `SIGNED_ADMISSION_COMMIT` ACKed
  - the follow-up unchanged `JOB_REQ` returned `JOB_ACK(ALLOW)`
- The same success was re-verified after `SAFE_STOP` cleanup with a fresh
  `job_id`.

The matching private signing key for the committed fixture public key is not
present in the repo/workspace search performed for this task, so baseline/current
signed-manifest validation was not possible from this workspace and was not
attempted.

## Evidence Boundary

### 1. Session-confirmed final facts

These four facts were handed forward as already confirmed in the active session:

1. Signed-admission firmware is on the board and cold-start survives.
2. Repeated real-board signed sideband flow succeeded:
   `BEGIN/CHUNK/SIGNATURE/COMMIT` all ACKed, and final `JOB_REQ` returned
   `JOB_ACK(ALLOW)`.
3. The success was re-verified after `SAFE_STOP` cleanup and a fresh `job_id`.
4. Live firmware now on board:
   `140e2e8ca22d951d518907ab92a3ec910969fba6830481fc3d397193ac1712f1`.

The raw final `140e...` board frame dump was not found in the repo, `/tmp`, or
the local archived session transcript, so this package preserves those facts as
session-confirmed rather than pretending to have recovered missing raw logs.

### 2. Committed fixture artifacts

The signed-admission success was explicitly described as the committed fixture
flow. The exact committed reference artifacts are:

- `session_bootstrap/examples/openamp_signed_manifest.fixture.bundle.json`
- `session_bootstrap/examples/openamp_signed_manifest.fixture.transport.json`
- `session_bootstrap/examples/openamp_signed_manifest.fixture.firmware_contract.json`
- `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`

Those artifacts define the exact byte-level shape of the reference signed flow:

- transport schema: `openamp_signed_admission_transport_plan/v1`
- reference `job_id`: `7301`
- manifest SHA-256:
  `dcde2829dcf76b7c974dc193ac93dd8641d2dfb948b15b4d46c9bbbef7f45d54`
- artifact SHA-256:
  `09af47ee1b0e2a7d3cad3add031f36811926e1fe34cfd58fa98d70eba9526b91`
- manifest length: `808`
- signature length: `71`
- chunk size: `160`
- chunk offsets: `0, 160, 320, 480, 640, 800`
- follow-up `JOB_REQ` payload:
  - `deadline_ms = 60000`
  - `expected_outputs = 300`
  - `flags = 2`
  - `job_flags = reconstruction`

That exact reference shape is the durable byte-level answer to "what success
shape were we trying to prove?"

### 3. Recovered local board-integration lineage

The final `140e...` trace was not recovered, but the local archived transcript
does preserve a concrete earlier signed-admission firmware integration lineage
showing that the work really did move onto the board source tree and the board
toolchain:

- board source snapshot recovered locally:
  - `/tmp/board_slaver_00_example.c`
  - sha256:
    `a8b3a064f39fe38fcc54be3b17b0d8e9108808077ded0ec3f37f0a3ad1c060ad`
- merged signed source snapshot recovered locally:
  - `/tmp/board_slaver_00_example.signed.c`
  - `2374` lines
  - sha256:
    `b1f2235d8dda6538a86816f00a10428851a31b0a32900dc6760c2e912b12e66d`
- earlier signed-admission board build and live install recovered from the
  local transcript:
  - built ELF:
    `phytiumpi_aarch64_firefly_openamp_core0.elf`
  - build/live SHA-256:
    `901e18027825689dc350b89a2b8da23607cf1234df896edadea92cfda3bd4789`
  - size:
    `1678832`
  - installed to `/lib/firmware/openamp_core0.elf`
  - reboot was triggered immediately after install
- immediately preceding small live firmware backup recovered from the same
  transcript:
  - live SHA-256:
    `45ab903160016ea1e0253c35df2e6ba2033b888142514576897dad50fdd479a1`
  - size:
    `911192`

Two recovered helper scripts also preserve the concrete board-side build
workarounds used during bring-up:

- `/tmp/openamp_mincrypto_build.sh`
- `/tmp/openamp_shafix_build.sh`

Their recovered hashes at packaging time were:

- `openamp_mincrypto_build.sh`:
  `583cc660d06e8fa668a369c0a72692d08aabc118a8733ff7b2366662306aabbd`
- `openamp_shafix_build.sh`:
  `09e529075b9109ecdfc618a662b2194896f563fefe30529c553bada88fe1d33c`

## Exact Success Shape

The exact signed-admission message shape used as the durable reference is:

1. `SIGNED_ADMISSION_BEGIN`
   - `manifest_len = 808`
   - `signature_len = 71`
   - `chunk_size = 160`
   - `manifest_sha256 = dcde2829dcf76b7c974dc193ac93dd8641d2dfb948b15b4d46c9bbbef7f45d54`
2. `SIGNED_ADMISSION_CHUNK` x6
   - offsets: `0, 160, 320, 480, 640, 800`
   - lengths: `160, 160, 160, 160, 160, 8`
3. `SIGNED_ADMISSION_SIGNATURE`
   - `signature_len = 71`
4. `SIGNED_ADMISSION_COMMIT`
   - `manifest_crc32 = 4253828123`
   - `signature_crc32 = 3659953669`
5. unchanged `JOB_REQ`
   - `expected_sha256 = 09af47ee1b0e2a7d3cad3add031f36811926e1fe34cfd58fa98d70eba9526b91`
   - `deadline_ms = 60000`
   - `expected_outputs = 300`
   - `flags = 2`

The session-confirmed real-board success matched that shape at the protocol
level and achieved:

- per-stage sideband ACKs for `BEGIN`, `CHUNK`, `SIGNATURE`, and `COMMIT`
- final `JOB_REQ -> JOB_ACK(ALLOW)`
- repeat `ALLOW` after `SAFE_STOP` cleanup with a fresh `job_id`

What is still missing from durable storage is the raw final ACK frame dump for
the `140e...` run. This package does not claim to have it.

## Blockers Overcome

### Legacy allowlist admission root

The original real-board control path admitted artifacts by comparing the 44-byte
`JOB_REQ.expected_sha256` against a static firmware allowlist. That was the
first blocker because it made every new artifact a firmware rewrite problem.

What changed:

- repo-side design and firmware artifacts introduced a dual-path model:
  - preserve legacy SHA allowlist fallback when no signed stage exists
  - allow staged signed-manifest verification when a signed stage exists for the
    `job_id`

This blocker was overcome at the design and board-source level before the final
real-board success.

### Signed sideband scaffold

No signed sideband existed in the original board source snapshot.

What changed:

- new control message IDs were introduced for:
  - `SIGNED_ADMISSION_BEGIN`
  - `SIGNED_ADMISSION_CHUNK`
  - `SIGNED_ADMISSION_SIGNATURE`
  - `SIGNED_ADMISSION_COMMIT`
  - `SIGNED_ADMISSION_ACK`
- staging state and ACK emission were added around those message types

Without that scaffold there was nothing for the board to ACK.

### mbedTLS integration

The board source had to move from a deny-by-default crypto boundary to a real
SDK-backed implementation.

Recovered evidence shows the integration path centered on:

- `SC_CTRL_USE_MBEDTLS`
- `mbedtls/ecdsa.h`
- `mbedtls/ecp.h`
- `mbedtls/sha256.h`

The recovered merged source snapshot and helper scripts show that the board-side
integration was not hypothetical; it was wired into the real board tree and
real board toolchain.

### Minimal crypto-only build path

The board-side bring-up did not succeed by simply flipping on a full generic
mbedTLS port. The recovered helper scripts show a narrower "minimal crypto"
path was used to get through the actual board build blockers:

- `openamp_mincrypto_build.sh`
  - injects `sdkconfig.h`
  - turns on `CONFIG_USE_MBEDTLS`
  - symlinks board tree `third-party/mbedtls` to the standalone-SDK copy
  - appends `third-party/mbedtls/include.mk`
  - appends a `lib_libmbedtls.a` build rule to `thirdparty.mk`
- `openamp_shafix_build.sh`
  - keeps the same minimal mbedTLS enablement
  - patches `mbedtls_sha256_ret(` to `mbedtls_sha256(`

That pair of recovered scripts is the durable evidence that the blocker was not
"we should use mbedTLS someday", but rather "we had to carve out the minimal
board build path that actually links and then fix the exact SHA symbol mismatch."

### Repeat validation after cleanup

The final success was not accepted as a one-shot lucky run.

Per the session-confirmed final facts, signed admission was re-validated after:

- `SAFE_STOP` cleanup
- a fresh `job_id`

This matters because it proves the board returned to a reusable READY state and
did not only admit a single staged run.

## Concrete Recovered Snippets

Recovered board compile success snippet:

```text
COPIED
b1f2235d8dda6538a86816f00a10428851a31b0a32900dc6760c2e912b12e66d  .../src/slaver_00_example.c
BUILD_OK
-rwxrwxr-x 1 user user 1678832 ... ./phytiumpi_aarch64_firefly_openamp_core0.elf
```

Recovered earlier signed live install snippet:

```text
901e18027825689dc350b89a2b8da23607cf1234df896edadea92cfda3bd4789  .../phytiumpi_aarch64_firefly_openamp_core0.elf
901e18027825689dc350b89a2b8da23607cf1234df896edadea92cfda3bd4789  /lib/firmware/openamp_core0.elf
```

Those snippets are not the final `140e...` run, but they are direct durable
evidence that the signed-admission lineage reached:

- real board source replacement
- real board bare-metal compilation
- real live firmware installation

before the final session-confirmed success advanced to `140e...`.

## Private Key Availability Check

Search scope used for this task:

- repo tree: `/home/tianxing/tvm_metaschedule_execution_project`
- transient workspace: `/tmp`
- local Codex state: `/home/tianxing/.codex`
- local home key material up to depth 6 under `/home/tianxing`

Search result:

- found the committed fixture public key:
  `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`
- found one unrelated private key:
  `/home/tianxing/.ssh/id_ed25519`
- found no PEM/DER/private-key material carrying:
  - `fixture-dev-20260316`
  - `openamp-fixture`
  - a P-256 private key matching the committed fixture public key

Conclusion:

- the matching private signing key is not available in the repo/workspace search
  performed for this task
- no attempt was made to fabricate, derive, or guess that private key
- baseline/current signed-manifest validation could not be attempted from this
  workspace

## Why Baseline Signed Validation Was Not Attempted

The gating reason is simple:

- the committed fixture public key is present
- the matching private signing key is absent

Without that key, a truthful baseline signed-manifest test cannot be run.

So for this task:

- `current` signed validation beyond the already-confirmed session facts was not
  re-driven
- `baseline` signed validation was not attempted

## Recommended Next Step Once the Private Key Is Available

1. Obtain the exact private key corresponding to:
   - `key_id = fixture-dev-20260316`
   - `channel = openamp-fixture`
   - `session_bootstrap/examples/openamp_signed_manifest.fixture.public.pem`
2. Build a signed baseline bundle with the existing tool:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py bundle \
  --artifact <baseline_artifact.so> \
  --private-key <fixture_private_key.pem> \
  --output <baseline_bundle.json> \
  --variant baseline \
  --key-id fixture-dev-20260316 \
  --publisher-channel openamp-fixture \
  --deadline-ms 60000 \
  --expected-outputs 300 \
  --job-flags reconstruction
```

3. Emit a transport plan with a fresh `job_id`:

```bash
python3 session_bootstrap/scripts/openamp_signed_manifest.py transport-plan \
  --signed-manifest <baseline_bundle.json> \
  --job-id <fresh_uint32_job_id> \
  --key-slot 1 \
  --output <baseline_transport.json>
```

4. Replay the exact proven real-board path used in the successful session:
   - sideband `BEGIN/CHUNK/SIGNATURE/COMMIT`
   - wait for each board ACK
   - follow with unchanged 44-byte `JOB_REQ`
   - confirm `JOB_ACK(ALLOW)`
5. Repeat the same with the current artifact and persist the raw board outputs
   this time:
   - each sideband ACK frame
   - final `JOB_ACK`
   - the post-`SAFE_STOP` repeat run

## What This Package Proves

This package proves, durably:

- the exact signed-admission reference wire shape used for the successful run
- the board-side signed-admission integration really reached board source merge,
  board toolchain build, and live firmware install
- the mbedTLS and minimal-crypto blocker-removal path is recoverable and not
  merely aspirational
- the final session-confirmed success state was:
  - cold-start survives
  - sideband stages ACKed
  - final `JOB_REQ -> JOB_ACK(ALLOW)`
  - repeat success after `SAFE_STOP` cleanup with fresh `job_id`
- baseline signed validation from this workspace was not possible because the
  matching private key is absent

## What This Package Does Not Claim

It does not claim that:

- the raw final `140e...` frame dump was recovered
- a baseline signed bundle was generated
- a baseline signed admission probe was run
- any private signing key exists in this repo/workspace

Those omissions are intentional and accurate.
