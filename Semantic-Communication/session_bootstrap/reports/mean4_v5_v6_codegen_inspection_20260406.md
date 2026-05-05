# Mean4 v5/v6 Codegen Inspection

Date: `2026-04-06`

## Purpose

This note answers a specific question raised after the `mean4 v6` board result:

Was `v6` near-parity caused by losing good code generation, or was the
phase-ordering idea itself just too weak?

To answer that, I dumped and compared the generated AArch64 code for the
integrated handwritten-line artifacts:

- `v5` artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so`
- `v6` artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so`

Target symbol inspected in both shared objects:

- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_`

## Commands

```bash
nm -S --size-sort \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so \
  | rg 'fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_'

nm -S --size-sort \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so \
  | rg 'fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_'

llvm-objdump -d --no-show-raw-insn --symbolize-operands \
  --disassemble-symbols=fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_ \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so \
  > ./session_bootstrap/tmp/mean4_v5_compute_asm_20260406.txt

llvm-objdump -d --no-show-raw-insn --symbolize-operands \
  --disassemble-symbols=fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_ \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so \
  > ./session_bootstrap/tmp/mean4_v6_compute_asm_20260406.txt
```

## Function Size

- `v5` compute symbol:
  - address: `0x1f240`
  - size: `0x66c` (`1644` bytes)
- `v6` compute symbol:
  - address: `0x1f240`
  - size: `0x220` (`544` bytes)

So `v6` generates a much smaller function body than `v5`.

That size drop does **not** automatically mean it is faster. It mostly tells us
that LLVM emitted a much more compact channel-loop structure for `v6`, while
`v5` carries a larger code body due to the all-channel phase layout and the
way the reduction results are staged before the epilogue section.

## Question 1: Is the v5 epilogue already NEON-vectorized?

Yes.

`v5` already has a vectorized affine+ReLU hot loop. The key instructions are:

```asm
1f7b8: dup     v4.4s, v2.s[0]
1f7bc: dup     v5.4s, v3.s[0]
1f7d8: ldp     q6, q7, [x16, #-0x20]
1f7dc: ldp     q16, q17, [x16]
1f7e4: fmla    v18.4s, v4.4s, v6.4s
1f7f0: fmaxnm  v18.4s, v18.4s, v0.4s
1f7f4: fmla    v6.4s, v4.4s, v7.4s
1f7f8: fmaxnm  v6.4s, v6.4s, v0.4s
1f800: stp     q18, q6, [x16, #-0x30]
1f804: fmla    v7.4s, v4.4s, v16.4s
1f80c: fmaxnm  v7.4s, v7.4s, v0.4s
1f810: fmla    v6.4s, v4.4s, v17.4s
1f814: fmaxnm  v6.4s, v6.4s, v0.4s
1f818: stp     q7, q6, [x16, #-0x10]
```

Interpretation:

- scalar `scale` / `shift` are duplicated across vector lanes
- input is loaded as `q` registers
- the affine epilogue is lowered as vector `fmla`
- ReLU is lowered as vector `fmaxnm`
- output is written back with vector stores

So the answer is unambiguous:

- `v5` epilogue is **already** NEON-vectorized

## Question 2: Is the reduction still scalar?

Yes.

`v5` reduction is still a scalar dependency chain. Representative lines:

```asm
1f328: fcsel   s1, s0, s1, eq
1f32c: ldp     s2, s3, [x4, #-0x8]
1f330: fadd    s1, s1, s2
1f334: fadd    s1, s1, s3
1f338: ldp     s2, s3, [x4], #0x10
1f33c: fadd    s1, s1, s2
1f340: fadd    s1, s1, s3
```

This pattern repeats for each channel.

Important detail:

- there is no vector reduction like `fadd v?.4s, ...`
- there is no partial-sum lane structure
- accumulation stays on scalar `s` registers

So the current mean4 codegen state is:

- epilogue: vectorized
- reduction: scalar

## Question 3: Did v6 lose the vectorized epilogue?

No.

`v6` keeps the same kind of vectorized epilogue. Representative lines:

```asm
1f370: dup     v6.4s, v4.s[0]
1f374: dup     v7.4s, v5.s[0]
1f388: ldp     q16, q17, [x16, #-0x20]
1f38c: ldp     q18, q19, [x16]
1f394: fmla    v20.4s, v6.4s, v16.4s
1f3a0: fmaxnm  v20.4s, v20.4s, v1.4s
1f3a4: fmla    v16.4s, v6.4s, v17.4s
1f3a8: fmaxnm  v16.4s, v16.4s, v1.4s
1f3b0: stp     q20, q16, [x16, #-0x30]
1f3b4: fmla    v17.4s, v6.4s, v18.4s
1f3bc: fmaxnm  v17.4s, v17.4s, v1.4s
1f3c0: fmla    v16.4s, v6.4s, v19.4s
1f3c4: fmaxnm  v16.4s, v16.4s, v1.4s
1f3c8: stp     q17, q16, [x16, #-0x10]
```

So `v6` did **not** regress the hot-loop vectorization. It still gets:

- lane broadcast with `dup`
- vector multiply-add with `fmla`
- vector ReLU with `fmaxnm`
- vector loads/stores on `q` registers

## Instruction-Level Summary

Mnemonic counts inside the inspected compute symbol:

### v5

- `fadd`: `48`
- `fmul`: `1`
- `fdiv`: `1`
- `fmadd`: `1`
- `fmla`: `4`
- `fmaxnm`: `4`
- `dup`: `2`
- `fcsel`: `12`
- total instruction lines: `412`

### v6

- `fadd`: `4`
- `fmul`: `1`
- `fdiv`: `1`
- `fmadd`: `1`
- `fmla`: `4`
- `fmaxnm`: `4`
- `dup`: `2`
- `fcsel`: `1`
- total instruction lines: `136`

Interpretation:

- the vectorized epilogue core is present in both
- `v6` does **not** show a loss of vector affine codegen
- the big difference is in the scalar reduction/control structure, not in the
  vector epilogue itself

The `fadd` and `fcsel` count drop from `v5` to `v6` is consistent with a more
compact channel-loop body, not with a worse hot-loop lowering.

## What This Implies

The important conclusion is negative:

`v6` near-parity is **not** explained by "LLVM stopped vectorizing the
epilogue".

That means the earlier suspicion should be narrowed:

- `v5` already had a good NEON epilogue
- `v6` kept that good NEON epilogue
- yet route-level payload stayed flat

So the likely interpretations are:

1. the phase-ordering idea itself was too weak to matter materially
2. the remaining bottleneck is more reduction-side than epilogue-side
3. future wins are more likely to come from
   - reduction restructuring
   - explicit lane/partial-sum structure
   - width-lane control only if it improves something LLVM is not already doing

## Practical Design Consequence

The next move should probably **not** assume that explicit epilogue vectorization
will create a breakthrough, because the epilogue is already vectorized.

The more valuable next inspection / implementation target is:

- reduction-side codegen
- whether there is still a strict scalar accumulation chain on the hot path
- whether a partial-sum or lane-structured reduction can break that dependency

If a `v7` is attempted, the strongest justification is now:

- not "force epilogue vectorization"
- but "change reduction code shape, because epilogue vectorization is already
  there"

## Artifacts

- `v5` assembly dump:
  `./session_bootstrap/tmp/mean4_v5_compute_asm_20260406.txt`
- `v6` assembly dump:
  `./session_bootstrap/tmp/mean4_v6_compute_asm_20260406.txt`
- `v6` board benchmark:
  `./session_bootstrap/reports/handwritten_mean4_v6_line_remote_benchmark_20260406_1804.md`
- `v6` postmortem:
  `./session_bootstrap/reports/mean4_v6_postmortem_for_opus_20260406.md`
