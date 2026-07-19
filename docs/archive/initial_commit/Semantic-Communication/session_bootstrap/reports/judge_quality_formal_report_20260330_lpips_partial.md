# Formal Quality Report

- run_id: judge_quality_formal_report_20260330_lpips_partial
- generated_at: 2026-03-30T17:06:09+08:00
- comparison_count: 3
- report_json: session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_partial.json

## Aggregate Matrix

| Comparison | Images | PSNR mean | PSNR 95% CI | SSIM mean | SSIM 95% CI | LPIPS mean | LPIPS 95% CI | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pytorch_vs_tvm_baseline | 300 | 34.4244 | 0.2358 | 0.970454 | 0.000595 | 0.025883 | 0.000661 | status=success; crop=0; missing=0; extra=0 |
| pytorch_vs_tvm_current | 300 | 35.6633 | 0.1803 | 0.972751 | 0.000557 | 0.025124 | 0.000584 | status=success; crop=0; missing=0; extra=0 |
| tvm_baseline_vs_tvm_current | 300 | 34.5299 | 0.2403 | 0.970432 | 0.000607 | NA | NA | status=success; crop=300; missing=0; extra=0 |

## Findings

- Against the same PyTorch reference, current is 1.2389 dB higher in mean PSNR and 0.002297 higher in mean SSIM than baseline.
- Direct TVM baseline-vs-current divergence is 34.5299 dB PSNR and 0.970432 SSIM.
- LPIPS is missing for at least one comparison; keep PSNR/SSIM as the formal minimum set and treat LPIPS as environment-gated complementary evidence.
- At least one comparison required spatial normalization; judge-facing tables should footnote the crop policy.

## Worst Cases

| Comparison | Image | PSNR (dB) | SSIM | LPIPS |
|---|---|---:|---:|---:|
| pytorch_vs_tvm_baseline | Places365_val_00000449_recon.png | 25.8307 | 0.948315 | 0.051841 |
| tvm_baseline_vs_tvm_current | Places365_val_00000449_recon.png | 26.1983 | 0.950388 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000386_recon.png | 26.6632 | 0.967806 | 0.030235 |
| pytorch_vs_tvm_baseline | Places365_val_00000486_recon.png | 26.9056 | 0.972942 | 0.025932 |
| pytorch_vs_tvm_baseline | Places365_val_00000290_recon.png | 27.3792 | 0.963786 | 0.040692 |
| tvm_baseline_vs_tvm_current | Places365_val_00000290_recon.png | 27.6409 | 0.964890 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000386_recon.png | 27.8179 | 0.967695 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000362_recon.png | 28.1428 | 0.936151 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000362_recon.png | 28.3392 | 0.945818 | 0.034390 |
| tvm_baseline_vs_tvm_current | Places365_val_00000486_recon.png | 28.9133 | 0.975025 | NA |

## Limitations

- The report is descriptive by default; it does not silently enforce pass/fail thresholds.
- LPIPS remains environment-dependent because the historical run skipped it when torch/lpips was unavailable.
- Historical data is consumed as-is from quality_metrics JSON files; regenerate the source JSONs if the underlying reconstruction directories change.
