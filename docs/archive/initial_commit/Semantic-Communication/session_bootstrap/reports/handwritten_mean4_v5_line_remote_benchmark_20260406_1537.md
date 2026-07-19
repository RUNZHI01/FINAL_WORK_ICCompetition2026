# Handwritten Mean4 v5 Line Remote Benchmark

- generated_at: `2026-04-06 15:37 +0800`
- scope: `handwritten line only`
- preset: `opus_final_v3_mean4`
- candidate override:
  `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v5 working copy`
- status: `board_validated_same_day_speedup_vs_current_handwritten_final`

## Board State

Same-session remote probe confirmed that the board is reachable again and still
in the intended three-core Linux-visible state:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `On-line CPU(s) list`: `0-2`
- `remoteproc0`: `running`

This is the same three-core gate used for the handwritten-line fairness checks,
so the correct comparison here is a **same-day handwritten-final control**, not
a cross-day absolute number.

## Upload Integrity

Integrated handwritten-line artifact under test:

- local artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so`
- local sha256:
  `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
- local size:
  `1674024`

Dedicated remote archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v5_20260406`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v5_20260406/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `f6383df86aa8d8b0bd5e93ad98538a40df469aa57e0114fed161ca47e5d5026e`
- remote size:
  `1674024`
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

`v5` candidate:

- run_median_ms: `240.129`
- run_mean_ms: `240.750`
- run_min_ms: `239.379`
- run_max_ms: `245.892`
- run_variance_ms2: `3.479984`
- run_count: `10`

Current handwritten final control:

- run_median_ms: `242.083`
- run_mean_ms: `242.280`
- run_min_ms: `241.304`
- run_max_ms: `243.575`
- run_variance_ms2: `0.414744`
- run_count: `10`

Comparison:

- `v5` vs same-day handwritten control:
  `-1.954 ms` (`-0.81%`)

### Longer same-day comparison (`repeat=30`)

`v5` candidate:

- run_median_ms: `240.775`
- run_mean_ms: `241.253`
- run_min_ms: `239.654`
- run_max_ms: `252.226`
- run_variance_ms2: `4.679037`
- run_count: `30`

Current handwritten final control:

- run_median_ms: `241.405`
- run_mean_ms: `241.587`
- run_min_ms: `240.913`
- run_max_ms: `243.897`
- run_variance_ms2: `0.423959`
- run_count: `30`

Comparison:

- `v5` vs same-day handwritten control:
  `-0.630 ms` (`-0.26%`)

### Candidate reprobe after control (`repeat=30`)

`v5` candidate reprobe:

- run_median_ms: `240.410`
- run_mean_ms: `242.325`
- run_min_ms: `239.465`
- run_max_ms: `298.376`
- run_variance_ms2: `108.674316`
- run_count: `30`

Comparison against the same-day handwritten control:

- `v5` reprobe vs handwritten control:
  `-0.995 ms` (`-0.41%`)

The reprobe includes a large outlier (`298.376 ms`), but the median still
stays below the same-day control. That matters more than the mean here because
the route decision is being made on repeated payload median, not on a single
worst-case sample.

## Interpretation

Three things matter here.

First, this is no longer the old `v4` identity case. The route under test is a
new handwritten-line artifact:

- current handwritten final:
  `2aa25d2b...e216 / 1674120 bytes`
- `v5` handwritten-line candidate:
  `f6383df8...026e / 1674024 bytes`

Second, the route-level benchmark was done the right way:

- remote upload and SHA guard passed
- candidate and control were run serially, not in parallel
- the result is supported by a `candidate -> control -> candidate` chain

Third, the speedup is modest but directionally stable:

- `repeat=10`: faster
- `repeat=30`: still faster
- `repeat=30` reprobe: still faster on median

That is enough to treat `mean4 v5` as a **real handwritten-line positive
candidate beyond the baked-in `v4` baseline**, not just another local-only
branch.

## Conclusion

- board SSH path: `working`
- three-core gate: `confirmed`
- upload integrity: `pass`
- handwritten-line artifact distinctness: `pass`
- `mean4 v5` handwritten-line payload status: `same-day positive`
- candidate decision: `keep as next handwritten-line candidate`
- important scope note:
  current checked-in handwritten baseline still resolves to the baked-in `v4`
  route, and `v5` was exercised through `--candidate-override`

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
  --inference-env ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v5_line_20260406.env \
  --local-artifact ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v5_20260406/optimized_model.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_opus_final_mean4_v5_20260406
```

Candidate payload (`repeat=30`):

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v5_line_20260406.env
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
  `./session_bootstrap/tmp/handwritten_mean4_v5_board_probe_20260406.txt`
- upload-only JSON:
  `./session_bootstrap/tmp/handwritten_mean4_v5_upload_only_20260406.json`
- candidate repeat=10:
  `./session_bootstrap/tmp/handwritten_mean4_v5_line_candidate_repeat10_20260406_rerun.json`
- control repeat=10:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat10_20260406_rerun.json`
- candidate repeat=30:
  `./session_bootstrap/tmp/handwritten_mean4_v5_line_candidate_repeat30_20260406_rerun.json`
- control repeat=30:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat30_20260406_rerun.json`
- candidate repeat=30 reprobe:
  `./session_bootstrap/tmp/handwritten_mean4_v5_line_candidate_repeat30_reprobe_20260406_rerun.json`
