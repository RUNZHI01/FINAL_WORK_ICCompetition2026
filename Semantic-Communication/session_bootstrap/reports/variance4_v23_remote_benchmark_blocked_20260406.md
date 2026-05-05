# `fused_variance4_add13_tir_sqrt4` v23 Remote Benchmark Blocked

Date: `2026-04-06`

## Candidate Being Blocked

- operator: `fused_variance4_add13_tir_sqrt4`
- candidate: `v23_flatten_channel_buffers`
- local artifact:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local artifact SHA256:
  `2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720`
- local artifact size:
  `1674696`

## Remote Path Intended

Reuse the existing variance4 staging path already used by earlier board runs:

- remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4`
- remote artifact target:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4/tvm_tune_logs/optimized_model.so`
- payload runner:
  `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`

## Probe Attempt

```bash
timeout 10s bash session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 \
  --user user \
  --pass user \
  -- "echo CONNECTED && hostname"
```

Result:

- exit code summary: `RC:124`
- observed behavior: timeout before any remote command output

## Interpretation

The current execution environment still cannot establish the SSH session needed
to stage the `v23` artifact or run the board payload benchmark.

This means:

- no remote upload happened in this round
- no remote SHA validation happened in this round
- no board payload median happened in this round

So the lane state remains:

- `variance4 v18 = 158.347 ms` is still the current **board-proven** best
- `variance4 v23` is the new **board-worthy local** candidate waiting for the
  next environment that can actually reach the Phytium Pi

## Related Evidence

- local status:
  `./session_bootstrap/reports/variance4_v23_local_status_20260406.md`
- correctness JSON:
  `./session_bootstrap/tmp/variance4_v23_correctness_check.json`
- build report:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap_report.json`
