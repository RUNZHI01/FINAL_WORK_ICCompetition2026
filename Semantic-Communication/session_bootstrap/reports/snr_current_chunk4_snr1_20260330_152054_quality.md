# Image Quality Metrics Report

- run_id: snr_current_chunk4_snr1_20260330_152054_quality
- status: success
- timestamp: 2026-03-30T15:31:42+08:00
- comparison_label: trusted_current_snr1_vs_pytorch_reference
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/snr_sweep_current_chunk4_20260330_152054/snr_current_chunk4_snr1_20260330_152054_current/reconstructions
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
| PSNR (dB) | 29.1452 | 29.0372 | 1.5689 | 24.6234 | 34.3483 |
| SSIM | 0.900039 | 0.900238 | 0.017268 | 0.840185 | 0.938664 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| trusted_current_snr1_vs_pytorch_reference | 300 | 29.1452 | 0.900039 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000355_recon.png | 24.6234 | 0.885390 | NA | False |
| Places365_val_00000395_recon.png | 25.0498 | 0.880697 | NA | False |
| Places365_val_00000433_recon.png | 25.3898 | 0.864113 | NA | False |
| Places365_val_00000262_recon.png | 25.7767 | 0.876682 | NA | False |
| Places365_val_00000235_recon.png | 25.9961 | 0.876338 | NA | False |
| Places365_val_00000484_recon.png | 25.9964 | 0.854536 | NA | False |
| Places365_val_00000343_recon.png | 26.0016 | 0.863891 | NA | False |
| Places365_val_00000369_recon.png | 26.1135 | 0.874397 | NA | False |
| Places365_val_00000337_recon.png | 26.3006 | 0.873564 | NA | False |
| Places365_val_00000389_recon.png | 26.4118 | 0.877406 | NA | False |
