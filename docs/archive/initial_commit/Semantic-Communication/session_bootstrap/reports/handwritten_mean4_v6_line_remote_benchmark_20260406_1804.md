# Handwritten Mean4 v6 Line Remote Benchmark

- generated_at: `2026-04-06 18:04 +0800`
- scope: `handwritten line only`
- preset: `opus_final_v3_mean4`
- candidate override:
  `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v6 working copy`
- status: `board_tested_near_parity_no_stable_win_vs_current_handwritten_final`

## Board State

Same-session remote probe confirmed that the board remains reachable and still
in the intended three-core Linux-visible state:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `On-line CPU(s) list`: `0-2`
- `remoteproc0`: `running`

This is the same handwritten-line fairness gate used for the recent mean4 reruns,
so the correct comparison here remains a same-day handwritten-final control.

## Upload Integrity

Integrated handwritten-line artifact under test:

- local artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so`
- local sha256:
  `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`
- local size:
  `1672000`

Dedicated remote archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v6_20260406`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v6_20260406/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `ce9b5317750c57a73e5deef770cdbad1c16386bfc3f784cff533ba55b777b5a2`
- remote size:
  `1672000`
- local/remote sha match: `true`
- local/remote size match: `true`

Current handwritten final control:

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_retest`
- artifact sha256:
  `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- artifact size:
  `1674120`

## Serial Payload Results

### First same-day comparison (`repeat=10`)

`v6` candidate:

- run_median_ms: `241.086`
- run_mean_ms: `241.393`
- run_min_ms: `240.423`
- run_max_ms: `243.945`
- run_variance_ms2: `0.902207`
- run_count: `10`

Current handwritten final control:

- run_median_ms: `240.658`
- run_mean_ms: `241.009`
- run_min_ms: `240.347`
- run_max_ms: `243.009`
- run_variance_ms2: `0.596226`
- run_count: `10`

Comparison:

- `v6` vs same-day handwritten control:
  `+0.428 ms` (`+0.18%`)

### Longer same-day comparison (`repeat=30`)

`v6` candidate:

- run_median_ms: `240.261`
- run_mean_ms: `240.291`
- run_min_ms: `239.381`
- run_max_ms: `241.056`
- run_variance_ms2: `0.176255`
- run_count: `30`

Current handwritten final control:

- run_median_ms: `240.097`
- run_mean_ms: `240.169`
- run_min_ms: `239.416`
- run_max_ms: `241.394`
- run_variance_ms2: `0.168207`
- run_count: `30`

Comparison:

- `v6` vs same-day handwritten control:
  `+0.164 ms` (`+0.07%`)

### Candidate reprobe and end-of-chain control (`repeat=30`)

`v6` candidate reprobe:

- run_median_ms: `239.504`
- run_mean_ms: `239.642`
- run_min_ms: `239.067`
- run_max_ms: `242.078`
- run_variance_ms2: `0.336393`
- run_count: `30`

End-of-chain handwritten control:

- run_median_ms: `239.682`
- run_mean_ms: `239.815`
- run_min_ms: `238.906`
- run_max_ms: `242.139`
- run_variance_ms2: `0.453967`
- run_count: `30`

Comparison:

- `v6` reprobe vs end-of-chain handwritten control:
  `-0.178 ms` (`-0.07%`)

### Bracketed long-sample view

Because the second `v6` run was slightly faster while both control medians also
drifted downward over time, the meaningful summary is the paired long-sample
average:

- `v6` long-sample average median:
  `(240.261 + 239.504) / 2 = 239.8825 ms`
- handwritten control long-sample average median:
  `(240.097 + 239.682) / 2 = 239.8895 ms`
- paired average delta:
  `-0.007 ms`

That is effectively parity.

## Interpretation

Three things matter here.

First, `v6` is a real handwritten-line artifact:

- current handwritten final:
  `2aa25d2b...e216 / 1674120 bytes`
- `v6` handwritten-line candidate:
  `ce9b5317...b5a2 / 1672000 bytes`

Second, the board route was validated the right way:

- upload-only SHA and size guard passed
- candidate and control were run serially, not in parallel
- the long-sample evidence is bracketed as
  `candidate -> control -> candidate -> control`

Third, the structural phase reorder did **not** convert into a stable route-level
win:

- first short sample: slower
- first long sample: still slightly slower
- reprobe: slightly faster
- paired long-sample average: effectively identical

That is not strong enough to promote `v6` over the current handwritten final,
and it is also not strong enough to displace `v5` as the next handwritten-line
promotion candidate.

## Conclusion

- board SSH path: `working`
- three-core gate: `confirmed`
- upload integrity: `pass`
- handwritten-line artifact distinctness: `pass`
- `mean4 v6` handwritten-line payload status:
  `near parity / no stable same-day win`
- candidate decision:
  `keep as board-tested structural evidence, do not promote`
- active handwritten-line promotion candidate remains:
  `mean4 v5`

## Commands

Board-state probe:

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user --port 22 -- \
  'echo hostname=$(hostname); echo nproc=$(nproc); echo online=$(getconf _NPROCESSORS_ONLN); lscpu | grep "On-line CPU(s) list"; echo remoteproc0=$(cat /sys/class/remoteproc/remoteproc0/state)'
```

Upload verification:

```bash
env INFERENCE_REPEAT=10 \
  bash ./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v6_line_20260406.env \
  --local-artifact ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v6_20260406/optimized_model.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_opus_final_mean4_v6_20260406
```

Candidate payload (`repeat=30`):

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v6_line_20260406.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

Current handwritten final control (`repeat=30`):

```bash
set -a
source ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/handwritten_big_little_compare.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Outputs

- board-state probe:
  `./session_bootstrap/tmp/handwritten_mean4_v6_board_probe_20260406.txt`
- upload-only JSON:
  `./session_bootstrap/tmp/handwritten_mean4_v6_upload_only_20260406.json`
- candidate repeat=10:
  `./session_bootstrap/tmp/handwritten_mean4_v6_line_candidate_repeat10_20260406.json`
- control repeat=10:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat10_20260406_v6_cmp.json`
- candidate repeat=30:
  `./session_bootstrap/tmp/handwritten_mean4_v6_line_candidate_repeat30_20260406.json`
- control repeat=30:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat30_20260406_v6_cmp.json`
- candidate repeat=30 reprobe:
  `./session_bootstrap/tmp/handwritten_mean4_v6_line_reprobe_repeat30_20260406.json`
- end-of-chain control repeat=30:
  `./session_bootstrap/tmp/handwritten_current_final_control_reprobe_repeat30_20260406_v6_cmp.json`
