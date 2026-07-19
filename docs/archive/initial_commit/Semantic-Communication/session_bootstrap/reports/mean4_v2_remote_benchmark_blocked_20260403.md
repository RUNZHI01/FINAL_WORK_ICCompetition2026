# Mean4 v2 Remote Benchmark Blocked

- generated_at: `2026-04-03T03:56:56+08:00`
- operator: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- candidate: `v2 scalar epilogue handoff`
- status: `remote_helper_path_blocked_by_exec_sandbox`

## Artifact

- local artifact:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- local sha256:
  `4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2`
- intended remote archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- intended remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3/tvm_tune_logs/optimized_model.so`
- env snapshot:
  `./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env`
- helper scripts added this round:
  - `./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py`
  - `./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh`

## Local Maturity Gate

- correctness vs frozen scheduled reference:
  - `exact_equal = false`
  - `allclose_atol1e-6_rtol1e-6 = true`
  - `allclose_atol1e-5_rtol1e-5 = true`
  - `max_abs_diff = 9.5367431640625e-07`
- post-db swap/build/export:
  - `swap_succeeded = true`
  - `structural_equal_post_swap_vs_candidate = true`
  - `build_status = built`
  - `export_status = exported`
- artifact distinctness:
  - prior v1 proof artifact:
    `de429fe2...2bbc9 / 1678704 bytes`
  - current v2 artifact:
    `4486eef6...02bd2 / 1674256 bytes`

This was therefore a legitimate first board attempt for the lane: the candidate
was real, locally validated, exported, and distinct.

## Commands Attempted

Env preparation:

```bash
./session_bootstrap/scripts/prepare_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_env.py \
  --expected-sha256 4486eef66fdf7817e4afca0078ea2294634df0b344070ac218366afb54902bd2 \
  --output-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env
```

Standard helper path:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --report-id mean4_v2_remote_payload_20260403
```

Observed stderr:

```text
Control socket connect(/tmp/ssh_mux/8299aa164475924595f533969ee578ceac910254): Operation not permitted
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

Controlled retry with helper mux disabled:

```bash
SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1 \
  ./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --report-id mean4_v2_remote_payload_20260403_retry
```

Observed stderr:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

## Interpretation

This blocker is in the current exec sandbox network/socket boundary, not in the
`mean4 v2` lane:

- the missing helper gap is now closed inside the repo
- the failure happened before remote upload completed
- no remote SHA or payload samples were produced in this environment

## Conclusion

- keep `mean4 v2` as the next board-worthy local candidate for this lane
- make no performance claim from this blocked attempt
- treat the new helper path itself as a valuable forward step, because `mean4`
  no longer lacks a checked-in board-proof route
- the next executable board step outside this sandbox is to reuse
  `./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env` and run:

```bash
./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --inference-env ./session_bootstrap/tmp/mean4_v2_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v2_20260403_scalar_epilogue/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs
```

## Postscript: Helper Gate Hardened

This report remains accurate for the `03:56` attempt itself: that attempt was
blocked before remote upload completed because the current exec sandbox could
not open SSH sockets.

Later continuation exposed a second blocker shape in the same helper family:
`local/remote sha mismatch`. The lane status therefore advanced from
"no socket available" to "the upload-integrity gate also needs to be made more
transparent."

That helper hardening is now recorded separately in:

- `./session_bootstrap/reports/mean4_v2_remote_sha_guard_fix_20260403.md`

Practical consequence:

- keep using this report as the historical record of the sandbox-blocked first
  board attempt
- use the new SHA-guard report for the current recommended retry flow
