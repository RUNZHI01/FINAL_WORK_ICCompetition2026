# Cockpit USRP/QPSK TVM Runbook

本记录用于 Windows cockpit desktop 现场复现。Bash/SSH 优先走 Docker；需要本机 Bash 时使用 Git Bash，不使用 WSL。

## Host Environment

```powershell
$env:OPENAMP_BASH="E:\Software\Scoop\apps\git\current\bin\bash.exe"
$env:GIT_BASH=$env:OPENAMP_BASH
$env:OPENAMP_SSH_RUNNER="local"
$env:SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER="1"
$env:OPENAMP_USRP_TX_RUNNER="docker"
$env:OPENAMP_USRP_TX_DOCKER_IMAGE="iccomp-usrp-tx:latest"
$env:OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET="/host_workspace"
$env:REMOTE_HOST="100.121.87.73"
$env:REMOTE_USER="user"
$env:REMOTE_PASS="user"
$env:REMOTE_SSH_PORT="22"
$env:REMOTE_USRP_RX_DIR="/home/user/cockpit_usrp_rx"
$env:REMOTE_USRP_DECODE_PYTHON="/home/user/venv/bin/python"
$env:OPENAMP_DEMO_REMOTE_DECODE_PYTHON="/home/user/venv/bin/python"
$env:JSCC_LINK_MODE="qpsk"
$env:ANALOG_SPS="16"
$env:ANALOG_AMPLITUDE="24000"
$env:ICCOMP_COCKPIT_PROFILE="tvm250-prerecorded"
$env:OPENAMP_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_DEMO_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_TVM_BATCH_EXIT_GRACE_SEC="0.5"
$env:MLKEM_AUTH_ENABLED="0"
```

TX bash/USRP 发送在 Docker 中运行；Windows 到板端 SSH 使用本机 `sshpass`，因为 Docker 容器通常拿不到 Tailscale 路由。板端 decode 使用 `/home/user/venv/bin/python`；TVM 重建使用 big.LITTLE wrapper 和 `/home/user/anaconda3/envs/tvm310_safe/bin/python`。

## Start Cockpit Backend

```powershell
python Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py --host 127.0.0.1 --port 8079
```

写入板端会话：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8079/api/session/board-access `
  -ContentType "application/json" `
  -Body '{"host":"100.121.87.73","user":"user","password":"user","port":"22","transport_mode":"usrp","remote_usrp_rx_dir":"/home/user/cockpit_usrp_rx","jscc_link_mode":"qpsk"}'
```

## Verified Milestones

- Prerecorded TVM big.LITTLE path: `openamp3_handwritten_mean4_v7_big_little_current_20260709_052201.json`, 300/300, median 243.30 ms, mean 252.91 ms, p95 311.88 ms. This is the 250 ms reproduction reference.
- USRP/QPSK + TVM big.LITTLE path after backend restart with `user/user`: `batch-1783549789-1`, 1/1 success, fallback 0; TVM inference 281.527 ms for the single online sample. Raw log: `openamp3_usrp_1783549789_current_20260709_063102.raw.log`.
- USRP/QPSK + TVM big.LITTLE path: `batch-1783548059-1`, 1/1 success; TVM inference 284.345 ms for the single online sample, artifact SHA matched, affinity applied with inferencer on big core `[2]` and pre/post on little cores `[0,1]`.
- Earlier QPSK evidence: `batch-1783545491-1`, 1/1 transport pass, byte/bit errors 0, SHA matched.
- USRP TVM stage now consumes stdout/stderr concurrently, recovers complete summaries from stale SSH wrappers, and accepts statusless complete summaries.
- When `INFERENCE_CURRENT_CMD` selects `run_big_little_pipeline.sh`, USRP TVM uses the big.LITTLE wrapper with the current run-specific RX directory; verified affinity is big core `[2]`, little cores `[0,1]`.
- IQ direct remains experimental, not the default. The current live OTA profile is `ANALOG_SPS=16`, `ANALOG_AMPLITUDE=24000`: `cockpit_iq_sps16_amp24000_retry_20260709_064549` passed strict decode with sync metric `0.981`, estimated SNR `14.35 dB`, latent MSE `17337`, detected airtime `65.152 ms`, and decode wall time `1.42 s`. After removing remote-pull TX/manifest staging and the extra remote `mkdir`, full cockpit/backend IQ-direct + TVM run `batch-1783552955-1` completed 1/1 with fallback 0, TVM inference `286.970 ms`, radio airtime `65.152 ms`, decode `1.895 s`, and transport wall `12.125 s`; the run produced no `remote_mkdir.log`, `remote_push_tx.log`, or `remote_push_manifest.log`. IQ quality is still unstable (sync `0.865`, estimated SNR `-3.76 dB`, latent MSE `1.12e6`), so keep QPSK as the reliable default until IQ quality and decode overhead are fixed.
- Earlier IQ direct amplitude-only evidence remains useful for regression: `batch-1783548778-1` with amplitude 24000 showed high initial sync (`0.974`) but bad payload quality (estimated SNR about -3 dB, latent MSE about `9.4e5`). The decoder now rejects a CFO estimate when it degrades an already valid sync peak and records `cfo_estimator=.../rejected`.

## Useful Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8079/api/health
Invoke-RestMethod http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 12
```

USRP run artifacts are under `USRP292x/qpsk_batch_spool_arq_runs/`; board-side decoded RX inputs are under `/home/user/cockpit_usrp_rx/`.
