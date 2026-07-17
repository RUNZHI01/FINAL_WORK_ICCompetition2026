# PyTorch Reference and Showcase Sample Ranking

## Scope

Generate PyTorch reference reconstructions for all 5,000 images in `E:\Main\Career\集创赛\原始图像`, then extend the host-side reconstruction comparison page so its left reference can switch between the original image and the matching PyTorch reconstruction. The existing board-side TVM/USRP job remains on the right.

The implementation must reuse the prerecorded baseline path: `run_remote_pytorch_reference_reconstruction.sh` and `pytorch_reference_reconstruction.py`. Host execution may call the same Python entry point directly, using `host_pic_to_latent/jscc` and `board_deps/pytorch/compressed_gan.pt`; this changes placement, not model code.

## Dataset and Provenance

The source set is exactly `00000001.jpg` through `00005000.jpg`. Latents are generated with the existing `host_pic_to_latent/encode_latent.py` path and stored as runtime artifacts outside Git. A manifest must map every source filename, source hash, latent filename, latent hash, PyTorch output, model hash, SNR, seed, and command line.

PyTorch uses SNR 10 and a fixed seed, matching the prerecorded baseline defaults. Existing output and manifest formats remain readable.

## Comparison Page

Add an `原图 | PyTorch` segmented selector to the left directory band. `原图` remains the default. The selected reference controls the left preview and the per-image metrics shown against the right TVM reconstruction.

The service receives a local PyTorch output directory and source-to-latent manifest. Reference images never use SFTP. Metric cache keys include `(job, image index, reference mode)` so values cannot leak between modes. A missing PyTorch result is shown as unavailable and does not silently fall back to the original.

## Quality Standard

Use one canonical RGB, exact-shape metric implementation for the comparison page and ranking tools:

- PSNR in dB, higher is better.
- Global SSIM, higher is better.
- Chroma MAE, lower is better; this is the existing color-noise auxiliary metric.

Reports keep the comparison scope explicit: `original-pytorch`, `original-tvm`, or `pytorch-tvm`.

## Selecting 300 Showcase Samples

PyTorch alone cannot measure OTA retries. Selection therefore has two stages:

1. Rank all 5,000 images by original-to-PyTorch quality. Reject missing outputs and shape mismatches, then prefer high PSNR/SSIM and low chroma MAE. Keep a buffered candidate pool rather than immediately freezing 300 images.
2. Run the candidate pool through USRP IQ + TVM. Final ranking first minimizes actual retry count, then maximizes original-to-TVM and PyTorch-to-TVM quality while minimizing chroma MAE. Samples without USRP evidence cannot enter the final 300.

The ranking output is a CSV and JSON report with raw metrics, retry evidence, normalized score, exclusion reason, and selected flag. It must also create a manifest for the final 300; source images are referenced, not duplicated by default.

## Verification

Unit tests cover manifest mapping, reference switching, cache isolation, metric consistency, missing references, and ranking order. Run a small PyTorch smoke before the 5,000-image job. Verify output count and hashes, then compare a sample manually in the browser. Existing original-reference behavior and lazy board downloads must remain unchanged.
