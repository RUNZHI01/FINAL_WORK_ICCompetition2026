# Variance4 v18 Remote Benchmark

- generated_at: `2026-04-03T02:39:06+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v18 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_small_positive_move`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v18/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.796`
- vm_init_ms: `0.473`
- run_median_ms: `158.347`
- run_mean_ms: `158.428`
- run_min_ms: `158.120`
- run_max_ms: `159.172`
- run_variance_ms2: `0.082016`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v17` remote median: `158.478 ms`
- variance4 `v15` remote median: `158.549 ms`
- variance4 `v16` remote median: `159.774 ms`
- variance4 `v14` remote median: `159.655 ms`

This `v18` run compares as:

- vs frozen staging: `-1.596 ms` (`-1.00%`)
- vs variance4 `v17`: `-0.131 ms` (`-0.08%`)
- vs variance4 `v15`: `-0.202 ms` (`-0.13%`)
- vs variance4 `v16`: `-1.427 ms` (`-0.89%`)
- vs variance4 `v14`: `-1.308 ms` (`-0.82%`)

## Interpretation

This run confirms two useful things:

1. The first `v18` draft that collapsed to the same artifact as `v17` was
   correctly rejected as a false-new candidate.
2. The corrected `v18` follow-up — keeping `v17`'s normalized-mean handoff and
   additionally materializing the centered value once into `T_subtract_local`
   before squaring — does produce a genuinely distinct artifact and a small
   board-side improvement.

The absolute gain is still tiny, so it should be described as a **very small
but real** positive move. One nice side effect is that the sample variance is
also lower than the recent nearby runs.

## Conclusion

- **keep** `variance4 v18` as the new current best checked-in board-proven candidate for the variance4 lane
- preserve the rejected artifact-identical first `v18` draft as negative methodology evidence
- if the lane continues, keep following reuse/handoff-style micro-moves rather than scope stacking

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v18_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v18/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v18_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v18_remote_payload_20260403_0239_payload.log`
