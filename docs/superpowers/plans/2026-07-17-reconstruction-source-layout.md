# Reconstruction Source Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five selectable reconstruction sources, route new USRP jobs into separate QPSK/IQ directories, and migrate only historically classifiable USRP jobs.

**Architecture:** A small source-registry module owns source IDs, remote roots, name filters, and historical USRP classification. The comparison service accepts the registry at configuration time and exposes source-scoped job lists. Cockpit selects the new USRP output root before invoking TVM/MNN, while a separate SFTP migration command handles existing board jobs with dry-run as the default.

**Tech Stack:** Python 3.11, `http.server`, Paramiko/SFTP, pytest, vanilla HTML/CSS/JavaScript, existing Cockpit Python backend.

## Global Constraints

- Do not move, rename, or change generation behavior for prerecorded TVM, MNN, or PyTorch outputs.
- New USRP TVM roots are exactly `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` and `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm`.
- Never infer a historical link mode from a board directory name alone.
- Migration is dry-run by default, idempotent, auditable, and never overwrites a destination.
- Existing lazy image pulling, reference selection, quality metrics, and resource gates remain active.

## File Map

- Create `scripts/board_image_compare/sources.py`: source IDs, filters, historical classifier, and migration decisions.
- Create `scripts/migrate_usrp_output_layout.py`: SFTP dry-run/apply/rollback CLI.
- Create `tests/test_board_image_compare_sources.py`: source and migration unit tests.
- Modify `scripts/board_image_compare/service.py`: multi-source config and source-scoped API.
- Modify `scripts/board_image_compare/web/{index.html,app.js,styles.css}`: upper-right source selector.
- Modify `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/{reconstruction_browser.py,server.py}`: pass source registry and route new USRP outputs.
- Modify corresponding tests under `tests/` and `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/`.
- Create `docs/USRP_OUTPUT_LAYOUT.md`; update `docs/README.md` and `docs/HANDOFF.md`.

---

### Task 1: Source Registry And Historical Classifier

**Files:**
- Create: `scripts/board_image_compare/sources.py`
- Create: `tests/test_board_image_compare_sources.py`

**Interfaces:**
- Produces: `ReconstructionSource`, `classify_usrp_summary(payload)`, `extract_usrp_token(job_name)`, and `plan_usrp_migration(job_names, run_root, legacy_root, output_root)`.
- Classification returns only `usrp-qpsk`, `usrp-iq-direct`, or `None`.

- [ ] **Step 1: Write failing source-filter tests**

```python
def test_prerecorded_filters_keep_existing_layout():
    sources = default_reconstruction_sources("/home/user/Downloads/jscc-test-usrp")
    assert sources["prerecorded-pytorch"].accepts("pytorch_reference_reconstruction_20260715")
    assert not sources["prerecorded-tvm"].accepts("pytorch_reference_reconstruction_20260715")
    assert sources["prerecorded-tvm"].remote_root.endswith("/jscc/infer_outputs")
    assert sources["prerecorded-mnn"].remote_root.endswith("/mnn_benchmark_outputs")
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `python -m pytest tests/test_board_image_compare_sources.py -v`

Expected: FAIL because `scripts.board_image_compare.sources` does not exist.

- [ ] **Step 3: Implement the source registry**

```python
@dataclass(frozen=True)
class ReconstructionSource:
    id: str
    label: str
    remote_root: str
    include_prefixes: tuple[str, ...] = ()
    exclude_prefixes: tuple[str, ...] = ()

    def accepts(self, job_name: str) -> bool:
        name = job_name.casefold()
        included = not self.include_prefixes or any(name.startswith(p.casefold()) for p in self.include_prefixes)
        excluded = any(name.startswith(p.casefold()) for p in self.exclude_prefixes)
        return included and not excluded
```

Define all five IDs and preserve the existing prerecorded roots. Use `pytorch_reference_reconstruction_` as the PyTorch include prefix and exclude it from prerecorded TVM.

- [ ] **Step 4: Write failing classifier tests**

```python
@pytest.mark.parametrize(("payload", "expected"), [
    ({"phy": "analog-latent-iq"}, "usrp-iq-direct"),
    ({"images": [{"round_records": [{"remote_received_latent_npz": "/rx/0.npz"}]}]}, "usrp-iq-direct"),
    ({"max_arq_rounds": 2, "chunk_bytes": 4096}, "usrp-qpsk"),
    ({"target_count": 1, "all_pass": True}, None),
])
def test_classify_usrp_summary_requires_evidence(payload, expected):
    assert classify_usrp_summary(payload) == expected
