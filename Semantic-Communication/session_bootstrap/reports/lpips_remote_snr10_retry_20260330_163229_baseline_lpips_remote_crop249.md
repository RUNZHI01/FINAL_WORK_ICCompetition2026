# Image Quality Metrics Report

- run_id: lpips_remote_snr10_retry_20260330_163229_baseline_quality_crop249
- status: success
- timestamp: 2026-03-30T17:05:35+08:00
- comparison_label: pytorch_vs_tvm_baseline_lpips_remote_snr10_crop249
- ref_dir: /tmp/lpips_remote_snr10_retry_20260330_163229_ref_crop249/reconstructions
- test_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/lpips_remote_snr10_retry_20260330_163229_baseline/reconstructions
- matched_png_count: 300
- compared_image_count: 300
- max_images: 300
- size_mismatch_mode: crop-top-left
- size_mismatch_mode_resolved: crop-top-left
- cropped_pair_count: 0
- shape_mismatch_count: 0
- shape_mismatch_status: none
- shape_mismatch_message: No shape mismatch detected.
- lpips_mode: force
- lpips_status: LPIPS enabled (alex on cpu)
- psnr_perfect_match_count: 0
- missing_in_test_count: 0
- extra_in_test_count: 0

## Aggregate

| Metric | Mean | Median | Std | Min | Max |
|---|---:|---:|---:|---:|---:|
| PSNR (dB) | 34.4244 | 34.5601 | 2.0802 | 25.8307 | 40.3009 |
| SSIM | 0.970454 | 0.970567 | 0.005250 | 0.945818 | 0.982541 |
| LPIPS | 0.025883 | 0.025599 | 0.005828 | 0.011361 | 0.051841 |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| pytorch_vs_tvm_baseline_lpips_remote_snr10_crop249 | 300 | 34.4244 | 0.970454 | 0.025883 |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000449_recon.png | 25.8307 | 0.948315 | 0.051841 | False |
| Places365_val_00000386_recon.png | 26.6632 | 0.967806 | 0.030235 | False |
| Places365_val_00000486_recon.png | 26.9056 | 0.972942 | 0.025932 | False |
| Places365_val_00000290_recon.png | 27.3792 | 0.963786 | 0.040692 | False |
| Places365_val_00000362_recon.png | 28.3392 | 0.945818 | 0.034390 | False |
| Places365_val_00000434_recon.png | 29.2101 | 0.962699 | 0.042604 | False |
| Places365_val_00000214_recon.png | 29.4134 | 0.967300 | 0.031257 | False |
| Places365_val_00000249_recon.png | 29.5468 | 0.969452 | 0.024947 | False |
| Places365_val_00000454_recon.png | 29.5554 | 0.965619 | 0.029374 | False |
| Places365_val_00000347_recon.png | 30.4306 | 0.968709 | 0.023731 | False |
