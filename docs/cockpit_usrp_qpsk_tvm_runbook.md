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
$env:ANALOG_SPS="2"
$env:ANALOG_AMPLITUDE="6000"
$env:ANALOG_RX_TAIL_SEC="0.05"
$env:ANALOG_RX_POST_QUANTIZE="0"
# Optional write-path experiment only; not the recommended default yet.
# $env:ANALOG_REMOTE_DECODED_FORMAT="npy"
# Use board access remote_usrp_rx_dir="/dev/shm/cockpit_usrp_rx" to test tmpfs.
$env:ANALOG_REMOTE_CLEANUP_MODE="skip"
$env:ANALOG_REMOTE_DECODE_WORKER="1"
$env:ANALOG_REMOTE_DECODE_RESULT_MODE="remote-dir"
$env:ANALOG_REMOTE_DECODE_ASSET_SYNC_TIMEOUT_SEC="90"
$env:ANALOG_DECODE_PIPELINE_WARMUP="1"
$env:ANALOG_PIPELINE_DEPTH="2"
$env:ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS="4096"
$env:ANALOG_SYNC_PROFILE="fast-first"
$env:ANALOG_FAST_SYNC_CANDIDATES="4"
$env:ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS="1024"
$env:ANALOG_FALLBACK_SYNC_CANDIDATES="12"
$env:ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS="4096"
$env:ANALOG_MIN_SYNC_METRIC="0.05"
$env:ANALOG_ROBUST_SYNC="0"
$env:MLKEM_USRP_MAX_ARQ_ROUNDS="5"
$env:USRP_MAX_ARQ_ROUNDS="5"
$env:ANALOG_RETRY_ON_BURST_MISS="1"
$env:ANALOG_RETRY_ON_LOW_SYNC="1"
$env:ANALOG_LOW_SYNC_RETRY_THRESHOLD="0.08"
$env:OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="0"
$env:ICCOMP_COCKPIT_PROFILE="tvm250-prerecorded"
$env:OPENAMP_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_DEMO_TVM_BATCH_RUNNER="biglittle"
$env:OPENAMP_TVM_BATCH_EXIT_GRACE_SEC="0.5"
$env:MLKEM_AUTH_ENABLED="0"
Remove-Item Env:OPENAMP_IQ_STREAMING_TVM -ErrorAction SilentlyContinue
Remove-Item Env:USRP_IQ_STREAMING_TVM -ErrorAction SilentlyContinue
Remove-Item Env:ANALOG_PRECONNECT_CONTROL -ErrorAction SilentlyContinue
Remove-Item Env:ANALOG_RX_SESSION_CONTROL -ErrorAction SilentlyContinue
Remove-Item Env:ANALOG_REMOTE_DECODE_REQUEST_TIMEOUT_SEC -ErrorAction SilentlyContinue
Remove-Item Env:ANALOG_REMOTE_DECODE_RESTART_ON_TIMEOUT -ErrorAction SilentlyContinue
```

TX bash/USRP 发送在 Docker 中运行；Windows cockpit 到板端 SSH 默认也走 Docker runner，避免 WSL/Git Bash shell 状态污染。板端用户名和密码均为 `user`，板端 IQ decode 使用 `/home/user/venv/bin/python`；TVM 重建使用 big.LITTLE wrapper 和 `/home/user/anaconda3/envs/tvm310_safe/bin/python`。不要默认设置 `OPENAMP_IQ_STREAMING_TVM`、`ANALOG_PRECONNECT_CONTROL`、short STOP、short RX WAIT 或 remote decode request timeout/restart envs：这些路径已有实测数据，只保留给定向实验。

2026-07-11 当前 Cockpit IQ 直传复现 profile 覆盖早期环境块中的旧建议：使用 Docker SSH/TX、`REMOTE_RX_RUN_ROOT=/tmp/usrp292x_remote_runs`、`ANALOG_RX_TAIL_SEC=0.040`、`ANALOG_RX_POST_QUANTIZE=0`、`ANALOG_REMOTE_DECODED_FORMAT=npy`、`ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal`、`ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1`、`ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05`、`ANALOG_RX_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16`、`ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1`、`ANALOG_RX_SC16_MMAP=1`、`ANALOG_RX_CLIPPING_DECIMATION=8`、`MLKEM_USRP_MAX_ARQ_ROUNDS=5`、`ANALOG_RETRY_ON_BURST_MISS=1`、`ANALOG_RETRY_ON_LOW_SYNC=1`、`ANALOG_LOW_SYNC_RETRY_THRESHOLD=0.08`、`RX_ARM_WAIT_MS=500`、`RX_STOP_WAIT_MS=8000`、`ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0`、`ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5`。不要启用 tmpfs、publish-event、worker timeout/restart 或 streaming TVM，除非是在做单独 A/B。

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

## Latest 300-Image Cockpit Evidence

These runs were started through the same backend path used by the cockpit desktop test button: `POST /api/session/board-access` to select the link mode, then `POST /api/run-inference-batch` with `{"count":300,"allow_preflight_degraded":true}`. ML-KEM/auth was configured on the board but the crypto toggle was off for the performance run.

最新一次 `cockpit_usrp_usrp-1783772592` 不是有效 gate：捕获请求跑完 300 张，但 `image_0163` 因 low sync 失败，只产出 299 个 decoded latent。失败日志显示 sync metric 约 `0.0324`，低于 `ANALOG_MIN_SYNC_METRIC=0.05`。这说明 UI 的 fallback 是真实 RF/IQ 弱同步，不是前一次修复过的状态刷新或 TCP 10061 问题。ARQ5 + low-sync retry 已经作为新默认写入代码，但还需要重启后跑新的 20/300 张回归。

| Link | Batch | Result | Transport metric | RF airtime | Decode / merge | TVM big.LITTLE |
|---|---:|---:|---:|---:|---:|---:|
| IQ direct, RX health extra-attempt accepted profile | `batch-1783753807-300` | 300/300, fallback 0 | median `172.43 ms`, p95 `268.58 ms`, max `11461.36 ms` | `9.58 ms` class | image `48` recovered on attempt 4; remaining tails are RX/decode-worker outliers | median `240.38 ms`, p95 `242.90 ms`, max `256.28 ms` |
| IQ direct, current 2026-07-11 profile with probe-id/precreate retry | `batch-1783730551-300` | 300/300, fallback 0 | median `155.66 ms`, p95 `274.33 ms`, max `11124.64 ms` | `9.58 ms` class | `.npy`, minimal/summary-only response, soft probes with `probe_id`; remaining tails are board publish/file-visibility | median `241.69 ms`, p95 `244.45 ms`, max `280.68 ms` |
| IQ direct, async stall-snapshot diagnostic | `batch-1783642640-300` | 300/300, fail 0 | median `190.29 ms`, p95 `946.07 ms` | `9.58 ms` | mixed RX wait and decode-worker stalls; publish p95 `1.79 ms` | median `240.79 ms`, p95 `243.97 ms` |
| IQ direct, fast-first sync recommended | `batch-1783626884-300` | 300/300, fail 0 | median `182.28 ms`, p95 `372.96 ms` | `9.58 ms` | decode median `62.96 ms` | median `242.41 ms`, p95 `245.77 ms` |
| IQ direct, previous sequential-sync baseline | `batch-1783625337-300` | 300/300, fail 0 | median `189.10 ms`, p95 `642.66 ms` | `9.58 ms` | decode median `68.47 ms` | median `242.16 ms`, p95 `244.89 ms` |
| IQ direct, streaming TVM opt-in experiment | `batch-1783624303-300` | 300/300, fail 0 | median `338.90 ms`, p95 `694.20 ms` | `9.58 ms` | decode median `158.52 ms` | median `248.29 ms`, p95 `322.37 ms` |
| IQ direct, earlier baseline | `batch-1783610422-300` | 300/300, fail 0 | median `202.54 ms`, mean `311.21 ms`, p95 `598.89 ms` | `9.58 ms` | decode median `63.96 ms` | median `241.21 ms`, p95 `243.76 ms` |
| QPSK | `batch-1783610673-300` | 300/300, fail 0 | `2961.78 ms/image` | mean `48.02 ms` | decode command mean `2295.96 ms`, merge mean `14.23 ms` | median `240.06 ms`, p95 `242.88 ms` |

IQ direct used `remote-dir`: the board decoder wrote flat latent files to `/home/user/cockpit_usrp_rx/<run>_rx`, and TVM consumed that directory directly. In the recommended 2026-07-10 profile, inference stayed pending while transport advanced to `300/300`; TVM started only after IQ decode completed. The streaming TVM experiment did overlap transport and inference, but total wall worsened from `161.17 s` to `233.76 s`, so the overlap path is opt-in only. The QPSK run is now a stable fallback rather than a single-frame proof, but it is still about `16.3x` slower than the latest IQ direct median transport.

`batch-1783642640-300` was a diagnostic run with `ANALOG_REMOTE_STALL_SNAPSHOT=1`, not a new recommended default. It stayed all-pass and TVM remained in the 240 ms band, but transport p95 rose because rare RX wait/capture stalls and decode-worker request stalls appeared. The snapshot launcher is asynchronous, so the captured logs did not block the decode worker; use a higher snapshot limit than `3` if late-batch outliers need board CPU/IO evidence.

2026-07-10 control diagnostics added `rx_arm_ms` and `rx_wait_ms` to the IQ stage benchmark. In `batch-1783629764-50`, transport median was `206.51 ms`, p95 `308.24 ms`, with `tx_control_ms` median `31.42`, `rx_arm_ms` median `35.27`, and `rx_wait_ms` median `30.75`. The opt-in `ANALOG_PRECONNECT_CONTROL=1` run `batch-1783631315-50` stayed all-pass and improved transport p95 to `290.16 ms`, but median stayed `207.08 ms`; keep it experimental rather than default.

The opt-in `ANALOG_RX_SESSION_CONTROL=1` run `batch-1783632169-50` also stayed all-pass, but it worsened transport to median `287.71 ms`, p95 `462.23 ms`, and max `1138.94 ms`. The C++ RX/TX persistent servers can now accept multiple commands on one connection, but the recommended cockpit profile must leave this env unset.

The low-sync early retry path adds `ANALOG_RETRY_ON_LOW_SYNC=1` and `ANALOG_LOW_SYNC_RETRY_THRESHOLD=<metric>`. It prevents obviously bad fast-sync frames from entering slow fallback decode when another ARQ capture remains. Early 50-image testing with threshold `0.05` stayed all-pass, but a later 300-image validation failed `299/300`. After the separate weak-sync incident in `cockpit_usrp_usrp-1783772592`, the current Cockpit default promotes low-sync retry with ARQ5 and threshold `0.08`; treat the older result as diagnostic history, not the current recommendation.

The opt-in decode-worker timeout path adds `ANALOG_REMOTE_DECODE_REQUEST_TIMEOUT_SEC=1.0` and `ANALOG_REMOTE_DECODE_RESTART_ON_TIMEOUT=1`. The 50-image validation `batch-1783635469-50` stayed all-pass but did not trigger a timeout. The 300-image validation `batch-1783635568-300` stayed all-pass and triggered 3 timeouts, but transport p95 worsened to `865.77 ms` and max to `13835.21 ms` because synchronous worker restart and RX stalls still propagated through the depth-2 queue. Newer runner summaries expose `remote_decode_restart_ms` to split restart cost from decode request time. Keep this diagnostic off in the recommended profile.

`ANALOG_PIPELINE_DEPTH=1` is also diagnostic only. Batch `batch-1783636039-300` stayed 300/300 and reduced transport p95 to `318.43 ms`, but total transport wall rose to `104.43 s`; depth 2 remains the throughput profile. Do not reduce `ANALOG_RX_TAIL_SEC` below `0.05`: `0.02` failed `28/50` in `batch-1783636392-50`, while `0.04` stayed all-pass in `batch-1783636541-50` but worsened transport median to `241.27 ms` and p95 to `1169.05 ms`.

The recommended IQ profile now sets `ANALOG_RX_POST_QUANTIZE=0`. Batch `batch-1783638234-300` stayed 300/300 with TVM median `241.28 ms`, p95 `244.10 ms`, PSNR `37.0445`, SSIM `0.97494`, transport median `186.83 ms`, p95 `351.67 ms`, and max `6368.37 ms`. This avoids writing unused `quant/scale/zero_point` arrays to the remote-dir `.npz`; the TVM loader consumes the `latent` array directly.

`ANALOG_REMOTE_DECODED_FORMAT=npy` is now part of the Cockpit IQ profile. On `/home/user/cockpit_usrp_rx`, `batch-1783640049-300` stayed 300/300 with TVM median `241.49 ms`, p95 `248.64 ms`, transport median `189.19 ms`, and p95 `383.88 ms`; `.npy` publish p95 was `1.64 ms`, but one board filesystem stall still made write max `3337.46 ms`. Moving only the decoded latent directory to tmpfs with board access `remote_usrp_rx_dir=/dev/shm/cockpit_usrp_rx` removed that write stall, but it is not the default because RF/RX stalls and no-sync retries still pushed transport p95 to `1013.67 ms` in that long run.

Compared with the older QPSK notes below, the QPSK path improved from tens of seconds per image to about 3 seconds per image:

| QPSK evidence | Samples | Transport | TVM inference |
|---|---:|---:|---:|
| `batch-1783545491-1` | 1 | `79.46 s/image` | raw log `438.42 ms` |
| `batch-1783548059-1` | 1 | `21.98 s/image` | `284.345 ms` |
| `batch-1783549789-1` | 1 | `48.64 s/image` | `281.527 ms` |
| `batch-1783610673-300` | 300 | `2.962 s/image` | median `240.06 ms` |

## IQ Direct Current Flow

1. Cockpit stores the board session with `transport_mode=usrp`, `jscc_link_mode=iq-direct`, and `remote_usrp_rx_dir=/home/user/cockpit_usrp_rx`.
2. The test button calls `/api/run-inference-batch`; the backend prepares the same 300 latent inputs and starts the transport stage before TVM.
3. `usrp_runtime.py` selects `USRP292x/RunAnalogLatentBatch.py` instead of the QPSK runner. Host-side TX runs in Docker; board-side RX runs under the board user environment.
4. The data plane is USRP RF only. Tailscale is used for cockpit API, SSH setup, TX/RX control sockets, and status/log collection, not for raw IQ payload movement.
5. For each latent, `AnalogLatentLink.py` maps float latent values to complex I/Q symbols, applies RRC shaping, writes sc16, and sends it through the persistent host TX server at `127.0.0.1:29221`.
6. The board RX server at `100.121.87.73:29220` captures sc16 into `/tmp/usrp292x_remote_runs/...`. The RX/TX servers stay up across images; per image only sends `CAPTURE`, `SEND`, and `WAIT` style control operations.
7. A persistent board-side decode worker runs `/home/user/venv/bin/python /home/user/USRP292x/AnalogLatentLink.py decode-server`. `ANALOG_DECODE_PIPELINE_WARMUP=1` moves FFT/import/decode cold start out of the per-image timing path.
8. `ANALOG_SYNC_PROFILE=fast-first` first tries a short sync search (`4` candidates, `1024` symbols). Only failed frames fall back to the slower `12` candidate, `4096` symbol search.
9. In `remote-dir` mode the board decode worker writes `000000xx.npy` in the current profile, or `000000xx.npz` in older runs, directly into `/home/user/cockpit_usrp_rx/<run>_rx`. The cockpit host does not pull the raw sc16 or re-upload decoded latents for TVM.
10. The TVM big.LITTLE wrapper consumes that board-side RX directory. The inferencer is pinned to big core `[2]`, pre/post stages to little cores `[0,1]`; artifact SHA matches `bf255cd4...`.
11. Cockpit displays transport and reconstruction separately. Transport median comes from IQ raw round records; TVM median comes from the big.LITTLE run summary.

## Inference Engine Support In USRP Mode

| Engine | USRP data plane | Current behavior |
|---|---|---|
| TVM | Supported | Main demo path. IQ direct writes board-side latent files, then handwritten TVM + big.LITTLE consumes the remote-dir input. |
| MNN | Supported | Uses the same USRP remote-dir latent input and writes MNN outputs under the USRP output root. A 2026-07-11 backend lock bug in MNN/USRP startup is fixed by arming ML-KEM security outside `DashboardState` lock. |
| PyTorch | Not connected | PyTorch remains the reference comparison. In USRP mode `/api/run-baseline` returns `execution_mode=prerecorded` and `data_transport=prerecorded`; it does not start USRP transport. |

## IQ Direct Current Blockers

- RF/RX outliers remain. The current accepted 300-image IQ run has median transport below TVM (`172.43 ms` versus `240.38 ms`), but IQ p95 is still above TVM p95 (`268.58 ms` versus `242.90 ms`) and max transport still has rare multi-second stalls. The chain is demo-usable after all-pass runs, but not a final p95 win.
- Do not default-enable streaming TVM. Batch `batch-1783624303-300` proved that TVM can consume IQ decoded files before transport ends, but board CPU/IO contention pushed transport median to `338.90 ms` and TVM p95 to `322.37 ms`.
- Sync quality is still the main physical-layer risk. Lowering `ANALOG_MIN_SYNC_METRIC` to `0.05` avoids expensive robust CFO fallback on marginal but decodable captures; it does not solve weak RF captures.
- Decode still costs real time. The warmed board worker is now around `62.96 ms` median in the recommended run, with fast sync median `21.07 ms`; rare decode/RX stalls still drive the max tail.
- `ANALOG_RETRY_ON_BURST_MISS=1` is now a reliability default for the Cockpit IQ path, not a claimed performance win. Earlier 50-image testing showed it can avoid slow low-burst fallback decode, but RX capture tails still dominate p95.
- `ANALOG_PRECONNECT_CONTROL=1` and `ANALOG_RX_SESSION_CONTROL=1` are also opt-in diagnostics. Preconnect improved TX control time but not transport median. RX same-session control increased median and p95, so do not use it for the default 300-image run.
- `ANALOG_RETRY_ON_LOW_SYNC=1` with threshold `0.08` is now a reliability default after the `299/300` weak-sync incident. It should request a fresh capture before wasting time in fallback decode when another ARQ attempt remains. It still needs a fresh 300-image hardware gate after Cockpit restart.
- `ANALOG_REMOTE_DECODE_REQUEST_TIMEOUT_SEC` and `ANALOG_REMOTE_DECODE_RESTART_ON_TIMEOUT=1` are opt-in diagnostics for decode-worker stalls. The 300-image run stayed all-pass, but p95 worsened because restart time and RX stalls still affected the queue.
- `ANALOG_PIPELINE_DEPTH=1` and shorter RX tail are not default optimizations. Depth 1 lowers p95 but hurts batch throughput; tail `0.04`/`0.02` reduces sync margin and either causes retries or failures.
- `ANALOG_RX_POST_QUANTIZE=0` is the default IQ direct profile. It preserves the `latent` array consumed by TVM while avoiding extra diagnostic arrays in the remote-dir `.npz`.
- `ANALOG_REMOTE_DECODED_FORMAT=npy` is the current decoded-output format. tmpfs remains diagnostic only: it proves publish I/O can be kept near 1 ms, while the remaining p95 failures come from RX arm/wait, no-sync retries, and decode queue propagation.
- Status polling must stay isolated during live runs. The backend currently defers telemetry/USRP/position refresh while batches run; reintroducing SSH polling in the hot path can hide the RF improvements.
- The security-on path is not this performance number. ML-KEM/auth is configured, but the crypto toggle was off for these latency runs. Measure security-on separately after the IQ data plane is stable.
- The container-to-board migration is still sensitive to environment state: `/home/user/venv`, `/home/user/USRP292x/AnalogLatentLink.py`, persistent TX/RX ports, Docker TX image, and `REMOTE_USRP_RX_DIR` must all match the runbook.

## Verified Milestones

- 2026-07-11 publish-event diagnostic: `ANALOG_REMOTE_DECODE_PUBLISH_EVENT=1` adds a board-side `published` event after decoded latent `atomic_savez`, with runner-side matching and partial decode timing. `batch-1783732029-20` stayed 20/20 with IQ p95 `236.94 ms` below TVM p95 `259.66 ms`, but `batch-1783732287-50` stayed 50/50 with IQ p95 `363.37 ms` above TVM p95 `247.02 ms`. Keep it opt-in; the 50-image tail was RX capture/wait, one low-sync retry, and true weak-sync decode rather than only stdout latency.
- 2026-07-11 weak-sync incident and retry default: `cockpit_usrp_usrp-1783772592` completed 300 capture requests but failed the all-pass gate at `299/300`; `image_0163` had sync metric about `0.0324` below the `0.05` minimum. The current code now defaults IQ direct to ARQ5 plus burst-miss and low-sync retry (`ANALOG_LOW_SYNC_RETRY_THRESHOLD=0.08`). This is a reliability change awaiting a fresh 300-image hardware gate.
- 2026-07-11 low-sync early-retry diagnostic: `ANALOG_RETRY_ON_LOW_SYNC=1` with threshold `0.06` stayed 50/50 in `batch-1783732885-50`, but IQ p95/max was `273.66/518.02 ms` while TVM p95 was `243.78 ms`. This did not prove a p95 win; its current role is to avoid weak-sync fallback decode when ARQ retries remain.
- 2026-07-11 IQ direct probe-id/precreate retry validation: `batch-1783730551-300`, 300/300, fallback 0, TVM median/p95/max `241.69/244.45/280.68 ms`, IQ transport median/p95/max `155.66/274.33/11124.64 ms`, PSNR `37.0445`, SSIM `0.97494`. This fixes stale same-request path-probe responses and transient SSH kex failures during precreate. It is not final performance success because IQ p95 is still above TVM p95 and max is dominated by board `.npy` publish/file-visibility tails.
- 2026-07-11 IQ direct worker-timing validation: `batch-1783726777-300`, 300/300, fallback 0, TVM median/p95 `241.78/244.73 ms`, IQ transport median/p95/max `158.38/333.24/10395.30 ms`, PSNR `37.0445`, SSIM `0.97494`. The soft-completion path-probe timeout fix capped worker response-wait max at `405.91 ms`; remaining tails were RX arm/capture and occasional board decode/write stalls.
- 2026-07-11 rejected IQ timeout/STOP profiles: `ANALOG_RX_WAIT_TIMEOUT_SEC=1.0` is now correctly passed through to the runner, but `batch-1783727897-300` worsened IQ p95 to `904.15 ms`. Short STOP defaults (`RX_STOP_WAIT_MS=200`, `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=0.2`) failed 300-image gates (`296/300` and `299/300`). Keep these knobs opt-in and keep the stable Cockpit default at `RX_STOP_WAIT_MS=8000` / `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0`.
- 2026-07-11 bounded arm-failure drain: IQ direct keeps the stable 8-second normal STOP drain, but when arm status proves `started=0`, `done=0`, and `written_samps=0`, the second arm-failure STOP now uses `ANALOG_RX_STOP_ARM_FAIL_FULL_DRAIN_TIMEOUT_SEC=1.5`. This targets recovered 10-second outliers such as `RX CAPTURE did not arm before TX` without weakening cleanup after a real receive has started.
- 2026-07-11 accepted 500 ms RX arm-wait profile: after explicit USRP control restart, `batch-1783782559-300` completed transport and TVM at `300/300`, fallback `0`. IQ transport median/p95/max was `166.63/198.46/15934.08 ms`; TVM median/p95/max was `241.20/242.59/259.35 ms`. Use IQ p95 below TVM p95 as the current speed result; the max is still a recovered RF/RX outlier.
- 2026-07-10 IQ direct fast-first recommended profile: `batch-1783626884-300`, 300/300, fallback 0, transport median `182.28 ms`, transport p95 `372.96 ms`, RF airtime `9.58 ms`, RX capture median `97.23 ms`, board decode median `62.96 ms`, TVM median `242.41 ms`, TVM p95 `245.77 ms`, total cockpit batch wall `157.12 s`. All 300 decode summaries used `sync_pass=1`; fast sync median `21.07 ms`, p95 `61.51 ms`.
- 2026-07-10 IQ direct post-quantize-off profile: `batch-1783638234-300`, 300/300, fallback 0, transport median `186.83 ms`, p95 `351.67 ms`, max `6368.37 ms`, TVM median `241.28 ms`, TVM p95 `244.10 ms`, quality PSNR `37.0445`, SSIM `0.97494`. This is the recommended profile when using the Docker/cockpit defaults after this update.
- 2026-07-10 IQ direct `.npy` remote-dir diagnostics: `/home/user/cockpit_usrp_rx` run `batch-1783640049-300` stayed 300/300 with transport median `189.19 ms`, p95 `383.88 ms`, TVM median `241.49 ms`, p95 `248.64 ms`, and `.npy` write p95 `1.64 ms`. tmpfs run `batch-1783640401-300` stayed 300/300 with write max `3.43 ms` and TVM p95 `244.97 ms`, but transport p95 worsened to `1013.67 ms` because RX/no-sync stalls dominated.
- 2026-07-10 decode-worker and pipeline diagnostics: timeout/restart `batch-1783635568-300` stayed 300/300 but worsened p95 to `865.77 ms`; depth-1 `batch-1783636039-300` stayed 300/300 with p95 `318.43 ms` but wall `104.43 s`; RX tail `0.02` failed `28/50`, and tail `0.04` stayed 50/50 but worsened p95 to `1169.05 ms`. Recommended cockpit remains tail `0.05`, depth `2`, timeout unset.
- 2026-07-10 burst-miss retry diagnostic: `batch-1783628596-50`, 50/50, fallback 0, `ANALOG_RETRY_ON_BURST_MISS=1`, transport median `199.90 ms`, p95 `783.40 ms`, decode max `197.08 ms`, `remote_decode_queue_ms` median `0.05 ms`, p95 `48.91 ms`. Compared with `batch-1783627996-50` without the guard, decode max improved but RX capture p95 worsened. It is now kept as a reliability guard, not a p95 optimization.
- 2026-07-10 IQ direct previous sequential-sync profile after a clean restart: `batch-1783625337-300`, 300/300, fallback 0, transport median `189.10 ms`, transport p95 `642.66 ms`, RF airtime `9.58 ms`, RX capture median `97.40 ms`, board decode median `68.47 ms`, TVM median `242.16 ms`, TVM p95 `244.89 ms`, total cockpit batch wall `161.17 s`. Polling showed inference remained `0/300 pending` until transport was `300/300 completed`; this was the recommended default before fast-first sync.
- 2026-07-10 IQ streaming TVM experiment: `batch-1783624303-300`, 300/300, fallback 0, but total wall `233.76 s`, transport median `338.90 ms`, transport p95 `694.20 ms`, decode median `158.52 ms`, TVM median `248.29 ms`, TVM p95 `322.37 ms`. Keep `OPENAMP_IQ_STREAMING_TVM` / `USRP_IQ_STREAMING_TVM` unset unless explicitly testing overlap.
- 2026-07-10 cockpit button-equivalent 300-image validation: IQ direct `batch-1783610422-300` completed 300/300 with transport median `202.54 ms`, TVM median `241.21 ms`, remote-dir board decode, and no fallback. QPSK `batch-1783610673-300` completed 300/300 with transport `2961.78 ms/image`, TVM median `240.06 ms`, and no fallback.
- 2026-07-09 IQ direct keeps the same persistent USRP control plane as QPSK: board RX stays on `100.121.87.73:29220`, host TX stays on `127.0.0.1:29221`, and each frame sends only `CAPTURE/SEND/WAIT` to those servers. Remote-decode now avoids uploading the unused `tx_analog.sc16`, pulls `received_latent.npz`, `merged_round0.bin`, and `decode_summary.json` in one tar stream, and removes all remote per-frame artifacts with one batched cleanup command.
- 2026-07-09 Windows SSH helper now supports `OPENAMP_SSH_RUNNER=paramiko`. The same board `user/user` login succeeds through Paramiko while Git Bash OpenSSH/sshpass fails with `Permission denied`; `resolve_bash_executable()` now finds Scoop Git Bash through `git --exec-path` and avoids WSL `bash.exe`. This fixes big.LITTLE TVM wrapper uploads on the Windows cockpit path without moving USRP IQ/QPSK data through Tailscale.
- 2026-07-09 IQ remote-decode can keep one board-side Python decoder alive with `ANALOG_REMOTE_DECODE_WORKER=1` (default in the Docker cockpit wrapper). Per frame now sends a JSON decode request to `AnalogLatentLink.py decode-server` instead of starting a fresh board Python process. Live run `usrp-1783566831` created a single `remote_decode_worker.log`; `image_0000/remote_decode.log` returned `status=ok`, sync metric `0.8910`, and `sync_search_window_enabled=true`. The following frame failed sync at about `0.084`, matching current physical IQ quality fluctuation rather than process startup overhead.
- 2026-07-09 IQ remote-decode supports `ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir` for cockpit + TVM runs. The board-side decoder publishes flat latent files such as `/home/user/cockpit_usrp_rx/<run>_rx/00000000.npz`; cockpit then passes that directory directly to TVM instead of pulling `received_latent.npz`/`merged_round0.bin` back to Windows and uploading them to the board again. IQ decoder asset sync is cached per cockpit backend process; the default upload timeout is 90 s because the measured Windows + Docker SSH binary stdin path took about 31 s for the 19 KB asset tar.
- 2026-07-09 IQ remote-decode worker mode now sends `manifest_json` through the persistent `AnalogLatentLink.py decode-server` request instead of launching a per-frame Docker SSH command to upload `manifest.json`. `OtaRxPersistentServer` creates capture parent directories, so the hot path keeps persistent RX/TX plus the persistent board decode worker.
- 2026-07-09 IQ direct defaults now use `ANALOG_MIN_SYNC_METRIC=0.08` and `ANALOG_ROBUST_SYNC=0` unless explicitly overridden. Re-decoding live capture `cockpit_usrp_usrp-1783571012` showed the three frames that failed at the old `0.25` threshold can decode at about 4.1-7.5 s instead of burning 70-80 s in robust CFO grid search. This is a latency guard, not a final PHY-quality fix.
- 2026-07-09 IQ direct originally passed `USRP_MAX_ARQ_ROUNDS=2` into `RunAnalogLatentBatch.py`; for IQ this means re-capturing the same latent over USRP OTA after a sync/decode miss, not running QPSK packet ARQ. The current Cockpit default supersedes this with `MLKEM_USRP_MAX_ARQ_ROUNDS=5`. The big.LITTLE wrapper also uploads its transient runner through `ssh_with_password.sh`, so Windows bare `scp` no longer breaks TVM parsing. Verified cockpit end-to-end run `batch-1783572523-5`: transport 5/5, TVM 5/5, remote input `/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-1783572523_rx`, TVM mean `251.22 ms`, median `246.72 ms`, PSNR `37.0445`, SSIM `0.97494`.
- 2026-07-09 USRP data plane is RF/USRP only; Tailscale is used for control-plane SSH/API/control sockets. After an RX stream stall (`written_samps=0`, `RX_capture_deadline_exceeded`), `/api/usrp-control/stop` + `/api/usrp-control/start` and a 50k-sample RF probe restored RX (`50000/50000`). Verified follow-up run `batch-1783585508-5`: transport 5/5, TVM 5/5, fallback 0, remote input `/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-1783585508_rx`, TVM samples `[289.08, 249.35, 264.85, 243.64, 243.25]`, mean `258.03 ms`, median `249.35 ms`, artifact SHA matched, big core `[2]`, little cores `[0,1]`.
- 2026-07-09 Windows big.LITTLE wrapper hardening: Paramiko SSH helper now uses a 900 s default timeout and the remote execute call closes stdin with `/dev/null`; local Git Bash dry-runs use the current `$BASH` instead of accidentally resolving `C:\Windows\System32\bash.exe`/WSL, and stdout JSON is ASCII-escaped while report files stay UTF-8.
- 2026-07-09 board-side IQ decode now uses SciPy FFT correlation for large sync searches when SciPy is available, with NumPy direct correlation as fallback. Board offline profile on `/home/user/USRP292x/AnalogLatentLink.py` showed one full sync search drop from about `480 ms` to about `98 ms` with the same best sync point. The cockpit default stays at `ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS=4096` for RF reliability; a 1024-symbol experiment was faster but missed sync under one live RF run.
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
