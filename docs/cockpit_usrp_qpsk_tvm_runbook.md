# Cockpit USRP/QPSK/IQ TVM Runbook

本记录用于 Windows cockpit desktop 现场复现。Bash/SSH 优先走 Docker；需要本机 Bash 时使用 Git Bash，不使用 WSL。

## Host Environment

```powershell
$env:OPENAMP_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:GIT_BASH=$env:OPENAMP_BASH
$env:OPENAMP_SSH_RUNNER="docker"
$env:OPENAMP_SSH_DOCKER_IMAGE="iccomp-usrp-tx:latest"
$env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER="1"
$env:OPENAMP_USRP_TX_RUNNER="docker"
$env:OPENAMP_USRP_TX_DOCKER_IMAGE="iccomp-usrp-tx:latest"
$env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET="/host_workspace"
$env:REMOTE_HOST="100.121.87.73"
$env:REMOTE_USER="user"
$env:REMOTE_PASS="user"
$env:REMOTE_SSH_PORT="22"
$env:REMOTE_USRP_RX_DIR="/home/user/cockpit_usrp_rx"
$env:REMOTE_RX_RUN_ROOT="/tmp/usrp292x_remote_runs"
$env:REMOTE_USRP_PROJECT_ROOT="/home/user"
$env:REMOTE_USRP_DECODE_PYTHON="/home/user/venv/bin/python"
$env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON="/home/user/venv/bin/python"
$env:JSCC_LINK_MODE="iq-direct"
$env:ANALOG_SPS="16"
$env:ANALOG_AMPLITUDE="24000"
$env:ANALOG_RX_TAIL_SEC="0.12"
$env:ANALOG_REMOTE_CLEANUP_MODE="async"
$env:ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS="4096"
$env:ICCOMP_COCKPIT_PROFILE="tvm250-prerecorded"
$env:OPENAMP_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_DEMO_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_TVM_BATCH_EXIT_GRACE_SEC="0.5"
$env:MLKEM_AUTH_ENABLED="0"
```

TX bash/USRP 发送在 Docker 中运行；Windows 到板端 SSH 也优先走 `OPENAMP_SSH_RUNNER=docker`，避免 Git Bash/OpenSSH 子进程卡住。板端用户名和密码均为 `user`，板端 IQ decode 使用 `/home/user/venv/bin/python`；TVM 重建使用 big.LITTLE wrapper 和 `/home/user/anaconda3/envs/tvm310_safe/bin/python`。

## Start Cockpit Backend

```powershell
python Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py --host 127.0.0.1 --port 8079
```

写入板端会话：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8079/api/session/board-access `
  -ContentType "application/json" `
  -Body '{"host":"100.121.87.73","user":"user","password":"user","port":"22","transport_mode":"usrp","remote_usrp_rx_dir":"/home/user/cockpit_usrp_rx","jscc_link_mode":"iq-direct"}'
```

## Verified Milestones

- 2026-07-09 live cockpit restart: after a clean backend/control restart, `OPENAMP_SSH_RUNNER=docker` reliably auto-started RX `100.121.87.73:29220` and TX `127.0.0.1:29221`. IQ remote-decode asset sync reported `status=current`, and the remote decode command used `/home/user/venv/bin/python`.
- IQ direct remote-decode now uses board-side decode with `ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS=4096`. Live run `usrp-1783563177` completed the first frame with `frame_complete=true`, sync metric `0.8929`, RX capture `0.383 s`, TX send `0.055 s`, and `sync_search_window_enabled=true`. This proves the long-capture 37 s decode failure mode is removed; remaining latency is dominated by per-frame SSH/docker setup, remote file staging, and Python decode startup.
- Prerecorded TVM big.LITTLE path: `openamp3_handwritten_mean4_v7_big_little_current_20260709_052201.json`, 300/300, median 243.30 ms, mean 252.91 ms, p95 311.88 ms. This is the 250 ms reproduction reference.
- Cockpit USRP/IQ-direct + TVM big.LITTLE path after status-poll isolation: `batch-1783557824-1`, 1/1 success, fallback 0; TVM inference `262.916 ms`, artifact SHA matched, inferencer on big core `[2]`, pre/post on little cores `[0,1]`, PSNR `37.0445`, SSIM `0.97494`. The current cockpit `/api/batch-state` updates Compare/result state for this run.
- Status polling no longer starts remote SSH refreshes while the session is in USRP transport mode. After loading this fix, repeated `/api/system-status` calls returned about `200-274 ms` and reported telemetry/USRP/position probes as `deferred`.
- USRP/QPSK + TVM big.LITTLE path after backend restart with `user/user`: `batch-1783549789-1`, 1/1 success, fallback 0; TVM inference 281.527 ms for the single online sample. Raw log: `openamp3_usrp_1783549789_current_20260709_063102.raw.log`.
- USRP/QPSK + TVM big.LITTLE path: `batch-1783548059-1`, 1/1 success; TVM inference 284.345 ms for the single online sample, artifact SHA matched, affinity applied with inferencer on big core `[2]` and pre/post on little cores `[0,1]`.
- Earlier QPSK evidence: `batch-1783545491-1`, 1/1 transport pass, byte/bit errors 0, SHA matched.
- USRP TVM stage now consumes stdout/stderr concurrently, recovers complete summaries from stale SSH wrappers, and accepts statusless complete summaries.
- When `INFERENCE_CURRENT_CMD` selects `run_big_little_pipeline.sh`, USRP TVM uses the big.LITTLE wrapper with the current run-specific RX directory; verified affinity is big core `[2]`, little cores `[0,1]`.
- IQ direct remains experimental for physical quality. With `ANALOG_RX_TAIL_SEC=0.12` and async remote cleanup, `batch-1783557031-1` completed 1/1 with TVM `258.279 ms`, radio airtime `65.152 ms`, decode `924.9 ms`, cleanup `21.94 ms`, and transport wall `5.446 s`. The later cockpit-visible run `batch-1783557824-1` kept TVM near target at `262.916 ms`, but RX raw waveform pull spiked to `19.07 s`. IQ sync succeeds but payload quality remains poor (`sync_metric=0.596`, estimated SNR `-2.97 dB`, latent MSE `9.33e5`), so QPSK remains the reliable fallback and IQ-direct needs server-side/cropped decode to meet the “far below TVM” transport goal.
- Earlier IQ direct amplitude-only evidence remains useful for regression: `batch-1783548778-1` with amplitude 24000 showed high initial sync (`0.974`) but bad payload quality (estimated SNR about -3 dB, latent MSE about `9.4e5`). The decoder now rejects a CFO estimate when it degrades an already valid sync peak and records `cfo_estimator=.../rejected`.

## Useful Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8079/api/health
Invoke-RestMethod http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 12
```

USRP run artifacts are under `USRP292x/qpsk_batch_spool_arq_runs/`; board-side decoded RX inputs are under `/home/user/cockpit_usrp_rx/`.
