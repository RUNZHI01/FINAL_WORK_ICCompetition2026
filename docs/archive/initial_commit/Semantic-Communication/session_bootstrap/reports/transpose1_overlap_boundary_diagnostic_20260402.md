# `fused_conv2d_transpose1_add9` Overlap Boundary Diagnostic

Date: `2026-04-02`

## Scope

Local-only follow-up for the dropped transpose1 `v8` overlap probe.

- operator: `fused_conv2d_transpose1_add9`
- baseline still in force: checked-in `v7`
- no board benchmark was run
- this diagnostic did not create or bless any new `v8` candidate
- separate untracked transpose1 `v8` source/test files were present in the
  worktree by the end of the session and were left untouched

## Boundary Diagnosis

The preserved `v8` follow-up was a **producer-only** overlap carry, not a
producer+consumer carry:

- reconstructed semantic edit from the preserved `v8` bytecode:
  inside `data_dilate`, when `h_1 == 1`, skip `ax2 = 0, 1`
- that means the intended carry was:
  `data_dilate` global rows `31/32` for the first height tile and `95/96` for
  the second height tile

The row-level boundary proof says the overlap rows themselves are exact:

- `data_dilate` previous-stripe local rows `32/33` match current-stripe local
  rows `0/1` exactly for all width tiles
- that is the same global row pair:
  `31/32` in the first 64-row tile and `95/96` in the second
- `data_pad` previous-stripe local rows `32/33` also match current-stripe local
  rows `0/1` exactly for all width tiles
- that is the same global row pair:
  `32/33` in the first 64-row tile and `96/97` in the second
- rebuilding the current `data_pad` stripe from a producer-carried
  `data_dilate` stripe is row-exact
- directly carrying the consumer-facing `data_pad` boundary rows is also
  row-exact

So the boundary-row values do **not** support the theory that only producer-side
overlap is reusable. At the row-value level, the consumer-facing padded rows are
also safe to carry.

## What Still Fails

Even with that exact row-level identity, the real producer-only overlap edit is
still not a valid scheduled TIR candidate yet.

The current local repro of the preserved producer-only carry still differs from
`v7` on output rows:

- `32`, `33`, `96`, `97`
- `nonzero_diff_count = 12288`
- preserved local compare:
  `./session_bootstrap/tmp/transpose1_v8_vs_v7_correctness_20260402/check_report.json`

That means the failing boundary is **not** “producer rows are reusable but
consumer rows are not.” The failing boundary is that the current stripe relies
on an implicit skipped-write carry, and that is not a clean enough scheduled
boundary for exact local correctness.

## Concrete Conclusion

Result: **another more precise boundary condition is required**

- producer-only overlap carry is not ready as a checked-in next candidate
- consumer-facing `data_pad` rows are row-exact too, so abandoning them on
  principle would be the wrong diagnosis
- the next overlap attempt must make the carried rows explicit and stable for
  the consumer, rather than depending on a skipped write to leave old values in
  place

## Recommended Next Step

If overlap work is resumed at all, do one more local-only proof that makes the
two carried boundary rows explicit before compute reads them. Concretely:

1. keep the scope on transpose1 only
2. introduce an explicit 2-row carry mechanism at the `h_1` seam
3. prove local exactness against `v7` before creating any real `v8` candidate
4. do not run a board benchmark until that proof is clean

## Files Added

- `./session_bootstrap/scripts/diagnose_transpose1_overlap_boundary.py`
- `./session_bootstrap/reports/transpose1_overlap_boundary_diagnostic_20260402.md`

## Repro Command

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/diagnose_transpose1_overlap_boundary.py \
  --output-json ./session_bootstrap/tmp/transpose1_overlap_boundary_diagnostic_20260402.json
```
