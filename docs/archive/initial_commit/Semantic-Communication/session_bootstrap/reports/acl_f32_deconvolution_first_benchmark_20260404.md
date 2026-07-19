# ACL F32 Deconvolution First Benchmark — 2026-04-04

- generated_at: `2026-04-04T16:40:00+08:00`
- target_board: `Phytium Pi`
- library: `~/ComputeLibrary/build/libarm_compute.so`
- binary: custom standalone benchmark built on board as `/tmp/acl_deconv_f32_bench`
- purpose: obtain the first runnable ACL deconvolution numbers on Phytium Pi after ACL build completed

## Background

ACL itself compiled successfully on the board:

- `~/ComputeLibrary/build/libarm_compute.so`
- `~/ComputeLibrary/build/examples/neon_deconvolution`
- `~/ComputeLibrary/build/examples/neon_convolution`

However, the official ACL examples are hard-coded to `DataType::F16`, and the Phytium Pi CPU does not support the required ARMv8.2 F16 path. Therefore, the official example failed at runtime with:

- `This CPU architecture does not support F16 data type, you need v8.2 or above`

To avoid blocking on that, a minimal standalone `DataType::F32` benchmark was compiled and run directly against `NEDeconvolutionLayer`.

## Shapes Tested

The first batch used three shapes corresponding to our three deconvolution hotspots:

1. `fused_conv2d_transpose1_add9`
   - TVM shape: `float32[1, 48, 64, 64] x float32[48, 24, 3, 3] -> float32[1, 24, 128, 128]`
2. `fused_conv2d_transpose2_add12`
   - TVM shape: `float32[1, 24, 128, 128] x float32[24, 12, 3, 3] -> float32[1, 12, 256, 256]`
3. `fused_conv2d_transpose_add6`
   - TVM shape: `float32[1, 96, 32, 32] x float32[96, 48, 3, 3] -> float32[1, 48, 64, 64]`

ACL benchmark used stride=2, pad=1, kernel=3 in `NEDeconvolutionLayer`, which produced output sizes `127/255/63` rather than `128/256/64`. So these numbers are **first runnable reference numbers, not yet strict apples-to-apples**.

## Results

- threads: `2`
- datatype: `F32`
- warmup: `3`
- repeat: `15`

| Case | ACL output shape | ACL median (ms) | ACL mean (ms) |
|---|---:|---:|---:|
| transpose1-like (`64x64x48 -> 24`) | `127x127x24` | **27.016** | 26.969 |
| transpose2-like (`128x128x24 -> 12`) | `255x255x12` | **45.619** | 45.647 |
| transpose_add6-like (`32x32x96 -> 48`) | `63x63x48` | **14.958** | 15.281 |

## TVM Current Reference (same hotspot family)

From existing runtime profiling evidence:

- `fused_conv2d_transpose1_add9`: `19.295 ms`
- `fused_conv2d_transpose2_add12`: `23.695 ms`
- `fused_conv2d_transpose_add6`: `18.622 ms`

Source reference:
- `session_bootstrap/reports/profiling_runtime_joint_top5_staging_artifact_reprobe_fixed_20260330_2305/runtime_command.log`

## Preliminary Interpretation

### What is already confirmed

1. **ACL build was successful** and usable on the board.
2. **A runnable ACL F32 deconvolution path now exists** on Phytium Pi.
3. The official ACL example failure was a **dtype/example issue**, not an ACL build failure.

### What is not yet safe to claim

It is **not yet safe** to claim a final ACL-vs-TVM winner from these three numbers alone, because:

1. ACL output shapes are currently `127/255/63`, while TVM hotspots are `128/256/64`.
2. The standalone ACL benchmark only times deconvolution itself, not the fused bias/add/epilogue around the TVM hotspot.
3. Therefore this is a **first runnable ACL reference**, not a final fairness-proof comparison.

### Still-useful signal

Even with the shape mismatch, the current first signal is:

- ACL transpose1-like: clearly slower than TVM hotspot reference (`27.0 ms` vs `19.3 ms`)
- ACL transpose2-like: clearly slower than TVM hotspot reference (`45.6 ms` vs `23.7 ms`)
- ACL transpose_add6-like: numerically faster than TVM hotspot reference (`15.0 ms` vs `18.6 ms`), but because the output shape is `63` instead of `64`, this one is **not yet a fair conclusion**

## API Boundary Confirmed After Follow-up Inspection

A follow-up source inspection on the board confirmed that stock ACL `NEDeconvolutionLayer` does **not** expose an `output_padding`-style parameter for these cases.

Relevant implementation points:

- `arm_compute/core/Utils.h`
- `src/core/Utils.cpp`
- `arm_compute/runtime/NEON/functions/NEDeconvolutionLayer.h`
- `src/runtime/NEON/functions/NEDeconvolutionLayer.cpp`

The effective output-width/height formula is:

```text
(width_input - 1) * stride_x - (pad_left + pad_right) + kernel_x
(height_input - 1) * stride_y - (pad_top + pad_bottom) + kernel_y
```

For our three hotspot-like cases with `stride=2`, `kernel=3`, `pad=1`, that means ACL naturally produces:

- `64 -> 127`
- `128 -> 255`
- `32 -> 63`

rather than TVM's `128 / 256 / 64`.

Therefore the current fairness boundary is now explicit:

1. **ACL build succeeded**
2. **ACL F32 deconvolution benchmark succeeded**
3. **Stock ACL deconvolution cannot exactly reproduce the TVM hotspot output geometry here without extra patching / semantic adaptation**

So the current ACL numbers are valid as a **first runnable reference**, but not as a final apples-to-apples claim against TVM fused transpose hotspots.

## Next Step

Given the confirmed API boundary, the defensible next move is:

1. keep these ACL numbers as `first runnable reference`
2. avoid over-claiming direct winner/loser for the `63/127/255`-mismatched case
3. if needed later, implement a patched/custom ACL-side benchmark or a normalized comparison methodology instead of pretending stock `NEDeconvolutionLayer` is shape-identical to TVM

## Raw Console Output

```text
__COMPILE_OK__
input=64x64x48 kernel=3x3 out_c=24 stride=2x2 pad=1x1 output=127x127x24 median_ms=27.016 mean_ms=26.969
input=128x128x24 kernel=3x3 out_c=12 stride=2x2 pad=1x1 output=255x255x12 median_ms=45.619 mean_ms=45.647
input=32x32x96 kernel=3x3 out_c=48 stride=2x2 pad=1x1 output=63x63x48 median_ms=14.958 mean_ms=15.281
```