```

- [ ] **Step 5: Implement token extraction and migration planning**

`extract_usrp_token()` must parse `openamp3_usrp_<token>_current`; `_recovery` and `_retry` suffixes first try their exact local run, then their base numeric token. `plan_usrp_migration()` reads only `batch_spool_summary.json`, records `source`, `destination`, `mode`, and `reason`, and returns unresolved entries without a destination.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest tests/test_board_image_compare_sources.py -v`

Expected: PASS.

```bash
git add scripts/board_image_compare/sources.py tests/test_board_image_compare_sources.py
git commit -m "feat(compare): classify reconstruction sources"
```

### Task 2: Multi-Source Comparison Service

**Files:**
- Modify: `scripts/board_image_compare/service.py`
- Modify: `tests/test_board_image_compare_service.py`

**Interfaces:**
- Consumes: `Mapping[str, ReconstructionSource]` from Task 1.
- Produces: `ComparisonServiceState.list_jobs(source_id: str)` and `GET /api/jobs?source=<id>`.

- [ ] **Step 1: Write failing service tests**

```python
def test_jobs_are_scoped_to_requested_source(tmp_path):
    state, remote = configured_state(tmp_path)
    jobs = state.list_jobs("usrp-iq-direct")
    assert remote.listed_roots == ["/usrp/iq-direct/tvm"]
    assert [job["name"] for job in jobs] == ["job-new", "job-old"]

def test_unknown_source_is_rejected(tmp_path):
    state, _ = configured_state(tmp_path)
    with pytest.raises(ValueError, match="unknown reconstruction source"):
        state.list_jobs("not-a-source")

def test_missing_source_root_returns_empty_list(tmp_path):
    state, remote = configured_state(tmp_path)
    remote.list_jobs = Mock(side_effect=FileNotFoundError("missing"))
    assert state.list_jobs("prerecorded-mnn") == []
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_board_image_compare_service.py -v`

Expected: FAIL because `ComparisonConfig` and `list_jobs()` still accept one `remote_root`.

- [ ] **Step 3: Implement source-scoped state**

Replace `ComparisonConfig.remote_root` with `sources: tuple[ReconstructionSource, ...]` and `default_source: str`. Serialize only source IDs, labels, and roots in `public_config()`. Filter `RemoteJob` objects through `source.accepts(job.name)` after listing the selected root. Clear job/pair state when the selected source changes so stale job IDs cannot be opened.

- [ ] **Step 4: Update HTTP config and jobs routes**

Parse the configured sources as a JSON list:

```json
{"sources":[{"id":"usrp-iq-direct","label":"USRP-IQ直传","remote_root":"/home/user/Downloads/jscc-test-usrp/iq-direct/tvm","include_prefixes":[],"exclude_prefixes":[]}]}
```

Route `GET /api/jobs?source=usrp-iq-direct` to `state.list_jobs(source_id)`. Return HTTP 400 for unknown IDs and `{"jobs": []}` for a missing root.

- [ ] **Step 5: Run focused and regression tests**

Run: `python -m pytest tests/test_board_image_compare_service.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_core.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/board_image_compare/service.py tests/test_board_image_compare_service.py
git commit -m "feat(compare): expose source-scoped jobs"
```

### Task 3: Reconstruction Source Selector

**Files:**
- Modify: `scripts/board_image_compare/web/index.html`
- Modify: `scripts/board_image_compare/web/app.js`
- Modify: `scripts/board_image_compare/web/styles.css`
- Modify: `tests/test_board_image_compare_service.py`

**Interfaces:**
- Consumes: `config.sources`, `config.default_source`, and `/api/jobs?source=` from Task 2.
- Produces: `<select id="reconstruction-source">` in the upper-right job controls.

- [ ] **Step 1: Add a failing static-page contract test**

