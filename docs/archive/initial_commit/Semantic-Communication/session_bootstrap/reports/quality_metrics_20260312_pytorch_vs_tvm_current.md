# Image Quality Metrics Report

- run_id: quality_metrics_20260312_pytorch_vs_tvm_current
- status: success
- timestamp: 2026-03-12T14:31:05+08:00
- comparison_label: pytorch_vs_tvm_current
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/current/reconstructions
- matched_png_count: 300
- compared_image_count: 300
- max_images: 300
- size_mismatch_mode: crop
- cropped_pair_count: 0
- lpips_mode: auto
- lpips_status: torch/lpips unavailable; LPIPS skipped
- psnr_perfect_match_count: 0
- missing_in_test_count: 0
- extra_in_test_count: 0

## Aggregate

| Metric | Mean | Median | Std | Min | Max |
|---|---:|---:|---:|---:|---:|
| PSNR (dB) | 35.6942 | 35.7298 | 1.6079 | 31.6955 | 40.7936 |
| SSIM | 0.972836 | 0.972942 | 0.004894 | 0.950743 | 0.983247 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| pytorch_vs_tvm_current | 300 | 35.6942 | 0.972836 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000355_recon.png | 31.6955 | 0.969382 | NA | False |
| Places365_val_00000433_recon.png | 31.9282 | 0.962747 | NA | False |
| Places365_val_00000395_recon.png | 32.0987 | 0.968317 | NA | False |
| Places365_val_00000235_recon.png | 32.2058 | 0.966003 | NA | False |
| Places365_val_00000366_recon.png | 32.3021 | 0.960819 | NA | False |
| Places365_val_00000262_recon.png | 32.3493 | 0.965451 | NA | False |
| Places365_val_00000369_recon.png | 32.3540 | 0.963744 | NA | False |
| Places365_val_00000484_recon.png | 32.5021 | 0.957401 | NA | False |
| Places365_val_00000452_recon.png | 32.7437 | 0.950743 | NA | False |
| Places365_val_00000389_recon.png | 32.7709 | 0.966925 | NA | False |
