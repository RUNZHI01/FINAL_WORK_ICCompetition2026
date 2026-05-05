# Phytium Pi Speed Test Summary

- generated_at: 2026-03-13T16:27:31+08:00
- scope: payload inference + real end-to-end reconstruction speed, using existing project scripts/env conventions
- session_result: no fresh live Pi rerun from this sandbox; SSH is blocked here with `socket: Operation not permitted`
- status: summarized from existing March 13 Pi-side reports plus today’s new `chunk4` candidate artifact report

## Scripts and envs selected

- payload benchmark wrapper:
  - `session_bootstrap/scripts/run_inference_benchmark.sh`
- payload current runner:
  - `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh`
- payload baseline runner:
  - `session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh`
- real reconstruction current runner:
  - `session_bootstrap/scripts/run_remote_current_real_reconstruction.sh`
- one-shot / upload / immediate current-only payload validation:
  - `session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh`
- incremental tuning wrapper that produced today’s candidate:
  - `session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh`

- tracked safe-runtime inference env inspected:
  - `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env`
- tracked real end-to-end compare env inspected:
  - `session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env`
- latest formal payload compare env snapshot:
  - `session_bootstrap/tmp/inference_compare_currentsafe_split_topup15_validate_20260313_0002.env`
- latest formal end-to-end compare env snapshot:
  - `session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_split_topup15_retry_20260313_005140.env`
- today’s `chunk4` tuning env:
  - `session_bootstrap/tmp/chunked_incremental_1000_20260313_012433/resume_from_chunk2_20260313_131545/chunk4.env`

## Artifact assessment

### Latest fully validated current

- local artifact:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_split_topup15_20260312_2000/optimized_model.so`
- remote artifact:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- SHA256:
  - `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
- validation status:
  - fully validated on the Pi for both payload-only and real end-to-end reconstruction

### Latest tuned candidate from today (`chunk4`)

- local artifact:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- remote artifact at time of the `chunk4` report:
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- SHA256:
  - `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- validation status:
  - payload current-only post-upload validation exists
  - no paired baseline-vs-current formal compare or real end-to-end compare is present in this repo yet
- interpretation:
  - this is the newest tuned candidate
  - it is not yet the newest fully validated current across both requested speed metrics

## Commands run in this session

### Inspection

```bash
rg --files session_bootstrap | sed -n '1,240p'
```

```bash
rg -n "chunk4|tvm310-safe|PYTHONPATH|torchvision|PIL|tqdm|reconstruct|end-to-end|benchmark|inference" session_bootstrap -S
```

```bash
nl -ba session_bootstrap/scripts/run_inference_benchmark.sh | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/scripts/run_remote_tvm_inference_payload.sh | sed -n '1,320p'
```

```bash
nl -ba session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh | sed -n '1,280p'
```

```bash
nl -ba session_bootstrap/scripts/run_remote_current_real_reconstruction.sh | sed -n '1,320p'
```

```bash
nl -ba session_bootstrap/scripts/current_real_reconstruction.py | sed -n '1,320p'
```

```bash
nl -ba session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh | sed -n '1,360p'
```

```bash
nl -ba session_bootstrap/runbooks/artifact_registry.md | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.md | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.json | sed -n '1,260p'
```

```bash
nl -ba session_bootstrap/tmp/inference_compare_currentsafe_split_topup15_validate_20260313_0002.env | sed -n '1,220p'
```

```bash
nl -ba session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_split_topup15_retry_20260313_005140.env | sed -n '1,240p'
```

```bash
nl -ba session_bootstrap/tmp/chunked_incremental_1000_20260313_012433/resume_from_chunk2_20260313_131545/inference_tvm310_safe_chunk2_b944dce3.env | sed -n '1,240p'
```

```bash
sha256sum session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so
```

### Live Pi reachability check

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh --host 100.121.87.73 --user user --pass user -- hostname
```

- result:
  - failed immediately in this sandbox with `socket: Operation not permitted`

## Existing Pi-side results

### A. Payload inference

#### Latest fully validated baseline vs current

- report:
  - `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002.md`
- env snapshot:
  - `session_bootstrap/tmp/inference_compare_currentsafe_split_topup15_validate_20260313_0002.env`
- exact benchmark commands recorded by the report:
  - baseline: `bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline`
  - current: `bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant current`
