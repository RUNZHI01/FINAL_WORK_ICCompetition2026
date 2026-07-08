# Cockpit USRP IQ Direct Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore cockpit desktop prerecorded TVM performance, restore USRP full-chain demo, and expose QPSK vs IQ-direct transport selection with IQ direct becoming the default after stability verification.

**Architecture:** Keep cockpit as the operator surface and `server.py` as the state/API boundary. Reuse existing USRP persistent TX/RX services; select between `RunQpskFileBatchSpoolArq.py` and `RunAnalogLatentBatch.py` through explicit environment/config state. Keep prerecorded TVM and USRP transport metrics separate so the UI does not mix reconstruction time with data-plane airtime.

**Tech Stack:** Python demo backend, Electron/React cockpit, Docker launch scripts, NI USRP-2922 helpers, pytest, npm typecheck.

## Global Constraints

- Windows field runs use native PowerShell + Docker or Git Bash only; do not use WSL.
- Bash/SSH work should run inside Docker when possible.
- TVM prerecorded target is 300 images within 250 ms +/- 10 ms in cockpit.
- TVM current chain must include handwritten operator artifact and big.LITTLE runner.
- USRP transport must expose QPSK and IQ direct as selectable modes.
- IQ direct must target total transport time well below TVM reconstruction time.
- Each milestone updates one-click scripts and docs, then commits; every third commit is followed by a push.

---

### Task 1: Commit Prerecorded TVM250 Milestone

**Files:**
- Modify: `docker/start-electron-prod-demo.sh`
- Modify: `docker/run-demo.sh`
- Modify: `docker/run-demo.ps1`
- Modify: `docker/run-demo-tailscale.sh`
- Modify: `docker/run-demo-tailscale.ps1`
- Modify: `README.md`
- Modify: `docker/README.md`
- Test: `docker/test_demo_scripts.py`

**Interfaces:**
- Consumes: live API `/api/run-inference-batch`, `/api/batch-state`, `/api/system-status`.
- Produces: `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded`, with `OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded`, `MLKEM_TRANSPORT_MODE=tcp`, and default `MLKEM_AUTH_ENABLED=0`.

- [x] **Step 1: Write the failing test**

```python
def test_start_electron_has_tvm250_prerecorded_profile():
    script = read_script("start-electron-prod-demo.sh")
    assert "ICCOMP_COCKPIT_PROFILE" in script
    assert "tvm250-prerecorded" in script
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest docker/test_demo_scripts.py -q`

Expected before implementation: FAIL because the profile and env forwarding are absent.

- [x] **Step 3: Write minimal implementation**

Add the `tvm250-prerecorded` profile in `docker/start-electron-prod-demo.sh`, forward board/profile env in `run-demo.*`, and set the profile by default in `run-demo-tailscale.*`.

- [x] **Step 4: Run tests and live verification**

Run:

```powershell
python -m pytest docker/test_demo_scripts.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -q -k "uses_runner_summary_for_tvm_benchmark or compute_tvm_benchmark or start_batch_inference_usrp_tvm_hydrates_recent_current_quality"
```

Live evidence: `openamp3_handwritten_mean4_v7_big_little_current_20260708_233215`, 300/300, fallback 0, mean 244.23 ms.

- [ ] **Step 5: Commit**

```powershell
git add README.md docker/README.md docker/*.ps1 docker/*.sh docker/test_demo_scripts.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py
git commit -m "feat: restore cockpit tvm250 prerecorded profile"
```

### Task 2: Restore USRP Full-Chain Mode

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/usrp_runtime.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/hooks/useBatchState.ts`
- Test: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`

**Interfaces:**
- Consumes: `MLKEM_TRANSPORT_MODE=usrp`, `OPENAMP_DEMO_LINK_MODE=qpsk`, existing USRP TX/RX control ports.
- Produces: batch state with host preprocess, transport, and inference progress populated for USRP mode.

- [ ] **Step 1: Write failing backend test**

Add a test that sets `MLKEM_TRANSPORT_MODE=usrp` and `OPENAMP_DEMO_LINK_MODE=qpsk`, mocks USRP control readiness, and expects `/api/run-inference-batch` to produce non-empty `transport_progress` and a `runner_summary` from the QPSK runner.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -q -k usrp`

- [ ] **Step 3: Implement minimal restoration**

Route USRP batch execution through the existing QPSK runner when `OPENAMP_DEMO_LINK_MODE=qpsk`; keep prerecorded TVM path unchanged.

- [ ] **Step 4: Verify**

Run the targeted pytest and then a small live USRP count such as 5 or 50 before attempting 300.

- [ ] **Step 5: Update docs/script and commit**

Update `README.md`, `docker/README.md`, and one-click env forwarding if a new variable is introduced. Commit as `feat: restore cockpit usrp qpsk mode`.

### Task 3: Add QPSK vs IQ Direct Selection

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/usrp_runtime.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/board_access.py`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx`
- Test: backend USRP tests and cockpit typecheck.

**Interfaces:**
- Consumes: `OPENAMP_DEMO_LINK_MODE=qpsk|iq-direct`.
- Produces: UI selector and backend mode state that choose QPSK runner or `USRP292x/RunAnalogLatentBatch.py`.

- [ ] **Step 1: Write failing tests**

Add backend tests asserting `iq-direct` selects `RunAnalogLatentBatch.py`, and React tests/type checks asserting the transport selector exposes `QPSK` and `IQ direct`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -q -k iq
cd Semantic-Communication/cockpit_desktop; npm run typecheck
```

- [ ] **Step 3: Implement minimal selection**

Thread `OPENAMP_DEMO_LINK_MODE` through board access, backend batch launch, and cockpit controls.

- [ ] **Step 4: Verify IQ direct timing target**

Run dry/simulated IQ first, then real USRP with count 50; require transport total well below TVM reconstruction median.

- [ ] **Step 5: Update docs/script and commit**

Document `OPENAMP_DEMO_LINK_MODE=iq-direct` and commit as `feat: add cockpit iq direct transport selection`.

### Task 4: Align Gallery Source Range

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/demo_data.py`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/hooks/comparisonResult.ts`
- Test: existing comparison result tests.

**Interfaces:**
- Consumes: selected mode and requested count.
- Produces: original image gallery selecting `000001-000050` for USRP count 50 and analogous ranges for other counts.

- [ ] **Step 1: Write failing gallery test**

Assert that USRP count 50 resolves originals numbered `000001` through `000050`.

- [ ] **Step 2: Run test to verify failure**

Run: `npm test -- comparisonResult` if configured, otherwise `npm run typecheck` plus backend pytest for demo data.

- [ ] **Step 3: Implement minimal resolver**

Derive original image IDs from count and mode, avoiding hard-coded stale archive samples.

- [ ] **Step 4: Verify UI data**

Call `/api/system-status` after a count 50 USRP run and inspect recent current sample metadata.

- [ ] **Step 5: Update docs/script and commit**

Document gallery range behavior and commit as `fix: align usrp gallery source range`.
