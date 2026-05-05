# Variance4 v15 Remote Benchmark Attempt Blocked

- generated_at: `2026-04-03T01:05:11+0800`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v15 exact-preserving post-db swapped full-module payload validation`
- status: `blocked_by_exec_sandbox_socket_before_remote_upload`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
- intended remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`

## Commands Attempted

Artifact staging:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v14_remote_benchmark_20260403.env
set +a
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs"
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so" < ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v15/fused_variance4_add13_tir_sqrt4_post_db_swap.so
bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "sha256sum /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so | awk '{print \$1}'"
```

Planned payload benchmark path:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v14_remote_benchmark_20260403.env
set +a
export INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4
export REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4
export INFERENCE_CURRENT_EXPECTED_SHA256=9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Failure

The existing repo SSH helper failed before the artifact could be uploaded:

```text
Control socket connect(/tmp/ssh_mux/8299aa164475924595f533969ee578ceac910254): Operation not permitted
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

The same sandbox socket error repeated for the follow-up upload and SHA-check
commands, so this session produced:

- no remote artifact upload
- no remote SHA confirmation
- no payload benchmark JSON

## Interpretation

This is an execution-environment boundary, not a new candidate regression:

- `v15` had already passed focused local tests
- `v15` had already passed exact local correctness against the frozen scheduled
  reference
- `v15` had already passed post-db swap/build/export and produced a distinct
  artifact

But because the current exec sandbox cannot open the SSH socket to
`100.121.87.73:22`, there is still **no board-side result** for `v15` in this
session.

## Conclusion

- keep `variance4 v14` as the current best checked-in **board-proven** candidate
- treat `variance4 v15` as the next board-worthy local follow-up
- in a remote-capable session, rerun the exact same helper path with the `v15`
  artifact SHA `9f85c6c532f451cb89751bab44eab8725a2b19087c4fc6a604acd3cb88651ac7`
