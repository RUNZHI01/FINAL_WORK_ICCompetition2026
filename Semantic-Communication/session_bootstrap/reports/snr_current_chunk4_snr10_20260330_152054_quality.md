# Image Quality Metrics Report

- run_id: snr_current_chunk4_snr10_20260330_152054_quality
- status: success
- timestamp: 2026-03-30T15:45:21+08:00
- comparison_label: trusted_current_snr10_vs_pytorch_reference
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/snr_sweep_current_chunk4_20260330_152054/snr_current_chunk4_snr10_20260330_152054_current/reconstructions
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
| PSNR (dB) | 35.6644 | 35.6799 | 1.5782 | 31.1182 | 40.5466 |
| SSIM | 0.972735 | 0.972800 | 0.004935 | 0.946512 | 0.983191 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| trusted_current_snr10_vs_pytorch_reference | 300 | 35.6644 | 0.972735 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000355_recon.png | 31.1182 | 0.967922 | NA | False |
| Places365_val_00000433_recon.png | 32.0078 | 0.963208 | NA | False |
| Places365_val_00000395_recon.png | 32.0545 | 0.967375 | NA | False |
| Places365_val_00000262_recon.png | 32.2141 | 0.965364 | NA | False |
| Places365_val_00000235_recon.png | 32.3933 | 0.966976 | NA | False |
| Places365_val_00000369_recon.png | 32.4875 | 0.964369 | NA | False |
| Places365_val_00000452_recon.png | 32.4994 | 0.946512 | NA | False |
| Places365_val_00000343_recon.png | 32.5885 | 0.964300 | NA | False |
| Places365_val_00000484_recon.png | 32.6847 | 0.955025 | NA | False |
| Places365_val_00000337_recon.png | 32.8673 | 0.966143 | NA | False |
