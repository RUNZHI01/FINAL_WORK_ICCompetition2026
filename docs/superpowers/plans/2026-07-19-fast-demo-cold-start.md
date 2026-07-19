# Fast Demo Cold Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the interactive EOF hang and reduce ML-KEM board-runtime cold start from several minutes to one bundled transfer, while skipping transfer when the board manifest matches.

**Architecture:** Keep the repository authoritative and the runtime permanently installed on the board. Compute one deterministic asset signature, probe a board-side signature file, and on mismatch upload one `tar.gz` followed by one atomic install command. Preserve piped stdin in the Paramiko helper but never read an interactive TTY.

**Tech Stack:** Python 3, `tarfile`, Paramiko, Docker-backed SSH/SCP helpers, Bash, unittest/pytest.

## Global Constraints

- Work directly in `FINAL_WORK_ICCompetition2026` on `main`, as explicitly requested.
- Do not expose passwords, identity keys, or environment dumps.
- Do not add board dependencies such as Git or rsync.
- Keep existing remote runtime paths and cryptographic behavior.
- Push the verified commit to `origin/main`, then fast-forward `FINAL_WORK_ICCompetition2026_CLEAN`.

---

### Task 1: Non-blocking interactive SSH helper input

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/scripts/ssh_with_password_paramiko.py`
- Test: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_ssh_with_password_paramiko.py`

**Interfaces:**
- Produces: `read_stdin_bytes(stream: object) -> bytes`
- Consumes: `main()` passes its result to the existing `run_remote_command(..., stdin_bytes=...)`.

- [ ] **Step 1: Write failing TTY and redirected-input tests**

Add a fake input stream that records `read()` calls. Assert a TTY returns `b""` without reading, and a redirected stream returns its bytes.

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_ssh_with_password_paramiko.py -q
```

Expected: failure because `read_stdin_bytes` does not exist.

- [ ] **Step 3: Implement the minimal input selector**

Add `read_stdin_bytes`. If `stream.isatty()` is true, return immediately. Otherwise read from `stream.buffer` when present, falling back to `stream`. Update `main()` to call it.

- [ ] **Step 4: Verify the focused tests pass**

Run the same pytest command. Expected: all tests pass.

### Task 2: Persistent board manifest and bundled asset transfer

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Test: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`

**Interfaces:**
- Consumes: existing `run_ssh_command`, `run_scp_file`, `BoardAccessConfig`, and the asset list built by `_sync_remote_mlkem_server_assets`.
- Produces: `_sync_remote_mlkem_server_assets(...) -> dict[str, Any]` with the existing `updated`, `note`, and error semantics.

- [ ] **Step 1: Replace the per-file upload expectation with failing bundle tests**

Cover three behaviors:

1. A successful remote signature probe skips SCP on a fresh backend instance.
2. A cache miss creates one archive containing every expected relative path, invokes SCP once, and invokes one install SSH command after the probe.
3. A failed install returns an error and does not populate the in-process signature cache.

- [ ] **Step 2: Verify the bundle tests fail**

Run:

```powershell
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "sync_remote_mlkem_server_assets" -q
```

Expected: failures showing the current implementation performs one upload per asset and has no remote signature probe.

- [ ] **Step 3: Implement deterministic bundle installation**

Import `tarfile`. Retain the existing asset discovery and SHA-256 calculation. Use the parent of the remote `tcp_server.py` as the install root and reject any asset outside it. Probe `.openamp-mlkem-assets.sha256` with one SSH command that exits zero only on a signature match.

On mismatch, create a temporary `tar.gz` with safe relative entry names, SCP it once to `/tmp`, and run one `set -eu` installation command. The command extracts to a temporary directory, verifies every expected file, installs them with mode `0755`, and atomically writes the signature file last. Clean local and remote temporary files in all paths. Populate the in-process signature cache only after a matching probe or successful install.

- [ ] **Step 4: Verify the bundle tests pass**

Run the focused pytest command again. Expected: all selected tests pass.

### Task 3: Startup deadline and visible progress

**Files:**
- Modify: `Semantic-Communication/cockpit_desktop/start-dev.sh`
- Test: `docker/test_demo_scripts.py`

**Interfaces:**
- Consumes: `/api/crypto-status` response fields already returned by the backend.
- Produces: a 180-second security deadline and a progress line at least every ten seconds.

- [ ] **Step 1: Add failing script-contract assertions**

Assert `start-dev.sh` uses a 180-second crypto deadline and prints elapsed security-wait progress including the latest error.

- [ ] **Step 2: Verify the assertions fail**

Run:

```powershell
python -m pytest docker/test_demo_scripts.py -q
```

Expected: new assertions fail against the 90-second silent loop.

- [ ] **Step 3: Implement the deadline and progress output**

Change the deadline to 180 seconds. Track the start time and print elapsed seconds plus the latest non-empty error every ten seconds. Keep the readiness condition unchanged.

- [ ] **Step 4: Verify script tests pass**

Run the same pytest command. Expected: all tests pass.

### Task 4: Full verification and delivery

**Files:**
- Verify all modified files and the two Superpowers documents.

- [ ] **Step 1: Run focused and regression suites**

```powershell
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_ssh_with_password_paramiko.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "sync_remote_mlkem_server_assets or write_remote_text_file" -q
python -m pytest docker/test_demo_scripts.py -q
```

- [ ] **Step 2: Run static checks**

```powershell
python -m py_compile Semantic-Communication/session_bootstrap/scripts/ssh_with_password_paramiko.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py
git diff --check
```

- [ ] **Step 3: Inspect and commit only intended changes**

Review `git status -sb` and `git diff`. Stage explicit paths and commit with `fix: accelerate demo cold start`.

- [ ] **Step 4: Push and update CLEAN**

Push `main` to `origin`. Confirm CLEAN has no local changes, run `git pull --ff-only`, and verify both checkouts resolve to the same commit.
