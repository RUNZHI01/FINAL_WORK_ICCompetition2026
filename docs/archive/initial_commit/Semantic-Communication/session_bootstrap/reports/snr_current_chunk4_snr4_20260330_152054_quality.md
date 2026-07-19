# Image Quality Metrics Report

- run_id: snr_current_chunk4_snr4_20260330_152054_quality
- status: success
- timestamp: 2026-03-30T15:41:22+08:00
- comparison_label: trusted_current_snr4_vs_pytorch_reference
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/snr_sweep_current_chunk4_20260330_152054/snr_current_chunk4_snr4_20260330_152054_current/reconstructions
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
| PSNR (dB) | 31.8047 | 31.7900 | 1.5966 | 27.2412 | 36.7651 |
| SSIM | 0.939559 | 0.939619 | 0.010898 | 0.897358 | 0.963047 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| trusted_current_snr4_vs_pytorch_reference | 300 | 31.8047 | 0.939559 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000355_recon.png | 27.2412 | 0.928601 | NA | False |
| Places365_val_00000433_recon.png | 27.8515 | 0.914932 | NA | False |
| Places365_val_00000262_recon.png | 28.0816 | 0.917368 | NA | False |
| Places365_val_00000395_recon.png | 28.1998 | 0.926736 | NA | False |
| Places365_val_00000235_recon.png | 28.5686 | 0.924238 | NA | False |
| Places365_val_00000369_recon.png | 28.7094 | 0.921774 | NA | False |
| Places365_val_00000484_recon.png | 28.8133 | 0.911472 | NA | False |
| Places365_val_00000308_recon.png | 28.8459 | 0.927764 | NA | False |
| Places365_val_00000459_recon.png | 28.8634 | 0.922190 | NA | False |
| Places365_val_00000215_recon.png | 28.8764 | 0.918805 | NA | False |
