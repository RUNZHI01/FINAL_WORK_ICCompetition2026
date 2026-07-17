# PyTorch Reference Sample Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct all 5000 source images with the existing PyTorch JSCC baseline, expose those references in the comparison page, and produce a reproducible shortlist whose final 300 samples prioritize real USRP retry evidence and reconstruction quality.

**Architecture:** Verify and reuse the board-side PyTorch helper, JSCC source, model, and settings on the host, then run the 5,000-image reference workload locally. Add two focused host-side modules: one canonical image-quality implementation and one manifest-driven ranking tool. The ranking tool first probes reproducibility, conditionally averages three fixed-seed runs, then merges PyTorch quality with real USRP retry records.

**Tech Stack:** Python 3, PyTorch CPU, Pillow, NumPy, pytest, existing host HTTP comparison service, vanilla HTML/CSS/JavaScript.

## Global Constraints

- Source set is `E:\Main\Career\集创赛\原始图像`, containing `00000001.jpg` through `00005000.jpg`.
- Reuse `board_deps/pytorch/compressed_gan.pt`, `host_pic_to_latent/jscc`, SNR 10 dB, and the existing prerecorded PyTorch inference implementation.
- Final reference data is generated on the host only after helper/source/model hashes have been checked against the board-side PyTorch runtime.
- Runtime images, latents, manifests, and reports remain untracked; only code, tests, and concise documentation are committed.
- Canonical metrics are exact-shape RGB PSNR, global SSIM, and chroma MAE; no silent resizing or fallback reference substitution.
- A same-seed mismatch forces investigation. Identical rankings need one full run; highly similar rankings use two-run mean/std aggregation; only low correlation or low top-set overlap triggers a third run.
- Final showcase ranking only treats retry counts as authoritative when backed by an actual USRP IQ run record.

---

### Task 1: Canonical Quality Metrics and Ranking Core

**Files:**
- Create: `scripts/image_quality_metrics.py`
- Create: `scripts/rank_showcase_samples.py`
- Create: `tests/test_showcase_sample_ranking.py`
- Modify: `scripts/board_image_compare/core.py`

**Interfaces:**
- Produces: `measure_rgb_quality(reference: Path, candidate: Path) -> QualityMetrics`.
- Produces: `aggregate_quality_runs(rows: Sequence[QualityRow]) -> list[AggregatedQualityRow]`.
- Produces: `rank_showcase_samples(quality_rows, usrp_rows, limit) -> list[RankedSample]`.

- [ ] **Step 1: Write failing metric and aggregation tests**

```python
def test_aggregate_quality_runs_reports_mean_and_std():
    rows = [quality("00000001.jpg", 0, 30.0), quality("00000001.jpg", 1, 34.0)]
    result = aggregate_quality_runs(rows)[0]
    assert result.psnr_mean == 32.0
    assert result.psnr_std == 2.0

def test_rank_requires_usrp_evidence_before_retry_priority():
    ranked = rank_showcase_samples(quality_rows(), usrp_rows_for("00000002.jpg", retries=0), 2)
    assert ranked[0].source_name == "00000002.jpg"
    assert ranked[0].has_usrp_evidence is True
```

- [ ] **Step 2: Run tests and verify the missing-module failure**

Run: `python -m pytest tests/test_showcase_sample_ranking.py -v`

Expected: FAIL because `image_quality_metrics` and `rank_showcase_samples` do not exist.

- [ ] **Step 3: Implement exact-shape metrics and deterministic ranking**

```python
@dataclass(frozen=True)
class QualityMetrics:
    psnr_db: float
    ssim: float
    chroma_mae: float

def ranking_key(row: RankedSample) -> tuple[object, ...]:
    return (
        not row.has_usrp_evidence,
        row.retry_count if row.has_usrp_evidence else math.inf,
        -row.psnr_mean,
        -row.ssim_mean,
        row.chroma_mae_mean,
        row.source_name,
    )
```

