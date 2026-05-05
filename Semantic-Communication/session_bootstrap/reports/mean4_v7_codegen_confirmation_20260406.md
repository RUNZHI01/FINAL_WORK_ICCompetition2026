# Mean4 v7 Codegen Confirmation

Date: `2026-04-06`

## Purpose

This note records the one question that mattered for `v7`:

Did the new partial-sum reduction actually lower into vectorized AArch64 code,
or did the TIR change collapse back to scalar codegen?

## Artifact Under Inspection

- integrated handwritten-line artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so`
- target symbol:
  `fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_`

## Commands

```bash
nm -S --size-sort \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so \
  | rg 'fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_'

llvm-objdump -d --no-show-raw-insn --symbolize-operands \
  --disassemble-symbols=fused_mean4_subtract4_divide4_multiply4_add14_relu3_compute_ \
  ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so \
  > ./session_bootstrap/tmp/mean4_v7_compute_asm_20260406.txt
```

## Function Size

- compute symbol address: `0x1f240`
- compute symbol size: `0x288` (`648` bytes)

## Reduction-Side Confirmation

Yes. `v7` reduction is vectorized.

Representative instructions:

```asm
1f324: ldp     q1, q2, [x14, #-0x20]
1f328: fadd    v0.4s, v0.4s, v1.4s
1f32c: fadd    v0.4s, v0.4s, v2.4s
1f330: ldp     q1, q2, [x14]
1f334: fadd    v0.4s, v0.4s, v1.4s
1f338: fadd    v0.4s, v0.4s, v2.4s
1f358: faddp   s1, v0.2s
1f360: fadd    s1, s1, s2
1f368: fadd    s1, s1, s2
```

Interpretation:

- the loop consumes input as vector `q` loads
- accumulation happens on vector lanes via `fadd v?.4s`
- the four partial sums are then horizontally reduced with `faddp`
- this is exactly the intended `4`-lane partial-sum structure

## Epilogue-Side Confirmation

`v7` keeps the expected vector affine + ReLU path:

```asm
1f3c8: dup     v4.4s, v2.s[0]
1f3cc: dup     v5.4s, v3.s[0]
1f3ec: fmla    v18.4s, v4.4s, v6.4s
1f3f8: fmaxnm  v18.4s, v18.4s, v0.4s
1f3fc: fmla    v6.4s, v4.4s, v7.4s
1f400: fmaxnm  v6.4s, v6.4s, v0.4s
```

So `v7` does not trade away the already-good epilogue codegen in order to win
on the reduction side.

## Comparison Against the Earlier State

From the earlier `v5/v6` inspection, the situation was:

- epilogue: already vectorized
- reduction: still scalar

`v7` changes that to:

- epilogue: still vectorized
- reduction: now vectorized as well

That makes `v7` the first `mean4` handwritten branch in this lane that reaches
the intended NEON path on both sides of the operator hot path.

## Conclusion

- `v7` reduction-side TIR change does survive lowering
- the generated code contains real vector reduction instructions
- `v7` therefore tests the intended seam honestly rather than merely producing
  a different artifact shape

## Output

- disassembly:
  `./session_bootstrap/tmp/mean4_v7_compute_asm_20260406.txt`
