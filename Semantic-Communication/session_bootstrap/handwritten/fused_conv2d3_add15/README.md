# Checked-in scheduled-form lane: `fused_conv2d3_add15`

This directory is the smallest repo-native handwritten lane for
`fused_conv2d3_add15` that keeps the frozen best-staging MetaSchedule context
intact locally.

It intentionally starts at the post-db scheduled reference seed and does not
introduce a separate raw pre-compile hook lane.

## Files

- `fused_conv2d3_add15_post_db_scheduled_reference_seed_tir.py`: checked-in post-db scheduled reference seed recovered from the frozen best-staging DB.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for that scheduled reference seed.
- `fused_conv2d3_add15_scheduled_form_candidate_v1_working_copy_tir.py`: accepted scheduled-form v1 bias-fused working copy.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: manifest for the accepted v1 working copy.
- `fused_conv2d3_add15_scheduled_form_candidate_v1.py`: local-only wrapper for the accepted v1 working copy.
- `fused_conv2d3_add15_scheduled_form_candidate_v2_working_copy_tir.py`: isolated v2 working copy on top of the accepted v1 baseline.
- `scheduled_form_candidate_v2_working_copy_manifest.json`: manifest for the isolated v2 working copy.
- `fused_conv2d3_add15_scheduled_form_candidate_v2.py`: local-only wrapper for the v2 working copy.

## Refresh / Build

Refresh the checked-in scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d3_add15_post_db_scheduled_seed.py \
  --allow-overwrite
```

Refresh the editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d3_add15_scheduled_form_working_copy.py \
  --allow-overwrite
```

Run the local-only post-db scheduled swap build:

```bash
python3 ./session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build
```

Run the isolated v2 local build without mutating the accepted v1 path:

```bash
python3 ./session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d3_add15/fused_conv2d3_add15_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_v2
```

This lane is local-only and diagnostic-only. Do not use it for SSH or remote
benchmark claims until a real `fused_conv2d3_add15` handwritten edit exists.
