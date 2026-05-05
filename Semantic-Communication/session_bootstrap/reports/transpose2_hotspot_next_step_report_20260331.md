# `fused_conv2d_transpose2_add12` Hotspot Next-Step Report

- date: `2026-03-31`
- scope: repo-local inspection only
- operator: `fused_conv2d_transpose2_add12`
- conclusion: `transpose2` already has stable hotspot evidence plus reusable best-staging DB/task-log assets, but it does **not** yet have a checked-in handwritten lane like `transpose1`.

## Existing assets

1. Hotspot evidence already exists and is stable:
   - `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
   - `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
   - `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
   - `session_bootstrap/reports/runtime_joint_top6_targeted_staging_search_diagnosis_20260331.md`
   - `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
   - Current best staging reference is still `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`.

2. Runtime-targeted search assets already include `transpose2`:
   - `session_bootstrap/runbooks/runtime_top2_targeted_search_2026-03-30.md`
   - `session_bootstrap/runbooks/runtime_joint_top6_targeted_staging_search_2026-03-30.md`
   - `session_bootstrap/scripts/run_phytium_runtime_top2_targeted_search.sh`
   - `session_bootstrap/scripts/run_phytium_runtime_joint_top6_targeted_staging_search.sh`

3. Best staging task-summary / DB inputs already exist and are the right frozen source for a handwritten lane:
   - task summary: `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
   - tuning DB: `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
   - per-task log: `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_4_fused_conv2d_transpose2_add12.log`
   - `task_summary.json` shows `transpose2` at `rank=17`, `stage_name=legalized_fused_tir`, and included in `selected_op_names`.

4. A schedule-preserving seam is already mechanically reusable from the `transpose1` lane:
   - reusable probe: `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`
   - proof from a local probe run on `2026-03-31` against the best-staging DB:
     - `query_tuning_record_hit = true`
     - `query_ir_module_hit = true`
     - `query_schedule_hit = true`
     - `standalone_scheduled_task_build.status = built`
     - `post_database_apply.operator_present = true`
     - `post_database_apply.operator_tir_is_scheduled = true`

5. The `transpose1` lane already documents what to reuse conceptually:
   - regression warning against raw pre-compile replacement:
     - `session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`
   - schedule-preserving seam note:
     - `session_bootstrap/reports/transpose1_schedule_preserving_seam_note_20260331.md`
   - operator-specific local build lane:
     - `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
     - `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

## Missing assets

1. No `transpose2`-specific checked-in handwritten directory exists under:
   - `session_bootstrap/handwritten/`

2. No `transpose2`-specific checked-in files exist for:
   - raw editable seed
   - post-DB scheduled reference seed
   - scheduled-form working copy
   - hook-facing candidate module
   - candidate metadata / manifests

3. No `transpose2`-specific scaffold / overlay / sync / local-build helper exists.
   The only checked-in handwritten scripts and template are hardwired to `fused_conv2d_transpose1_add9`:
   - `session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_handwritten_scaffold.py`
   - `session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py`
   - `session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_post_db_scheduled_seed.py`
   - `session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py`
   - `session_bootstrap/templates/handwritten/fused_conv2d_transpose1_add9_manual_impl.py.tmpl`

4. No `transpose2`-specific report or runbook exists yet. Current coverage is indirect only through generic hotspot / targeted-search reports.

## Recommended exact next step

Do **not** start from the old raw pre-compile handwritten seam. Reuse the `transpose1` lesson and begin `transpose2` with a **local-only post-DB scheduled reference-seed recovery** from the frozen best-staging candidate:

1. Use the frozen best-staging inputs:
   - `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
   - `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`

2. Run the existing seam probe for `transpose2` and write only a local seed pack under `session_bootstrap/tmp/`.

Recommended command:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py \
  --task-summary ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --operator fused_conv2d_transpose2_add12 \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py \
  --build-standalone-scheduled-task \
  --scheduled-seed-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose2_add12_seed_probe
```

Notes:
- This command is the smallest already-supported step because `probe_transpose1_schedule_preserving_seam.py` already accepts `--operator` and can write a post-DB scheduled seed.
- The `--candidate-impl` path above is only a temporary loader placeholder for the probe contract. It is acceptable for seed recovery, but **not** as a real `transpose2` handwritten candidate.
- Stop after the seed is emitted. Do not yet add remote validation, manual hook overlays, or a large new script family.

## Why this is the smallest honest step

1. `transpose1` already showed that raw handwritten replacement can destroy schedule-context reuse and produce misleading performance conclusions.
2. `transpose2` already has the DB/query evidence needed to skip that dead-end:
   - DB hit path exists
   - post-DB scheduled operator exists
   - standalone local build exists
3. Therefore the smallest concrete continuation is:
   - recover `transpose2` scheduled reference seed first
   - only then decide whether to check in `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/` and clone the `transpose1` local-build/working-copy lane

## Precise follow-on paths after the seed probe

If the seed probe writes cleanly, the next code change should stay minimal and operator-specific:

1. New handwritten lane root:
   - `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/`

2. First files to materialize there:
   - `fused_conv2d_transpose2_add12_post_db_scheduled_reference_seed_tir.py`
   - `post_db_scheduled_reference_seed_manifest.json`

3. Only after that, mirror the `transpose1` scheduled-form path in this order:
   - working-copy refresh pattern from `session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py`
   - local build wrapper pattern from `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
   - optional sync wrapper pattern from `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

