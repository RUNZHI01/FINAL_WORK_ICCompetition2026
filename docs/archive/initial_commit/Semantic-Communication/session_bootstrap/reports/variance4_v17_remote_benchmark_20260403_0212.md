# Variance4 v17 Remote Benchmark

- generated_at: `2026-04-03T02:11:13+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v17 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_small_positive_move`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.767`
- vm_init_ms: `0.458`
- run_median_ms: `158.478`
- run_mean_ms: `158.804`
- run_min_ms: `158.196`
- run_max_ms: `160.580`
- run_variance_ms2: `0.513597`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v17` local predecessor baseline: `v15 = 158.549 ms`
- variance4 `v16` remote median: `159.774 ms`
- variance4 `v14` remote median: `159.655 ms`
- variance4 `v13` remote median: `161.156 ms`

This `v17` run compares as:

- vs frozen staging: `-1.465 ms` (`-0.92%`)
- vs variance4 `v15`: `-0.071 ms` (`-0.04%`)
- vs variance4 `v16`: `-1.296 ms` (`-0.81%`)
- vs variance4 `v14`: `-1.177 ms` (`-0.74%`)
- vs variance4 `v13`: `-2.678 ms` (`-1.66%`)

## Interpretation

This run is valuable because it tests a different narrow dimension than `v16`:

- instead of stacking another explicit local-scope placement,
- `v17` materializes the normalized mean once into a tiny handoff buffer and
  reuses that value inside the hot `T_multiply_local` loop.

That change preserves exactness and produces a distinct artifact, and this time
it does move the board-side median in the right direction relative to `v15`.

The gain over `v15` is very small, so it should be described as a **tiny but
real** positive move, not as a major breakthrough.

## Conclusion

- **keep** `variance4 v17` as the new current best checked-in board-proven candidate for the variance4 lane
- treat `v16` as useful negative evidence against blind local-scope stacking
- if the lane continues, prefer similarly narrow reuse/handoff ideas over more scope-only edits

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v17_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v17_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v17_remote_payload_20260403_0212_payload.log`
