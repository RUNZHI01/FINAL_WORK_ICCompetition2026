# `fused_variance4_add13_tir_sqrt4` v11 vs v12 Lowering Diagnostic

Date: `2026-04-02`

## Question

After `v12` removed the source-level raw `T.allocate(...)` handle while keeping

- the one-element local store/load boundary
- the explicit `.data`-level `volatile_scope`
- exact local correctness

is `v12` now effectively equivalent to `v11` at the local artifact / lowering /
codegen-visible level?

## Scope

This is a **repo-local diagnostic** only.

- no SSH / remote board work
- no runtime/performance claims
- compare only the local AArch64/LLVM lowering path already used by the
  handwritten variance4 lane

## Commands Run

### Pure TIR path probe

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# build v11 / v12 working-copy TIR with tvm.tir.build(target=aarch64 llvm)
# capture per-pass IR after:
#   - tir.FlattenBuffer
#   - tir.StorageRewrite
#   - tir.MakePackedAPI
#   - tir.LowerTVMBuiltin
# capture final llvm via built.inspect_source()
PY
```

### Full Relax / post-db swap path probe

```bash
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# rebuild the post-db applied module through the existing handwritten seam for
# v11 and v12, then capture the imported LLVM IR from ex.mod.imports[0]
PY
```

### Exported artifact identity check

```bash
python3 - <<'PY'
# compare local_build_output.artifact_sha256 and artifact_size_bytes from
# v11 and v12 post-db local build reports
PY
```

Diagnostic JSON written to:

- `./session_bootstrap/tmp/variance4_v11_v12_lowering_diagnostic_20260402.json`

## Core Findings

### 1) v11 and v12 are **identical** at the key observed TIR lowering checkpoints

Across the same four checkpoints used in the earlier `v8 vs v11` diagnostic,
`v11` and `v12` match exactly:

- `tir.FlattenBuffer`: structural_equal = `true`
- `tir.StorageRewrite`: structural_equal = `true`
- `tir.MakePackedAPI`: structural_equal = `true`
- `tir.LowerTVMBuiltin`: structural_equal = `true`

The captured script SHA256 values are also equal at every one of those stages.

That is a stronger result than the earlier `v8 vs v11` comparison: by these
observed lowering checkpoints, the source-level raw handle removal in `v12`
has already disappeared as a meaningful distinction.

### 2) Final LLVM IR text SHA still differs, but the codegen-visible volatile shape matches

For both `v11` and `v12`:

#### Pure `tvm.tir.build(...)` LLVM IR

- LLVM IR length: equal
- `volatile` count: equal
- `load volatile` count: equal
- `store volatile` count: equal

#### Full Relax / post-db swap build imported LLVM IR

- LLVM IR length: equal
- `volatile` count: equal
- `load volatile` count: equal
- `store volatile` count: equal

The whole-module LLVM SHA hashes are still different, so these are not bitwise
identical text dumps. But all directly inspected volatility/load/store counts
match, and the key lowering checkpoints are already identical.

### 3) Exported local artifact is identical

The local post-db build reports for `v11` and `v12` agree on:

- artifact size bytes: `1674456`
- artifact sha256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`

So at the exported local artifact level, `v11` and `v12` are fully identical.

## Interpretation

The source-level raw `T.allocate(...)` handle removed in `v12` is no longer a
meaningful distinction for this local toolchain.

Practical takeaway:

- `v11` proved that `.data`-level volatility is buildable and exact-preserving
- `v12` proved that the explicit raw local allocation handle can be removed
  without changing the exact local result
- This diagnostic now strengthens that further: for the observed lowering
  checkpoints and the final exported local artifact, `v11` and `v12` are
  effectively equivalent

The remaining LLVM text SHA mismatch is therefore most likely attributable to
non-semantic differences elsewhere in the generated module text, not to a
meaningful change in the variance4 candidate’s codegen-visible volatility
behavior.

## Recommendation

Treat `v12` as the new preferred exact-preserving baseline, because it is the
cleaner source form and is already equivalent to `v11` at:

- the observed key lowering checkpoints
- the codegen-visible volatile load/store counts
- the exported local artifact SHA256
- the exact local correctness result

If this lane continues, the next narrow exactness-aware step (`v13`) should no
longer revisit the raw allocation handle question. Instead, it should target
another still-visible source-level redundancy above the now-established
`v12` baseline.

## Status

- no new remote benchmark produced
- no new performance claim produced
- no new candidate committed in this diagnostic step
- preferred exact-preserving local baseline moving forward: `v12`
