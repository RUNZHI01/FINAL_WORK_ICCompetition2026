# Image Quality Metrics Report

- run_id: quality_metrics_20260312_pytorch_vs_tvm_baseline
- status: success
- timestamp: 2026-03-12T14:30:24+08:00
- comparison_label: pytorch_vs_tvm_baseline
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/baseline/reconstructions
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
| PSNR (dB) | 34.4795 | 34.6546 | 2.1793 | 25.8395 | 40.1744 |
| SSIM | 0.970358 | 0.970553 | 0.005509 | 0.935944 | 0.982276 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| pytorch_vs_tvm_baseline | 300 | 34.4795 | 0.970358 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000449_recon.png | 25.8395 | 0.948625 | NA | True |
| Places365_val_00000290_recon.png | 26.3012 | 0.963977 | NA | True |
| Places365_val_00000386_recon.png | 27.1003 | 0.967453 | NA | True |
| Places365_val_00000362_recon.png | 27.8638 | 0.935944 | NA | True |
| Places365_val_00000486_recon.png | 28.4483 | 0.975332 | NA | True |
| Places365_val_00000347_recon.png | 29.0411 | 0.966493 | NA | True |
| Places365_val_00000214_recon.png | 29.2799 | 0.966222 | NA | True |
| Places365_val_00000249_recon.png | 29.3813 | 0.969825 | NA | True |
| Places365_val_00000434_recon.png | 29.7841 | 0.963748 | NA | True |
| Places365_val_00000251_recon.png | 30.1214 | 0.969803 | NA | True |
