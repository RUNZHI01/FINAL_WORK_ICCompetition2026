# Single-Image Quality Metrics

## Goal

Show the PSNR and SSIM for the currently selected image in the reconstruction comparison page. The values help distinguish normal JSCC blur from a corrupted IQ reconstruction without starting a full-job scan.

## Behavior

- Add a compact metric row below the reconstruction preview.
- Before an image is pulled, show `PSNR -- dB` and `SSIM --`.
- After `/api/pull` returns, display that pair's `quality.psnr_db` and `quality.ssim` values.
- Format PSNR to two decimal places and SSIM to four decimal places.
- If the images have incompatible shapes or metrics are unavailable, keep the placeholder values.
- Changing the job or image index immediately refreshes the row for the selected pair.

The row is always visible and independent of the existing quality-assistance switch. Quality assistance keeps its current role: background scanning of the selected job and subtle marking of suspected color-noise outputs.

## Implementation

The backend already computes and returns per-image metrics from `/api/pull`, so no API change is needed. Add two metric elements to `web/index.html`, update them from `qualityFor(state.index)` in `web/app.js`, and use a neutral inline layout in `web/styles.css`.

## Verification

Add a frontend contract test that checks the metric elements, formatting rules, and placeholder handling. Run the comparison-service tests and inspect the live page after pulling one cached and one uncached reconstruction.
