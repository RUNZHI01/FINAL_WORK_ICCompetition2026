# Handwritten `fused_variance4_add13_tir_sqrt4` Local-First Runbook

Updated: `2026-04-02`

## Purpose

Establish the smallest local handwritten lane for
`fused_variance4_add13_tir_sqrt4` using the frozen best-staging references and
without touching trusted current or launching any SSH / remote benchmark work.

## Fixed references

- best staging candidate SHA: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- runtime reprobe hotspot evidence:
  `./session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`

## Checked-in lane files

- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_variance4_add13_tir_sqrt4/fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v1.py`

## Operator-specific scripts

- `./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_variance4_post_db_local_build.py`

## Workflow

1. Refresh the checked-in post-db reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_post_db_scheduled_seed.py \
  --allow-overwrite
```

2. Refresh the checked-in editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_variance4_add13_tir_sqrt4_scheduled_form_working_copy.py \
  --allow-overwrite
```

3. Prove the local post-db swap path still builds:

```bash
python3 ./session_bootstrap/scripts/run_variance4_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/variance4_post_db_swap_local_build
```

## Notes

- Current best-staging keeps `fused_variance4_add13_tir_sqrt4` at `rank=26` in
  `legalized_fused_tir`, but the DB lookup does not return a direct tuning
  record, IRModule, or schedule for it.
- The checked-in seed therefore comes from the post-db applied-module operator
  path via the existing seam, not from `query_schedule`.
- This lane is deliberately local-only and diagnostic-only.
- Do not run SSH or remote benchmark work from this runbook yet.
