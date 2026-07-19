# Checked-in scheduled-form lane: `fused_variance4_add13_tir_sqrt4`

This directory is the smallest repo-native handwritten lane for
`fused_variance4_add13_tir_sqrt4` that keeps the frozen best-staging
MetaSchedule context intact locally.

It intentionally starts at the post-db scheduled reference seed and does not
introduce a separate raw pre-compile hook lane yet.

## Current Status

- historical checked-in board-proven best remains `v18 = 158.347 ms`:
  `session_bootstrap/reports/variance4_v18_remote_benchmark_20260403_0239.md`
- `v22` and `v24` are exact-preserving local branches that collapse back to the
  `v21` artifact, so they stay classified as artifact-identical negative
  evidence:
  `session_bootstrap/reports/variance4_v22_local_status_20260406.md`,
  `session_bootstrap/reports/variance4_v24_local_status_20260406.md`
- `v23` is still exact-preserving and artifact-distinct locally, but a real
  board run on `2026-04-06` with `3` online cores did not show a stable win
  over same-day `v18` controls, so `v23` should not be promoted:
  `session_bootstrap/reports/variance4_v23_remote_benchmark_20260406_1344.md`
- current practical interpretation:
  the `v18` handoff family is still the winning lane, but the specific
  `v23` buffer-flattening branch should now be treated as board-tested negative
  evidence rather than the next promotion candidate

## Files

