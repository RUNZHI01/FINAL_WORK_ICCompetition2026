# 2026-07-10 IQ Direct Handoff

## Current Conclusion

Branch: `feat/restore-248`.

Latest implementation checkpoint before this handoff:

```text
cb921d2 perf: close iq rx sessions promptly
8966711 perf: promote iq arm wait profile
71a591d docs: add iq direct handoff
e7ac4e8 perf: stabilize iq cockpit container path
```

The Cockpit Desktop one-click path is back on IQ direct with handwritten TVM and the big.LITTLE runner. The latest 300-image Cockpit-equivalent run is all-pass and keeps the IQ transport median below the TVM median. This is good enough as the current recovered profile, but it is not the final tail-latency fix: p95 and max still show RX/decode long-tail events.

Do not change QPSK while continuing IQ work. QPSK is the regression baseline.

## Active Runtime Path

```text
cockpit_desktop
-> openamp_control_plane_demo/server.py
-> usrp_runtime.py
-> USRP292x/RunAnalogLatentBatch.py
-> persistent TX/RX USRP servers
-> board decode-server
-> board big.LITTLE TVM
```

Use Docker for Linux/bash and SSH helper commands on the Windows host. If Docker is unavailable, use Windows Git Bash. Do not use WSL. Board-side Python must come from `/home/user/venv/bin/python`. Keep host addresses, passwords, Tailscale credentials, keys, and local secrets out of committed files.

The USRP sample data plane should stay on the direct USRP path. Tailscale is acceptable for control, SSH, status, and logs only.

## Validated Metrics

All runs below used the Cockpit `/api/run-inference-batch` behavior, IQ direct, Docker TX, board RX, remote-dir `.npz`, handwritten TVM, big.LITTLE, and security channel disabled for performance measurement.

| Batch | Count | Result | TVM median | TVM p95 | IQ median | IQ p95 | Notes |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `batch-1783671744-300` | 300 | `300/300`, fallback `0` | `241.04 ms` | `243.75 ms` | `171.54 ms` | `363.50 ms` | Container/Cockpit path recovered. |
| `batch-1783672570-50` | 50 | `50/50`, fallback `0` | `241.58 ms` | `248.65 ms` | `169.31 ms` | `245.63 ms` | `RX_ARM_WAIT_MS=150`; no extra retry records. |
| `batch-1783672642-300` | 300 | `300/300`, fallback `0` | `241.93 ms` | `248.18 ms` | `170.84 ms` | `332.98 ms` | Candidate 150 ms arm-wait gate. |
| `batch-1783674212-50` | 50 | `50/50`, fallback `0` | `238.58 ms` | `241.01 ms` | `182.34 ms` | `251.66 ms` | Smoke after RX session close shutdown fix. |
| `batch-1783674397-300` | 300 | `300/300`, fallback `0` | `238.87 ms` | `245.54 ms` | `175.28 ms` | `337.46 ms` | Latest gate; session close fix is safe but did not remove 300-image tails. |

Reference QPSK transport is about `2961.78 ms/image`. IQ direct is far faster than QPSK on the data plane. The visible reconstruction cadence is still mostly set by TVM, currently around `239-245 ms` per inference sample.

Latest `batch-1783674397-300` stage medians:

```text
tx_control_ms        23.61
rx_arm_ms            24.02
rx_capture_ms        90.25
rx_wait_ms           40.83
remote_decode_ms     60.23
board_reported_decode_ms 43.54
total_transport_ms  175.34
```

## Current Profile To Preserve

Use this profile unless you are running an explicit experiment:

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
REMOTE_USRP_DECODE_PYTHON=/home/user/venv/bin/python
OPENAMP_DEMO_REMOTE_DECODE_PYTHON=/home/user/venv/bin/python
ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir
ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal
RX_ARM_WAIT_MS=150
RX_STOP_WAIT_MS=8000
ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0
ANALOG_RX_WAIT_TIMEOUT_SEC=1.0
ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC=1.0
ANALOG_RX_ARM_STATUS_TIMEOUT_SEC=0.5
ANALOG_RX_ARM_STATUS_POLL_SEC=0.025
ANALOG_PIPELINE_DEPTH=1
ANALOG_PRECONNECT_CONTROL=1
ANALOG_RX_SESSION_CONTROL=1
ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=0
PERSISTENT_RX_TX_DELAY=0
OPENAMP_TVM_BATCH_RUNNER=biglittle
```

Keep streaming TVM, depth-2 overlap, tmpfs output, `.npy` output, soft completion, and burst-miss retries opt-in. Earlier runs showed some of these improve a local median while making the 300-image tail or total wall time worse.

## Clean Restart Procedure

Run from `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`.

1. Stop Cockpit backend and USRP helpers.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

2. Clear stale board-side TX/RX servers through Docker. Set board host/user/password only in the local shell environment before running this.

```powershell
docker run --rm -e SSHPASS=$env:REMOTE_PASS iccomp-usrp-tx:latest `
  sshpass -e ssh -p $env:REMOTE_SSH_PORT `
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null `
  "$env:REMOTE_USER@$env:REMOTE_HOST" `
  'pgrep -f "/home/user/USRP292x/[O]taRxPersistentServer" | xargs -r kill || true; pgrep -f "/home/user/USRP292x/[O]taTxPersistentServer" | xargs -r kill || true'
