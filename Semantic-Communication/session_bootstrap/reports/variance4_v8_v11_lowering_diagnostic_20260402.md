# `fused_variance4_add13_tir_sqrt4` v8 vs v11 Lowering Diagnostic

Date: `2026-04-02`

## Question

Does the current exact-preserving `v11` volatility encoding

- `T.attr(T_multiply_local.data, "volatile_scope", 1)`

lower to the same codegen-visible storage / volatility semantics as the older
exact-preserving `v8` encoding

- `T.attr(T_multiply_local, "volatile_scope", 1)` on the raw local allocation handle?

## Scope

This is a **repo-local diagnostic** only.

- no SSH / remote board work
- no performance claims
- compare only the local AArch64/LLVM lowering path already used by the
  handwritten variance4 lane

## Commands Run

### Pure TIR path probe

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# build v8 / v11 working-copy TIR with tvm.tir.build(target=aarch64 llvm)
# capture per-pass IR after:
#   - tir.FlattenBuffer
#   - tir.StorageRewrite
#   - tir.MakePackedAPI
#   - tir.LowerTVMBuiltin
# capture final llvm via lib.inspect_source()
PY
```

### Full Relax / post-db swap path probe

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# rebuild the post-db applied module through the existing handwritten seam for
# v8 and v11, then capture the imported LLVM IR from ex.mod.imports[0]
PY
```

Diagnostic JSON written to:

- `./session_bootstrap/tmp/variance4_v8_v11_lowering_diagnostic_20260402.json`

## Core Findings

### 1) v8 and v11 are **not structurally identical** after lowering

Across the key observed TIR build stages, the captured modules are different:

- `tir.FlattenBuffer`: structural_equal = `false`
- `tir.StorageRewrite`: structural_equal = `false`
- `tir.MakePackedAPI`: structural_equal = `false`
- `tir.LowerTVMBuiltin`: structural_equal = `false`

The captured script SHA256 values also differ at every one of those stages.

So the answer is **not** “they are literally the same lowered TIR.”

### 2) But the codegen-visible volatile behavior is the same shape

For both `v8` and `v11`:

#### Pure `tvm.tir.build(...)` LLVM IR

- LLVM IR length: `109416`
- `volatile` count: `4`
- `load volatile` count: `2`
- `store volatile` count: `2`

The diagnostic snippets from the final LLVM both include the same critical form:

```llvm
%200 = load volatile float, ptr %T_multiply_local, align 64
%201 = fadd float %199, %200
```

#### Full Relax / post-db swap build imported LLVM IR

- LLVM IR length: `4510877`
- `volatile` count: `4`
- `load volatile` count: `2`
- `store volatile` count: `2`

So while the whole-module LLVM SHA differs, the **observable volatility pattern**
seen by the local AArch64 backend is unchanged in the dimensions that mattered
for the earlier exactness experiments.

### 3) v8 and v11 also converge at the exported artifact / correctness level

From the checked local status runs:

- `v8`: `exact_equal = true`
- `v11`: `exact_equal = true`

And the rebuilt exported artifact SHA256 is the same for both exact-preserving
variants:

- `v8` artifact SHA256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`
- `v11` artifact SHA256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`

That is stronger than “same volatile counts”: under the current local build
path, both encodings end up exporting the same artifact bytes.

## Interpretation

The local toolchain distinguishes the source-level placement enough that the
intermediate lowered TIR and whole-module LLVM SHA hashes differ, but it still
preserves the same effective volatile load/store boundary needed to keep the
variance4 round-trip exact.

Practical takeaway:

- `v10` proved that attaching `volatile_scope` to the declared buffer object is
  not accepted by local LLVM/AArch64 codegen.
- `v9` proved that removing volatility entirely loses exact equality.
- `v8` and `v11` both preserve exact equality.
- `v11` therefore looks like a **buildable exact-preserving alternative
  encoding**, not just a lucky local-only accident.

## Recommendation

Treat `v8` and `v11` as **effectively equivalent exact-preserving baselines for
this local toolchain**, even though they are not textually or structurally
identical at every lowering stage.

For the next narrow exactness-aware simplification (`v12`), prefer to start
from `v11`, because it makes the volatility attachment point explicit at
`T_multiply_local.data`, while still building and preserving exact equality.

The next candidate should therefore try **one tiny simplification that keeps
that explicit `.data`-level volatility encoding intact**, rather than revisiting
whether volatility can be removed.

## Status

- no new remote benchmark produced
- no new performance claim produced
- no new candidate committed in this diagnostic step
- current exact-preserving local baselines remain: `v8` and `v11`