- `fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py`: checked-in post-db scheduled reference seed recovered from the frozen best-staging DB.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for that scheduled reference seed.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy_tir.py`: editable scheduled-form working copy cloned from the checked-in reference seed.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: small manifest for the editable working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1.py`: local-only candidate wrapper that points the existing post-db seam at the working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy_tir.py`: first handwritten edit candidate that removes the standalone `T_add_intermediate` epilogue stage by folding the epsilon add into the final `sqrt` consumer.
- `scheduled_form_candidate_v2_working_copy_manifest.json`: manifest for the versioned `v2` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py`: local-only candidate wrapper for the `v2` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3_working_copy_tir.py`: narrow follow-up candidate that removes the standalone `T_divide_intermediate` epilogue stage by folding the `/65536.0` directly into the final `sqrt` consumer.
- `scheduled_form_candidate_v3_working_copy_manifest.json`: manifest for the versioned `v3` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3.py`: local-only candidate wrapper for the `v3` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4_working_copy_tir.py`: narrow follow-up candidate that removes the standalone `T_divide` mean stage by folding the mean `/65536.0` directly into the `T_subtract` consumer while keeping the `v3` simplifications intact.
- `scheduled_form_candidate_v4_working_copy_manifest.json`: manifest for the versioned `v4` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4.py`: local-only candidate wrapper for the `v4` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v5_working_copy_tir.py`: narrow follow-up candidate that removes the standalone full-size `T_subtract` stage by folding the subtraction directly into the `T_multiply` consumer while keeping the `v4` simplifications intact.
- `scheduled_form_candidate_v5_working_copy_manifest.json`: manifest for the versioned `v5` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v5.py`: local-only candidate wrapper for the `v5` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy_tir.py`: narrow follow-up candidate that removes the standalone full-size `T_multiply` stage by folding the squared subtract expression directly into the `T_multiply_red` consumer while keeping the `v5` simplifications intact.
- `scheduled_form_candidate_v6_working_copy_manifest.json`: manifest for the versioned `v6` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6.py`: local-only candidate wrapper for the `v6` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a_working_copy_tir.py`: exactness-recovery follow-up that keeps the `v6` full-size `T_multiply` removal but adds a one-element volatile local round-trip before `T_multiply_red` accumulation to block backend `fmadd` contraction.
- `scheduled_form_candidate_v6a_working_copy_manifest.json`: manifest for the versioned `v6a` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a.py`: local-only candidate wrapper for the `v6a` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7_working_copy_tir.py`: exactness-aware follow-up that keeps the `v6a` volatile local round-trip but removes the redundant explicit `T.Cast("float32", ...)` on the local write.
- `scheduled_form_candidate_v7_working_copy_manifest.json`: manifest for the versioned `v7` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7.py`: local-only candidate wrapper for the `v7` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8_working_copy_tir.py`: exactness-aware follow-up that keeps the `v7` volatile local round-trip but simplifies the one-element local buffer declaration by dropping the redundant explicit `scope="local"` from `T.decl_buffer(...)` while keeping the same float32 local store/load boundary.
- `scheduled_form_candidate_v8_working_copy_manifest.json`: manifest for the versioned `v8` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8.py`: local-only candidate wrapper for the `v8` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9_working_copy_tir.py`: exactness-aware follow-up that keeps the explicit one-element local store/load round-trip from `v8` but removes the `volatile_scope` attribute from the local allocation to test whether the store/load boundary alone is sufficient for exact equality.
- `scheduled_form_candidate_v9_working_copy_manifest.json`: manifest for the versioned `v9` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9.py`: local-only candidate wrapper for the `v9` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10_working_copy_tir.py`: exactness-aware follow-up that keeps the full `v8` one-element local store/load round-trip intact while moving the explicit `volatile_scope` marker from the raw local allocation handle to the declared one-element local buffer.
- `scheduled_form_candidate_v10_working_copy_manifest.json`: manifest for the versioned `v10` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10.py`: local-only candidate wrapper for the `v10` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11_working_copy_tir.py`: exactness-aware follow-up that keeps the full `v8` one-element local store/load round-trip intact while moving the explicit `volatile_scope` marker to the declared one-element local buffer data handle via `T_multiply_local.data`.
- `scheduled_form_candidate_v11_working_copy_manifest.json`: manifest for the versioned `v11` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11.py`: local-only candidate wrapper for the `v11` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy_tir.py`: exactness-aware follow-up that keeps the `v11` `.data`-level volatility encoding intact while removing the separate raw `T.allocate(...)` handle and declaring the one-element local buffer directly via `T.decl_buffer(..., scope="local")`.
- `scheduled_form_candidate_v12_working_copy_manifest.json`: manifest for the versioned `v12` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py`: local-only candidate wrapper for the `v12` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13_working_copy_tir.py`: exactness-aware follow-up that keeps the full `v12` handle-free `.data`-volatile local round-trip intact while replacing the remaining hardcoded unit `lv335_red[..., 0, 0]` accesses in the folded `T_multiply_local` expression with the already-remapped unit axes.
- `scheduled_form_candidate_v13_working_copy_manifest.json`: manifest for the versioned `v13` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py`: local-only candidate wrapper for the `v13` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14_working_copy_tir.py`: exactness-aware follow-up that keeps the full `v13` unit-axis-cleaned `.data`-volatile local round-trip intact while switching the one-element local declaration from `T.decl_buffer(..., scope="local")` to the alternate handle-free `T.alloc_buffer(..., scope="local")` encoding.
- `scheduled_form_candidate_v14_working_copy_manifest.json`: manifest for the versioned `v14` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14.py`: local-only candidate wrapper for the `v14` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15_working_copy_tir.py`: performance-oriented exactness-aware follow-up that keeps the full `v14` handle-free `.data`-volatile local round-trip intact while making only the tiny `lv335_red` reduction buffer explicitly `scope="local"`.
- `scheduled_form_candidate_v15_working_copy_manifest.json`: manifest for the versioned `v15` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v15.py`: local-only candidate wrapper for the `v15` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16_working_copy_tir.py`: performance-oriented exactness-aware follow-up that keeps the full `v15` storage placement intact while making only the tiny `T_multiply_red` reduction buffer explicitly `scope="local"`.
- `scheduled_form_candidate_v16_working_copy_manifest.json`: manifest for the versioned `v16` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v16.py`: local-only candidate wrapper for the `v16` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17_working_copy_tir.py`: performance-oriented exactness-aware follow-up that returns to the checked-in `v15` baseline, treats `v16` only as negative evidence, and adds a tiny `lv335_mean_local` handoff buffer so the normalized mean is materialized once per channel and reused inside the hot `T_multiply_local` loop.
- `scheduled_form_candidate_v17_working_copy_manifest.json`: manifest for the versioned `v17` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v17.py`: local-only candidate wrapper for the `v17` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18_working_copy_tir.py`: performance-oriented exactness-aware follow-up that starts from the checked-in board-proven `v17` state, keeps the `lv335_mean_local` normalized-mean handoff intact, and adds a tiny one-element `T_subtract_local` handoff so the centered value is materialized once and reused for the square.
- `scheduled_form_candidate_v18_working_copy_manifest.json`: manifest for the versioned `v18` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v18.py`: local-only candidate wrapper for the `v18` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19_working_copy_tir.py`: performance-oriented exactness-aware follow-up that starts from the checked-in board-proven `v18` state, keeps the centered-value `T_subtract_local` reuse intact, and tightens the normalized-mean handoff itself to a one-element per-channel local scalar reused across the full inner loop.
- `scheduled_form_candidate_v19_working_copy_manifest.json`: manifest for the versioned `v19` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v19.py`: local-only candidate wrapper for the `v19` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21_working_copy_tir.py`: exactness-aware follow-up that retries the `v19` scalar normalized-mean handoff while restoring `T_multiply_red` to `scope="local"` so the mean-handoff idea is isolated from the earlier reduction-storage regression.
- `scheduled_form_candidate_v21_working_copy_manifest.json`: manifest for the versioned `v21` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v21.py`: local-only candidate wrapper for the `v21` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22_working_copy_tir.py`: exactness-aware follow-up that keeps the original `v18` mean-handoff shape and centered-value reuse intact but retimes the second phase so each per-channel mean is produced and then consumed through the full inner reduction before advancing.
- `scheduled_form_candidate_v22_working_copy_manifest.json`: manifest for the versioned `v22` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v22.py`: local-only candidate wrapper for the `v22` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23_working_copy_tir.py`: exactness-aware follow-up that keeps the `v18` handoff family intact but flattens the tiny 12-channel internal buffers from `(1, 12, 1, 1)` to `(12,)` so the indexing change is more codegen-visible.
- `scheduled_form_candidate_v23_working_copy_manifest.json`: manifest for the versioned `v23` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v23.py`: local-only candidate wrapper for the `v23` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24_working_copy_tir.py`: exactness-aware follow-up that starts from the scalar-mean `v21` branch and flattens the tiny reduction buffers `lv335_red` / `T_multiply_red` from `(1, 12, 1, 1)` to `(12,)`.
- `scheduled_form_candidate_v24_working_copy_manifest.json`: manifest for the versioned `v24` working copy.
- `fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24.py`: local-only candidate wrapper for the `v24` working copy.

## Refresh / Build

Refresh the checked-in scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed.py \
  --allow-overwrite
```

