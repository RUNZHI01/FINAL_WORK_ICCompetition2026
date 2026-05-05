# Variance4 v15 Remote Benchmark

- generated_at: `2026-04-03T01:15:23+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v15 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_small_positive_move`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.856`
- vm_init_ms: `0.473`
- run_median_ms: `158.549`
- run_mean_ms: `158.881`
- run_min_ms: `158.342`
- run_max_ms: `161.363`
- run_variance_ms2: `0.740381`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v13` remote median: `161.156 ms`
- variance4 `v14` remote median: `159.655 ms`
- accepted transpose1 `P2+P4` median: `159.356 ms`
- accepted transpose_add6 `v1` median: `159.503 ms`

This `v15` run compares as:

- vs frozen staging: `-1.394 ms` (`-0.87%`)
- vs variance4 `v13`: `-2.607 ms` (`-1.62%`)
- vs variance4 `v14`: `-1.106 ms` (`-0.69%`)
- vs accepted transpose1 `P2+P4`: `-0.807 ms` (`-0.51%`)
- vs accepted transpose_add6 `v1`: `-0.954 ms` (`-0.60%`)

## Interpretation

This is stronger than the `v14` result in two ways:

- `v15` stays exact-preserving locally while producing yet another distinct full-module artifact
- the board-side median moved further in the right direction and now edges past the previously accepted transpose handwritten medians that were near this band

The gain is still modest in absolute terms, so this should be described as a
small but real board-side improvement, not as a dramatic breakthrough.

## Conclusion

- **keep** `variance4 v15` as the new current best checked-in handwritten candidate for the variance4 lane
- relative to current nearby handwritten references in this repo, `v15` is now the strongest result in this latency band among the compared variance4 / transpose handwritten candidates cited above
- preserve `v14` as the immediate predecessor and evidence of the intermediate positive step
- if this lane continues, build on the `v15` storage-placement direction rather than reverting to artifact-identical cleanup work

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v15_remote_payload_20260403_0116_payload.log`
