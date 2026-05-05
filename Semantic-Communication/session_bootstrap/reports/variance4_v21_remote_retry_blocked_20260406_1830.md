# Variance4 v21 Remote Retry Blocked

- generated_at: `2026-04-06T18:30:00+08:00`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v21 exact-preserving post-db swapped full-module payload retry`
- status: `remote_connect_timeout_persists`

## Local Maturity Revalidated

Before retrying the board path in this session:

- focused `v21` wrapper/working-copy tests: `4/4 OK`
- local correctness JSON still reports:
  `exact_equal = true`, `max_abs_diff = 0.0`, `nonzero_diff_count = 0`
- local artifact still exists:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v21/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local artifact SHA256:
  `a60e0f5a40985d220e55c3ad541998767769d29725af377d339682927020e279`
- local artifact size bytes: `1674688`

## Commands Retried

Using the existing variance4 remote env base:

```bash
source ./session_bootstrap/tmp/variance4_v19_remote_benchmark_20260403.env
```

Retried first-hop staging directory create through the repository SSH helper:

```bash
timeout 30s env SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1 \
  bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- \
  "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
```

Retried direct TCP probe to the board SSH port:

```bash
timeout 10s bash -lc 'cat < /dev/null > /dev/tcp/100.121.87.73/22'
```

## Observed Result

- helper retry: `exit code 124`
- direct TCP probe to `100.121.87.73:22`: `exit code 124`

No remote stdout/stderr, remote SHA, or payload JSON was produced in this
session.

## Interpretation

This retry reconfirms the same boundary already seen in the earlier blocked
report:

- `variance4 v21` itself is not blocked by local correctness or buildability
- the blocker is still the network path from the current exec environment to
  the board's SSH endpoint
- because the failure occurs before upload, this retry produces **no new board
  performance evidence**

## Conclusion

- keep `variance4 v18` as the current best checked-in **board-proven** result
  for this lane with remote median `158.347 ms`
- keep `variance4 v21` as the next exact-preserving, schedule-swappable,
  artifact-distinct local candidate
- when a network-capable session is available, resume from the existing helper
  path: create the remote archive, upload the `v21` artifact, validate remote
  SHA, then run
  `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`