Refresh the editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy.py \
  --allow-overwrite
```

Run the local-only post-db scheduled swap build:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build
```

Run the local-only post-db scheduled swap build for the first handwritten `v2`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v2
```

Run the local correctness compare for the current `v2` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v2_correctness_check.json
```

Run the local-only post-db scheduled swap build for the follow-up `v3`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v3
```

Run the local correctness compare for the current `v3` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v3_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v3_correctness_check.json
```

Run the local-only post-db scheduled swap build for the follow-up `v4`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v4
```

Run the local correctness compare for the current `v4` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v4_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v4_correctness_check.json
```

Run the local-only post-db scheduled swap build for the follow-up `v5`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v5.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v5
```

Run the local correctness compare for the current `v5` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v5_correctness_check.json
```

Run the local-only post-db scheduled swap build for the follow-up `v6`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6
```

Run the local correctness compare for the current `v6` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v6_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-recovery `v6a`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v6a
```

Run the local correctness compare for the current `v6a` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6a_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v6a_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v7`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v7
```

Run the local correctness compare for the current `v7` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v7_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v8`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v8
```

Run the local correctness compare for the current `v8` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v8_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v8_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v9`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v9
```

Run the local-only post-db scheduled swap build for the exactness-aware `v13`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v13
```

Run the local correctness compare for the current `v13` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v13_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v13_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v14`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14
```

Run the local correctness compare for the current `v14` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v14_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v14_correctness_check.json
```

Run the local correctness compare for the current `v9` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v9_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v9_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v10`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v10
```

Run the local correctness compare for the current `v10` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v10_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v10_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v11`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v11
```

Run the local correctness compare for the current `v11` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v11_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v11_correctness_check.json
```

Run the local-only post-db scheduled swap build for the exactness-aware `v12`
candidate:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v12
```

Run the local correctness compare for the current `v12` working copy:

```bash
python3 ./session_bootstrap/scripts/check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py \
  --candidate-tir ./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy_tir.py \
  --output-json ./session_bootstrap/tmp/variance4_v12_correctness_check.json
```

Current best-staging keeps `fused_variance4_add13_tir_sqrt4` in the task
summary, but does not expose a direct `query_schedule` / `query_ir_module` /
`query_tuning_record` hit for it. This lane therefore starts from the post-db
applied-module operator form recovered through the existing seam.

The checked-in working copies in this directory remain local-only and
diagnostic-only. When a candidate is later staged onto the board, record that
separately under `session_bootstrap/reports/` rather than treating the wrapper
itself as benchmark evidence.
