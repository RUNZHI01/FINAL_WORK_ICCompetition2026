# Fast Demo Cold Start Design

## Problem

The demo currently has two unrelated startup delays.

First, `ssh_with_password_paramiko.py` reads all of standard input before it opens an SSH connection. When PowerShell launches it from an interactive terminal, the read waits for EOF forever. The user has to press `Ctrl+Z` and Enter before startup can continue.

Second, the control-plane backend copies the remote ML-KEM runtime one file at a time. A fresh Docker container and SSH or SCP connection is created for each step. The runtime contains `tcp_server.py`, five adjacent helper scripts, and the Python files in `mlkem_link`. The files are small, but repeated container startup and Tailscale SSH handshakes make the synchronization take several minutes. The backend remembers the content signature only in memory, so every backend restart repeats the work. Meanwhile, `start-dev.sh` gives the board security service only 90 seconds to become ready and reports failure while the background synchronization is still running.

The observed failed run began board-session initialization at 20:33:25, exited on the 90-second security deadline, and then became healthy at 20:38:50. The eventual status was `tongsuo-ML-KEM-768`, `sm4-gcm`, with `DUAL_REQUIRED` authentication.

## Goals

- An interactive `demo.ps1` run must never require a manual EOF keystroke.
- Keep the ML-KEM runtime installed permanently on the board.
- Skip content transfer when the board already has the current runtime bundle.
- Transfer a changed runtime with one archive upload rather than one upload per file.
- Target at most 60 seconds for a reachable-board cold start and 15 seconds when the board manifest matches.
- Print enough progress to distinguish asset verification, upload, service startup, and health waiting.
- Preserve the existing remote paths and the current automatic `tcp_server.py` restart rules.

## Non-goals

- Do not change ML-KEM, SM4, ML-DSA, or SM2 behavior.
- Do not change the USRP data-plane protocol.
- Do not require Git, rsync, or a new package on the board.
- Do not make the board copy the source of truth. The repository remains authoritative; the board keeps an installed runtime plus a content manifest.

## Chosen Approach

### Interactive stdin

The Paramiko helper will read stdin only when stdin is redirected or piped. An interactive TTY contributes an empty byte string immediately. Piped callers keep the existing behavior, including forwarding binary input and closing the remote stdin channel.

### Permanent board runtime and manifest

The backend will continue to derive the same remote paths it uses today. It will calculate the existing deterministic SHA-256 signature from every remote path and local file body. A manifest stored beside the remote server runtime will contain that signature.

Startup performs one SSH manifest check:

1. If the remote signature matches, record the signature in the in-process cache and skip the upload.
2. If the manifest is absent or differs, build one archive containing the complete runtime layout.
3. Upload that archive once to a temporary remote path.
4. Execute one remote install command that extracts into a staging directory, validates the expected files, moves them into their permanent paths, applies executable permissions, and writes the manifest last.
5. Remove temporary local and remote files in success and failure paths.

Writing the manifest last is the commit point. A failed transfer cannot mark a partial installation as current. Existing permanent files remain usable until their replacements have been extracted and validated.

The archive format will be `tar.gz`, which is already supported by the board delivery environment. Archive entries are relative to the parent directory of the remote `tcp_server.py`. The implementation must reject any asset path outside that root and must not emit absolute paths or `..` entries.

### Startup waiting and feedback

`start-dev.sh` will retain the required order: configure board access, start persistent USRP TX/RX, wait for the security service, probe the control plane, then launch Electron/Vite.

The security wait will use a 180-second safety deadline. Every ten seconds it will print elapsed time and the latest board status error. This deadline is not the primary speed fix; it prevents a valid first deployment from being reported as failed when hardware or Docker is temporarily slower than the target.

The backend will print whether the board manifest matched, whether a bundle upload started, how many files were included, and when the security status endpoint becomes ready. Passwords, private keys, and full environment dumps must not appear in logs.

## Alternatives Considered

### Increase the timeout only

This avoids the false failure but still spends several minutes uploading unchanged files after every backend restart. It does not meet the cold-start requirement.

### Parallel per-file uploads

Parallel uploads shorten wall-clock time but create many Docker containers and SSH sessions at once. They increase contention and leave the persistent-cache problem unchanged.

### One persistent SFTP session

This would also remove most handshake overhead, but the current Windows path intentionally routes board access through the reproducible Docker image. Adding a separate long-lived Paramiko/SFTP path would duplicate credential and error handling. A single archive keeps the existing Docker-based transport while reducing it to a few operations.

## Error Handling

- Interactive stdin detection failure defaults to no stdin rather than blocking.
- A manifest probe failure is treated as a cache miss and is logged without exposing credentials.
- Archive creation or path-validation failure stops synchronization before remote mutation.
- Upload or extraction failure returns an explicit synchronization error and does not update either signature cache.
- The old remote runtime remains available when installation does not reach the manifest commit point.
- The startup script reports the last board status error when the 180-second deadline expires.

## Testing

- Unit-test that the SSH helper returns immediately for a TTY and still reads redirected bytes.
- Add a regression test for an interactive invocation so the original EOF hang cannot return.
- Unit-test that a matching remote manifest performs no archive upload.
- Unit-test that a changed manifest creates one archive upload and one remote install operation for the complete asset set.
- Unit-test that a failed install does not write the new manifest or populate the in-process signature cache.
- Assert that archive entries preserve the expected runtime layout and reject traversal outside the remote root.
- Update the demo-script tests to require the 180-second deadline and periodic progress output.
- Run the targeted Python suites, the existing demo-script tests, and cockpit type checking before publishing.

## Delivery

Implementation happens in `FINAL_WORK_ICCompetition2026` on `main`, as requested. After tests pass, the change is committed and pushed to `origin/main`. `FINAL_WORK_ICCompetition2026_CLEAN` is inspected for local changes and then fast-forwarded to the pushed commit. No force push, reset, or destructive cleanup is allowed.
