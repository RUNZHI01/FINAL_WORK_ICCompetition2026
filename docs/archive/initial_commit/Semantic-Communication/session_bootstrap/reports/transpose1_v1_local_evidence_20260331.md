# Transpose1 v1 Local Evidence Note

- generated_at: `2026-03-31T13:41:33+08:00`
- operator: `fused_conv2d_transpose1_add9`
- scope: `scheduled-form v1 / local-only compare`
- recommendation: `Proceed to stronger local compare`

## What v1 changed structurally

- `v1` still uses the checked-in scheduled reference form as the base and keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized.
- `compute_intermediate` is removed from `v1`, while it is present in the scheduled reference.
- The trailing `T_add` block is removed from `v1`, while it is present in the scheduled reference.
- `compute_init` now seeds `T_add_intermediate` from bias `lv320` instead of zero-initializing `compute_intermediate`.
- `compute_update` now accumulates directly into `T_add_intermediate`.
- Working-copy manifest states: `Bias is folded into the scheduled compute_init/compute_update path so the full-size compute_intermediate buffer and trailing T_add pass are removed.`

## Known local artifact/build facts

- Scheduled reference source stays anchored to `post_database_scheduled_primfunc_swap` with `post_db_operator_tir_is_scheduled=true` and task summary `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`.
- Current `v1` local post-db report: `swap_succeeded=true`, `build_status=built`, `export_status=exported`, `structural_equal_post_swap_vs_candidate=true`.
- Current `v1` local artifact: `sha256=4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`, `size=1678648`, report `./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1/fused_conv2d_transpose1_add9_post_db_swap_report.json`.
- Previous local post-db evidence: candidate `v0`, `swap_succeeded=true`, `build_status=built`, `export_status=exported`, `structural_equal_post_swap_vs_candidate=false`, artifact `sha256=b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28`, `size=1680408`.
- Compared with that previous local post-db artifact, `v1` changed the exported `.so` from `b654d55008b8...` to `4f0986e4806b...` and reduced size by `1760` bytes.
- Scheduled reference staged artifact in repo remains `sha256=5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`, `size=1678424`, `run_median_ms=159.943` from `./session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.json`.
- Relative to that staged reference artifact, the current `v1` local artifact differs in SHA and is `+224` bytes in size.
- Prior handwritten `v0` runtime evidence in repo remains `sha256=b654d55008b82a9e30a4d10650672698d9f5db64d91937507e0b044537982f28`, `size=1680408`, `run_median_ms=655.693`, but that report is still marked non-comparable because it came from the older raw pre-compile seam.

## Still unknown

- No local runtime number exists yet for `v1` on the post-db schedule-preserving seam.
- No correctness or numerical-equality check against the scheduled reference artifact is recorded here.
- No remote/staging-safe validation exists yet for this `v1` line.
- Artifact SHA/size movement alone does not justify any performance claim.

## Recommendation

- `v1` is worth the next stronger validation step because the structural delta is narrow, the post-db scheduled swap stayed mechanical (`true`), and the local build/export completed cleanly on the same scheduled reference inputs/DB.
- The next step should still be `stronger local compare`, not a performance claim: add a local correctness/behavior compare first, then decide whether staging-safe validation is justified.
