# `fused_conv2d_transpose_add6` Local Handwritten Lane Summary

- date: `2026-03-31`
- operator: `fused_conv2d_transpose_add6`
- scope: `local-only post-db scheduled-form lane`

## What now exists

Checked-in transpose_add6 handwritten lane root:

- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/README.md`
- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py`

Operator-specific transpose_add6 scripts:

- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py`

Runbook:

- `./session_bootstrap/runbooks/handwritten_fused_conv2d_transpose_add6_runbook_2026-03-31.md`

## Frozen asset inspection

- best staging task row: `rank=18`, `stage_name=legalized_fused_tir`, `prim_funcs=["main"]`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- per-task log:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_2_fused_conv2d_transpose_add6.log`

## Local proof run

Command:

```bash
python3 ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331
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
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331`
- artifact:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose_add6_post_db_swap.so`
- artifact sha256:
  `8e629c0d2905165283e43fd527292f0bea1ba3f74f4158e1e819b10338eb97d6`
- report:
  `./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose_add6_post_db_swap_report.json`
- report sha256:
  `9adcc9351c6f546001f2951edf2416126b6428dc4d0d7361b56879c66c558268`

## Current edit state

- checked-in working copy status: `seed_synced_unedited`
- meaning: the lane is ready for scheduled-form handwritten edits, but no operator-side transformation has been applied yet
- contract: local-only, diagnostic-only, and not suitable for SSH / remote benchmark claims

## Commit status

- requested focused commit: `blocked by sandbox`
- attempted from base HEAD: `6868342c3a110ee00a27e96edf6c96c9bf3017cc`
- failure:
  `git add ... -> fatal: Unable to create '/home/tianxing/tvm_metaschedule_execution_project/.git/index.lock': Read-only file system`
