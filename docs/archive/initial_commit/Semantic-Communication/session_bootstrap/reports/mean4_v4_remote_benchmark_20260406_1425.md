# Mean4 v4 Remote Benchmark

- generated_at: `2026-04-06 14:25 +0800`
- operator: `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
- candidate: `v4 channel-param-hoist fused epilogue`
- status: `board_validated_same_day_speedup_vs_trusted_current`

## Board State

Same-session remote probe confirmed the intended 3-core Linux-visible board
state:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `nproc --all`: `4`
- `On-line CPU(s) list`: `0-2`

This is the same board-state gate previously used for the OpenAMP three-core
fairness checks, so the correct comparison in this report is a **same-day
trusted-current control**, not a cross-day absolute number.

## Upload Integrity

`v4` local artifact:

- path:
  `./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4_20260406_channel_fused/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- local sha256:
  `cb38d01fbc59c7a4acf42a95074f16757d61911628236ef890e70637b37315cd`
- local size:
  `1674072`

Dedicated remote staging archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_v4`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_v4/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `cb38d01fbc59c7a4acf42a95074f16757d61911628236ef890e70637b37315cd`
- remote size:
  `1674072`
- local/remote sha match: `true`
- local/remote size match: `true`

## Payload Results

### First same-day comparison (`repeat=10`)

`v4` candidate:

- run_median_ms: `242.238`
- run_mean_ms: `243.722`
- run_min_ms: `241.413`
- run_max_ms: `257.382`
- run_variance_ms2: `21.063562`
- run_count: `10`

Trusted current control:

- archive: `/home/user/Downloads/jscc-test/jscc_staging`
- artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- run_median_ms: `250.897`
- run_mean_ms: `252.754`
- run_min_ms: `250.337`
- run_max_ms: `266.104`
- run_variance_ms2: `20.810443`
- run_count: `10`

Comparison:

- `v4` vs same-day trusted current:
  `-8.659 ms` (`-3.45%`)

### Longer same-day comparison (`repeat=30`)

`v4` candidate:

- run_median_ms: `241.948`
- run_mean_ms: `242.501`
- run_min_ms: `240.922`
- run_max_ms: `256.827`
- run_variance_ms2: `7.446757`
- run_count: `30`

Trusted current control:

- run_median_ms: `248.717`
- run_mean_ms: `249.309`
- run_min_ms: `247.730`
- run_max_ms: `264.692`
- run_variance_ms2: `8.451144`
- run_count: `30`

Comparison:

- `v4` vs same-day trusted current:
  `-6.769 ms` (`-2.72%`)

## Interpretation

Two things matter here.

First, this is not another fragile local-only branch. The upload path, remote
SHA guard, and full payload path all ran successfully on the real board.

Second, the direction that finally worked is the one the repo's hardware notes
pointed to:

- do not reuse the `variance4` scalar one-element handoff family
- do reduce full-frame memory traffic inside `mean4`
- do hoist channel-invariant parameters and fuse the hot epilogue pass

That is exactly what `v4` does, and the board result now matches the operator
analysis: the same-day control is beaten at both `repeat=10` and `repeat=30`.

One caution remains necessary: these `~242-249 ms` medians are a same-day
reboot-state comparison. They should not be mixed directly with older
cross-day absolute medians such as the historical `mean4 v2` report.

## Conclusion

- board SSH path: `working`
- 3-core gate: `confirmed`
- upload integrity: `pass`
- `mean4 v4` payload status: `stable same-day speedup`
- `mean4 v4` candidate decision: `keep and promote`
- current `mean4` lane conclusion:
  the old `v2` scalar-handoff family stays closed as negative evidence, and
  `v4` becomes the first board-proven positive branch for this operator

## Commands

Board-state probe:

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user --port 22 -- \
  'echo hostname=$(hostname); echo nproc=$(nproc); echo nproc_all=$(nproc --all); echo online=$(getconf _NPROCESSORS_ONLN); lscpu | grep -E "On-line CPU\(s\) list|Architecture"'
```

Upload verification:

```bash
bash ./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/trusted_env_snapshot.env \
  --local-artifact ./session_bootstrap/tmp/mean4_post_db_swap_local_build_v4_20260406_channel_fused/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_v4 \
  --report-id mean4_v4_remote_payload_20260406_upload_only
```

Candidate payload (`repeat=30`):

```bash
set -a
source ./session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/trusted_env_snapshot.env
set +a
export INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_v4
export REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_v4
export INFERENCE_CURRENT_EXPECTED_SHA256=cb38d01fbc59c7a4acf42a95074f16757d61911628236ef890e70637b37315cd
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=0
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

Trusted current control (`repeat=30`):

```bash
set -a
source ./session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/trusted_env_snapshot.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=0
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```
