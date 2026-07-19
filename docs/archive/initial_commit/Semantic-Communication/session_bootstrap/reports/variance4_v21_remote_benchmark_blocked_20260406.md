# Variance4 v21 Remote Benchmark Blocked

- generated_at: `2026-04-06T02:16:00+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v21 exact-preserving post-db swapped full-module payload validation`
- status: `remote_connect_timeout_in_current_exec_env`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v21/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- intended remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4`
- intended remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- env base:
  `./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env`

## Local Maturity Gate

- focused `v21` wrapper/working-copy tests: `4/4 OK`
- scheduled-reference correctness:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- post-db scheduled swap/build/export:
  `swap_succeeded = true`,
  `structural_equal_post_swap_vs_candidate = true`,
  `build_status = built`,
  `export_status = exported`
- artifact distinctness:
  `v18 = 72f5a2cf...850e / 1674624 bytes`,
  `v19 = a6e38b87...646a / 1674616 bytes`,
  `v21 = a60e0f5a...e279 / 1674688 bytes`

## Commands Attempted

Repository helper path, first-hop staging directory create:

```bash
source ./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- \
  "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
```

In this exec environment the helper produced no remote stdout/stderr and did
not complete within the observation window.

Controlled retry with helper mux disabled and explicit timeout:

```bash
source ./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env
timeout 20s env SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1 \
  bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- \
  "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
```

Observed result:

```text
exit code 124 (timeout)
```

Direct connectivity probes:

```bash
timeout 10s ssh -o BatchMode=yes -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null user@100.121.87.73 true
timeout 10s bash -lc 'cat < /dev/null > /dev/tcp/100.121.87.73/22'
```

Observed result:

```text
both probes exited 124 (timeout)
```

## Interpretation

This blocker is in the current exec environment's network path to the board,
not in the `variance4 v21` lane itself:

- the candidate is exact-preserving and fully buildable locally
- the failure occurs before upload or remote SHA validation
- both helper-based SSH and direct TCP probes time out on `100.121.87.73:22`
- no remote artifact SHA or payload samples were produced in this environment

## Conclusion

- keep `variance4 v18` as the current best checked-in **board-proven** result
  for this lane with median `158.347 ms`
- keep `variance4 v21` as the next exact-preserving, schedule-swappable,
  artifact-distinct local candidate
- the next executable board step in a network-capable session is to reuse the
  existing variance4 staging archive, upload the `v21` artifact through
  `ssh_with_password.sh`, validate remote SHA, and then run
  `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`
