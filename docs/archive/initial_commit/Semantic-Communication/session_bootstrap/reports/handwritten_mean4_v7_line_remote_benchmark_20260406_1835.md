# Handwritten Mean4 v7 Line Remote Benchmark

- generated_at: `2026-04-06 18:35 +0800`
- scope: `handwritten line only`
- preset: `opus_final_v3_mean4`
- candidate override:
  `fused_mean4_subtract4_divide4_multiply4_add14_relu3 -> v7 working copy`
- status: `board_validated_same_day_speedup_vs_current_handwritten_final`

## Board State

Same-session remote probe confirmed that the board remains reachable and still
in the intended three-core Linux-visible state:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `On-line CPU(s) list`: `0-2`
- `remoteproc0`: `running`

This keeps the comparison aligned with the current handwritten-line fairness
gate.

## Upload Integrity

Integrated handwritten-line artifact under test:

- local artifact:
  `./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so`
- local sha256:
  `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`
- local size:
  `1672096`

Dedicated remote archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`
- remote size:
  `1672096`
- local/remote sha match: `true`
- local/remote size match: `true`

Current handwritten final control:

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_retest`
- artifact sha256:
  `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- artifact size:
  `1674120`

## Evidence Hygiene

One early `repeat=10` candidate/control launch was started in parallel by
mistake during warmup. Those JSON outputs are not used for any conclusion here.

The only valid evidence in this note is the later strictly serial chain:

- candidate `repeat=10` serial
- control `repeat=10` serial
- candidate `repeat=30` rerun
- control `repeat=30` serial
- candidate `repeat=30` reprobe

This keeps the board claim tied only to non-overlapping runs.

## Serial Payload Results

### First same-day comparison (`repeat=10`)

`v7` candidate:

- run_median_ms: `238.684`
- run_mean_ms: `238.994`
- run_min_ms: `238.095`
- run_max_ms: `240.534`
- run_variance_ms2: `0.76523`
- run_count: `10`

Current handwritten final control:

- run_median_ms: `245.999`
- run_mean_ms: `245.927`
- run_min_ms: `244.093`
- run_max_ms: `247.779`
- run_variance_ms2: `0.978855`
- run_count: `10`

Comparison:

- `v7` vs same-day handwritten control:
  `-7.315 ms` (`-2.974%`)

### Longer same-day comparison (`repeat=30`)

`v7` candidate:

- run_median_ms: `238.602`
- run_mean_ms: `239.01`
- run_min_ms: `237.811`
- run_max_ms: `243.069`
- run_variance_ms2: `1.540812`
- run_count: `30`

Current handwritten final control:

- run_median_ms: `243.460`
- run_mean_ms: `243.757`
- run_min_ms: `242.947`
- run_max_ms: `246.080`
- run_variance_ms2: `0.692842`
- run_count: `30`

Comparison:

- `v7` vs same-day handwritten control:
  `-4.858 ms` (`-1.995%`)

### Candidate reprobe (`repeat=30`)

`v7` candidate reprobe:

- run_median_ms: `239.801`
- run_mean_ms: `240.03`
- run_min_ms: `238.966`
- run_max_ms: `241.711`
- run_variance_ms2: `0.51664`
- run_count: `30`

Comparison against the same same-day control median above:

- `v7` reprobe vs handwritten control:
  `-3.659 ms` (`-1.503%`)

### Supplemental same-day v5 rerun

To check whether `v7` only beats the current handwritten final or also appears
to move beyond the earlier `v5` branch, I also reran `v5` on the same day:

- `v5` repeat=30 rerun median: `242.734 ms`

This is slower than both valid `v7` long-sample medians:

- `v7` repeat=30 rerun: `238.602 ms`
- `v7` repeat=30 reprobe: `239.801 ms`

This is not a fully bracketed dedicated `v7` vs `v5` compare, so it should be
treated as supporting evidence rather than the sole ranking rule. But it does
make `v7` look stronger than `v5`, not just stronger than the baked current
handwritten final.

## Interpretation

Three things matter here.

First, `v7` is a real handwritten-line artifact:

- current handwritten final:
  `2aa25d2b...e216 / 1674120 bytes`
- `v7` handwritten-line candidate:
  `bf255cd4...edecb / 1672096 bytes`

Second, the board route was validated the right way:

- upload-only SHA and size guard passed
- the valid candidate/control evidence is serial, not parallel
- the positive result remains after a long-sample rerun and a candidate reprobe

Third, this is materially stronger than either prior beyond-`v4` seam:

- `v5` only landed a small handwritten-line win
- `v6` collapsed to near parity
- `v7` produces a larger and repeated handwritten-line gain while also matching
  the intended vectorized reduction codegen

## Conclusion

- board SSH path: `working`
- three-core gate: `confirmed`
- upload integrity: `pass`
- handwritten-line artifact distinctness: `pass`
- `mean4 v7` handwritten-line payload status:
  `stable same-day positive vs current handwritten final`
- candidate decision:
  `promote as the strongest next handwritten-line mean4 candidate`
- current practical interpretation:
  `v7` now appears to supersede `v5`, while `v6` remains negative structural
  evidence

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
  --inference-env ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_line_20260406.env \
  --local-artifact ./session_bootstrap/tmp/opus_integrated_opus_final_v3_mean4_v7_20260406/optimized_model.so \
  --database-dir ./session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406
```

Candidate payload (`repeat=30`):

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_line_20260406.env
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
  `./session_bootstrap/tmp/handwritten_mean4_v7_board_probe_20260406.txt`
- upload-only JSON:
  `./session_bootstrap/tmp/handwritten_mean4_v7_upload_only_20260406.json`
- invalid parallel warmup outputs, intentionally excluded:
  `./session_bootstrap/tmp/handwritten_mean4_v7_line_candidate_repeat10_20260406.json`
  and
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat10_20260406_v7_cmp.json`
- candidate repeat=10 serial:
  `./session_bootstrap/tmp/handwritten_mean4_v7_line_candidate_repeat10_20260406_serial.json`
- control repeat=10 serial:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat10_20260406_v7_cmp_serial.json`
- candidate repeat=30 rerun:
  `./session_bootstrap/tmp/handwritten_mean4_v7_line_candidate_repeat30_20260406_rerun.json`
- control repeat=30 serial:
  `./session_bootstrap/tmp/handwritten_current_final_control_repeat30_20260406_v7_cmp_serial.json`
- candidate repeat=30 reprobe:
  `./session_bootstrap/tmp/handwritten_mean4_v7_line_candidate_repeat30_reprobe_20260406.json`
- supplemental same-day `v5` rerun:
  `./session_bootstrap/tmp/handwritten_mean4_v5_line_candidate_repeat30_20260406_same_day_after_v7.json`
