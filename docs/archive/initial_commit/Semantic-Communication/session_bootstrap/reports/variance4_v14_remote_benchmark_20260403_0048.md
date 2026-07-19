# Variance4 v14 Remote Benchmark

- generated_at: `2026-04-03T00:47:40+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v14 exact-preserving post-db swapped full-module payload validation`
- status: `remote_path_validated_small_positive_move`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `59358735fe2c6653aa554bea60f53c35ab77d37e179c9e4ebb153d019be96a55`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.694`
- vm_init_ms: `0.446`
- run_median_ms: `159.655`
- run_mean_ms: `160.144`
- run_min_ms: `158.861`
- run_max_ms: `163.629`
- run_variance_ms2: `1.808987`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- frozen staging median: `159.943 ms`
- variance4 `v13` remote median: `161.156 ms`
- accepted transpose1 `P2+P4` median: `159.356 ms`
- accepted transpose_add6 `v1` median: `159.503 ms`

This `v14` run compares as:

- vs frozen staging: `-0.288 ms` (`-0.18%`)
- vs variance4 `v13`: `-1.501 ms` (`-0.93%`)
- vs accepted transpose1 `P2+P4`: `+0.299 ms` (`+0.19%` slower)
- vs accepted transpose_add6 `v1`: `+0.152 ms` (`+0.10%` slower)

## Interpretation

This is the first variance4 candidate in the checked-in lane that simultaneously
achieves all of the following:

- exact-preserving local correctness against the frozen scheduled reference
- successful local post-db swap/build/export
- exported artifact distinct from `v13`
- successful board-side payload validation through the existing handwritten staging path
- a small **positive** board-side median move relative to both frozen staging and `variance4 v13`

The gain is small, so it should not be oversold. But unlike `v13`, this is no
longer just a path-validation run:

- the artifact is different
- the board really ran the intended SHA
- the measured median moved in the right direction

## Conclusion

- **keep** `variance4 v14` as the current best checked-in handwritten candidate for this lane
- classify the result as a **small but real board-side positive move**, not a major breakthrough
- do not yet promote it as a headline optimization over the stronger transpose lanes
- if variance4 work continues, the next step should build on this new artifact-distinct equivalence class rather than returning to `v13`-style artifact-identical syntax cleanup

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v14_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v14/fused_variance4_add13_tir_sqrt4_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v14_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/variance4_v14_remote_payload_20260403_0048_payload.log`
