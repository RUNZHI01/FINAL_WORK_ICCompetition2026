# Image Quality Metrics Report

- run_id: quality_metrics_20260312_tvm_baseline_vs_tvm_current
- status: success
- timestamp: 2026-03-12T13:02:11+08:00
- comparison_label: tvm_baseline_vs_tvm_current
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/baseline/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/current/reconstructions
- matched_png_count: 300
- compared_image_count: 300
- max_images: 300
- size_mismatch_mode: crop
- cropped_pair_count: 300
- lpips_mode: auto
- lpips_status: torch/lpips unavailable; LPIPS skipped
- psnr_perfect_match_count: 0
- missing_in_test_count: 0
- extra_in_test_count: 0

## Aggregate

| Metric | Mean | Median | Std | Min | Max |
|---|---:|---:|---:|---:|---:|
| PSNR (dB) | 34.5299 | 34.6004 | 2.1202 | 26.1983 | 40.2348 |
| SSIM | 0.970432 | 0.970431 | 0.005356 | 0.936151 | 0.981954 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| tvm_baseline_vs_tvm_current | 300 | 34.5299 | 0.970432 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000449_recon.png | 26.1983 | 0.950388 | NA | True |
| Places365_val_00000290_recon.png | 27.6409 | 0.964890 | NA | True |
| Places365_val_00000386_recon.png | 27.8179 | 0.967695 | NA | True |
| Places365_val_00000362_recon.png | 28.1428 | 0.936151 | NA | True |
| Places365_val_00000486_recon.png | 28.9133 | 0.975025 | NA | True |
| Places365_val_00000214_recon.png | 28.9678 | 0.965130 | NA | True |
| Places365_val_00000347_recon.png | 29.0296 | 0.967891 | NA | True |
| Places365_val_00000249_recon.png | 29.0544 | 0.970065 | NA | True |
| Places365_val_00000482_recon.png | 30.1727 | 0.967985 | NA | True |
| Places365_val_00000454_recon.png | 30.4274 | 0.968181 | NA | True |
