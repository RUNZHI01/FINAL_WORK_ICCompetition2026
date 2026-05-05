# Variance4 v16 Remote Benchmark

- generated_at: `2026-04-03T01:42:59+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v16 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_but_regressed_vs_v15`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v16/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `07400ce1a89a5eb312dc5cf8ded067ea72373ab5f445abdc8208f70e2be860cd`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.927`
- vm_init_ms: `0.462`
- run_median_ms: `159.774`
- run_mean_ms: `160.289`
- run_min_ms: `159.535`
- run_max_ms: `163.974`
- run_variance_ms2: `1.638535`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v15` remote median: `158.549 ms`
- variance4 `v14` remote median: `159.655 ms`
- variance4 `v13` remote median: `161.156 ms`

This `v16` run compares as:

- vs frozen staging: `-0.169 ms` (`-0.11%`)
- vs variance4 `v15`: `+1.225 ms` (`+0.77%` slower)
- vs variance4 `v14`: `+0.119 ms` (`+0.07%` slower)
- vs variance4 `v13`: `-1.382 ms` (`-0.86%`)

## Interpretation

This run answers the exact question posed by the `v16` follow-up:

- making `T_multiply_red` explicitly `scope="local"` on top of the already
  local-scoped `lv335_red` / `T_multiply_local` chain does produce a new
  artifact and remains exact-preserving
- but the resulting board-side payload median moves in the wrong direction
  relative to the current best `v15`

So this is a useful negative result, not a wasted run.

## Conclusion

- **keep** `variance4 v15` as the current best checked-in board-proven candidate for this lane
- classify `v16` as a regressing follow-up relative to `v15`
- keep the `v16` evidence as a real explored branch, but do not promote it as the new baseline
- if the lane continues, do not stack more local-scope placements blindly; the next useful move should change a different aspect of the storage / reduction chain

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v16_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v16/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v16_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v16_remote_payload_20260403_0134_payload.log`
