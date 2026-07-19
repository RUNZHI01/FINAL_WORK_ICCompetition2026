# Transpose2 v4 Remote Benchmark

- generated_at: `2026-04-03T03:42:04+08:00`
- operator: `fused_conv2d_transpose2_add12`
- candidate: `v4 w0-local 10x34 data staging`
- status: `board proof completed; regression vs accepted v1`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256:
  `e8d66616b53064aa9af730dd8649dedbf399eb8afca5cbed8c1bf7a96a359a8f`
- remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `e8d66616b53064aa9af730dd8649dedbf399eb8afca5cbed8c1bf7a96a359a8f`
- local/remote sha match: `true`

## Payload Result

- load_ms: `3.774`
- vm_init_ms: `0.449`
- run_median_ms: `165.113`
- run_mean_ms: `165.640`
- run_min_ms: `164.679`
- run_max_ms: `167.949`
- run_variance_ms2: `1.089625`
- run_count: `10`

## Comparison

Reference points already recorded in this repo:

- accepted `transpose2 v1` remote median: `161.416 ms`
- frozen staging reference median: `159.943 ms`

This `v4` run compares as:

- vs accepted `v1`: `+3.697 ms` (`+2.29%` slower)
- vs frozen staging reference: `+5.170 ms` (`+3.23%` slower)

## Interpretation

This run cleanly answers the width-window staging question for this lane:

- the candidate is real (artifact-distinct, exact-vs-v1, board-run SHA verified)
- but narrowing the staged padded strip from the full `10 x 258` width to the
  current `w_0` `10 x 34` window regresses payload latency on board

So the apparent width-locality upside was not free; on this path the extra
staging frequency and/or lost cross-window reuse outweighed the smaller live
working set.

## Conclusion

- **keep** accepted `transpose2 v1` as the current best board-proven candidate for this lane
- classify `v4` as a real explored but regressing branch
- preserve `v4` as negative evidence against spending this width-window staging seam again without a materially different idea
- after this result, `transpose2` remains a live hotspot, but this exact locality family should be considered closed

## Commands

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/transpose2_v4_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap.so
```

Payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/transpose2_v4_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Logs

- payload log:
  `./session_bootstrap/logs/transpose2_v4_remote_payload_20260403_0343.log`