- results:
  - baseline median: `1853.7 ms`
  - current median: `131.343 ms`
  - improvement: `92.91%`
  - current artifact SHA: `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
  - current artifact SHA guard: matched

#### Today’s newest tuned candidate (`chunk4`) current-only payload validation

- report:
  - `session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.md`
- exact path used by that wrapper:
  - upload target: `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
  - runner semantics: `run_phytium_baseline_seeded_warm_start_current_incremental.sh` -> `run_phytium_current_safe_one_shot.sh` -> current-side safe payload validation
- results:
  - current-only median: `127.322 ms`
  - load: `3.766 ms`
  - VM init: `1.138 ms`
  - output shape: `[1, 3, 256, 256]`
  - candidate SHA: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- caveat:
  - no same-session paired baseline result is present for this candidate in the repo

### B. Real end-to-end reconstruction

#### Latest fully validated baseline vs current

- report:
  - `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140.md`
- env snapshot:
  - `session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_split_topup15_retry_20260313_005140.env`
- exact benchmark commands recorded by the report:
  - baseline: `bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline`
  - current: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`
- results:
  - baseline median: `1834.1 ms/image`
  - current median: `234.219 ms/image`
  - improvement: `87.23%`
  - baseline sample count: `300`
  - current sample count: `300`
  - current artifact SHA: `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
  - current artifact SHA guard: matched

#### Today’s `chunk4` candidate end-to-end status

- no formal end-to-end compare report exists yet for SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- because this sandbox cannot reach the Pi, that missing compare could not be produced here

## Env and import gotchas

- current safe-runtime payload path must keep using the existing `REMOTE_TVM_PYTHON` safe wrapper:
  - `TVM_FFI_DISABLE_TORCH_C_DLPACK=1`
  - `LD_LIBRARY_PATH` points at `tvm310_safe` `tvm_ffi/lib` plus `/home/user/tvm_samegen_safe_20260309/build`
  - `TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build`
  - `PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages`
- do not switch the main current interpreter to `myenv`; the legacy compat wrapper explicitly warns against that
- if `torch` / `PIL` imports are needed for real reconstruction:
  - use the existing `REMOTE_TORCH_PYTHONPATH` / `REMOTE_REAL_EXTRA_PYTHONPATH` mechanism
  - the latest real end-to-end env snapshot already injects `/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages`
- baseline and current intentionally use different runtime paths:
  - baseline: compat / legacy wrapper
  - current: `tvm310_safe` runtime path
- current SHA guard must be updated whenever remote current `.so` changes:
  - tracked config still contains older values
  - latest trusted formal env snapshots use `65747...b6377`
  - today’s `chunk4` candidate uses `6f236b07...6dc1`

## Durable artifacts and logs

- this summary:
  - `session_bootstrap/reports/phytium_speed_test_summary_20260313_162731.md`
- latest formal payload report:
  - `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002.md`
- latest formal payload raw csv:
  - `session_bootstrap/reports/inference_compare_currentsafe_split_topup15_validate_20260313_0002_raw.csv`
- latest formal payload log:
  - `session_bootstrap/logs/inference_compare_currentsafe_split_topup15_validate_20260313_0002.log`
- latest formal end-to-end report:
  - `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140.md`
- latest formal end-to-end raw csv:
  - `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140_raw.csv`
- latest formal end-to-end log:
  - `session_bootstrap/logs/inference_real_reconstruction_compare_currentsafe_split_topup15_20260313_003633_retry_20260313_005140.log`
- today’s `chunk4` candidate report:
  - `session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.md`
- today’s `chunk4` candidate json:
  - `session_bootstrap/reports/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.json`
- today’s `chunk4` candidate local artifact:
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`
- today’s `chunk4` candidate logs:
  - `session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545.log`
  - `session_bootstrap/logs/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545_remote_payload.log`

## Bottom line

- if the requirement is “best fully validated current on the Pi for both requested metrics,” use SHA `65747fb301851f27892666d28daefc856c0ff2f7f85d3702779be32dde4b6377`
- if the requirement is “newest tuned candidate seen today,” `chunk4` produced SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` and a current-only payload median of `127.322 ms`
- a fresh paired baseline-vs-current payload compare and a fresh paired end-to-end compare for `chunk4` were not possible from this sandbox because SSH to the Pi is blocked here
