# 2026-07-10 IQ 直传交接说明

## 当前结论

当前分支是 `feat/restore-248`。Cockpit Desktop 一键测试路径已经回到 IQ 直传，推理链路包含 handwritten TVM 和 big.LITTLE runner。最近一次 50 张 Cockpit 等价验证是 `batch-1783676258-50`，结果 `50/50`、fallback `0`，TVM median `242.22 ms`，IQ transport median `165.42 ms`，IQ p95 `251.70 ms`。

这说明现在的可见重建速度已经恢复到接近 `250 ms` 的目标区间。IQ 直传的数据面明显快于 QPSK，但 300 张长测里仍有 RX/解码尾延迟，不能把它当作最终优化完成状态。

## 代码与文档检查点

最新关键提交：

```text
7baebf8 perf: expose rx server timing fields
1cb50ff docs: refresh iq direct handoff
cb921d2 perf: close iq rx sessions promptly
8966711 perf: promote iq arm wait profile
71a591d docs: add iq direct handoff
```

主要文档：

- `handoff_20260710_iq_direct.md`：英文详细交接，包含指标表、参数配置、重启流程和已知问题。
- `plan_20260710.md`：优化计划和执行记录。后续 IQ 直传优化应继续按这个计划推进。
- 本文件：中文交接摘要，供接手时快速判断状态。

## 当前运行链路

```text
cockpit_desktop
-> openamp_control_plane_demo/server.py
-> usrp_runtime.py
-> USRP292x/RunAnalogLatentBatch.py
-> persistent TX/RX USRP servers
-> board decode-server
-> board big.LITTLE TVM
```

Windows 侧需要用 Docker 跑 Linux/bash 和 SSH 辅助命令；Docker 不可用时再用 Windows Git Bash。不要用 WSL。板端 Python 必须使用 `/home/user/venv/bin/python`，板端 Python 命令前要激活 `/home/user/venv`。

USRP 样本数据面应走直连 USRP 链路。Tailscale 只用于控制、SSH、状态和日志，不应进入 IQ 样本数据面。

## 当前推荐配置

除非明确做实验，否则保持这组 profile：

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

不要默认打开 streaming TVM、depth-2 overlap、tmpfs 输出、`.npy` 输出、soft completion 或 burst-miss retry。这些配置做过实验，有些能改善短跑 median，但会放大 300 张长测的 p95、max 或总 wall time。

## 已验证指标

最新 300 张 gate：`batch-1783674397-300`，`300/300`，fallback `0`，TVM median `238.87 ms`，TVM p95 `245.54 ms`，IQ transport median `175.28 ms`，IQ p95 `337.46 ms`。

最新 50 张 instrumentation smoke：`batch-1783676258-50`，`50/50`，fallback `0`，TVM median `242.22 ms`，IQ transport median `165.42 ms`。新加的 RX server 计时显示：

```text
rx_server_arm_wait_ms median 0.66
rx_server_drain_ms median 0.03
rx_server_stream_cmd_ms median 0.16
rx_server_receive_ms median 63.61
rx_server_capture_ms median 64.27
```

结论很直接：正常路径不是卡在 server-side drain 或 stream command，而是卡在 capture duration。当前 `ANALOG_RX_TAIL_SEC=0.05` 基本决定了 RX 正常路径的地板。

短 tail 复测已经拒绝：`ANALOG_RX_TAIL_SEC=0.04` 的 5 张 sanity 出现 no-sync retry；`0.045` 的 50 张 `batch-1783678227-50` 虽然 `50/50`、fallback `0`，但 IQ median `201.17 ms`、p95 `1207.08 ms`，明显差于 `0.05` 的 `165.42/251.70 ms`。

QPSK 参考 transport 约 `2961.78 ms/image`。IQ 直传已经比 QPSK 快很多，不要为了 IQ 优化去改 QPSK。

## 这轮主要改动

- Cockpit 启动时保留 IQ/USRP/Docker timing env，避免回到 prerecorded 或 TCP 默认链路。
- Docker TX 支持 `/host_workspace` mount target，容器内路径可以正常找到 latent cache。
- RX server 支持 `--arm-wait-ms` 和 `--stop-wait-ms`。
- Python runner 复用同一 RX control session，并在关闭 socket 前调用 shutdown，让 RX server 更快看到 EOF。
- RX `STOP` 会等 worker 收尾后再返回，减少 stale `capture_already_running`。
- 远端 decode 改为 minimal response，完整 `decode_summary.json` 留在板端，减少 stdout 等待。
- `OtaRxPersistentServer` 增加 `rx_server_*` 计时字段，`RunAnalogLatentBatch.py` 会记录并聚合到 `iq_stage_benchmark`。
- IQ runner 增加了 ControlMaster 防护：如果批次级 SSH ControlMaster 启动失败，就不再每张图重试一次。这个问题在 Windows/password SSH 路径上会带来约 `10 s/image` 的假尾延迟。

## 已知问题

300 张长测仍会出现少量 recovered retry 和多秒级 max。`batch-1783674397-300` 有 `305` 条 stage records，对应 `300` 张图，其中部分图片靠 ARQ retry 恢复。

主要尾延迟类型：

- RX WAIT timeout 后已有部分 samples 写入，下一次 retry 前需要更确定的 cancel/drain。
- RX arm/capture 偶发多秒级等待，但最后仍可能 decode 成功。
- runner 侧等待 decode worker 的时间偶尔远高于板端 reported decode time。
- 少量 low/no-sync retry，当前 ARQ 能恢复，但会拉高 p95 和 max。

## 下一步建议

1. 先提交当前文档更新，保持工作区干净。
2. 保持 `ANALOG_RX_TAIL_SEC=0.05`。`0.04` 和 `0.045` 当前都不要推广。
3. 做 RX WAIT timeout 恢复：timeout 后显式 cancel/drain，再进入下一次 ARQ retry。
4. 继续区分板端 decode compute 和 runner/worker/control wait。板端 reported decode 通常约 `44 ms`，runner 等待偶尔到秒级。
5. RX 状态机稳定前，不要默认打开 double buffering 或 streaming TVM。
6. 每次 IQ 行为变化后，都要跑 300 张 gate，再决定是否推广。

## 安全与认证

性能基线里 runtime security channel 是关闭的；配置里仍能看到认证相关设置存在。ML-KEM 和签名不要放进 per-image hot path。后续应单独测 security-on：先 20 张，确认握手是 session-level，再考虑 300 张。如果开启安全后超过约 `5%` 开销，就保留 security-off 作为性能基线，并在文档中写清楚差值。

不要提交板端密码、Tailscale 凭据、私钥、本机地址或临时 SSH 命令里的敏感信息。账号、密码、host、port 都只放在本地环境变量。

## 重启与验证

从 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026` 执行。先停止 Cockpit backend 和 USRP helper，再重启，避免继承上一轮状态。

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

重启后用 Cockpit 等价 endpoint 验证：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

提交前至少跑：

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最后一条必须为空。只要它不为空，先停下来分离 IQ 改动和 QPSK 改动。
