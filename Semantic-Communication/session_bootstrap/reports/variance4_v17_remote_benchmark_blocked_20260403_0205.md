# Variance4 v17 Remote Benchmark Blocked

- generated_at: `2026-04-03T02:05:32+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v17 exact-preserving post-db swapped full-module payload validation`
- status: `remote_helper_path_blocked_by_exec_sandbox`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v17/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`
- intended remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4`
- intended remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- base env snapshot:
  `./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env`
- runtime overrides:
  `INFERENCE_CURRENT_EXPECTED_SHA256=5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab`,
  `INFERENCE_EXECUTION_ID=variance4_v17_remote_payload_20260403_0208`

## Local Maturity Gate

- focused variance4 tests: `78/78 OK`
- scheduled-reference correctness:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- artifact distinctness:
  `v15 = 9f85c6c5...1ac7 / 1674560 bytes`,
  `v16 = 07400ce1...60cd / 1674632 bytes`,
  `v17 = 5d22553f...54ab / 1674664 bytes`

## Commands Attempted

Standard helper path:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env
set +a
export INFERENCE_CURRENT_EXPECTED_SHA256=5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab
export INFERENCE_EXECUTION_ID=variance4_v17_remote_payload_20260403_0208
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
```

Observed stderr:

```text
Control socket connect(/tmp/ssh_mux/8299aa164475924595f533969ee578ceac910254): Operation not permitted
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

Controlled retry with helper mux disabled:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env
set +a
export INFERENCE_CURRENT_EXPECTED_SHA256=5d22553f3b7a9a9f8793f3a434ad758d1120456db7f39b079596a196588754ab
export INFERENCE_EXECUTION_ID=variance4_v17_remote_payload_20260403_0208
SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1 \
  bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
```

Observed stderr:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

## Interpretation

This blocker is in the current exec sandbox network/socket boundary, not in the
`variance4` v17 lane itself:

- the attempt used the existing repository helper path only
- the failure occurred before remote upload began
- no remote artifact SHA or payload samples were produced in this environment

## Conclusion

- keep `variance4 v15` as the current best checked-in **board-proven** result
  for this lane with median `158.549 ms`
- keep `variance4 v16` as real negative evidence that blindly stacking more
  explicit local-scope placements on top of `v15` is not a safe direction
- keep `variance4 v17` as the next exact-preserving, schedule-swappable,
  artifact-distinct local follow-up because it changes a different narrow
  dimension: per-channel mean reuse / handoff
- the next executable board step outside this sandbox is to reuse
  `./session_bootstrap/tmp/variance4_v15_remote_benchmark_20260403.env`,
  override the expected SHA / execution id for `v17`, upload the `v17`
  artifact through `ssh_with_password.sh`, verify the remote SHA, and then run
  `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`
