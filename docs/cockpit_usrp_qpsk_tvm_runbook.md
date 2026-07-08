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
- USRP/QPSK + TVM big.LITTLE path: `batch-1783548059-1`, 1/1 success; TVM inference 284.345 ms for the single online sample, artifact SHA matched, affinity applied with inferencer on big core `[2]` and pre/post on little cores `[0,1]`.
- Earlier QPSK evidence: `batch-1783545491-1`, 1/1 transport pass, byte/bit errors 0, SHA matched.
- USRP TVM stage now consumes stdout/stderr concurrently, recovers complete summaries from stale SSH wrappers, and accepts statusless complete summaries.
- When `INFERENCE_CURRENT_CMD` selects `run_big_little_pipeline.sh`, USRP TVM uses the big.LITTLE wrapper with the current run-specific RX directory; verified affinity is big core `[2]`, little cores `[0,1]`.
- IQ direct remains experimental, not the default. With `remote-pull`, RX/TX and local decode are reachable, but true OTA capture `batch-1783547715-1` produced low sync/SNR (`sync_metric` about 0.09, estimated SNR about -3 dB), so keep QPSK as the reliable live data plane.

## Useful Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8079/api/health
Invoke-RestMethod http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 12
```

USRP run artifacts are under `USRP292x/qpsk_batch_spool_arq_runs/`; board-side decoded RX inputs are under `/home/user/cockpit_usrp_rx/`.
