# Board Reconstruction Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a host-only comparison service that lazily pulls board reconstruction images, pairs them with originals, marks likely color-noise failures, and opens from Cockpit Desktop.

**Architecture:** A standalone Python process bound to `127.0.0.1` owns the SSH/SFTP session, local cache, resource gate, quality calculations, and static web UI. The existing Cockpit Python backend starts or reconfigures that process; Electron opens the returned localhost URL in the system browser. The board runs no new service and performs no image analysis.

**Tech Stack:** Python 3, `http.server`, Paramiko, Pillow, NumPy, React/TypeScript, Electron IPC, pytest, Node test runner.

## Global Constraints

- Bind every comparison-service endpoint to `127.0.0.1`.
- Keep remote directory queries and downloads at concurrency 1.
- Pause new downloads when board CPU or memory reaches 85%; abort an active transfer at 90%; resume below 80%.
- Sample board resources every 3 seconds while work is queued.
- Do not run image decoding, thumbnail generation, PSNR/SSIM, or noise classification on the board.
- Opening the page or selecting a job must not download image contents.
- Quality assistance is off by default and only adds faint markers; it never hides, skips, or modifies images.
- Preserve unrelated runtime reports and generated image directories already present in the worktree.

---

### Task 1: Pairing, quality classification, and resource gate

**Files:**
- Create: `scripts/board_image_compare/core.py`
- Create: `scripts/board_image_compare/__init__.py`
- Test: `tests/test_board_image_compare_core.py`

**Interfaces:**
- Produces: `natural_key(value: str) -> tuple`, `pair_images(originals, reconstructions, manifest_names=None) -> list[ImagePair]`.
- Produces: `measure_quality(original_path: Path, reconstruction_path: Path) -> QualityMetrics` and `is_color_noise(metrics, job_history) -> QualityVerdict`.
- Produces: `ResourceGate.evaluate(snapshot: ResourceSnapshot) -> GateDecision` with `allow`, `pause`, and `abort` actions.

- [ ] **Step 1: Write failing pairing tests**

```python
def test_manifest_names_override_natural_sort(tmp_path: Path) -> None:
    pairs = pair_images(
        [tmp_path / "a.png", tmp_path / "b.png"],
        [tmp_path / "00000000_recon.png", tmp_path / "00000001_recon.png"],
        {0: "b", 1: "a"},
    )
    assert [pair.original.name for pair in pairs] == ["b.png", "a.png"]

def test_missing_side_stays_at_same_index(tmp_path: Path) -> None:
    pairs = pair_images([tmp_path / "a.png"], [tmp_path / "00000001_recon.png"])
    assert pairs[0].reconstruction is None
    assert pairs[1].original is None
```

- [ ] **Step 2: Run the pairing tests and verify RED**

Run: `python -m pytest tests/test_board_image_compare_core.py -q`

Expected: collection fails because `scripts.board_image_compare.core` does not exist.

- [ ] **Step 3: Implement immutable pair models and deterministic pairing**

```python
@dataclass(frozen=True)
class ImagePair:
    index: int
    original: Path | None
    reconstruction: PurePosixPath | None
    original_name: str = ""

def pair_images(originals, reconstructions, manifest_names=None):
    ordered_originals = sorted((Path(path) for path in originals), key=lambda path: natural_key(path.name))
    original_by_stem = {path.stem: path for path in ordered_originals}
    reconstruction_by_index = {
        int(match.group(1)): PurePosixPath(path)
        for path in reconstructions
        if (match := re.match(r"^(\d+)(?:_recon)?\.[^.]+$", PurePosixPath(path).name))
    }
    names = manifest_names or {}
    pair_count = max(len(ordered_originals), max(reconstruction_by_index, default=-1) + 1)
    return [
        ImagePair(
            index=index,
            original=(
                original_by_stem.get(Path(names[index]).stem)
                if index in names
                else ordered_originals[index] if index < len(ordered_originals) else None
            ),
            reconstruction=reconstruction_by_index.get(index),
            original_name=str(names.get(index, "")),
        )
        for index in range(pair_count)
    ]
```

- [ ] **Step 4: Add failing quality and resource-threshold tests**

