# Handwritten Mean4 v7 vs Trusted Current vs ACL Payload Compare

- generated_at: `2026-04-06 19:00 +0800`
- scope: `same-day serial payload`
- board mode: `OpenAMP 3-core Linux-visible state`
- routes under compare:
  - `handwritten mean4 v7 line`
  - `trusted current`
  - `ACL integration line`

## Purpose

Earlier `mean4 v7` evidence only proved that the new handwritten branch beat
the current handwritten final.

This note closes the next obvious gap: compare that same `v7` handwritten line
directly against the other two project-level routes under the same board state
and the same payload method.

## Board State

Same-session probe confirmed the intended board state before the compare:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `On-line CPU(s) list`: `0-2`
- `remoteproc0`: `running`

## Compared Artifacts

### Handwritten mean4 v7 line

- archive:
  `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406`
- artifact sha256:
  `bf255cd4bb29408b30b50bce2ad8713a260c5e45efc2d0e831bd293eec9edecb`

### Trusted current

- archive:
  `/home/user/Downloads/jscc-test/jscc`
- artifact sha256:
  `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

### ACL integration line

- archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6`
- artifact sha256:
  `602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba`

Important ACL note:

- this route still emits a preload registration line before the final JSON
  payload summary because it relies on
  `preload_transpose_add6_tvm_proxy.py`
- the benchmark itself still completed successfully
- the metrics below are taken from the final JSON line after that preload note

## Serial Payload Results (`repeat=30`)

### First `v7` run

- run_median_ms: `240.059`
- run_mean_ms: `240.373`
- run_min_ms: `239.449`
- run_max_ms: `242.122`
- run_variance_ms2: `0.585563`

### Trusted current

- run_median_ms: `244.617`
- run_mean_ms: `244.898`
- run_min_ms: `243.863`
- run_max_ms: `248.100`
- run_variance_ms2: `0.96774`

Comparison:

- `v7` vs trusted current:
  `-4.558 ms` (`-1.863%`)

### ACL integration line

- run_median_ms: `248.156`
- run_mean_ms: `248.848`
- run_min_ms: `247.442`
- run_max_ms: `261.470`
- run_variance_ms2: `6.103502`

Comparison:

- `v7` vs ACL line:
  `-8.097 ms` (`-3.263%`)
- trusted current vs ACL line:
  `-3.539 ms` (`-1.426%`)

### `v7` reprobe

- run_median_ms: `239.052`
- run_mean_ms: `239.394`
- run_min_ms: `238.624`
- run_max_ms: `241.743`
- run_variance_ms2: `0.64479`

Comparison:

- `v7` reprobe vs trusted current:
  `-5.565 ms` (`-2.275%`)
- `v7` reprobe vs ACL line:
  `-9.104 ms` (`-3.669%`)

### Bracketed `v7` view

Using the average of the first `v7` run and the reprobe:

- `v7` bracketed median average:
  `(240.059 + 239.052) / 2 = 239.5555 ms`

Comparison:

- bracketed `v7` vs trusted current:
  `-5.0615 ms` (`-2.069%`)
- bracketed `v7` vs ACL line:
  `-8.6005 ms` (`-3.466%`)

## Interpretation

This compare makes three things clear.

First, the new `mean4 v7` branch is no longer just "better than the current
handwritten final". Under the same board state and the same serial payload
method, it also beats the current project-level `trusted current` route.

Second, the ACL integration line remains slower than both:

- slower than trusted current
- slower than the `mean4 v7` handwritten line

Third, the `v7` advantage is not a one-shot median:

- first `v7` run beats both other routes
- the later reprobe still beats both other routes

That makes the route ordering on this same-day payload compare:

1. `handwritten mean4 v7 line`
2. `trusted current`
3. `ACL integration line`

## Conclusion

- board SSH path: `working`
- 3-core OpenAMP gate: `confirmed`
- payload comparison mode: `serial / same-day / repeat=30`
- current route ranking on this compare:
  `v7 handwritten line < trusted current < ACL line`
- current practical interpretation:
  `mean4 v7` now has direct same-day payload evidence not only against the
  handwritten-final control, but also against both external comparison lines

## Commands

`v7` payload:

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_payload_cmp_20260406.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

Trusted current payload:

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_trusted_current_payload_cmp_20260406.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

ACL payload:

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_acl_payload_cmp_20260406.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

`v7` reprobe:

```bash
set -a
source ./session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_payload_cmp_20260406.env
set +a
export INFERENCE_REPEAT=30
export INFERENCE_WARMUP_RUNS=2
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```

## Outputs

- board-state probe:
  `./session_bootstrap/tmp/handwritten_mean4_v7_board_probe_20260406.txt`
- `v7` first run:
  `./session_bootstrap/tmp/three_line_cmp_v7_repeat30_20260406.json`
- trusted current:
  `./session_bootstrap/tmp/three_line_cmp_trusted_current_repeat30_20260406.json`
- ACL line:
  `./session_bootstrap/tmp/three_line_cmp_acl_repeat30_20260406.json`
- `v7` reprobe:
  `./session_bootstrap/tmp/three_line_cmp_v7_reprobe_repeat30_20260406.json`
