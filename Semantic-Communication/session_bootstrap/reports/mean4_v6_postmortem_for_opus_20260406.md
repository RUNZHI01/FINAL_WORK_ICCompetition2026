# Mean4 v6 Postmortem For Opus

Date: `2026-04-06`

## Purpose

This note is a compact handoff for reviewing why the latest
`fused_mean4_subtract4_divide4_multiply4_add14_relu3` handwritten follow-up
(`v6`) did **not** turn into a stable handwritten-line payload win on the
Phytium Pi, even though the branch is real, distinct, and board-tested.

The goal is not to restate all logs. The goal is to answer four questions:

1. What exactly changed from `v5` to `v6`?
2. What did the board say?
3. What does that imply about the real bottleneck?
4. What should the next operator-specific direction be?

## One-Line Conclusion

`v6` proved that the "channelwise reduce -> immediate epilogue reuse" idea can
be implemented cleanly and produce a distinct handwritten-line artifact, but it
did **not** produce a stable same-day payload win. The paired long-sample delta
was only `-0.007 ms`, which is effectively parity. So the phase-ordering seam
alone is not enough.

## Current Mean4 Branches

- `v4`: baked into the current handwritten final route
- `v5`: current best post-`v4` handwritten-line candidate
- `v6`: board-tested structural follow-up after `v5`, but not promotable

Current file references:

- `v5` TIR:
  `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py`
- `v6` TIR:
  `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py`
- `v6` local report:
  `./session_bootstrap/reports/mean4_v6_local_status_20260406.md`
- `v6` remote report:
  `./session_bootstrap/reports/handwritten_mean4_v6_line_remote_benchmark_20260406_1804.md`

## What Changed From v5 To v6

### v5 structure

`v5` keeps one reduction pass for all channels, then does per-channel affine
precompute and epilogue:

```python
for ax0, ax1, ax2, ax3, k2, k3 in T.grid(1, 12, 1, 1, 256, 256):
    lv335_red[...] += lv335[...]

for ax0, ax1, ax2, ax3 in T.grid(1, 12, 1, 1):
    mean_local = lv335_red / 65536
    scale_local = weight / std
    shift_local = bias - mean * scale
    for k2, k3 in T.grid(256, 256):
        out = max(x * scale + shift, 0)
```

Its main idea was to reduce per-element scalar work inside the hot loop.

### v6 structure

`v6` keeps the exact same affine math as `v5`, but changes the phase order to
be channel-local:

```python
for ax1 in T.serial(12):
    for k2, k3 in T.grid(256, 256):
        lv335_red[0, ax1, 0, 0] += lv335[0, ax1, k2, k3]

    mean_local = lv335_red / 65536
    scale_local = weight / std
    shift_local = bias - mean * scale

    for k2, k3 in T.grid(256, 256):
        out = max(x * scale + shift, 0)
```

So `v6` changes **only** the channel-level phase ordering:

- `v5`: reduce all channels, then epilogue all channels
- `v6`: reduce one channel, immediately epilogue that same channel

The underlying hypothesis was that a `256 x 256` channel plane could be reused
more effectively if reduction and epilogue happened back-to-back, instead of
being separated by the reduction of the other 11 channels.

## What Stayed Unchanged

These parts did **not** change from `v5` to `v6`:

- reduction formula
- affine epilogue formula
- output shape and semantics
- post-db scheduled-form seam
- no explicit vectorization
- no explicit width tiling
- no NEON intrinsics
- no new intermediate full-frame buffers

This matters because `v6` was intentionally a narrow structural experiment, not
a broad rewrite.

## Local Result

`v6` is a clean local branch, not an identity-only branch:

- focused tests: `4 / 4 OK`
- correctness:
  - `exact_equal = false`
  - `allclose(1e-6, 1e-6) = true`
  - `max_abs_diff = 9.5367431640625e-07`
- post-db swap/build/export: `pass`
- operator-level artifact:
  `3bcdc181e3fe3c2e2284b8fdf3fc4e06797ccfdbbe2d52beb32c5c855d3c7a61`
- integrated handwritten-line artifact:
  `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`

That handwritten-line artifact is distinct from:

