# Single-Image Quality Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display PSNR and SSIM for the selected reconstruction after that image is pulled.

**Architecture:** Reuse the `quality` object already returned by `/api/pull` and stored in the browser state. Add read-only metric elements to the reconstruction pane and update them inside the existing `renderPreview()` path.

**Tech Stack:** Static HTML, CSS, browser JavaScript, pytest

## Global Constraints

- Do not change metric calculation or backend APIs.
- Do not start a full-job scan when showing one image's metrics.
- PSNR uses two decimals; SSIM uses four decimals.
- Missing metrics render as `--`.

---

### Task 1: Render Current-Pair Metrics

**Files:**
- Modify: `tests/test_board_image_compare_service.py`
- Modify: `scripts/board_image_compare/web/index.html`
- Modify: `scripts/board_image_compare/web/app.js`
- Modify: `scripts/board_image_compare/web/styles.css`

**Interfaces:**
- Consumes: `qualityFor(index)` returning `/api/pull`'s quality payload or `null`
- Produces: DOM elements `quality-psnr` and `quality-ssim`

- [ ] **Step 1: Write the failing page contract test**

Extend `test_http_page_exposes_two_previews_and_quality_switch`:

```python
assert 'id="quality-psnr"' in body
assert 'id="quality-ssim"' in body
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tests/test_board_image_compare_service.py -k exposes_two_previews -q
```

Expected: failure because both metric IDs are absent.

- [ ] **Step 3: Add the metric row and rendering logic**

Add below the reconstruction image stage:

```html
<div class="quality-metrics" aria-label="当前图片质量指标">
  <span>PSNR <strong id="quality-psnr">--</strong> dB</span>
  <span>SSIM <strong id="quality-ssim">--</strong></span>
</div>
```

Register both elements in `app.js`, then update them in `renderPreview()`:

```javascript
const quality = qualityFor(state.index)
const psnr = Number(quality?.psnr_db)
const ssim = Number(quality?.ssim)
elements.qualityPsnr.textContent = Number.isFinite(psnr) ? psnr.toFixed(2) : '--'
elements.qualitySsim.textContent = Number.isFinite(ssim) ? ssim.toFixed(4) : '--'
```

Reset the two values to `--` in the no-pair branch. Style `.quality-metrics` as a compact neutral row beneath the right preview without changing preview dimensions.

- [ ] **Step 4: Run focused and full comparison tests**

```powershell
python -m pytest tests/test_board_image_compare_service.py -q
python -m pytest tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Verify the running page and commit**

Restart Cockpit, pull one reconstruction, and confirm the displayed values match `/api/pull`. Then commit:

```powershell
git add tests/test_board_image_compare_service.py scripts/board_image_compare/web/index.html scripts/board_image_compare/web/app.js scripts/board_image_compare/web/styles.css
git commit -m "feat(compare): show per-image quality metrics"
```
