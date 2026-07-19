# Variance4 v23 Remote Benchmark

- generated_at: `2026-04-06 13:44 +0800`
- operator: `fused_variance4_add13_tir_sqrt4`
- stage: `v23 exact-preserving post-db swapped full-module payload validation on rebooted 3-core board`
- status: `board_validated_no_stable_speedup`

## Board State

Remote probe at `2026-04-06 13:40 +0800`:

- hostname: `Phytium-Pi`
- `nproc`: `3`
- `getconf _NPROCESSORS_ONLN`: `3`
- `nproc --all`: `4`
- `lscpu`:
  - `CPU(s): 4`
  - `On-line CPU(s) list: 0-2`
  - `Off-line CPU(s) list: 3`

This confirms the board was back online and the Linux-visible online core count
was exactly `3`, matching the intended OpenAMP three-core board state.

## Upload Integrity

`v23` local artifact:

- path:
  `./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap.so`
- local sha256:
  `2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720`
- local size:
  `1674696`

Dedicated remote staging archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v23`
- remote artifact:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v23/tvm_tune_logs/optimized_model.so`
- remote sha256:
  `2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720`
- remote size:
  `1674696`
- local/remote sha match: `true`
- local/remote size match: `true`

## Payload Results

### First v23 payload run (`repeat=10`)

- load_ms: `3.947`
- vm_init_ms: `2.906`
- run_median_ms: `245.838`
- run_mean_ms: `245.930`
- run_min_ms: `245.192`
- run_max_ms: `246.922`
- run_variance_ms2: `0.215998`
- run_count: `10`

### Same-day v18 control reprobe (`repeat=10`)

Re-uploaded the checked-in `v18` artifact into a dedicated control archive:

- archive:
  `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v18_reprobe_20260406`
- artifact sha256:
  `72f5a2cff7bc28989ecbd9fabe9b0bf60da64a47117a1c78bcb60ae11477850e`
- upload integrity: `verified`

Control payload result:

- load_ms: `3.890`
- vm_init_ms: `0.469`
- run_median_ms: `246.381`
- run_mean_ms: `246.524`
- run_min_ms: `245.872`
- run_max_ms: `247.626`
- run_variance_ms2: `0.323139`
- run_count: `10`

First-pass same-day comparison:

- `v23` vs same-day `v18`: `-0.543 ms` (`-0.22%`)

This first-pass lead was too small to promote and needed a longer reprobe.

### Longer same-day reprobe (`repeat=30`)

`v23` first long run:

- run_median_ms: `246.675`
- run_mean_ms: `246.845`
- run_min_ms: `245.591`
- run_max_ms: `248.459`
- run_variance_ms2: `0.392592`
- run_count: `30`

`v18` long control:

- run_median_ms: `245.831`
- run_mean_ms: `245.833`
- run_min_ms: `245.034`
- run_max_ms: `246.963`
- run_variance_ms2: `0.222536`
- run_count: `30`

Comparison:

- `v23` vs same-day `v18`: `+0.844 ms` (`+0.34%`)

### Final v23 reprobe (`repeat=30`)

Second long `v23` run:

- run_median_ms: `245.903`
- run_mean_ms: `247.338`
- run_min_ms: `245.086`
- run_max_ms: `285.564`
- run_variance_ms2: `50.936196`
- run_count: `30`

Comparison against the same-day `v18` long control:

- `v23` vs same-day `v18`: `+0.072 ms` (`+0.03%`)

The large mean/variance on this reprobe is caused by a single visible outlier
sample (`285.564 ms`), but even the median still does not beat the same-day
`v18` control.

## Interpretation

Three conclusions are stable from this run:

1. The board is reachable again and the target runtime state really is the
   intended `3` online Linux cores.
2. `v23` is a real exact-preserving distinct artifact and the upload/SHA guard
   path is working correctly.
3. `v23` does **not** show a stable board-side speedup over `v18` under the
   same reboot-day board state.

One extra caution is necessary: the absolute reboot-day medians
(`~245-246 ms`) are much slower than the earlier `2026-04-03` historical
`v18 = 158.347 ms` report, so the correct interpretation here is a **same-day
control comparison**, not a direct replacement of the older absolute best
number.

## Conclusion

- board-side SSH path: `restored`
- 3-core gate: `confirmed`
- `v23` upload integrity: `pass`
- `v23` payload status: `no confirmed speedup`
- `v23` candidate decision: `drop for promotion; keep as board-tested negative evidence`
- current historical checked-in board-proven best remains:
  `variance4 v18 = 158.347 ms`
- current same-day 3-core control best remains:
  `variance4 v18 = 245.831 ms` (`repeat=30`)

## Commands

Board-state probe:

```bash
timeout 20s bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  'hostname; nproc; getconf _NPROCESSORS_ONLN; nproc --all; lscpu | egrep "^CPU\(s\):|^On-line CPU\(s\) list:|^Off-line CPU\(s\) list:"'
```

`v23` upload verification:

```bash
bash ./session_bootstrap/scripts/run_mean4_remote_payload_benchmark.sh \
  --upload-only \
  --inference-env ./session_bootstrap/tmp/variance4_v18_remote_benchmark_20260403.env \
  --local-artifact ./session_bootstrap/tmp/variance4_post_db_swap_local_build_v23/fused_variance4_add13_tir_sqrt4_post_db_swap.so \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v23 \
  --report-id variance4_v23_remote_payload_<timestamp>
```

`v23` payload benchmark:

```bash
set -a
source ./session_bootstrap/tmp/variance4_v18_remote_benchmark_20260403.env
set +a
export INFERENCE_CURRENT_ARCHIVE=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v23
export REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_variance4_add13_tir_sqrt4_v23
export INFERENCE_CURRENT_EXPECTED_SHA256=2b1a05b9326c3695b8a546d7d4b403728c11694bf633a9b6a938a72bcd11f720
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current
```
