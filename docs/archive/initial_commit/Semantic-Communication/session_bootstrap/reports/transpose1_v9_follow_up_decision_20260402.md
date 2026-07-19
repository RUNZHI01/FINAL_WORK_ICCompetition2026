# `fused_conv2d_transpose1_add9` v9 Follow-up Decision

Date: `2026-04-02T20:15:00+08:00`

## Baseline To Beat

- current transpose1 board baseline: `v7`
- remote report:
  `./session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md`
- remote median: `156.785 ms`

## Re-ranked Remaining Follow-ups In The Same Winning Family

1. Explicit `h_1` seam carry on top of `v7`
   - still the strongest conceptual next move because `v7` already proved that
     shrinking the staged live set along the winning `h_1` stripe / `dc_0`
     slice family helps, and the remaining obvious redundant work is the
     2-row overlap between the two `h_1` stripes
   - chosen first again here, but only as a local scratch probe
2. `w_1` rolling-width carry / sub-stripe follow-up
   - deprioritized because `v7` already stages one `34 x 10` stripe once and
     reuses it across both `w_1` positions, so width-side carry would give less
     new reduction while pushing back toward the already-weaker consumer-order
     space
3. Kernel-side slice staging
   - deprioritized because the recent wins came from data-staging locality, not
     from moving `kernel_transform`, and `kernel_transform` is already
     materialized once per operator call rather than once per spatial tile
4. Narrower-than-`v7` reduction slices
   - closed: `v8` already showed that going from a `dc_0` 4-channel slice to a
     single input channel is the wrong direction

## Decision

No concrete `v9` candidate is worth checking in yet.

The top-ranked follow-up remained the explicit `h_1` seam-carry idea on top of
`v7`, but the local scratch proof still failed:

- temporary local reconstruction: keep `v7`'s `dc_0` 4-channel slice, add an
  explicit `data_pad_h1_carry` buffer for the two overlap rows, skip the
  redundant second-stripe `ax2 = 0, 1` producer/consumer rows, then reload the
  carried `data_pad` rows explicitly before `compute_update`
- compile status: `py_compile OK`
- local correctness vs `v7`:
  `allclose(atol=1e-5, rtol=1e-5) = false`,
  `max_abs_diff = 18.116403579711914`,
  `nonzero_diff_count = 12288`
- localized mismatch rows:
  output rows `32`, `33`, `96`, `97`

That means the best remaining non-narrower move is still not concrete enough to
promote into a checked-in `v9` path. It reproduces the same boundary failure
signature as the earlier dropped overlap probes, so creating a real `v9`
wrapper / manifest / test / build artifact here would leave a misleading
candidate in the tree.

## Why No Real `v9` Was Created

- the over-narrow single-channel direction is already closed by the `v8` board
  result, so a real next branch had to come from overlap-style reuse or a more
  weakly supported locality move
- the highest-value overlap-style reuse idea is still the explicit `h_1`
  seam-carry variant
- the temporary explicit-carry reconstruction was concrete enough to test
  locally, but it was **not** exact-safe enough to keep
- lower-ranked alternatives (`w_1` rolling carry, kernel-side slice staging)
  are less directly supported by the evidence than the overlap path and are not
  strong enough to justify a blind checked-in branch before the seam behavior is
  understood

## Next Evidence-gathering Step

Do one more local-only scratch proof before any real `v9` is created:

1. Keep scope on transpose1 only.
2. Build a throwaway second-`h_1` stripe path that uses a **disjoint explicit
   seam buffer**, not reused in-place `data_dilate` / `data_pad` storage.
3. Compare the fully materialized current-stripe staged rows
   (`data_pad` rows `32..35` and `96..99`, all `10` staged columns, all `dc_0`
   channels) against `v7` before `compute_update`.
4. If that disjoint-buffer proof is still not exact, close the overlap branch
   entirely and move on. If it is exact, only then promote it into a real `v9`
   path.

## Files Changed

- `./session_bootstrap/reports/transpose1_v9_follow_up_decision_20260402.md`

No new `v9` source, manifest, wrapper, test, or build artifact was kept.

## Commands Run

```bash
rg -n "transpose1 v[0-9]|fused_conv2d_transpose1_add9|v7|v8" -S .
rg --files . | rg "fused_conv2d_transpose1_add9|transpose1|add9|report|prep|test"
sed -n '1,240p' session_bootstrap/handwritten/fused_conv2d_transpose1_add9/README.md
sed -n '1,260p' session_bootstrap/reports/transpose1_v6_local_prep_20260402.md
sed -n '1,260p' session_bootstrap/reports/transpose1_v7_remote_benchmark_20260402_182039.md
sed -n '1,260p' session_bootstrap/reports/transpose1_v8_follow_up_decision_20260402.md
sed -n '1,260p' session_bootstrap/reports/transpose1_overlap_boundary_diagnostic_20260402.md
diff -u \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v6_working_copy_tir.py \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py
diff -u \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v7_working_copy_tir.py \
  session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v8_working_copy_tir.py
sed -n '1,260p' session_bootstrap/scripts/diagnose_transpose1_overlap_boundary.py
python3 - <<'PY'
# temporary reconstruction of /tmp/transpose1_v9_probe.py from the checked-in v7 TIR
PY
python3 -m py_compile /tmp/transpose1_v9_probe.py
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
# local correctness compare among scheduled reference, checked-in v7, and /tmp/transpose1_v9_probe.py
PY
```

## Local Status

- kept tracked transpose1 files: report only
- temporary scratch `v9` reconstruction: `py_compile OK`
- temporary scratch correctness vs `v7`: `FAILED`
- no kept transpose1 unit tests were run in this turn
- no kept local post-db swap build/export was run in this turn
- no SSH, scp, or remote board commands were used

## Board-side Next Step

None yet.

Do **not** run a board benchmark for transpose1 from this turn, because no new
checked-in `v9` candidate was created.

## Operator Control

Commit was intentionally left for manual operator control.
