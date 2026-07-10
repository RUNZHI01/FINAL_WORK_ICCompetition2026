# 2026-07-10 IQ Direct Handoff

## Current Conclusion

Branch: `feat/restore-248`.

Latest implementation checkpoint before this handoff:

```text
7baebf8 perf: expose rx server timing fields
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
| `batch-1783676258-50` | 50 | `50/50`, fallback `0` | `242.22 ms` | `243.93 ms` | `165.42 ms` | `251.70 ms` | First live run with `rx_server_*` timing fields. |
| `batch-1783678227-50` | 50 | `50/50`, fallback `0` | `240.61 ms` | `251.31 ms` | `201.17 ms` | `1207.08 ms` | Rejected `ANALOG_RX_TAIL_SEC=0.045`; server receive fell to `58.61 ms`, but RX arm/capture tail worsened. |
| `batch-1783678924-50` | 50 | `50/50`, fallback `0` | `239.96 ms` | `245.99 ms` | `183.51 ms` | `338.34 ms` | No mid-run status polling; not better. Server capture stayed near `64 ms`, while runner-side RX/decode response wait expanded. |
| `batch-1783680558-50` | 50 | `50/50`, fallback `0` | `240.13 ms` | `244.14 ms` | `207.72 ms` | `334.49 ms` | First run with derived overhead fields. Image 29 recovered after no-sync; image-level IQ max was `1129.46 ms`. |
| `batch-1783681389-50` | 50 | `50/50`, fallback `0` | `240.73 ms` | `245.35 ms` | `174.91 ms` | `269.24 ms` | Decode-failure STOP/drain cleanup did not regress the normal path; no retry occurred in this run. |

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

Instrumentation smoke `batch-1783676258-50` showed the normal RX path is not spending time in server-side drain or stream-command issue:

```text
rx_server_arm_wait_ms median 0.66, p95 0.89
rx_server_drain_ms median 0.03, p95 0.03
rx_server_stream_cmd_ms median 0.16, p95 0.22
rx_server_receive_ms median 63.61, p95 63.63
rx_server_capture_ms median 64.27, p95 64.40
```

This means the normal-path RX floor is currently dominated by capture duration, especially `ANALOG_RX_TAIL_SEC=0.05`, not by server pre-arm drain. Smaller RX tail values were re-tested and rejected: `0.04` hit a no-sync retry in a 5-image sanity run, and `0.045` completed 50 images but worsened median and p95.

Derived-overhead validation `batch-1783680558-50` showed server capture remained stable (`64.21/64.35 ms` median/p95), while `rx_capture_control_overhead_ms` p95 was `140.31 ms` and `remote_decode_response_overhead_ms` p95 was `128.12 ms`. The next fix should target RX arm/capture readiness and retry cleanup before decode-response tuning.

Decode-failure RX cleanup validation `batch-1783681389-50` stayed all-pass with IQ median/p95/max `174.91/269.24/347.72 ms`. This run had no retry records, so it proves the normal path stayed intact; the retry-path benefit still needs confirmation when the next no-sync or decode failure occurs.

## Current Profile To Preserve

Use this profile unless you are running an explicit experiment:

```text
OPENAMP_SSH_RUNNER=paramiko
SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1
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
ANALOG_REMOTE_DECODE_WORKER=1
ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir
ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal
ANALOG_REMOTE_CLEANUP_MODE=skip
ANALOG_RX_TAIL_SEC=0.05
ANALOG_RX_POST_QUANTIZE=0
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
docker run --rm --env SSHPASS iccomp-usrp-tx:latest `
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
- `iq_stage_benchmark` now adds derived `rx_capture_control_overhead_ms` and `remote_decode_response_overhead_ms` as diagnostic estimates for runner-side capture/decode response wait beyond server capture and board-reported decode time.
- After a successful RX `WAIT`, decode/no-sync failures now issue `STOP` and drain the RX server before ARQ retry.
- If batch-level SSH ControlMaster startup fails, the IQ runner now disables per-image ControlMaster retries. This prevents a missing `SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1` from adding about `10 s/image` on Windows/password SSH paths.
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
2. Keep `ANALOG_RX_TAIL_SEC=0.05`. `0.04` and `0.045` are rejected for the current RF/control profile.
3. Design RX arm/capture health handling. `batch-1783680558-50` showed stable server capture, but runner-side capture/control overhead and no-sync retry still raise image-level max. Decode/no-sync failure cleanup is now in place; confirm STOP timing fields on the next retry record.
4. Improve WAIT/no-sync recovery. A timeout or no-sync after partial samples should cancel/drain deterministically before the next ARQ attempt.
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
