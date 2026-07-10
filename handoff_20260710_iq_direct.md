# 2026-07-10 IQ Direct Handoff

## Current State

Branch: `feat/restore-248`

Latest committed checkpoint:

```text
e7ac4e8 perf: stabilize iq cockpit container path
8422b05 perf: tune iq rx session profile
fdc0766 perf: add minimal iq decode responses
```

The Cockpit Desktop one-click API path is back on IQ direct and reaches the expected near-250 ms visible reconstruction speed. QPSK was not changed; keep it as the regression baseline.

The current IQ route is:

```text
cockpit_desktop -> server.py -> usrp_runtime.py -> RunAnalogLatentBatch.py
-> persistent TX/RX -> board decode-server -> board big.LITTLE TVM
```

Use Docker for Linux/bash and SSH helper commands from Windows. Do not use WSL. Board-side Python must come from the board virtual environment, for example `/home/user/venv/bin/python`. Do not commit board passwords, host addresses, private keys, or Tailscale credentials.

## Validated Metrics

All runs below used Cockpit-equivalent `/api/run-inference-batch`, IQ direct, handwritten TVM, big.LITTLE, Docker TX, board RX, remote-dir `.npz`, and security channel disabled for performance measurement.

| Batch | Count | Result | TVM median | TVM p95 | IQ transport median | IQ transport p95 | Notes |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `batch-1783671744-300` | 300 | `300/300`, fallback `0` | `241.04 ms` | `243.75 ms` | `171.54 ms` | `363.50 ms` | Container/Cockpit path recovered. |
| `batch-1783672570-50` | 50 | `50/50`, fallback `0` | `241.58 ms` | `248.65 ms` | `169.31 ms` | `245.63 ms` | `RX_ARM_WAIT_MS=150`; no extra retry records. |
| `batch-1783672642-300` | 300 | `300/300`, fallback `0` | `241.93 ms` | `248.18 ms` | `170.84 ms` | `332.98 ms` | `RX_ARM_WAIT_MS=150`; still had 5 recovered extra attempts. |

Reference QPSK baseline in the project plan is about `2961.78 ms/image` transport. IQ direct is therefore much faster on the data plane. The visible reconstruction cadence is still dominated by TVM at roughly `241-243 ms`.

## What Changed In The Latest Checkpoint

- `OtaRxPersistentServer` now supports `--stop-wait-ms` and waits for the RX worker before replying to `STOP`.
- Cockpit startup preserves IQ/USRP/Docker-related environment variables instead of falling back to prerecorded inputs.
- Docker TX launch uses `OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET`, so `/host_workspace` containers work.
- USRP startup can discover the local 300 latent cache when `transport_mode=usrp`.
- Docker demo wrappers forward `RX_STOP_WAIT_MS`.
- Tests cover STOP wait propagation, Docker TX path mapping, USRP env preservation, and latent discovery.

## Clean Startup Procedure

1. Stop the backend and USRP helpers.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

2. From Docker, clear board-side stale RX/TX helpers.

```powershell
docker run --rm -e SSHPASS=$env:REMOTE_PASS iccomp-usrp-tx:latest `
  sshpass -e ssh -p 22 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  "$env:REMOTE_USER@$env:REMOTE_HOST" `
  'pgrep -f "/home/user/USRP292x/[O]taRxPersistentServer" | xargs -r kill || true; pgrep -f "/home/user/USRP292x/[O]taTxPersistentServer" | xargs -r kill || true'
```

3. Start the backend with IQ direct variables. Keep host, user, and password in local environment variables only.

Key settings:

```text
OPENAMP_SSH_RUNNER=paramiko
OPENAMP_USRP_TX_RUNNER=docker
OPENAMP_USRP_TX_DOCKER_IMAGE=iccomp-usrp-tx:latest
OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET=/host_workspace
MLKEM_TRANSPORT_MODE=usrp
MLKEM_USRP_MODE=ota
OPENAMP_DEMO_LINK_MODE=iq-direct
JSCC_LINK_MODE=iq-direct
OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp
OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED=0
OPENAMP_DEMO_LOCAL_LATENT_DIR=<local 300-latent cache>
REMOTE_USRP_DECODE_PYTHON=/home/user/venv/bin/python
OPENAMP_DEMO_REMOTE_DECODE_PYTHON=/home/user/venv/bin/python
ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir
ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal
RX_ARM_WAIT_MS=150
RX_STOP_WAIT_MS=8000
ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0
ANALOG_PIPELINE_DEPTH=1
ANALOG_PRECONNECT_CONTROL=1
ANALOG_RX_SESSION_CONTROL=1
ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=0
OPENAMP_TVM_BATCH_RUNNER=biglittle
```

4. Start USRP control and run the Cockpit-equivalent batch.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":300,"allow_preflight_degraded":true}'
```

Poll with:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

## Known Issues

- `RX_ARM_WAIT_MS=150` improves p95 in the 300-image run but does not remove every long tail.
- Latest 300-image `batch-1783672642-300` had `305` transport stage records for `300` images. Recovered retry images were `74`, `146`, `152`, `154`, and `194`.
- The worst current tail is still RX not arming before TX or a real board decode stall. Examples:
  - image `194`: `RX CAPTURE did not arm before TX`, failed attempt about `5715 ms`, retry succeeded.
  - image `160`: board-reported decode about `2140 ms`.
  - image `180`: runner decode about `2349 ms`, board-reported decode about `50 ms`.
- The `qpsk_batch_spool_arq_runs/` directory name is legacy. Current `cockpit_usrp_usrp-*` summaries there are IQ direct runs.

## Next Work

1. Keep QPSK frozen. Check `git diff -- USRP292x/RunQpskFileBatchSpoolArq.py` before and after IQ changes.
2. Treat `RX_ARM_WAIT_MS=150` as the current candidate profile, but do not promote it solely from one 300-image run. Repeat once after a clean restart.
3. Add condition-based RX readiness handling so the runner does not start TX until the RX server has actually left the drain/pre-arm state.
4. Investigate decode tails separately from RX tails. Board-reported decode and runner-side decode wait diverge in some records, so do not assume every tail is RF.
5. Keep streaming TVM and double buffering opt-in. Earlier overlap runs worsened contention.
6. Measure ML-KEM/auth overhead only after the IQ data plane is stable. Security should be session-level, not per image.

## Verification Commands

Run before committing changes:

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m pytest docker/test_demo_scripts.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_discovers_usrp_latent_dir Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_keeps_usrp_runtime_env Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_usrp_local_tx_server_can_start_from_docker_image Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::test_start_remote_rx_server_passes_arm_wait_ms -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\usrp_runtime.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\server.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

Last verified before `e7ac4e8`:

```text
USRP292x/test_analog_latent_link.py: 82 passed
docker/test_demo_scripts.py: 8 passed
targeted server tests: 4 passed
py_compile: passed
QPSK runner diff: empty
git diff --check: exit 0, line-ending warnings only
```
