# Image Quality Metrics Report

- run_id: lpips_remote_snr10_retry_20260330_163229_quality
- status: success
- timestamp: 2026-03-30T16:39:55+08:00
- comparison_label: pytorch_vs_tvm_current_lpips_remote_snr10
- ref_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/lpips_remote_snr10_retry_20260330_163229_pytorch_ref/reconstructions
- test_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/lpips_remote_snr10_retry_20260330_163229_current/reconstructions
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
| PSNR (dB) | 35.6633 | 35.6442 | 1.5907 | 31.7987 | 40.8741 |
| SSIM | 0.972751 | 0.972870 | 0.004913 | 0.948686 | 0.983229 |
| LPIPS | 0.025124 | 0.024821 | 0.005156 | 0.013095 | 0.042058 |

## Paper Row

| Comparison | Images | PSNR (dB) | SSIM | LPIPS |
|---|---:|---:|---:|---:|
| pytorch_vs_tvm_current_lpips_remote_snr10 | 300 | 35.6633 | 0.972751 | 0.025124 |

## Worst Cases By PSNR

| Image | PSNR (dB) | SSIM | LPIPS | Cropped |
|---|---:|---:|---:|---|
| Places365_val_00000433_recon.png | 31.7987 | 0.963049 | 0.029204 | False |
| Places365_val_00000355_recon.png | 31.8891 | 0.968488 | 0.025168 | False |
| Places365_val_00000395_recon.png | 32.2032 | 0.967174 | 0.028232 | False |
| Places365_val_00000369_recon.png | 32.2530 | 0.965183 | 0.030265 | False |
| Places365_val_00000235_recon.png | 32.2641 | 0.965010 | 0.036331 | False |
| Places365_val_00000452_recon.png | 32.3488 | 0.948686 | 0.024794 | False |
| Places365_val_00000484_recon.png | 32.3613 | 0.955722 | 0.028244 | False |
| Places365_val_00000262_recon.png | 32.4434 | 0.965969 | 0.031603 | False |
| Places365_val_00000443_recon.png | 32.8089 | 0.964845 | 0.024391 | False |
| Places365_val_00000358_recon.png | 32.8294 | 0.967606 | 0.023793 | False |
