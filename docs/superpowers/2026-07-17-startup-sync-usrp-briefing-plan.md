# Startup Sync and USRP Briefing Implementation Plan

**Goal:** Make board synchronization executable from PowerShell/Docker, enforce strict daily startup warm-up, and produce an accurate USRP chain briefing for the team.

**Architecture:** Extend the existing bundle wrapper rather than adding another launcher. Keep bundle creation local and opt-in deployment explicit. Continue to use `start-demo.ps1` as the only daily Cockpit entry point.

**Tech Stack:** PowerShell 7, Docker, Bash, pytest, Markdown.

---

### Task 1: Lock startup and sync behavior with tests

- Assert `start-demo.ps1` exports a minimum warm-up success count equal to `WarmupCount`.
- Assert the sync wrapper exposes parameterized Docker deployment and optional board verification.

### Task 2: Implement strict startup and Docker deployment

- Add the strict warm-up environment default to `start-demo.ps1`.
- Add `-Deploy`, board connection parameters, Docker/Tailscale upload, atomic extraction, hash output, and `-Verify` to `prepare-iq-board-sync.ps1`.
- Keep package-only behavior as the default.

### Task 3: Synchronize the board

- Regenerate `artifacts/iq_board_sync.tar.gz` and its manifest.
- Deploy with the current board address and runtime password.
- Run focused board-side verification in `tvm310_safe` and compare key hashes.

### Task 4: Update presentation and handoff documents

- Correct warm-up acceptance and USRP output paths in `README`, `STARTUP`, and `HANDOFF`.
- Add a focused USRP chain briefing with stage ownership, timing definitions, reliability controls, security boundaries, and PPT claims.

### Task 5: Verify

- Run focused pytest suites and PowerShell parser checks.
- Validate Markdown links and search for stale warm-up/path language.
- Run a readiness/startup regression after synchronization.
