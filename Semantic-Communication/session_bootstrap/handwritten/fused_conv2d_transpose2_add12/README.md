# Checked-in scheduled-form lane: `fused_conv2d_transpose2_add12`

This directory is the smallest repo-native handwritten lane for
`fused_conv2d_transpose2_add12` that keeps the best-staging MetaSchedule
context intact locally.

It intentionally starts at the post-db scheduled reference seed and does not
introduce a separate raw pre-compile hook lane yet.

## Files

- `fused_conv2d_transpose2_add12_post_db_scheduled_reference_seed_tir.py`: checked-in post-db scheduled reference seed recovered from the frozen best-staging DB.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for that scheduled reference seed.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py`: accepted scheduled-form v1 working copy cloned from the checked-in reference seed and carrying the bias-fusion edit.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: small manifest for the accepted v1 working copy.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v1.py`: local-only candidate wrapper that points the existing post-db seam at the accepted v1 working copy.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v2_working_copy_tir.py`: isolated scheduled-form v2 working copy that tries a P1-style `data_dilate + data_pad -> data_dilate_pad` fusion on top of the accepted v1 state.
- `scheduled_form_candidate_v2_working_copy_manifest.json`: small manifest for the v2 working copy.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py`: local-only candidate wrapper for the checked-in v2 working copy.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v3_working_copy_tir.py`: isolated scheduled-form v3 working copy that repacks `kernel_transform` into an input-major, output-channel-inner layout.
- `scheduled_form_candidate_v3_working_copy_manifest.json`: small manifest for the checked-in v3 kernel-pack branch.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py`: local-only candidate wrapper for the checked-in v3 branch.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v4_working_copy_tir.py`: isolated scheduled-form v4 working copy for the first width-window data-staging locality branch.
- `scheduled_form_candidate_v4_working_copy_manifest.json`: small manifest for the v4 width-window branch.
- `fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py`: local-only candidate wrapper for the checked-in v4 branch.

## Refresh / Build

Refresh the checked-in scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py \
  --allow-overwrite
```

Refresh the editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py \
  --allow-overwrite
```

Run the local-only post-db scheduled swap build:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build
```

To build the isolated v2 candidate instead of the accepted v1 baseline:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v2
```

To build the isolated v3 scaffold instead of the accepted v1 baseline:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v3
```

To build the isolated v4 width-window-staging candidate instead of the accepted v1 baseline:

```bash
python3 ./session_bootstrap/scripts/run_transpose2_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_conv2d_transpose2_add12/fused_conv2d_transpose2_add12_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4
```

Current repo state:

- accepted remote baseline: `v1 bias fusion`, report `./session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`, median `161.416 ms`
- dropped follow-up experiments: `P2`, `P4`, `v2` P1-style `data_dilate + data_pad` fusion, and `v3` kernel_transform pack
- current next local surface: isolated `v4` width-window data-staging branch
- target-selection rationale: `./session_bootstrap/reports/project_speedup_rerank_after_variance4_freeze_20260403.md`

This lane is still local-only and diagnostic-only inside the repo. Use the
accepted `v1` artifact as the baseline when manually benchmarking any future
real `v3` candidate on the board.
