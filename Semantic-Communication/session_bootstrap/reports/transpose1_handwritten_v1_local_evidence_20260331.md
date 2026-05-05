# Transpose1 Handwritten V1 Local Evidence

- operator: `fused_conv2d_transpose1_add9`
- scope: `scheduled-form v1`, local-only, repo-local evidence only
- compared inputs:
  - `session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`
  - `session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.json`
  - `session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1/fused_conv2d_transpose1_add9_post_db_swap_report.json`
  - `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json`
  - `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`

## What V1 Changed Structurally

The `v1` working copy is derived from the checked-in post-db scheduled reference seed, not from the older raw pre-compile seed. The scheduled reference seed records TIR SHA `fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`; the current `v1` working copy records TIR SHA `2bda63c11d39172edcd82248327ba48ac5e436d5c433db28716e327a7d8949c6`.

Relative to the frozen scheduled reference seed, `v1` keeps the scheduled loop nest and the materialized `data_dilate`, `data_pad`, and `kernel_transform` stages, but makes one narrow operator-side change:

- bias is folded into the scheduled `compute_init` / `compute_update` path
- the full-size `compute_intermediate` allocation is removed
- the trailing `T_add` block is removed

This is a real structural delta from the scheduled reference seed, but it stays inside the post-db scheduled form instead of jumping back to the older raw pre-compile replacement seam.

## Local Evidence Available Now

`v0` already has an honest negative diagnostic result, but only through the older non-comparable seam:

- path kind: `diagnostic_raw_pre_compile_replacement`
- schedule context guarantee: `not_guaranteed`
- handwritten `v0` artifact: `sha256=b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28`, `size=1680408`
- safe runtime payload median from the existing staging-safe diagnostic run: `655.693 ms`
- reference staging artifact cited in the same diagnosis: `sha256=5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`, `run_median_ms=159.943`
- disposition already recorded locally: `v0 = drop / not for reprobe`

`v1` now has a better local structural consumption result through the schedule-preserving seam:

- path kind: `diagnostic_post_db_scheduled_primfunc_swap`
- schedule context guarantee: `post_db_scheduled_form_expected`
- comparison semantics: `local_build_structural_only`
- `swap_succeeded=true`
- `structural_equal_post_swap_vs_candidate=true`
- local artifact: `sha256=4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`, `size=1678648`
- artifact size delta vs `v0`: `-1760 bytes`

The smallest useful repo-local evidence step is now complete: the existing `v1` local build result has been synced into the transpose1 scaffold bookkeeping, so the local snapshot and expected SHA now point at `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1/...` instead of the older `v0` artifact.

## What Remains Unknown

- no `v1` runtime or payload measurement exists yet
- no `v1` correctness/output-equivalence evidence exists yet beyond successful swap/build/export
- no side-by-side local compare has been recorded yet for `scheduled reference seed` vs `v1` through the same post-db seam
- no staging-safe validation result exists yet for `v1`

## Recommendation

`v1` is worth the next stronger validation step, but not a performance claim and not a direct staging-safe validate yet.

Concrete recommendation: proceed to a stronger local compare first. Keep the post-db schedule-preserving seam fixed and compare the scheduled reference seed against `v1` through the same local lane, so the next result can answer whether the `v1` edit stays mechanically consumable and semantically sane before spending a staging-safe run on it.
