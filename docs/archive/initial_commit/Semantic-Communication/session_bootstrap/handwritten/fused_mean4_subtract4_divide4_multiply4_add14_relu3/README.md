# Checked-in scheduled-form lane: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

This directory is the smallest repo-native handwritten lane for
`fused_mean4_subtract4_divide4_multiply4_add14_relu3` that keeps the
best-staging MetaSchedule context intact locally.

It intentionally starts at the post-db scheduled reference seed and does not
introduce a separate raw pre-compile hook lane yet.

## Files

- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_reference_seed_tir.py`: checked-in post-db scheduled reference seed recovered from the frozen best-staging DB.
- `post_db_scheduled_reference_seed_manifest.json`: small manifest for that scheduled reference seed.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1_working_copy_tir.py`: editable scheduled-form working copy cloned from the checked-in reference seed.
- `scheduled_form_candidate_v1_working_copy_manifest.json`: small manifest for the editable working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v1.py`: local-only candidate wrapper that points the existing post-db seam at the working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2_working_copy_tir.py`: first real handwritten follow-up on top of the checked-in v1 seed clone.
- `scheduled_form_candidate_v2_working_copy_manifest.json`: manifest for the v2 scalar-epilogue-handoff working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py`: local post-db wrapper for the v2 working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v3_working_copy_tir.py`: operator-specific ablation after v2 board regression; keep v1 structure and change only the tiny mean handoff buffer placement (`scope="local"`).
- `scheduled_form_candidate_v3_working_copy_manifest.json`: manifest for the v3 local-mean-handoff-only ablation working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v3.py`: local post-db wrapper for the v3 working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy_tir.py`: current operator-specific branch; keep the reduction, hoist mean/std/weight/bias once per channel into local buffers, and fuse the subtract/divide/multiply/add/relu epilogue into one hot pass.
- `scheduled_form_candidate_v4_working_copy_manifest.json`: manifest for the v4 channel-param-hoist fused-epilogue working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py`: local post-db wrapper for the v4 working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py`: beyond-v4 follow-up; keep the one-pass fused epilogue, but collapse the per-channel epilogue parameters into an affine pair `scale = weight / std` and `shift = bias - mean * scale`.
- `scheduled_form_candidate_v5_working_copy_manifest.json`: manifest for the v5 channel-affine-precompute working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py`: local post-db wrapper for the v5 working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py`: structural follow-up on top of `v5`; keep the affine epilogue math unchanged, but reorder the channel phases into `reduce channel c -> affine precompute c -> epilogue c`.
- `scheduled_form_candidate_v6_working_copy_manifest.json`: manifest for the v6 channelwise phase-ordering working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py`: local post-db wrapper for the v6 working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy_tir.py`: reduction-side follow-up on top of `v5`; keep the affine epilogue unchanged, but replace the scalar reduction chain with a four-lane partial-sum vectorized reduction.
- `scheduled_form_candidate_v7_working_copy_manifest.json`: manifest for the v7 partial-sum reduction working copy.
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py`: local post-db wrapper for the v7 working copy.

## Refresh / Build

Refresh the checked-in scheduled reference seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py \
  --allow-overwrite
```

Refresh the editable working copy from that seed:

```bash
python3 ./session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py \
  --allow-overwrite
```

Run the local-only post-db scheduled swap build:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build
```

Run the first real handwritten v2 follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v2.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2
```

Run the v3 local ablation follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v3.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v3
```

Run the current v4 fused-epilogue follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4
```

Run the current v5 affine-precompute follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v5
```

Run the current v6 channelwise phase-ordering follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v6
```

Run the current v7 partial-sum reduction follow-up:

```bash
python3 ./session_bootstrap/scripts/run_mean4_post_db_local_build.py \
  --candidate-impl ./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7.py \
  --output-dir ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v7
```

Build a handwritten-line artifact with the real handwritten preset plus a
temporary mean4 `v5` override:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5
```

Build the same handwritten-line preset with the temporary mean4 `v6` override:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v6_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6
```

Build the same handwritten-line preset with the temporary mean4 `v7` override:

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/integrate_opus_candidates.py \
  --preset opus_final_v3_mean4 \
  --candidate-override fused_mean4_subtract4_divide4_multiply4_add14_relu3=./session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v7_working_copy_tir.py \
  --output-dir ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7
```

Prepare a dedicated handwritten env for a board payload attempt:

```bash
./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py \
  --expected-sha256 <artifact_sha256>
```

Run the dedicated board payload helper:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_profile.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

If the immediate blocker is upload integrity rather than the benchmark itself,
run the helper in upload-only mode first:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_profile.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

Current best-staging keeps `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
in the task summary, but does not expose a direct `query_schedule` /
`query_ir_module` hit for it. This lane therefore starts from the post-db
applied-module operator form recovered through the same seam.

Important scope note:

- the checked-in `v1` lane remains only a seed-clone edit surface
- `v2` is the first real mean4 handwritten edit and the first one worth a
  board payload attempt
- `v3` is a smallest operator-specific ablation to isolate whether v2's
  regression came from scalar epilogue fusion vs tiny mean-handoff placement
