# Checked-in scheduled-form lane: `fused_conv2d_transpose_add6`

This directory is the smallest repo-native handwritten lane for
`fused_conv2d_transpose_add6` that keeps the frozen best-staging MetaSchedule
context intact locally.

It intentionally starts at the post-db scheduled reference seed and does not
introduce a separate raw pre-compile hook lane.

## Files

- `fused_conv2d_transpose_add6_post_db_scheduled_reference_seed_tir.py`: checked-in post-db scheduled reference seed recovered from the frozen best-staging DB.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for that scheduled reference seed.
- `fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py`: editable scheduled-form working copy cloned from the checked-in reference seed.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: small manifest for the editable working copy.
- `fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py`: local-only candidate wrapper that points the existing post-db seam at the working copy.
- `fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py`: isolated v2 working copy carrying the first transpose1-style locality edit on top of the accepted v1 state.
- `scheduled_form_candidate_v2_working_copy_manifest.json`: manifest for the v2 locality edit.
- `fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py`: local-only candidate wrapper for the v2 locality edit.

## Refresh / Build

Refresh the checked-in scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_post_db_scheduled_seed.py \
  --allow-overwrite
```

Refresh the editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_scheduled_form_working_copy.py \
  --allow-overwrite
```

Run the local-only post-db scheduled swap build:

```bash
python3 ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build
```

Run the local-only post-db scheduled swap build for the isolated v2 locality
edit:

```bash
python3 ./session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_v2_locality_seed
```

Current checked-in v2 move:

- keep the accepted v1 bias-fused compute path intact
- keep `data_dilate` and `kernel_transform` materialized
- stage the tile-local `data_pad` patch one `dc_0` slice (`16` channels) at a
  time and reuse that staged slice across all three `c_1` groups before
  staging the next slice

This lane is still local-only and diagnostic-only. Do not use it for SSH or
remote benchmark claims until the edited v2 path is board-validated.
