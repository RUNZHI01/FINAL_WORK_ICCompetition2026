# `fused_conv2d3_add15` Local Handwritten Lane Summary

- date: `2026-03-31`
- operator: `fused_conv2d3_add15`
- scope: `local-only post-db scheduled-form lane`

## What now exists

Checked-in `fused_conv2d3_add15` handwritten lane root:

- `./session_bootstrap/handwritten/fused_conv2d3_add15/README.md`
- `./session_bootstrap/handwritten/fused_conv2d3_add15/fused_conv2d3_add15_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d3_add15/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d3_add15/fused_conv2d3_add15_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d3_add15/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d3_add15/fused_conv2d3_add15_scheduled_form_candidate_v1.py`

Operator-specific `fused_conv2d3_add15` scripts:

- `./session_bootstrap/scripts/refresh_fused_conv2d3_add15_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_conv2d3_add15_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py`

Runbook:

- `./session_bootstrap/runbooks/handwritten_fused_conv2d3_add15_runbook_2026-03-31.md`

## Frozen asset inspection

- best staging task row: `rank=14`, `stage_name=legalized_fused_tir`, `prim_funcs=["main"]`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- tuning DB files:
  `database_workload.json` and `database_tuning_record.json`
- per-task log:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_0_fused_conv2d3_add15.log`

## Local proof run

Command:

```bash
python3 ./session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331
```

Observed proof facts:

- `database_lookup.query_tuning_record_hit = true`
- `database_lookup.query_ir_module_hit = true`
- `database_lookup.query_schedule_hit = true`
- `standalone_scheduled_task_build.status = built`
- `post_db_scheduled_swap.swap_succeeded = true`
- `post_db_scheduled_swap.build_status = built`
- `local_build_output.export_status = exported`

Artifacts:

- output dir:
  `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331`
- artifact:
  `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331/fused_conv2d3_add15_post_db_swap.so`
- artifact sha256:
  `bcfb7d6fe54da7edc4517cd669c3244788ee6d4ea866c3817ab766d7abb5db07`
- report:
  `./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331/fused_conv2d3_add15_post_db_swap_report.json`
- report sha256:
  `42285cee1af40b30a903ecef6db02d255c175e794dfe08511e640124c65e6712`

## Current edit state

- checked-in working copy status: `seed_synced_unedited`
- meaning: the lane is ready for scheduled-form handwritten edits, but no operator-side transformation has been applied yet
- contract: local-only, diagnostic-only, and not suitable for SSH / remote benchmark claims

## Commit status

- requested focused commit: `blocked by sandbox`
- attempted from base HEAD: `47c9c5869fc74c25da76670e641a38c335f92937`
- failure:
  `git add ... -> fatal: Unable to create '/home/tianxing/tvm_metaschedule_execution_project/.git/index.lock': Read-only file system`