Make `board_image_compare.core.measure_quality` delegate to the canonical implementation while preserving its response field names.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_showcase_sample_ranking.py tests/test_board_image_compare_core.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the ranking core**

```powershell
git add scripts/image_quality_metrics.py scripts/rank_showcase_samples.py scripts/board_image_compare/core.py tests/test_showcase_sample_ranking.py
git commit -m "feat(quality): add reproducible showcase ranking"
```

### Task 2: PyTorch Provenance and Stability Policy

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/scripts/pytorch_reference_reconstruction.py`
- Create: `tests/test_pytorch_reference_reconstruction.py`
- Modify: `scripts/rank_showcase_samples.py`

**Interfaces:**
- Consumes: the existing latent manifest and per-file deterministic seed behavior.
- Produces: manifest records with `source_name`, `source_path`, `run_seed`, `output_path`, and output SHA-256.
- Produces: `assess_ranking_stability(run_rows) -> StabilityReport` with same-seed hash equality, Spearman correlation, and top-set overlap.

- [ ] **Step 1: Write failing provenance and stability tests**

```python
def test_manifest_record_keeps_source_identity():
    record = build_manifest_record(source_name="00000001.jpg", run_seed=7)
    assert record["source_name"] == "00000001.jpg"
    assert record["run_seed"] == 7

def test_unstable_cross_seed_probe_requires_three_runs():
    report = assess_ranking_stability(disjoint_top_sets())
    assert report.full_run_count == 3
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_pytorch_reference_reconstruction.py tests/test_showcase_sample_ranking.py -v`

Expected: FAIL on missing provenance fields and stability function.

- [ ] **Step 3: Implement the conditional repeat policy**

Run two identical seed-0 probes and require identical output hashes. Compare fixed seeds on the probe set. Use one full run for identical rankings, two full runs when Spearman correlation is at least `0.98` and top-20% overlap is at least `0.90`, and three runs otherwise. Aggregated ranking uses metric means and emits standard deviations for audit.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_pytorch_reference_reconstruction.py tests/test_showcase_sample_ranking.py -v`

Expected: PASS.

- [ ] **Step 5: Commit provenance and stability logic**

```powershell
git add Semantic-Communication/session_bootstrap/scripts/pytorch_reference_reconstruction.py scripts/rank_showcase_samples.py tests/test_pytorch_reference_reconstruction.py tests/test_showcase_sample_ranking.py
git commit -m "feat(pytorch): record reference provenance and stability"
```

### Task 3: Original and PyTorch Reference Selector

**Files:**
- Modify: `scripts/board_image_compare/service.py`
- Modify: `scripts/board_image_compare/web/index.html`
- Modify: `scripts/board_image_compare/web/app.js`
- Modify: `scripts/board_image_compare/web/styles.css`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Modify: `tests/test_board_image_compare_service.py`

**Interfaces:**
- Consumes: `pytorch_manifest_paths: list[str]` in comparison-service configuration.
- Produces: `GET /api/image/reference?mode=original|pytorch&job=...&index=...`.
- Produces: quality cache key `(job_id, index, reference_mode)`.

- [ ] **Step 1: Write failing API tests**

```python
def test_pytorch_reference_mode_uses_manifest_mapping(client):
    response = client.get("/api/image/reference?mode=pytorch&job=job-1&index=0")
    assert response.status_code == 200

def test_missing_pytorch_reference_does_not_fall_back(client):
    response = client.get("/api/image/reference?mode=pytorch&job=job-1&index=99")
    assert response.status_code == 404
```

- [ ] **Step 2: Run service tests and verify failure**

Run: `python -m pytest tests/test_board_image_compare_service.py -v`

Expected: FAIL because the reference endpoint and PyTorch manifest config are absent.

- [ ] **Step 3: Implement backend reference resolution and cache separation**

Parse host-side PyTorch manifests by `source_name`, return explicit `404` JSON when absent, and keep existing original-image URLs compatible. Pass the local output root and manifest path from `server.py` through `ReconstructionBrowserConfig`.

- [ ] **Step 4: Add the segmented control**

