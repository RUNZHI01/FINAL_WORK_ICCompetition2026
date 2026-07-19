# Handwritten `fused_conv2d_transpose2_add12` Local-First Runbook

Updated: `2026-03-31`

## Purpose

Establish the smallest schedule-preserving local handwritten lane for
`fused_conv2d_transpose2_add12` using the frozen best-staging DB and without
touching trusted current or launching any SSH / remote benchmark work.

## Fixed references

- best staging candidate SHA: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- per-task log:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_4_fused_conv2d_transpose2_add12.log`

## Checked-in lane files

- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/scheduled_form_candidate_v2_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py`

## Operator-specific scripts

- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_transpose2_post_db_local_build.py`

## Workflow

1. Refresh the checked-in post-db scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py \
  --allow-overwrite
```

2. Refresh the checked-in editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py \
  --allow-overwrite
```

3. Prove the local post-db scheduled swap path still builds:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build
```

4. When preparing the next manual board benchmark, build the isolated `v2`
candidate instead of overwriting the accepted `v1` baseline:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v2
```

## Notes

- This lane is deliberately local-only and diagnostic-only.
- The accepted checked-in `v1` working copy already carries the bias-fusion edit and has a remote baseline report at `161.416 ms`.
- The new `v2` working copy is the isolated P1-style structural candidate that fuses `data_dilate + data_pad`.
- Do not run SSH or remote benchmark work from this runbook yet.