- current handwritten final:
  `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- `v5` handwritten-line candidate:
  `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`

So `v6` definitely changed real codegen output. The problem is not "the branch
collapsed back to baseline". The problem is "the branch changed, but the board
did not reward it".

## Board Result

Board state during the run:

- host: `Phytium-Pi`
- online cores: `3`
- `On-line CPU(s) list = 0-2`
- `remoteproc0 = running`

Upload integrity passed:

- local SHA = remote SHA =
  `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`

### Same-day serial payload A/B

`repeat=10`

- `v6`: `241.086 ms`
- handwritten final control: `240.658 ms`
- delta: `+0.428 ms`

First `repeat=30`

- `v6`: `240.261 ms`
- handwritten final control: `240.097 ms`
- delta: `+0.164 ms`

Reprobe `repeat=30`

- `v6`: `239.504 ms`
- end-of-chain control: `239.682 ms`
- delta: `-0.178 ms`

Paired long-sample average:

- candidate average median: `239.8825 ms`
- control average median: `239.8895 ms`
- average delta: `-0.007 ms`

Practical interpretation:

- `v6` is not a real regression
- `v6` is also not a real speedup
- it lands in the noise band

## What This Probably Means

This section is deliberately phrased as inference, not as a proven fact.

### 1. The bottleneck is not solved by phase ordering alone

The original `v6` hypothesis was that reusing a single `256 KB` channel plane
more immediately would reduce effective memory cost enough to show up on
payload. That did not happen in a stable way.

The most likely implication is:

- the real bottleneck is **not primarily** the phase split between
  "all-channel reduction" and "all-channel epilogue"
- or the benefit from phase-local reuse is too small compared with other costs

### 2. The dominant remaining cost is more likely inside the hot loop form

`v5` already cut the epilogue arithmetic down to:

- multiply
- add
- relu

`v6` kept that same arithmetic and only changed phase order. Since this still
did not move the board result materially, the next likely bottleneck is the
**shape of the hot loop itself**, not the high-level phase arrangement.

In plain terms:

- width traversal is still scalar-looking TIR
- there is still no explicit width blocking
- there is still no explicit vector lane structure
- there is still no explicit partial-sum strategy for reduction

### 3. The L2-reuse story may have been overestimated

`v6` was motivated by the idea that channel-local reuse should be much better
than revisiting the input later. That may still be directionally true, but the
board result says the realized gain is tiny.

Likely explanations:

- the original second read was not as expensive as expected
- hardware prefetch / existing cache behavior already masked much of the split
- the new loop nest may have lost something elsewhere
  - codegen quality
  - vectorization opportunities
  - instruction scheduling
  - register pressure

### 4. v6 does not overturn the current ranking inside mean4

Current ordering should remain:

1. `v4`: baked-in baseline
2. `v5`: current best promotion candidate
3. `v6`: useful structural evidence, but not a promote candidate

## Why This Matters For Next-Step Design

The key lesson is that the next move should probably **not** be another
small phase-order permutation in the same family.

`v6` answered that question already:

- "Does channelwise reduce->epilogue reordering alone beat current handwritten
  final?"
- answer: no stable win

That means the next promising seam should target a different code-level issue.

## Suggested Next Directions For Opus To Review

These are the highest-value directions now.

### Direction A: width-lane structure, not just phase structure

The hottest remaining work is still the `256 x 256` spatial sweep. A stronger
follow-up should make the width dimension look more explicitly vector-friendly.

What to inspect:

- split `k3` into an outer and small fixed inner lane
- see whether a lane-structured TIR gives better LLVM/NEON lowering
- verify whether the current `v5/v6` code is already auto-vectorized or not

This is the most obvious next seam because `v6` showed that phase reordering
alone is too weak.

### Direction B: reduction-specific restructuring

The reduction is still a long scalar accumulation chain per channel.

What to inspect:

- whether the reduction remains a strict dependency chain in generated code
- whether partial-sum restructuring could help more than phase-local reuse
- whether a reduction-side rewrite is numerically acceptable under the current
  tolerance contract

This is riskier than `v6`, but more likely to touch the real remaining cost.

### Direction C: verify whether v6 hurt or helped codegen quality

Before inventing a broader `v7`, it is worth checking whether the `v6` loop
nest changed low-level code generation in a good or bad way.

What to inspect:

- LLVM IR or assembly for `v5` vs `v6`
- whether the epilogue loop keeps the same vectorization pattern
- whether the reduction loop shape changed register allocation or scheduling

The point is not to defend `v6`; the point is to learn whether its near-parity
result came from:

- "correct idea but too small"
- or "reuse gain cancelled by worse generated code"

## Recommended Message To Carry Forward

If this needs to be summarized in one paragraph for design review:

`mean4 v6` was a clean structural experiment that kept the accepted `v5`
affine epilogue unchanged and tested whether channel-local reduction->epilogue
reuse would materially help on Phytium Pi. It produced a distinct artifact and
passed full local + board validation, but same-day handwritten-line payload
ended at effective parity (`-0.007 ms` paired long-sample delta). So the next
useful move is probably not another phase-order tweak in the same family; it is
more likely a hot-loop-shape change, especially width-lane/vector structure or
reduction-chain restructuring.

## Pointers

- local status:
  `./session_bootstrap/reports/mean4_v6_local_status_20260406.md`
- remote benchmark:
  `./session_bootstrap/reports/handwritten_mean4_v6_line_remote_benchmark_20260406_1804.md`
- current lane README:
  `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/README.md`
- overall progress:
  `./session_bootstrap/PROGRESS_LOG.md`
