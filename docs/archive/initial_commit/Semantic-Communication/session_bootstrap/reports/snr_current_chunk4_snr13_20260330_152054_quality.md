# Image Quality Metrics Report

- run_id: snr_current_chunk4_snr13_20260330_152054_quality
- status: success
- timestamp: 2026-03-30T15:47:13+08:00
- comparison_label: trusted_current_snr13_vs_pytorch_reference
- ref_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/quality_metrics_inputs_20260312/reference/reconstructions
- test_dir: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/snr_sweep_current_chunk4_20260330_152054/snr_current_chunk4_snr13_20260330_152054_current/reconstructions
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
| PSNR (dB) | 36.8695 | 36.8223 | 1.6059 | 32.3850 | 42.0978 |
| SSIM | 0.978757 | 0.978931 | 0.003849 | 0.961448 | 0.987226 |
| LPIPS | skipped | skipped | skipped | skipped | skipped |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| trusted_current_snr13_vs_pytorch_reference | 300 | 36.8695 | 0.978757 | skipped |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000355_recon.png | 32.3850 | 0.974939 | NA | False |
| Places365_val_00000433_recon.png | 33.1775 | 0.971597 | NA | False |
| Places365_val_00000235_recon.png | 33.2142 | 0.973409 | NA | False |
| Places365_val_00000484_recon.png | 33.4507 | 0.963163 | NA | False |
| Places365_val_00000395_recon.png | 33.4588 | 0.975608 | NA | False |
| Places365_val_00000369_recon.png | 33.5593 | 0.971317 | NA | False |
| Places365_val_00000262_recon.png | 33.6166 | 0.972750 | NA | False |
| Places365_val_00000452_recon.png | 33.8080 | 0.961448 | NA | False |
| Places365_val_00000459_recon.png | 33.8256 | 0.973579 | NA | False |
| Places365_val_00000366_recon.png | 34.0798 | 0.970719 | NA | False |