```html
<div class="reference-mode" role="group" aria-label="参考图来源">
  <button data-reference-mode="original" class="active">原图</button>
  <button data-reference-mode="pytorch">PyTorch</button>
</div>
```

Switching mode clears the selected reference and metric display, reloads only the visible image, and never changes the selected reconstruction job.

- [ ] **Step 5: Run service and browser source tests**

Run: `python -m pytest tests/test_board_image_compare_service.py tests/test_board_image_compare_remote.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the selector**

```powershell
git add scripts/board_image_compare Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/reconstruction_browser.py Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py tests/test_board_image_compare_service.py
git commit -m "feat(compare): select original or PyTorch reference"
```

### Task 4: Generate, Probe, Rank, and Document the 5000-Sample Set

**Files:**
- Modify: `docs/HANDOFF.md`
- Runtime only: `host_pic_to_latent/encoder_outputs_airfield5000/`
- Runtime only: `Semantic-Communication/session_bootstrap/reports/pytorch_reference_5000/`
- Runtime only: `Semantic-Communication/session_bootstrap/reports/showcase_ranking/`

**Interfaces:**
- Consumes: the source manifest, PyTorch run manifests, and USRP run manifests.
- Produces: `pytorch_quality_ranking.csv`, `pytorch_quality_ranking.json`, `showcase_candidates.json`, and `selected_300_manifest.json`.

- [ ] **Step 1: Generate the 5000 latent inputs and manifest**

```powershell
python host_pic_to_latent/encode_latent.py --image_dir 'E:\Main\Career\集创赛\原始图像' --output_dir host_pic_to_latent/encoder_outputs_airfield5000 --test_num 5000 --snr 10 --device cpu
```

Verify exactly 5000 manifest records, unique source names, and unique latent paths before inference.

- [ ] **Step 2: Run the 100-image reproducibility probe**

After validating the host copy against the board, run seed 0 twice and seeds 1 and 2 once on the host with `pytorch_reference_reconstruction.py --max-images 100`. Feed all probe manifests to `rank_showcase_samples.py probe` and abort on same-seed hash mismatch. Record whether the full run count is one, two, or three.

- [ ] **Step 3: Run the required 5000-image PyTorch passes**

Run seed 0 over all 5000 images on the host using the verified board-side code and model copy. If the probe requires averaging, also run seeds 1 and 2 on the host. Preserve each output directory and manifest separately so interrupted runs can resume without overwriting completed evidence.

- [ ] **Step 4: Calculate metrics and emit the candidate pool**

```powershell
python scripts/rank_showcase_samples.py rank --original-dir 'E:\Main\Career\集创赛\原始图像' --pytorch-manifest Semantic-Communication/session_bootstrap/reports/pytorch_reference_5000/seed-0/manifest.json --output-dir Semantic-Communication/session_bootstrap/reports/showcase_ranking --candidate-limit 600 --final-limit 300
```

When three runs are required, pass all three manifests. The initial 600 are quality candidates; the final 300 file is emitted only after matching real USRP retry evidence.

- [ ] **Step 5: Run candidates through USRP IQ and finalize the selection**

Execute segmented serial USRP IQ + TVM batches for the candidate pool, then rerun `rank_showcase_samples.py rank` with the USRP manifest/report arguments. Verify all final 300 records have `has_usrp_evidence=true`, retry counts, PSNR, SSIM, chroma MAE, means, and standard deviations.

- [ ] **Step 6: Run full automated verification**

Run: `python -m pytest tests/test_showcase_sample_ranking.py tests/test_pytorch_reference_reconstruction.py tests/test_board_image_compare_core.py tests/test_board_image_compare_service.py tests/test_board_image_compare_remote.py -v`

Expected: PASS.

- [ ] **Step 7: Document reproducibility and commit code documentation only**

Record the seed policy, model hash, probe result, metric definitions, report locations, and the rule that retries require actual USRP evidence in `docs/HANDOFF.md`.

```powershell
git add docs/HANDOFF.md
git commit -m "docs: record showcase sample selection workflow"
```
