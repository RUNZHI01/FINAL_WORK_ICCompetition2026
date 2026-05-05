# Variance4 v19 Remote Benchmark

- generated_at: `2026-04-03T03:07:03+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v19 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_but_regressed_vs_v18`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v19/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `a6e38b879d01993b98e6cc50b43bc772e3d7b2fbdf52f9fcc830365111e7646a`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `a6e38b879d01993b98e6cc50b43bc772e3d7b2fbdf52f9fcc830365111e7646a`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.789`
- vm_init_ms: `0.468`
- run_median_ms: `158.556`
- run_mean_ms: `158.433`
- run_min_ms: `157.616`
- run_max_ms: `159.337`
- run_variance_ms2: `0.233997`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v18` remote median: `158.347 ms`
- variance4 `v17` remote median: `158.478 ms`
- variance4 `v15` remote median: `158.549 ms`

This `v19` run compares as:

- vs frozen staging: `-1.387 ms` (`-0.87%`)
- vs variance4 `v18`: `+0.209 ms` (`+0.13%` slower)
- vs variance4 `v17`: `+0.078 ms` (`+0.05%` slower)
- vs variance4 `v15`: `+0.007 ms` (`+0.00%` slower, effectively flat)

## Interpretation

This run answers the exact question posed by `v19`:

- keeping the centered-value handoff from `v18` while tightening the
  normalized-mean handoff down to a one-element scalar does produce a genuinely
  new artifact and remains exact-preserving
- but that scalarized mean-handoff shape does not improve over the current best
  `v18` board result

So the right conclusion is not that the idea was pointless, but that the more
compact scalar mean handoff is not the winning form on this path.

## Conclusion

- **keep** `variance4 v18` as the current best checked-in board-proven candidate for this lane
- classify `v19` as a real explored branch that regresses slightly relative to `v18`
- preserve `v19` as negative evidence against over-tightening the mean handoff to a scalar
- if the lane continues, keep following reuse/handoff ideas, but do not assume that smaller/scalar handoffs are automatically better

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v19/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v19_remote_payload_20260403_0307_payload.log`
