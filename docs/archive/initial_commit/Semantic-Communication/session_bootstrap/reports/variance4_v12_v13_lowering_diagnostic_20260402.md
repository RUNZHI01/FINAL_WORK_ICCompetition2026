# `fused_variance4_add13_tir_sqrt4` v12 vs v13 Lowering Diagnostic

Date: `2026-04-02`

## Question

After `v13` replaced the redundant hardcoded unit indices

- `lv335_red[v_ax0, v_ax1, T.int64(0), T.int64(0)]`

with the already-remapped unit-extent axes

- `lv335_red[v_ax0, v_ax1, v_ax2, v_ax3]`

while keeping the exact-preserving one-element local round-trip and `.data`-level
volatility intact, is `v13` now effectively equivalent to `v12` at the local
artifact / lowering / codegen-visible level?

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
# build v12 / v13 working-copy TIR with tvm.tir.build(target=aarch64 llvm)
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
# v12 and v13, then capture the imported LLVM IR from ex.mod.imports[0]
PY
```

### Exported artifact identity check

```bash
python3 - <<'PY'
# compare local_build_output.artifact_sha256 and artifact_size_bytes from
# v12 and v13 post-db local build reports
PY
```

Diagnostic JSON written to:

- `./session_bootstrap/tmp/variance4_v12_v13_lowering_diagnostic_20260402.json`

## Core Findings

### 1) v12 and v13 are **identical** at the key observed TIR lowering checkpoints

Across the same four checkpoints used in the earlier variance diagnostics,
`v12` and `v13` match exactly:

- `tir.FlattenBuffer`: structural_equal = `true`
- `tir.StorageRewrite`: structural_equal = `true`
- `tir.MakePackedAPI`: structural_equal = `true`
- `tir.LowerTVMBuiltin`: structural_equal = `true`

The captured script SHA256 values are also equal at every one of those stages.

This means the `v13` source-level unit-axis cleanup has already disappeared as a
meaningful distinction by the time the observed lowering pipeline reaches the
key codegen-adjacent checkpoints.

### 2) Final LLVM IR text SHA still differs, but the codegen-visible volatile shape matches

For both `v12` and `v13`:

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

The local post-db build reports for `v12` and `v13` agree on:

- artifact size bytes: `1674456`
- artifact sha256: `0ddf784727c578bbe37efac9be9939b4e5303644b20cd2dd1132d2d5a5578a12`

So at the exported local artifact level, `v12` and `v13` are fully identical.

## Interpretation

The `v13` unit-axis cleanup is a valid exact-preserving source-level cleanup,
but it no longer creates a meaningful distinction for the observed local
lowering/build path.

Practical takeaway:

- `v12` proved the raw local allocation handle can be removed while staying exact
- `v13` proved the remaining hardcoded unit indices can be replaced by the
  already-remapped unit axes while staying exact
- This diagnostic now strengthens that further: for the observed lowering
  checkpoints and the final exported local artifact, `v12` and `v13` are
  effectively equivalent

The remaining LLVM text SHA mismatch is therefore most likely attributable to
non-semantic differences elsewhere in the generated module text, not to a
meaningful change in the variance4 candidate’s codegen-visible volatility or
storage behavior.

## Recommendation

Treat `v13` as confirmation that the current variance4 handwritten line is now
very close to the practical local simplification floor under the current seam.

If this lane continues, the next step should **not** be another blind syntactic
cleanup candidate. Instead, prefer one of:

1. stop the local simplification chain here and summarize the exact-preserving
   boundary results for future reporting, or
2. run a targeted search for a genuinely new local equivalence class (for
   example a different exact-preserving volatility/store encoding), rather than
   another cosmetic source rewrite.

## Status

- no new remote benchmark produced
- no new performance claim produced
- no new candidate committed in this diagnostic step
- preferred exact-preserving local baseline remains effectively `v12` / `v13`
