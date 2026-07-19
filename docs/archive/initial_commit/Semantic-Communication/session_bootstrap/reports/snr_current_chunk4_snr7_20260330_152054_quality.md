# Image Quality Metrics Report

- run_id: snr_current_chunk4_snr7_20260330_152054_quality
- status: success
- timestamp: 2026-03-30T15:43:28+08:00
- comparison_label: trusted_current_snr7_vs_pytorch_reference
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/snr_sweep_current_chunk4_20260330_152054/snr_current_chunk4_snr7_20260330_152054_current/reconstructions
- matched_png_count: 300
- compared_image_count: 300
- max_images: 300
- size_mismatch_mode: crop-top-left
- size_mismatch_mode_resolved: crop-top-left
- cropped_pair_count: 0
- shape_mismatch_count: 0
- shape_mismatch_status: none
- shape_mismatch_message: No shape mismatch detected.
- lpips_mode: auto
- lpips_status: torch/lpips unavailable; LPIPS skipped
- psnr_perfect_match_count: 0
- missing_in_test_count: 0
- extra_in_test_count: 0

## Aggregate

| Metric | Mean | Median | Std | Min | Max |
|---|---:|---:|---:|---:|---:|
| PSNR (dB) | 34.0185 | 34.0157 | 1.6228 | 29.9479 | 38.7852 |
| SSIM | 0.961243 | 0.961409 | 0.007072 | 0.928509 | 0.977072 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| trusted_current_snr7_vs_pytorch_reference | 300 | 34.0185 | 0.961243 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000395_recon.png | 29.9479 | 0.952634 | NA | False |
| Places365_val_00000355_recon.png | 29.9624 | 0.953883 | NA | False |
| Places365_val_00000235_recon.png | 30.3563 | 0.949160 | NA | False |
| Places365_val_00000433_recon.png | 30.3898 | 0.948838 | NA | False |
| Places365_val_00000262_recon.png | 30.6017 | 0.949171 | NA | False |
| Places365_val_00000369_recon.png | 30.6448 | 0.946805 | NA | False |
| Places365_val_00000484_recon.png | 30.7852 | 0.939633 | NA | False |
| Places365_val_00000452_recon.png | 30.8076 | 0.928509 | NA | False |
| Places365_val_00000459_recon.png | 31.0028 | 0.951442 | NA | False |
| Places365_val_00000337_recon.png | 31.1908 | 0.950879 | NA | False |
