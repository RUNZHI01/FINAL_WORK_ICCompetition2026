# Image Quality Metrics Report

- run_id: lpips_remote_snr10_retry_20260330_163229_tvm_baseline_vs_current_quality_crop249
- status: success
- timestamp: 2026-03-30T17:42:25+08:00
- comparison_label: tvm_baseline_vs_tvm_current_lpips_remote_snr10_crop249
- ref_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/lpips_remote_snr10_retry_20260330_163229_baseline/reconstructions
- test_dir: /tmp/lpips_remote_snr10_retry_20260330_163229_current_crop249/reconstructions
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
| PSNR (dB) | 34.4464 | 34.4451 | 2.0828 | 25.6136 | 40.8146 |
| SSIM | 0.970427 | 0.970448 | 0.005232 | 0.946121 | 0.982541 |
| LPIPS | 0.025850 | 0.025252 | 0.005787 | 0.011926 | 0.051834 |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| tvm_baseline_vs_tvm_current_lpips_remote_snr10_crop249 | 300 | 34.4464 | 0.970427 | 0.025850 |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000449_recon.png | 25.6136 | 0.946121 | 0.051834 | False |
| Places365_val_00000386_recon.png | 26.3244 | 0.967811 | 0.026618 | False |
| Places365_val_00000486_recon.png | 27.5051 | 0.971906 | 0.024823 | False |
| Places365_val_00000290_recon.png | 27.8438 | 0.965361 | 0.038753 | False |
| Places365_val_00000214_recon.png | 28.4665 | 0.966201 | 0.034291 | False |
| Places365_val_00000362_recon.png | 28.5468 | 0.946460 | 0.034315 | False |
| Places365_val_00000249_recon.png | 29.9670 | 0.969741 | 0.023984 | False |
| Places365_val_00000434_recon.png | 29.9955 | 0.965254 | 0.039887 | False |
| Places365_val_00000347_recon.png | 30.2734 | 0.969167 | 0.023287 | False |
| Places365_val_00000482_recon.png | 30.2831 | 0.968980 | 0.031802 | False |