```python
def test_color_noise_requires_low_similarity_and_chroma_error(tmp_path: Path) -> None:
    metrics = QualityMetrics(psnr_db=9.0, ssim=0.05, chroma_mae=58.0, shape_match=True)
    assert is_color_noise(metrics, []).suspected is True

@pytest.mark.parametrize(
    ("cpu", "memory", "latched", "action"),
    [(84.9, 20, False, "allow"), (85, 20, False, "pause"), (20, 90, False, "abort"), (79.9, 20, True, "allow")],
)
def test_resource_gate_hysteresis(cpu, memory, latched, action):
    gate = ResourceGate(paused=latched)
    assert gate.evaluate(ResourceSnapshot(cpu, memory)).action == action
```

- [ ] **Step 5: Run the tests and verify RED**

Run: `python -m pytest tests/test_board_image_compare_core.py -q`

Expected: failures report missing quality and gate types.

- [ ] **Step 6: Implement host-side metrics and gate hysteresis**

Use Pillow RGB arrays and NumPy. The absolute color-noise rule is `psnr_db < 14`, `ssim < 0.35`, and `chroma_mae > 25`; after ten samples, also mark records at least 5 dB and 0.20 below the job medians when `chroma_mae > 20`.

- [ ] **Step 7: Run core tests and commit**

Run: `python -m pytest tests/test_board_image_compare_core.py -q`

Expected: all tests pass.

```bash
git add scripts/board_image_compare tests/test_board_image_compare_core.py
git commit -m "feat(tools): add reconstruction comparison core"
```

### Task 2: Single-session remote access and atomic cache

**Files:**
- Create: `scripts/board_image_compare/remote.py`
- Create: `scripts/board_image_compare/cache.py`
- Test: `tests/test_board_image_compare_remote.py`

**Interfaces:**
- Consumes: `ResourceGate`, `ResourceSnapshot`, and `ImagePair` from Task 1.
- Produces: `BoardConnectionConfig`, `RemoteJob`, and `BoardSftpClient`.
- Produces: `ImageCache.path_for(host, job_path, remote_file) -> Path` and `ImageCache.download_atomic(client, remote_file, target, monitor) -> Path`.

- [ ] **Step 1: Write failing job-order and cache-isolation tests**

```python
def test_jobs_are_newest_first(fake_transport):
    client = BoardSftpClient(config(), transport_factory=lambda _: fake_transport)
    assert [job.name for job in client.list_jobs("/outputs")] == ["job-new", "job-old"]

def test_cache_key_includes_host_and_job(tmp_path: Path):
    cache = ImageCache(tmp_path)
    assert cache.path_for("board-a", "/a/job", "x.png") != cache.path_for("board-a", "/b/job", "x.png")
```

- [ ] **Step 2: Run remote tests and verify RED**

Run: `python -m pytest tests/test_board_image_compare_remote.py -q`

Expected: imports fail for the new modules.

- [ ] **Step 3: Implement one persistent Paramiko transport and SFTP session**

`list_jobs()` must use one quoted `find` command and return directories named `reconstructions` with parent job names and mtimes. `list_job_images()` lists supported image extensions without downloading content. Manifest reads are small metadata requests and may occur before image pulls.

- [ ] **Step 4: Implement `/proc` CPU/memory sampling and guarded downloads**

Read `/proc/stat` twice around a 250 ms host-side delay and `/proc/meminfo` once. Call the download callback at most every 3 seconds. Raise `ResourcePaused` at 85% and `ResourceAborted` at 90%.

- [ ] **Step 5: Implement `.partial` writes and atomic replacement**

```python
partial = target.with_suffix(target.suffix + ".partial")
client.get(remote_file, partial, callback=monitor)
os.replace(partial, target)
```

Remove a partial file after a failed transfer; never remove a completed cache entry.

- [ ] **Step 6: Run remote tests and commit**

Run: `python -m pytest tests/test_board_image_compare_remote.py -q`

Expected: all tests pass without a real board.

```bash
git add scripts/board_image_compare tests/test_board_image_compare_remote.py
git commit -m "feat(tools): add guarded board image cache"
```

### Task 3: Local comparison HTTP service and web UI

