# Handwritten `fused_mean4_subtract4_divide4_multiply4_add14_relu3` Local-First Runbook

Updated: `2026-04-03`

## Purpose

Establish and extend the handwritten lane for
`fused_mean4_subtract4_divide4_multiply4_add14_relu3` using the frozen
best-staging references, first locally and then through the dedicated
repo-pattern remote helper path when a socket-capable session is available.

## Fixed references

- best staging candidate SHA: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- task summary:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json`
- tuning DB:
  `./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs`
- current best-staging per-task log:
  `absent under ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs/logs/`
- historical local mean4 tuning log for context only:
  `./session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk3_20260313_131545/tuning_logs/logs/tvm.s_tir.meta_schedule.logging.task_02_fused_mean4_subtract4_divide4_multiply4_add14_relu3.log`

## Checked-in lane files

- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_reference_seed_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/post_db_scheduled_reference_seed_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v1_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2_working_copy_tir.py`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/scheduled_form_candidate_v2_working_copy_manifest.json`
- `./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py`

## Operator-specific scripts

- `./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py`
- `./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py`
- `./session_bootstrap/scripts/run_mean4_post_db_local_build.py`
- `./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py`
- `./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`

## Workflow

1. Refresh the checked-in post-db reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py \
  --allow-overwrite
```

2. Refresh the checked-in editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py \
  --allow-overwrite
```

3. Prove the local post-db swap path still builds:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build
```

4. Run the first real handwritten follow-up locally:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2
```

5. If the local candidate is mature enough, prepare the dedicated payload env:

```bash
./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py \
  --expected-sha256 <artifact_sha256>
```

6. Use the dedicated remote payload helper when the current session can open SSH sockets:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_profile.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

7. If you only need to validate upload integrity first, isolate that gate:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_profile.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

## Notes

- Current best-staging keeps `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
  at `rank=22` in `legalized_fused_tir`, but the DB lookup does not return a
  direct tuning record, IRModule, or schedule for it.
- The checked-in seed therefore comes from the post-db applied-module operator
  path via the existing seam, not from `query_schedule`.
- The checked-in `v1` files are still just the seed-clone baseline.
- The checked-in `v2` files are the first real handwritten mean4 candidate.
- The remote helper now uses byte-stable Python writes and verifies remote
  `sha256 + size_bytes` before entering the payload benchmark.
- Use `--upload-only` whenever the current blocker is upload integrity rather
  than runtime performance.
- In a socket-blocked sandbox, keep the remote step diagnostic-only and record
  the blocker instead of claiming a board result.
