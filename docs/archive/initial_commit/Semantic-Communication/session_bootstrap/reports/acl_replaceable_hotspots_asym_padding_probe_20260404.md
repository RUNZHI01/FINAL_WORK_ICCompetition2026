# ACL 可回退局部替换实验 — 非对称 Padding 对齐探测（2026-04-04）

- date: 2026-04-04
- purpose: verify whether stock ACL `NEDeconvolutionLayer` can be configured to match the TVM transpose hotspot output geometry (`128/256/64`) using asymmetric padding, enabling a closer before/after A/B experiment
- board: `Phytium Pi`
- library: `~/ComputeLibrary/build/libarm_compute.so`
- benchmark binary: `/tmp/acl_deconv_f32_bench_asym`
- threads: `2`
- dtype: `F32`
- warmup: `3`
- repeat: `15`

## Motivation

Earlier ACL first-run evidence only used symmetric padding `(1,1,1,1)`, which produced output shapes `127 / 255 / 63` and prevented a fairer replacement-style A/B against TVM transpose hotspots.

This probe tested whether **asymmetric padding** `(left,right,top,bottom) = (0,1,0,1)` can force stock ACL to produce the same output geometry as the TVM hotspot family:

- `64 -> 128`
- `32 -> 64`
- `128 -> 256`

## Results

| case | ACL config | output shape | median_ms | mean_ms |
|---|---|---:|---:|---:|
| transpose1_sym | `pad=(1,1,1,1)` | `127x127x24` | 29.677 | 31.462 |
| transpose1_asym | `pad=(0,1,0,1)` | `128x128x24` | **34.996** | 35.117 |
| transpose_add6_sym | `pad=(1,1,1,1)` | `63x63x48` | 11.574 | 11.643 |
| transpose_add6_asym | `pad=(0,1,0,1)` | `64x64x48` | **11.581** | 11.603 |
| transpose2_sym | `pad=(1,1,1,1)` | `255x255x12` | 34.734 | 34.963 |
| transpose2_asym | `pad=(0,1,0,1)` | `256x256x12` | **33.029** | 33.083 |

## Interpretation

### Key finding

Stock ACL `NEDeconvolutionLayer` **can** reproduce the target output geometry for these three hotspot families using asymmetric padding `(0,1,0,1)`.

This removes the earlier hard blocker that the experiment was limited to `127 / 255 / 63` outputs only.

### Replacement-style A/B relevance

Using the asymmetric-padding results as the more relevant branch:

- `transpose1`-like (`128x128x24`): ACL `34.996 ms`
- `transpose_add6`-like (`64x64x48`): ACL `11.581 ms`
- `transpose2`-like (`256x256x12`): ACL `33.029 ms`

Compared with current TVM hotspot references from `profiling_judge_expanded_10samples_20260403.md`:

- `fused_conv2d_transpose1_add9`: TVM `~27.5 ms` → ACL **slower**
- `fused_conv2d_transpose_add6`: TVM `~20.4 ms` → ACL **faster**
- `fused_conv2d_transpose2_add12`: TVM `~22.5 ms` → ACL **slower**

### Engineering consequence

This means the simplest rollback-safe replacement experiment should now prioritize:

1. `transpose_add6` — strongest positive ACL signal
2. `transpose1` — now looks negative under shape-aligned compare
3. `transpose2` — negative under shape-aligned compare

So if we only spend time on one actual replacement-style follow-up, the best target is now clearly:

- **`fused_conv2d_transpose_add6`**

## Raw output

```text
case=transpose1_sym output=127x127x24 median_ms=29.677 mean_ms=31.462 pad_lrtb=1,1,1,1
case=transpose1_asym output=128x128x24 median_ms=34.996 mean_ms=35.117 pad_lrtb=0,1,0,1
case=transpose_add6_sym output=63x63x48 median_ms=11.574 mean_ms=11.643 pad_lrtb=1,1,1,1
case=transpose_add6_asym output=64x64x48 median_ms=11.581 mean_ms=11.603 pad_lrtb=0,1,0,1
case=transpose2_sym output=255x255x12 median_ms=34.734 mean_ms=34.963 pad_lrtb=1,1,1,1
case=transpose2_asym output=256x256x12 median_ms=33.029 mean_ms=33.083 pad_lrtb=0,1,0,1
```