**Files:**
- Create: `scripts/board_image_compare/service.py`
- Create: `scripts/board_image_compare_server.py`
- Create: `scripts/board_image_compare/web/index.html`
- Create: `scripts/board_image_compare/web/app.js`
- Create: `scripts/board_image_compare/web/styles.css`
- Test: `tests/test_board_image_compare_service.py`

**Interfaces:**
- Consumes: `BoardSftpClient`, `ImageCache`, `pair_images`, and `measure_quality`.
- Produces localhost endpoints: `POST /api/config`, `GET /api/jobs`, `GET /api/job`, `POST /api/pull`, `POST /api/quality-scan`, `GET /api/state`, and read-only image URLs.
- Produces CLI: `python scripts/board_image_compare_server.py --host 127.0.0.1 --port 8786 --cache-root artifacts/board_image_cache`.

- [ ] **Step 1: Write failing HTTP tests for lazy behavior**

```python
def test_listing_and_selecting_job_do_not_download(service_client, fake_remote):
    assert service_client.get("/api/jobs").status == 200
    assert service_client.get("/api/job?id=job-new").status == 200
    assert fake_remote.download_calls == []

def test_pull_downloads_only_requested_window(service_client, fake_remote):
    response = service_client.post("/api/pull", {"job_id": "job-new", "index": 17})
    assert response.status == 200
    assert fake_remote.download_calls[0].endswith("00000017_recon.png")
```

- [ ] **Step 2: Run service tests and verify RED**

Run: `python -m pytest tests/test_board_image_compare_service.py -q`

Expected: the service module is missing.

- [ ] **Step 3: Implement local-only configuration and APIs**

Reject non-loopback bind addresses. Keep the password only in process memory. Return public config without credentials. A new config closes the old SSH session and clears pending work while retaining disk cache.

- [ ] **Step 4: Implement the single worker queue**

Use priorities `0=current`, `10=adjacent`, `100=quality scan`. Deduplicate `(job_id, index)` jobs. Only the worker may call SFTP download methods. Quality scan queues all remaining indexes at priority 100 and stops when the mode is disabled or the selected job changes.

- [ ] **Step 5: Build the two-column page**

The page contains directory/status bands above two stable preview panes, one synchronized navigation row, a compact thumbnail strip, a descending job select, a `拉取` command, and a `质量辅助` switch. Use a faint text marker and dot for suspected images; do not use red filled cards. Use `loading="lazy"`, fixed aspect ratios, and responsive two-to-one-column layout below 900 px.

- [ ] **Step 6: Add API contract and static-layout tests**

Assert missing pairs remain aligned, jobs are descending, quality mode defaults to false, and HTML contains the two preview regions and quality switch. Assert `/api/image/reconstruction` returns 404 for uncached content rather than triggering a download.

- [ ] **Step 7: Run service tests and commit**

Run: `python -m pytest tests/test_board_image_compare_service.py tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py -q`

Expected: all tests pass.

```bash
git add scripts/board_image_compare scripts/board_image_compare_server.py tests/test_board_image_compare_service.py
git commit -m "feat(tools): add lazy reconstruction comparison service"
```

### Task 4: Cockpit backend lifecycle and API

**Files:**
- Create: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Test: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py`
- Test: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`

**Interfaces:**
- Produces: `ReconstructionBrowserManager.open(config: ReconstructionBrowserConfig) -> str` and `close() -> None`.
- Produces: `POST /api/reconstruction-browser/open` returning `{status, url}`.

- [ ] **Step 1: Write failing lifecycle and route tests**

```python
def test_open_reuses_healthy_process(fake_process, fake_http):
    manager = ReconstructionBrowserManager(process_factory=fake_process, http_client=fake_http)
    assert manager.open(config()) == "http://127.0.0.1:8786/"
    assert manager.open(config()) == "http://127.0.0.1:8786/"
    assert fake_process.calls == 1

def test_open_route_uses_current_board_access(state):
    status, _, body = request_json(state, "POST", "/api/reconstruction-browser/open", {})
    assert status == 200
    assert json.loads(body)["url"].startswith("http://127.0.0.1:")
```

