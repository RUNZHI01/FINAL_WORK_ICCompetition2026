# `fused_mean4_subtract4_divide4_multiply4_add14_relu3` Local Handwritten Lane Summary

- date: `2026-03-31`
- operator: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- scope: `local-only post-db handwritten lane`

## What now exists

Checked-in `fused_mean4_subtract4_divide4_multiply4_add14_relu3` handwritten lane root:

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/README.md`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1.py`

Operator-specific `fused_mean4_subtract4_divide4_multiply4_add14_relu3` scripts:

- `./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_mean4_post_db_local_build.py`

Runbook:

- `./session_bootstrap/runbooks/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_runbook_2026-03-31.md`

## Frozen asset inspection

- best staging task row: `rank=22`, `stage_name=legalized_fused_tir`, `prim_funcs=["main"]`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- tuning DB files:
  `database_workload.json` and `database_tuning_record.json`
- current best-staging per-task log:
  `absent under ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/`
- historical local mean4 tuning log for context only:
  `./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk3_20260313_131545/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_02_fused_mean4_subtract4_divide4_multiply4_add14_relu3.log`
- historical best logged trial in that local mean4 log:
  `Trial #31 -> 1604.0082 us`

## Local proof run

Command:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331
```

Observed proof facts:

- `database_lookup.query_tuning_record_hit = false`
- `database_lookup.query_ir_module_hit = false`
- `database_lookup.query_schedule_hit = false`
- `standalone_scheduled_task_build.status = missing_scheduled_ir_module`
- `post_database_apply.operator_present = true`
- `post_database_apply.operator_tir_is_scheduled = false`
- `post_db_scheduled_swap.swap_succeeded = true`
- `post_db_scheduled_swap.build_status = built`
- `local_build_output.export_status = exported`

Artifacts:

- output dir:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331`
- artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- artifact sha256:
  `de429fe2d2be48696c740aa4b279a9da6337fc469d2d05d6061f874e6702bbc9`
- report:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`
- report sha256:
  `79f13a8d82b0c8e89b946a716a3bee07d43b8f9e57893b8c7ca81eceb36f266c`

## Current edit state

- checked-in working copy status: `seed_synced_unedited`
- meaning: the local edit surface is ready, but current best-staging does not
  provide a direct mean4 DB schedule record, so the checked-in lane currently
  proves post-db swap/build viability rather than schedule-backed equivalence
- contract: local-only, diagnostic-only, and not suitable for SSH / remote
  benchmark claims

## Commit status

- requested focused commit: `blocked by sandbox`
- attempted from base HEAD: `e14e4fdf907e198cf45e113dd5a84b493aa8a39d`
- failure:
  `git add ... && git commit ... -> fatal: Unable to create '/home/tianxing/tvm_metaschedule_execution_project/.git/index.lock': Read-only file system`
