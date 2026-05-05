# `fused_variance4_add13_tir_sqrt4` Handwritten Lane Status

Date: `2026-04-02`

## Summary

A real repo-native handwritten lane now exists for
`fused_variance4_add13_tir_sqrt4`, but it is a local-only scheduled-form lane.

It is anchored to the frozen `joint-top6` best-staging references:

- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`

## What was established

- checked-in post-db scheduled reference seed:
  `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py`
- checked-in seed manifest:
  `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/post_db_scheduled_reference_seed_manifest.json`
- checked-in editable scheduled-form working copy:
  `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy_tir.py`
- checked-in working-copy manifest:
  `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v1_working_copy_manifest.json`
- checked-in local-only candidate wrapper:
  `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1.py`
- local helper scripts:
  `./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed.py`
  `./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy.py`
  `./session_bootstrap/scripts/run_variance4_post_db_local_build.py`

## Probe / Build Status

Observed from the local seam probe and the local post-db swap build:

- `legalized_fused_tir` task-summary row exists at `rank=26`
- `query_tuning_record_hit = false`
- `query_ir_module_hit = false`
- `query_schedule_hit = false`
- `post_database_apply.operator_present = true`
- `post_db_scheduled_seed.status = written`
- `post_db_scheduled_swap.swap_succeeded = true`
- `post_db_scheduled_swap.build_status = built`
- exported local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_proof_20260402/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- exported artifact SHA256:
  `5719231c5cd93468bab74761627330b7c16afd826d20b00810f937d69a03abaf`

## What this lane can prove

- the frozen best-staging task summary still carries `fused_variance4_add13_tir_sqrt4`
- the existing seam can recover a post-db reference seed for `variance4`
- the checked-in scheduled-form working copy is structurally loadable
- the checked-in wrapper can swap that working copy back into the post-db full
  module and complete a local export build

## What this lane cannot prove yet

- it does not prove a direct DB-scheduled record exists for `variance4`
- it does not prove any runtime speedup
- it does not prove board safety or integrated artifact health
- it does not justify SSH, remote validation, or promotion into trusted current

## Local Test Status

`python3 -m unittest` passed for the focused lane tests after `pytest` was found
to be unavailable in this environment.

## Next Step

Keep this lane as the starting surface for the first real variance4 scheduled-form
edit. The next coding pass should make one narrow local edit inside the checked-in
working copy, rerun the same local post-db swap build, and only then decide whether
the candidate is mature enough for a remote validation pass.