- [ ] **Step 2: Run targeted backend tests and verify RED**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -q`

Expected: import failure for `reconstruction_browser`.

- [ ] **Step 3: Implement child-process startup, health wait, and reconfiguration**

Launch with `sys.executable`, no shell, and no credentials in command arguments. Send board host/user/password/port, original directory, and remote output root through localhost `POST /api/config`. Reuse a healthy process and terminate the owned child during backend shutdown.

- [ ] **Step 4: Add the Cockpit endpoint**

Reject the request when board access is not ready or either directory is missing. Resolve original and output paths from current `BoardAccessConfig`; do not trust arbitrary renderer paths.

- [ ] **Step 5: Run backend tests and commit**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -q`

Expected: all tests pass.

```bash
git add Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests
git commit -m "feat(cockpit): manage reconstruction browser service"
```

### Task 5: Cockpit button and system-browser bridge

**Files:**
- Modify: `Semantic-Communication/cockpit_desktop/electron/main.ts`
- Modify: `Semantic-Communication/cockpit_desktop/electron/preload.ts`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/vite-env.d.ts`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/api/client.ts`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/api/types.ts`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/hooks/useActions.ts`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.tsx`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.module.css`
- Modify: `Semantic-Communication/cockpit_desktop/src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs`

**Interfaces:**
- Consumes: `POST /api/reconstruction-browser/open` from Task 4.
- Produces: `window.cockpit.openExternal(url: string): Promise<void>` restricted to loopback HTTP URLs.
- Produces: `useOpenReconstructionBrowser()` mutation and the “本次重建对比图” button.

- [ ] **Step 1: Add a failing layout test**

```javascript
test('reconstruction comparison entry follows board output directory', () => {
  assert.match(source, /板端重建输出目录[\s\S]*本次重建对比图/)
})
```

- [ ] **Step 2: Run the layout test and verify RED**

Run: `node --test src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs`

Expected: the new assertion fails.

- [ ] **Step 3: Add the typed API mutation and button**

Place the button inside the board output path item below the path value. Disable it while the mutation is pending or the board/output directory is unavailable. On success call `window.cockpit.openExternal(data.url)`; on failure use the existing toast path.

- [ ] **Step 4: Add a restricted Electron external-open IPC**

Validate with `new URL(url)`, require `protocol === 'http:'`, and require hostname `127.0.0.1` or `localhost` before `shell.openExternal`. Expose only this typed method through preload.

- [ ] **Step 5: Run UI checks and commit**

Run:

```bash
node --test src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs
npm run typecheck
npm run build
```

Expected: all commands exit 0.

```bash
git add Semantic-Communication/cockpit_desktop
git commit -m "feat(cockpit): open reconstruction comparison page"
```

### Task 6: Regression and live-board acceptance

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify: `docs/README.md`
- Modify: `docs/runbooks/STARTUP.md`

**Interfaces:**
- Documents the button, localhost service, cache path, quality mode, and 85/90/80 resource thresholds.

- [ ] **Step 1: Run the full focused regression suite**

Run:

```bash
python -m pytest tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -q
cd Semantic-Communication/cockpit_desktop
node --test src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs
npm run typecheck
npm run build
```

Expected: zero failures and zero type errors.

- [ ] **Step 2: Start Cockpit and verify the browser entry**

Use the repository daily-start script. Confirm one comparison-service process is reused across repeated clicks and the browser opens `http://127.0.0.1:8786/`.

- [ ] **Step 3: Perform live-board lazy-load acceptance**

Confirm jobs are newest-first, selecting a job causes zero image downloads, pulling index 0 aligns the original and reconstruction, adjacent navigation uses cache/prefetch, and quality mode adds only faint markers. While a 300-image scan is queued, compare the page resource status with SSH telemetry and confirm neither CPU nor memory reaches 90% because of this service.

- [ ] **Step 4: Update operator documentation and commit**

```bash
git add docs/HANDOFF.md docs/README.md docs/runbooks/STARTUP.md
git commit -m "docs: document reconstruction comparison workflow"
```

- [ ] **Step 5: Final repository verification**

Run: `git diff --check && git status --short --branch`

Expected: no whitespace errors; only pre-existing runtime reports and generated artifacts remain uncommitted.
