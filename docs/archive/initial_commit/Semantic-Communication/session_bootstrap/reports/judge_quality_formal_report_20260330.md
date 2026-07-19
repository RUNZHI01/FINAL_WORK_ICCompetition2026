# Formal Quality Report

- run_id: judge_quality_formal_report_20260330
- generated_at: 2026-03-30T15:23:44+08:00
- comparison_count: 3
- report_json: session_bootstrap/reports/judge_quality_formal_report_20260330.json

## Aggregate Matrix

| Comparison | Images | PSNR mean | PSNR 95% CI | SSIM mean | SSIM 95% CI | LPIPS mean | LPIPS 95% CI | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| pytorch_vs_tvm_baseline | 300 | 34.4795 | 0.2470 | 0.970358 | 0.000624 | NA | NA | status=success; crop=300; missing=0; extra=0 |
| pytorch_vs_tvm_current | 300 | 35.6942 | 0.1823 | 0.972836 | 0.000555 | NA | NA | status=success; crop=0; missing=0; extra=0 |
| tvm_baseline_vs_tvm_current | 300 | 34.5299 | 0.2403 | 0.970432 | 0.000607 | NA | NA | status=success; crop=300; missing=0; extra=0 |

## Findings

- Against the same PyTorch reference, current is 1.2147 dB higher in mean PSNR and 0.002478 higher in mean SSIM than baseline.
- Direct TVM baseline-vs-current divergence is 34.5299 dB PSNR and 0.970432 SSIM.
- LPIPS is missing for at least one comparison; keep PSNR/SSIM as the formal minimum set and treat LPIPS as environment-gated complementary evidence.
- At least one comparison required spatial normalization; judge-facing tables should footnote the crop policy.

## Worst Cases

| Comparison | Image | PSNR (dB) | SSIM | LPIPS |
|---|---|---:|---:|---:|
| pytorch_vs_tvm_baseline | Places365_val_00000449_recon.png | 25.8395 | 0.948625 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000449_recon.png | 26.1983 | 0.950388 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000290_recon.png | 26.3012 | 0.963977 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000386_recon.png | 27.1003 | 0.967453 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000290_recon.png | 27.6409 | 0.964890 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000386_recon.png | 27.8179 | 0.967695 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000362_recon.png | 27.8638 | 0.935944 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000362_recon.png | 28.1428 | 0.936151 | NA |
| pytorch_vs_tvm_baseline | Places365_val_00000486_recon.png | 28.4483 | 0.975332 | NA |
| tvm_baseline_vs_tvm_current | Places365_val_00000486_recon.png | 28.9133 | 0.975025 | NA |

## Limitations

- The report is descriptive by default; it does not silently enforce pass/fail thresholds.
- LPIPS remains environment-dependent because the historical run skipped it when torch/lpips was unavailable.
- Historical data is consumed as-is from quality_metrics JSON files; regenerate the source JSONs if the underlying reconstruction directories change.