```python
def test_http_page_exposes_reconstruction_source_selector(tmp_path):
    body, script = fetch_page_assets(configured_http_state(tmp_path))
    assert 'id="reconstruction-source"' in body
    assert "sourceSelect.addEventListener('change'" in script
    assert "/api/jobs?source=" in script
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_board_image_compare_service.py::test_http_page_exposes_reconstruction_source_selector -v`

Expected: FAIL because the selector is absent.

- [ ] **Step 3: Implement the selector and reset behavior**

Initialize `state.sourceId` from `config.default_source`. Populate options from `config.sources`. On change, clear `state.jobs`, `state.detail`, `state.index`, all preview image `src` values, quality marker, directory text, and job options before calling `loadJobs()`.

```javascript
async function selectSource(sourceId) {
  state.sourceId = sourceId
  resetSelectedJob()
  await loadJobs()
}
```

Use `encodeURIComponent(state.sourceId)` in the jobs request. Show `当前来源没有可用重建 job` for an empty list. Do not select a job from the previous source.

- [ ] **Step 4: Style without changing the page layout**

Keep the source and job selects in `.job-controls`; use stable 34 px control height and responsive wrapping below the existing mobile breakpoint. Do not change the preview grid or quality controls.

- [ ] **Step 5: Verify JavaScript and service tests**

Run: `node --check scripts/board_image_compare/web/app.js`

Run: `python -m pytest tests/test_board_image_compare_service.py -v`

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/board_image_compare/web tests/test_board_image_compare_service.py
git commit -m "feat(compare): select reconstruction source"
```

### Task 4: Cockpit Output Routing And Browser Configuration

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py`

**Interfaces:**
- Consumes: five serialized source definitions accepted by Task 2.
- Produces: mode-specific `REMOTE_OUTPUT_BASE` and browser configuration containing all five sources.

- [ ] **Step 1: Write failing output-routing tests**

```python
def test_usrp_stage_access_uses_qpsk_output_root(self):
    access = self.state._usrp_stage_access(
        self.base_access.with_env_overrides({"JSCC_LINK_MODE": "qpsk"}),
        {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx"},
    )
    self.assertEqual(
        access.build_env()["REMOTE_OUTPUT_BASE"],
        "/home/user/Downloads/jscc-test-usrp/qpsk/tvm",
    )

def test_usrp_stage_access_uses_iq_direct_output_root(self):
    access = self.state._usrp_stage_access(
        self.base_access.with_env_overrides({"JSCC_LINK_MODE": "iq-direct"}),
        {"remote_dir": "/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-123_rx"},
    )
    self.assertEqual(
        access.build_env()["REMOTE_OUTPUT_BASE"],
        "/home/user/Downloads/jscc-test-usrp/iq-direct/tvm",
    )
```

Also change the existing MNN assertion to `/home/user/Downloads/jscc-test-usrp/<mode>/mnn`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or reconstruction_browser" -v`

Expected: FAIL because output roots currently omit the link mode.

- [ ] **Step 3: Route actual Demo outputs by effective link mode**

Inside `_usrp_stage_access()`, normalize `JSCC_LINK_MODE` from `base_env`, then construct:

```python
usrp_output_base = f"{output_root.rstrip('/')}/{usrp_link_mode}/{output_engine}"
```

This value must be assigned to `REMOTE_OUTPUT_BASE` before the TVM/MNN runner starts. Keep prefixes and all prerecorded access paths unchanged.

- [ ] **Step 4: Pass five sources to the comparison service**

Change `ReconstructionBrowserConfig.remote_root` to `sources` and `default_source="usrp-iq-direct"`. `open_reconstruction_browser()` must pass the two existing prerecorded roots plus the two new USRP TVM roots. The manager serializes the list in its `/api/config` POST.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -v`

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or reconstruction_browser" -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py
git commit -m "feat(cockpit): split USRP reconstruction outputs"
```

### Task 5: Safe Historical Migration And Documentation

**Files:**
- Create: `scripts/migrate_usrp_output_layout.py`
- Modify: `tests/test_board_image_compare_sources.py`
- Create: `docs/USRP_OUTPUT_LAYOUT.md`
- Modify: `docs/README.md`
- Modify: `docs/HANDOFF.md`
- Runtime report: `Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json`

**Interfaces:**
- Consumes: `plan_usrp_migration()` from Task 1 and Paramiko connection settings.
- Produces: deterministic JSON report with `classified`, `moved`, `already_moved`, `unresolved`, and reversible source/destination paths.