```

3. Start the backend with the profile above, then start USRP control and run the Cockpit-equivalent batch.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":300,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

If the UI shows `board status endpoint unavailable` or connection refused, the backend or board-status helper is not running on the expected port. Fully stop the inherited state and restart from step 1.

## What Changed In FINAL WORK

- Cockpit startup now preserves IQ/USRP/Docker timing variables instead of falling back to prerecorded or TCP defaults.
- Docker TX uses `OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET`, so `/host_workspace` paths work inside the container.
- USRP startup can discover the local 300-latent cache for `transport_mode=usrp`.
- Persistent RX supports configurable `--arm-wait-ms` and `--stop-wait-ms`.
- RX `STOP` waits for the worker before replying, reducing stale `capture_already_running` failures.
- The Python runner uses same-session RX control and shuts the socket down before closing it, so the RX server sees EOF promptly after a timeout.
- RX control responses now carry additive server-side timings for arm wait, drain, stream command issue, receive loop, STOP command, and STOP wait. The Python runner records them as `rx_server_*_wall_sec` and aggregates them in `iq_stage_benchmark`.
- Remote decode returns minimal worker responses while keeping full `decode_summary.json` on the board.
- Docker wrappers default to `RX_ARM_WAIT_MS=150` and forward the IQ/USRP environment needed by Cockpit.

## Known Tail Issues

Latest 300-image gate `batch-1783674397-300` produced `305` stage records for `300` images. Recovered retry images were `2`, `46`, `144`, and `153`; image `46` needed two retries.

Main tail classes:

- RX WAIT timeout after partial capture: image `153` timed out after a `WAIT timeout=1.0` with only part of the expected samples written. This is the clearest remaining RX state-machine issue.
- RX arm/capture long tail without decode failure: image `186` spent about `4.0 s` in RX arm/capture and still decoded successfully.
- Decode-worker wait longer than board-reported decode: image `215` spent about `2.0 s` runner-side while board-reported decode was about `44 ms`.
- Low/no-sync retries: images such as `2`, `46`, and `144` recovered by ARQ retry.

The session-close shutdown fix is worth keeping for cleanup hygiene, but it did not improve the latest 300-image p95. The next real optimization should instrument or fix RX readiness and WAIT timeout recovery before trying more overlap.

## Security State

For speed runs, the runtime security channel was disabled while config still showed authentication settings present (`auth_enabled=true`, `sig_policy=DUAL_REQUIRED`). Do not put ML-KEM or signature work in the per-image hot path. Measure security-on overhead separately, and keep it session-level. If security-on adds more than about `5%` after setup, document the delta instead of mixing it into the performance baseline.

## Next Work

1. Keep QPSK frozen. Check `git diff -- USRP292x/RunQpskFileBatchSpoolArq.py` before and after IQ changes.
2. Re-run a 50-image IQ direct smoke and inspect the new `rx_server_*_ms` benchmark fields before changing behavior.
3. Improve WAIT-timeout recovery. A timeout after partial samples should cancel/drain deterministically before the next ARQ attempt.
4. Separate board decode compute from worker/control wait. The reported decode time is usually around `44 ms`, but runner-side waits can still reach seconds.
5. Only revisit double buffering or streaming TVM after RX state transitions are deterministic. Previous overlap experiments caused contention.
6. Re-run a 300-image gate after any timing behavior change. Do not promote a profile from a single short run.

## Verification Before Commit

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m pytest docker/test_demo_scripts.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_discovers_usrp_latent_dir Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_keeps_usrp_runtime_env Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_usrp_local_tx_server_can_start_from_docker_image Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::test_start_remote_rx_server_passes_arm_wait_ms -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\usrp_runtime.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\server.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

Last code verification before this handoff:

```text
USRP292x/test_analog_latent_link.py: 84 passed
docker/test_demo_scripts.py: passed after RX_ARM_WAIT_MS=150 default update
targeted server tests: passed
py_compile: passed
QPSK runner diff: empty
git diff --check: exit 0, line-ending warnings only
```

Latest diagnostic-code verification after adding `rx_server_*` fields:

```text
USRP292x/test_analog_latent_link.py: 87 passed
python -m py_compile USRP292x\RunAnalogLatentBatch.py: passed
```

Remove generated reports, raw logs, and run artifacts before committing unless the task explicitly requires preserving them as evidence.
