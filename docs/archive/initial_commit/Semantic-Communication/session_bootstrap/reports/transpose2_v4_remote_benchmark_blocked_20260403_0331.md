# Transpose2 v4 Remote Benchmark Blocked

- generated_at: `2026-04-03T03:31:26+08:00`
- operator: `fused_conv2d_transpose2_add12`
- candidate: `v4 w0-local 10x34 data staging`
- status: `board attempt blocked by current exec sandbox`

## Intended Board Path

This turn intentionally reused the existing repo pattern already used by the
other handwritten lanes:

- source the prior safe-runtime payload env
- stage the exported `.so` through `session_bootstrap/scripts/ssh_with_password.sh`
- run `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`

Target artifact for this attempt:

- local artifact:
  `./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap.so`
- local sha256:
  `e8d66616b53064aa9af730dd8649dedbf399eb8afca5cbed8c1bf7a96a359a8f`
- intended remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4`

## Blocking Failure

The first remote staging command failed before upload completed.

Observed stderr:

```text
Control socket connect(/tmp/ssh_mux/8299aa164475924595f533969ee578ceac910254): Operation not permitted
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

Interpretation:

- this is not evidence that `transpose2 v4` itself is bad
- it is not a candidate-side correctness or build failure
- it is the same class of child-sandbox socket restriction already seen
  elsewhere in this repo

## Decision

- keep `transpose2 v4` as a board-worthy local candidate
- make no performance claim from this blocked attempt
- if a network-capable main session is available later, rerun the exact same
  staging and payload path against the dedicated `transpose2 v4` archive

## Commands Attempted

```bash
set -a
source ./session_bootstrap/tmp/transpose2_v3_remote_benchmark_20260402_165612.env
set +a
export INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4
export REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4
export REMOTE_CURRENT_ARTIFACT=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs/optimized_model.so
export INFERENCE_CURRENT_EXPECTED_SHA256=e8d66616b53064aa9af730dd8649dedbf399eb8afca5cbed8c1bf7a96a359a8f

bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- \
  "mkdir -p /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs"

bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- \
  "cat > /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose2_add12_v4/tvm_tune_logs/optimized_model.so" \
  < ./session_bootstrap/tmp/transpose2_post_db_swap_local_build_v4_20260403_codex/fused_conv2d_transpose2_add12_post_db_swap.so

bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```
