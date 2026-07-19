# Mean4 v2 Remote SHA Guard Fix

- generated_at: `2026-04-03T04:07:00+08:00`
- operator: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- candidate: `v2 scalar epilogue handoff`
- status: `helper_hardened_waiting_for_socket_capable_board_retry`

## Trigger

The interrupted async continuation no longer pointed at the earlier
`socket: Operation not permitted` failure alone. Its key output had already
advanced to:

```text
ERROR: local/remote sha mismatch
```

That changed the immediate priority for the lane:

- the active handwritten target is still `mean4 v2`
- but the first blocker to clear is now the helper's upload-integrity gate,
  not a new operator-side edit

## What Changed

`./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh` is now
hardened in four ways:

1. Added `--upload-only`.
   - This exits after upload + remote SHA/size verification and does not enter
     the payload benchmark.
   - It isolates the exact gate that was failing.
2. Replaced the old raw `cat > remote_file` write path with a byte-stable
   `base64 | python3 write_bytes(...)` upload.
3. Added structured remote metadata reads for every uploaded file:
   - `sha256`
   - `size_bytes`
4. Added `REMOTE_SSH_PORT` handling and `SSH_SCRIPT` override support.
   - This makes the helper match the repo's more mature remote runners and
     enables stub-based local verification.

## Why This Is The Right Fix

I could not re-run the real board path from the current environment because SSH
socket access is still restricted here. So I did not try to guess whether the
remote mismatch was caused by a transient upload, a partial write, or a noisy
verification path.

Instead, I changed the flow so the next board-capable session can answer that
question deterministically:

- first run `--upload-only`
- require `local_sha == remote_sha` and `local_size == remote_size`
- only then run the actual payload benchmark

This converts a previously opaque blocker into a narrow, testable gate.

## Minimal Verification Run

Because real SSH is unavailable in this sandbox, the helper was verified with a
stub SSH wrapper that executes the remote commands locally and preserves stdin.

Command:

```bash
SSH_SCRIPT="$tmp_ssh" \
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env /tmp/mean4_upload_only_test.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --remote-archive-dir /tmp/mean4_upload_verify_stub
```

Observed result:

```json
{"status":"upload_verified","remote_artifact":"/tmp/mean4_upload_verify_stub/tvm_tune_logs/optimized_model.so","local_sha256":"4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2","remote_sha256":"4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2","local_size_bytes":1674256,"remote_size_bytes":1674256}
```

## Current State

- `mean4 v2` remains the next board-worthy local candidate
- no new board performance number is claimed here
- the helper is now fit to separate:
  - upload-integrity failure
  - from actual remote payload behavior

## Next Board-Capable Step

1. Reuse the checked-in env:
   `./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env`
2. First verify upload only:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

3. If upload verification passes, rerun without `--upload-only` to get the
   real payload number.