- [ ] **Step 1: Write failing migration behavior tests**

Use a fake SFTP object and assert that dry-run calls no rename, apply creates parent directories and renames once, an existing destination is reported without overwrite, and rollback swaps only report entries whose destination exists.

```python
def test_dry_run_never_renames(fake_sftp, migration_plan):
    result = apply_migration(fake_sftp, migration_plan, apply=False)
    assert fake_sftp.rename_calls == []
    assert result["moved"] == []
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_board_image_compare_sources.py -v`

Expected: FAIL because the migration CLI does not exist.

- [ ] **Step 3: Implement the SFTP migration CLI**

Arguments: `--host`, `--port`, `--user`, `--password`, `--run-root`, `--legacy-root`, `--output-root`, `--report`, `--apply`, and `--rollback-report`. Default to dry-run. Use `sftp.stat`, `sftp.mkdir`, and `sftp.rename`; do not build a remote shell command. Write the report atomically through a temporary local file and `Path.replace()`.

- [ ] **Step 4: Run unit tests and a real board dry-run**

Run: `python -m pytest tests/test_board_image_compare_sources.py -v`

Run:

```powershell
python scripts/migrate_usrp_output_layout.py --host 100.121.87.73 --user user --password user --run-root USRP292x/qpsk_batch_spool_arq_runs --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json
```

Expected: 239 direct IQ jobs, 4 QPSK jobs, one inherited IQ recovery job, and one unresolved retry job; `moved` remains empty.

- [ ] **Step 5: Review the dry-run report, apply, and verify board roots**

Run the same command with `--apply`. Then run it once more without `--apply`; every classified entry must report `already_moved`, no destination collision may occur, and the unresolved job must remain in the legacy root.

- [ ] **Step 6: Document the final layout and migration evidence**

`docs/USRP_OUTPUT_LAYOUT.md` must list all five browser sources, unchanged prerecorded roots, new USRP roots, classification fields, report path, unresolved job, dry-run/apply/rollback commands, and the fact that new Demo jobs route by `JSCC_LINK_MODE`. Update the README comparison-page paragraph and HANDOFF output-directory table to link to this document.

Rollback command:

```powershell
python scripts/migrate_usrp_output_layout.py --host 100.121.87.73 --user user --password user --rollback-report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json --apply
```

- [ ] **Step 7: Run full focused verification**

Run:

```powershell
python -m pytest tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py tests/test_board_image_compare_sources.py -v
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -v
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or reconstruction_browser" -v
node --check scripts/board_image_compare/web/app.js
```

Expected: all tests PASS and JavaScript syntax check exits 0.

- [ ] **Step 8: Commit implementation evidence and docs**

```bash
git add scripts/migrate_usrp_output_layout.py tests/test_board_image_compare_sources.py docs/USRP_OUTPUT_LAYOUT.md docs/README.md docs/HANDOFF.md Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json
git commit -m "docs: record USRP output migration"
```

### Task 6: End-To-End Acceptance

**Files:**
- No planned source changes; fix only defects demonstrated by this acceptance run.

**Interfaces:**
- Verifies all outputs from Tasks 1-5 together.

- [ ] **Step 1: Restart Cockpit and open the comparison page**

Use the repository startup flow, then call `POST /api/reconstruction-browser/open`. Confirm the page opens on loopback and lists the five source labels in the upper-right selector.

- [ ] **Step 2: Check each prerecorded source without changing its data**

Select prerecorded TVM, MNN, and PyTorch reference. Confirm each lists only matching existing board jobs and no prerecorded directory has been moved or renamed.

- [ ] **Step 3: Check migrated USRP sources**

Select USRP-QPSK and USRP-IQ direct. Confirm jobs are newest-first, pulling remains manual, original pairing still uses `qpsk_batch_spool_arq_runs`, and quality metrics update after pull.

- [ ] **Step 4: Produce one new job per USRP link mode**

Run the smallest practical QPSK and IQ smoke batch. Confirm their TVM output directories are under `qpsk/tvm` and `iq-direct/tvm` respectively and appear only under the matching selector option.

- [ ] **Step 5: Verify repository scope**

Run `git status --short` and `git diff --check`. Do not stage or modify existing runtime artifacts unrelated to this plan.
