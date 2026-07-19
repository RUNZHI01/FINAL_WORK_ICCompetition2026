# Formal Quality Report

- run_id: judge_quality_formal_report_20260330_lpips_full
- generated_at: 2026-03-30T17:42:52+08:00
- comparison_count: 3
- report_json: session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.json

## Aggregate Matrix

| Comparison | Images | PSNR mean | PSNR 95% CI | SSIM mean | SSIM 95% CI | LPIPS mean | LPIPS 95% CI | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pytorch_vs_tvm_baseline | 300 | 34.4244 | 0.2358 | 0.970454 | 0.000595 | 0.025883 | 0.000661 | status=success; crop=0; missing=0; extra=0 |
| pytorch_vs_tvm_current | 300 | 35.6633 | 0.1803 | 0.972751 | 0.000557 | 0.025124 | 0.000584 | status=success; crop=0; missing=0; extra=0 |
| tvm_baseline_vs_tvm_current | 300 | 34.4464 | 0.2361 | 0.970427 | 0.000593 | 0.025850 | 0.000656 | status=success; crop=0; missing=0; extra=0 |

## Findings

- Against the same PyTorch reference, current is 1.2389 dB higher in mean PSNR and 0.002297 higher in mean SSIM than baseline.
- Direct TVM baseline-vs-current divergence is 34.4464 dB PSNR and 0.970427 SSIM.

## Worst Cases

| Comparison | Image | PSNR (dB) | SSIM | LPIPS |
|---|---|---:|---:|---:|
| tvm_baseline_vs_tvm_current | Places365_val_00000449_recon.png | 25.6136 | 0.946121 | 0.051834 |
| pytorch_vs_tvm_baseline | Places365_val_00000449_recon.png | 25.8307 | 0.948315 | 0.051841 |
| tvm_baseline_vs_tvm_current | Places365_val_00000386_recon.png | 26.3244 | 0.967811 | 0.026618 |
| pytorch_vs_tvm_baseline | Places365_val_00000386_recon.png | 26.6632 | 0.967806 | 0.030235 |
| pytorch_vs_tvm_baseline | Places365_val_00000486_recon.png | 26.9056 | 0.972942 | 0.025932 |
| pytorch_vs_tvm_baseline | Places365_val_00000290_recon.png | 27.3792 | 0.963786 | 0.040692 |
| tvm_baseline_vs_tvm_current | Places365_val_00000486_recon.png | 27.5051 | 0.971906 | 0.024823 |
| tvm_baseline_vs_tvm_current | Places365_val_00000290_recon.png | 27.8438 | 0.965361 | 0.038753 |
| pytorch_vs_tvm_baseline | Places365_val_00000362_recon.png | 28.3392 | 0.945818 | 0.034390 |
| tvm_baseline_vs_tvm_current | Places365_val_00000214_recon.png | 28.4665 | 0.966201 | 0.034291 |

## Limitations

- The report is descriptive by default; it does not silently enforce pass/fail thresholds.
- LPIPS remains environment-dependent because the historical run skipped it when torch/lpips was unavailable.
- Historical data is consumed as-is from quality_metrics JSON files; regenerate the source JSONs if the underlying reconstruction directories change.
