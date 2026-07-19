# `fused_conv2d_transpose_add6` ACL vs TVM Standalone A/B — 2026-04-04

- date: 2026-04-04
- scope: rollback-safe standalone operator A/B for `fused_conv2d_transpose_add6`
- purpose: produce the smallest meaningful before/after-style comparison before attempting any deeper replacement experiment

## Why this report exists

Following the project's simplified execution direction, this run intentionally avoided touching Trusted Current and avoided direct full-model replacement.

Instead, it implemented the smallest comparable experiment:

- **TVM side**: compile the accepted `transpose_add6 v1` handwritten scheduled PrimFunc into a standalone `.so`
- **ACL side**: use the already-validated `F32` deconvolution benchmark with asymmetric padding to match output geometry `64x64x48`

This gives a rollback-safe operator-level A/B before attempting any larger integration.

## A side: TVM standalone operator

### Artifact

- local artifact:
  `session_bootstrap/tmp/transpose_add6_standalone_v1_20260404_171931/fused_conv2d_transpose_add6_v1_standalone.so`
- sha256:
  `640a835ac12f41a3b3315627fa7103aa0e0e460126fe2046e4db0d3d701eb7b1`

### Remote benchmark result

- label: `transpose_add6_tvm_v1`
- median: **`17521.767 us`**
- mean: `17564.678 us`
- min: `17483.057 us`
- max: `17906.171 us`
- std: `101.940 us`
- samples: `30`
- output shape: `[1, 48, 64, 64]`

## B side: ACL standalone operator

From:
- `session_bootstrap/reports/acl_replaceable_hotspots_asym_padding_probe_20260404.md`

Using the shape-aligned asymmetric padding branch:

- config: `pad=(0,1,0,1)`
- output shape: `64x64x48`
- median: **`11.581 ms`** = **`11581 us`**
- mean: `11.603 ms`

## A/B comparison

| side | output shape | median |
|---|---:|---:|
| TVM standalone `transpose_add6 v1` | `64x64x48` | **17521.767 us** |
| ACL standalone aligned branch | `64x64x48` | **11581 us** |

### Delta

- ACL vs TVM standalone delta: **`-5940.767 us`**
- relative improvement of ACL over TVM standalone: **`-33.90%`**

## Interpretation

This is the first operator-level A/B for `transpose_add6` where:

1. output geometry is aligned (`64x64x48`)
2. both sides are standalone operator measurements
3. the experiment is fully rollback-safe and isolated from Trusted Current

Under this experiment definition, the result is clear:

> **ACL is faster than the current standalone TVM handwritten `transpose_add6 v1` implementation by ~33.9%.**

## Boundary

This report still does **not** claim that:

- ACL has already been integrated into the full current model
- the full-model e2e result will improve by the same percentage
- Trusted Current should be upgraded

It only supports the narrower claim that:

- `transpose_add6` is now the strongest concrete candidate for a deeper ACL-based replacement experiment

## Next Step

The most justified next action is now:

1. keep `transpose_add6` as the sole priority hotspot for ACL replacement follow-up
2. attempt a deeper but still rollback-safe replacement-style experiment centered only on this operator
3. do **not** spend further time on ACL `transpose1` / `transpose2` before `transpose_add6` is exhausted
