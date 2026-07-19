# `fused_conv2d_transpose2_add12` Local Handwritten Lane Summary

- date: `2026-03-31`
- operator: `fused_conv2d_transpose2_add12`
- scope: `local-only post-db scheduled-form lane`

## What now exists

Checked-in transpose2 handwritten lane root:

- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/README.md`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`

Operator-specific transpose2 scripts:

- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_transpose2_post_db_local_build.py`

Minimal shared helper edit:

- `./session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`
  now supports `--skip-handwritten-candidate` so scheduled seed refresh can run
  without depending on any working-copy candidate state.

Runbook:

- `./session_bootstrap/runbooks/handwritten_fused_conv2d_transpose2_add12_runbook_2026-03-31.md`

## Local proof run

Command:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_proof_20260331
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

- artifact:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose2_add12_post_db_swap.so`
- artifact sha256:
  `7f7c13d44a392cf2dce8b3281fee3170b1781b25368944bb933c8c8775317858`
- report:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose2_add12_post_db_swap_report.json`
- report sha256:
  `7f72c20cd6f2de455e8074169706ca40841ebccb4d51c4fe4306cd4e64349052`

## Commit status

- requested focused commit: `blocked by sandbox`
- attempted from base HEAD: `f332aba5863b19a84e7aecd39b05f08e9ac1a79c`
- failure:
  `git add ... -> fatal: Unable to create '/home/tianxing/tvm_metaschedule_execution_project/.git/index.lock': Read-only file system`

The worktree now contains the complete transpose2 lane and the successful local
proof artifacts above. The only unfinished part is updating the main repo's git
metadata, which this sandbox does not permit.
