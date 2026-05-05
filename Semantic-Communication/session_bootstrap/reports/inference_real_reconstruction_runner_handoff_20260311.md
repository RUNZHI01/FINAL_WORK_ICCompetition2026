# Real Reconstruction Runner Handoff

- generated_at: 2026-03-11T20:55:00+08:00
- scope: current-side real reconstruction runner + benchmark path preparation
- status: implementation_complete_remote_run_blocked_by_sandbox

## What Was Added

- `session_bootstrap/scripts/run_remote_current_real_reconstruction.sh`
  - remote/local wrapper for a real reconstruction path
  - selects baseline/current artifact explicitly instead of mutating the trusted current archive in place
  - writes outputs under `REMOTE_OUTPUT_BASE/<prefix>_<variant>/reconstructions`
  - emits legacy-style `批量推理时间（1 个样本）: ... 秒` lines plus a final JSON summary

- `session_bootstrap/scripts/current_real_reconstruction.py`
  - reads latent inputs from `REMOTE_INPUT_DIR`
  - supports real `.pt` latent files and local-validation `.npz` / `.npy` fallbacks
  - adds AWGN noise, runs `relax.VirtualMachine(...)[\"main\"]`, writes reconstructions, and reports counts/timings

- `session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env`
  - baseline: `run_remote_legacy_tvm_compat.sh --variant baseline`
  - current: `run_remote_current_real_reconstruction.sh --variant current`
  - current SHA guard remains pinned to `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`

## Local Validation

Local smoke report:

- `session_bootstrap/reports/inference_local_real_reconstruction_validation_20260311.md`

Local smoke semantics:

- benchmark wrapper invoked the new real-reconstruction runner for both baseline/current
- one synthetic latent input (`.npz`) was read
- both variants wrote a real output file
- the wrapper parsed the final JSON summaries successfully

Observed local outputs:

- baseline output dir: `session_bootstrap/tmp/local_real_reconstruction_validation_20260311/outputs/local_real_reconstruction_validation_20260311_baseline/reconstructions`
- current output dir: `session_bootstrap/tmp/local_real_reconstruction_validation_20260311/outputs/local_real_reconstruction_validation_20260311_current/reconstructions`
- baseline file count: `1`
- current file count: `1`

Observed local timings:

- baseline median: `734.936 ms`
- current median: `713.969 ms`

## Remote Benchmark Path

Prepared Phytium Pi benchmark env:

- `session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env`

Prepared remote output dirs from that env:

- baseline: `/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_20260311_baseline/reconstructions`
- current: `/home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_20260311_current/reconstructions`

Prepared remote benchmark command:

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh \
  --env ./session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env
```

Useful remote count probes after the run:

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" --port "${REMOTE_SSH_PORT:-22}" -- \
  "find /home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_20260311_baseline/reconstructions -type f | wc -l"
```

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" --port "${REMOTE_SSH_PORT:-22}" -- \
  "find /home/user/Downloads/jscc-test/jscc/infer_outputs/inference_real_reconstruction_compare_20260311_current/reconstructions -type f | wc -l"
```

## Why The Real Pi Run Did Not Happen Here

This environment blocks outbound SSH sockets. The direct probe failed with:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

So the live Phytium Pi end-to-end run was not feasible from this sandboxed session, even though the repo-side implementation and local wrapper validation are complete.