- `v4` is the first operator-specific branch that matches the board-side
  hardware constraint directly: hoist per-channel parameters once and remove
  four extra full-frame epilogue intermediates
- `v5` is the first branch beyond the baked-in `v4` baseline: keep the same
  fused pass, but precompute the channel-wise affine pair so the hot loop only
  needs `x * scale + shift + relu`
- `v6` is the first structural follow-up beyond `v5`: keep the same affine
  epilogue, but reorder the per-channel phases so each channel is reduced and
  consumed before moving to the next one
- `v7` is the first reduction-side follow-up after the `v5/v6` codegen
  inspection: keep the `v5` two-phase structure and affine epilogue, but
  replace the scalar reduction chain with a four-lane partial-sum vectorized
  reduction
- the remote payload helper now verifies remote `sha256 + size_bytes` before
  it runs the benchmark, and `--upload-only` isolates that gate
- board claims still require a successful remote upload, SHA match, and payload
  benchmark result; helper availability alone is not a performance claim
- current mean4 lane state:
  - `v2` is closed as board-tested negative evidence
  - `v4` is the baked-in baseline for the repo's current handwritten final
    route, and reproduces handwritten final artifact
    `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
  - when integrated through the repo's actual handwritten final preset
    (`variance3 + mean4`), the current `v4` working copy reproduces the
    existing handwritten final artifact exactly:
    `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
  - `v5` is the current beyond-`v4` handwritten-line candidate:
    local operator artifact
    `02224b16b398cbe62d0c7c419051a5833c982072445639330486524cce082b1d`
    and integrated handwritten-line artifact
    `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
  - same-day 3-core handwritten-line payload rerun is positive against the
    current handwritten final at both `repeat=10`
    (`240.129 ms` vs `242.083 ms`) and `repeat=30`
    (`240.775 ms` vs `241.405 ms`), with a `repeat=30` candidate reprobe still
    faster on median (`240.410 ms` vs `241.405 ms`)
  - `v6` is a distinct handwritten-line artifact
    `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`,
    but same-day serial A/B ended at near parity:
    `repeat=10` slower (`241.086 ms` vs `240.658 ms`),
    first `repeat=30` slower (`240.261 ms` vs `240.097 ms`),
    reprobe `repeat=30` slightly faster (`239.504 ms` vs `239.682 ms`),
    and paired long-sample average only `-0.007 ms`
  - `v7` is the current strongest handwritten-line candidate:
    local operator artifact
    `98df71cc08e5f93c0f8dbc8e709694660acbd8e3b0afbc517adf31d7d5194a2b`
    and integrated handwritten-line artifact
    `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`
  - `v7` local correctness remains inside the accepted tolerance envelope:
    `allclose(1e-6)=true`, `max_abs_diff=1.430511474609375e-06`
  - `v7` codegen now confirms vectorized reduction
    (`fadd v0.4s` + `faddp`) while keeping the existing vectorized epilogue
    (`dup + fmla + fmaxnm`)
  - valid same-day handwritten-line payload A/B is positive at both sample
    lengths:
    `repeat=10` `238.684 ms` vs `245.999 ms`,
    `repeat=30` `238.602 ms` vs `243.460 ms`,
    and candidate reprobe `239.801 ms` vs the same-day control `243.460 ms`
  - supplemental same-day `v5` rerun landed at `242.734 ms`, slower than both
    valid `v7` long-sample medians (`238.602 / 239.801 ms`)
  - direct same-day three-line payload compare is now also positive:
    `v7` first `repeat=30` `240.059 ms`, trusted current `244.617 ms`,
    ACL line `248.156 ms`, and `v7` reprobe `239.052 ms`
  - handwritten-line big.LITTLE follow-up is now also complete:
    serial reconstruction median `345.609 ms/image`,
    pipeline total-wall endpoint `249.393 ms/image`,
    pipeline run median `240.885 ms`,
    throughput uplift `38.706%`
  - compared with the old handwritten final big.LITTLE compare
    (`342.927 -> 252.584 ms/image`, uplift `35.489%`),
    `v7` slightly gives back serial reconstruction but improves the actual
    pipeline endpoint by `-3.191 ms/image` and raises uplift by `+3.217`
    percentage points
  - compared with the documented trusted-current big.LITTLE compare
    (`360.218 -> 251.913 ms/image`, uplift `44.102%`),
    `v7` still trails on uplift ratio but now undercuts the trusted-current
    absolute pipeline endpoint by `-2.520 ms/image`
  - same-day three-line OpenAMP 3-core big.LITTLE compare is now complete:
    `v7` handwritten line
    `345.609 -> 249.393 ms/image`, uplift `38.706%`;
    trusted current
    `347.341 -> 257.388 ms/image`, uplift `34.569%`;
    ACL line
    `352.158 -> 262.922 ms/image`, uplift `33.814%`
  - on this same-day three-line compare, `v7` is best on all three relevant
    metrics: serial reconstruction, pipeline endpoint, and uplift ratio
  - current checked-in baseline still points at the baked-in `v4` route
  - `v7` is now the strongest next handwritten-line promotion candidate and
    currently appears to supersede `v5`
  - `v6` should be kept as board-tested structural evidence, but not promoted
