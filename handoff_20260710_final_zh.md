# 2026-07-10 IQ 直传交接说明

## 接手结论

当前分支是 `feat/restore-248`，最新关键提交到 `a8e6ea6 perf: avoid repeated ssh controlmaster stalls`。Cockpit Desktop 一键路径已经回到 IQ 直传，链路包含 handwritten TVM 和 big.LITTLE runner。当前推荐 profile 能稳定复现接近 250 ms 的可见重建速度：TVM median 约 `240 ms`，IQ transport median 通常在 `165-185 ms`。

IQ 直传已经明显快于 QPSK。QPSK transport 参考约 `2961.78 ms/image`，不要再改 QPSK；它现在只作为回归基线。

## 当前链路

```text
cockpit_desktop
-> openamp_control_plane_demo/server.py
-> usrp_runtime.py
-> USRP292x/RunAnalogLatentBatch.py
-> persistent TX/RX USRP servers
-> board decode-server
-> board big.LITTLE TVM
```

USRP 样本数据面走直连 USRP，不走 Tailscale。Tailscale 只用于 SSH、控制、状态和日志。Windows 侧 bash/SSH 辅助命令优先用 Docker，Docker 不可用时用 Windows Git Bash，不要用 WSL。板端 Python 固定使用 `/home/user/venv/bin/python`。

## 当前推荐配置

除非明确做实验，否则保持以下配置：

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
OPENAMP_DEMO_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0
```

不要默认打开 streaming TVM、depth-2 overlap、tmpfs 输出、`.npy` 输出、soft completion 或 burst-miss retry。之前的实验显示，这些开关可能改善短跑 median，但会放大 300 张长测的 p95、max 或总 wall time。

## 已验证指标

最新可靠 300 张 gate 是 `batch-1783674397-300`：`300/300`，fallback `0`，TVM median/p95 `238.87/245.54 ms`，IQ transport median/p95 `175.28/337.46 ms`。

最新 50 张 instrumentation smoke 是 `batch-1783676258-50`：`50/50`，fallback `0`，TVM median/p95 `242.22/243.93 ms`，IQ median/p95 `165.42/251.70 ms`。RX server 侧显示正常 receive/capture 约 `63.61/64.27 ms`，说明正常路径主要受 `ANALOG_RX_TAIL_SEC=0.05` 的 capture floor 限制，不是 server drain 或 stream command 卡住。

最新 no-poll 对照是 `batch-1783678924-50`：`50/50`，fallback `0`，TVM median/p95 `239.96/245.99 ms`，IQ median/p95/max `183.51/338.34/501.46 ms`。中途少轮询没有改善 tail；最慢样本 server capture 仍约 `64 ms`，但 runner 侧 `rx_capture/rx_wait` 和 decode response 等待拉长。结论：状态轮询不是主因。

最新 overhead 字段验证是 `batch-1783680558-50`：`50/50`，fallback `0`，TVM median/p95 `240.13/244.14 ms`，image-level IQ median/p95/max `207.72/334.49/1129.46 ms`。本轮有 51 条 stage record，image 29 第一次 attempt no-sync 后重试恢复。server capture 仍稳定在约 `64 ms`，但 `rx_capture_control_overhead_ms` p95 `140.31 ms`，`remote_decode_response_overhead_ms` p95 `128.12 ms`。下一步先处理 RX arm/capture readiness 和 retry cleanup，再处理 decode response wait。

decode 失败后 RX cleanup 验证是 `batch-1783681389-50`：`50/50`，fallback `0`，TVM median/p95 `240.73/245.35 ms`，IQ median/p95/max `174.91/269.24/347.72 ms`。本轮没有 retry，说明 STOP/drain 清理没有拖慢正常路径；下一次出现 no-sync/retry 时要确认失败 attempt 记录了 `rx_server_stop_cmd_wall_sec` 和 `rx_server_stop_wait_wall_sec`。

cleanup 后 300 张 gate 是 `batch-1783682083-300`：`300/300`，fallback `0`，TVM median/p95 `243.38/255.24 ms`，IQ median/p95/max `174.42/308.45/8377.89 ms`。本轮有 305 条 stage record。主要 tail 是一次 WAIT timeout 后 STOP 控制命令 5s 客户端超时、一次 decode worker response wait 约 `7.27 s` 但板端 reported decode 约 `43 ms`、以及一次真实板端 decode 约 `4.09 s`。STOP 客户端 timeout 已改为覆盖 `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0`，下一轮 300 张要验证 STOP log 不再出现 `ERR_TIMEOUT`。

STOP timeout-budget 验证是 `batch-1783682666-300`：`300/300`，fallback `0`，TVM median/p95 `240.17/243.93 ms`，IQ median/p95/max `172.39/310.55/19107.42 ms`，stage record `302`。image 196 仍出现 WAIT timeout 后 STOP `ERR_TIMEOUT`，并且第二次 attempt 有约 `6.96 s` runner-side decode wait。根因更新：`ANALOG_RX_SESSION_CONTROL=1` 下 WAIT timeout 后旧 RX session 没有先关闭，runner 直接开新连接发 STOP，可能卡在服务端旧会话/accept 状态。现在 depth-1 和 pipeline capture 两条路径都改成 STOP 前先关闭 RX session。

session-before-STOP 验证是 `batch-1783683491-300`：`300/300`，fallback `0`，TVM median/p95 `242.38/245.50 ms`，IQ median/p95/max `169.48/299.73/6822.54 ms`，stage record `301`。唯一 retry 是 image 263 arm/status timeout，`rx_stop_after_capture_busy.log` 返回 `OK`，不再是 `ERR_TIMEOUT`。剩余最大尾部主要在 decode 侧：真实板端 decode stall 和 runner-side decode response wait。

tmpfs decoded-output 复测：`batch-1783684070-50` 使用 `/dev/shm/cockpit_usrp_rx`，`50/50`、fallback `0`，TVM median/p95 `241.53/246.04 ms`，IQ median/p95/max `179.92/360.48/3979.87 ms`。tmpfs 把 `write_npz` median/p95/max 压到 `1.446/2.553/2.719 ms`，但总链路被一次 arm-not-ready retry 和 decode response p95 `125.67 ms` 拖慢。结论：tmpfs 继续保留为诊断项，不默认推广。

decode timing 字段验证是 `batch-1783686020-50`：`50/50`，fallback `0`，TVM median/p95 `239.71/250.01 ms`，IQ median/p95/max `171.80/324.63/1417.55 ms`。新增 `remote_decode_*_ms` 字段已出现在 `iq_stage_benchmark`；板端 decode 内部阶段 p95 都低于 `90 ms`，更大的尾巴仍在 RX control overhead 和 runner-side decode response overhead。

decode timing 300 张 gate 是 `batch-1783686930-300`：`300/300`，fallback `0`，TVM median/p95/max `240.29/242.87/257.55 ms`，IQ median/p95/max `166.04/288.97/7683.31 ms`。IQ median 已明显低于 TVM，但 p95/max 仍需优化。最大值来自一次 `/home` `.npz` 写入 stall；其他 top tail 主要是 RX arm/capture control 约 `1.0-1.1 s` 和 runner-side decode response wait。

Batch RX session A/B：`ANALOG_RX_BATCH_SESSION_CONTROL=1` 的 50 张 `batch-1783690852-50` 通过，IQ median/p95 `155.30/217.47 ms`，但 300 张 `batch-1783690925-300` 变成 IQ median/p95 `162.20/321.68 ms`，p95 高于 TVM。关闭该开关的同代码对照 `batch-1783691290-300` 是 IQ median/p95 `172.71/301.74 ms`。结论：batch session 降低 median，但 300 张 p95 不够稳，只保留 opt-in，不写进默认 profile。

`PERSISTENT_RX_TX_DELAY=0.005` 已拒绝：`batch-1783691806-50` 虽然 `50/50`、fallback `0`，但 IQ median/p95 恶化到 `202.47/306.92 ms`。保持 `PERSISTENT_RX_TX_DELAY=0`。

WAIT timeout cleanup 的计时记录已修复：STOP 成功后不再被原始 WAIT 错误文本里的 `stop_cmd_sec=0` / `stop_wait_sec=0` 覆盖，后续 300 张 tail 分析可以信任 `rx_server_stop_*` 字段。

短 RX tail 已拒绝：`ANALOG_RX_TAIL_SEC=0.04` 在 5 张 sanity 出现 no-sync retry；`0.045` 的 50 张 `batch-1783678227-50` 虽然全过，但 IQ median/p95 变成 `201.17/1207.08 ms`。保持 `0.05`。

## 本轮主要改动

- Cockpit 启动保留 IQ/USRP/Docker timing env，避免回到 prerecorded 或 TCP 默认链路。
- Docker TX 支持 `/host_workspace` mount target，容器内能找到 latent cache。
- RX server 支持 `--arm-wait-ms` 和 `--stop-wait-ms`，STOP 会等 worker 收尾后再返回。
- Python runner 复用 RX control session，关闭 socket 前调用 shutdown，减少 stale `capture_already_running`。
- 远端 decode 使用 minimal response，完整 `decode_summary.json` 留在板端，减少 stdout 等待。
- `OtaRxPersistentServer` 输出 `rx_server_*` 计时字段，runner 聚合到 `iq_stage_benchmark`。
- `iq_stage_benchmark` 额外输出 `rx_capture_control_overhead_ms` 和 `remote_decode_response_overhead_ms`，作为 runner 侧 capture/decode response 等待相对 server capture 和板端 reported decode 的诊断估算。
- 如果批次级 SSH ControlMaster 启动失败，runner 不再每张图重试一次，避免 Windows/password SSH 路径产生约 `10 s/image` 的假尾延迟。
- WAIT 成功后如果 decode/no-sync 失败，runner 会发送 `STOP` 并 drain RX server，再进入 ARQ retry，避免下一次 attempt 继承不确定的 RX 状态。
- `stop_rx_capture()` 的客户端 timeout 已覆盖 RX drain budget，避免 profile 配置 `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0` 时被旧的 5s cap 提前切断。
- WAIT timeout cleanup 会在 direct STOP 前关闭当前 RX control session，避免同一个服务端控制会话阻塞新 STOP 连接。
- remote-dir soft completion 命中时会记录 `remote_decode_soft_completed=true`，便于后续 A/B 区分正常 stdout response 和文件探测接管。
- `iq_stage_benchmark` 会聚合板端 `decode_timing_ms`，输出 `remote_decode_matched_filter_ms`、`remote_decode_initial_sync_ms`、`remote_decode_cfo_estimate_ms`、`remote_decode_payload_recovery_ms`、`remote_decode_write_npz_ms` 等字段，用于定位 decode-side tail。
- 失败 remote-decode attempt 也会保留 `decode_wall_sec`，避免低 sync/no-sync retry 的耗时归因丢失。
- 新增 opt-in `ANALOG_RX_BATCH_SESSION_CONTROL=1` / `--rx-batch-session-control`。它只用于非 pipeline 顺序批次，复用一个 RX control session 跨图片发送 CAPTURE/WAIT；正常结束后关闭，WAIT timeout/capture busy/session 失效后清空共享 session，避免后续图片复用死连接。现场 A/B 后不推广为默认。

## 已知卡点

300 张长测仍有少量 recovered retry 和多秒级 max。主要类型是：

- RX WAIT timeout 后已有部分 samples 写入，下一次 retry 前需要更确定的 cancel/drain。
- RX arm/capture 偶发长等待，但最后仍能 decode 成功。
- runner 等待 decode worker 的时间偶尔远高于板端 reported decode time。板端 reported decode 通常约 `44 ms`。
- 少量 low/no-sync retry，当前 ARQ 能恢复，但会拉高 p95 和 max。

## 重启和验证流程

从 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026` 执行。先停 Cockpit backend 和 USRP helper，避免继承上一轮状态。

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

重启 backend 后验证：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

如果打开 Cockpit 就看到 `board status endpoint unavailable` 或 connection refused，通常是 backend 或 board-status helper 没在预期端口运行。先全停，再按上面的流程重启。

## 下一步顺序

1. 保持 QPSK 冻结，任何 IQ 改动前后都检查 `git diff -- USRP292x/RunQpskFileBatchSpoolArq.py`。
2. 保持 `ANALOG_RX_BATCH_SESSION_CONTROL=0` 作为默认；`ANALOG_RX_BATCH_SESSION_CONTROL=1` 只作为诊断/后续实验开关。
3. 继续处理 IQ p95/max。最新 300 张显示 median 已低于 TVM，但 tail 主要来自 RX arm/capture control、runner 等 decode response，以及 rare `/home` `.npz` 写入 stall。
4. RX 状态机稳定前，不默认开启 double buffering、streaming TVM 或 depth-2 overlap。
5. 每次 timing 行为变化后先跑 50 张，再跑 300 张 gate。只看短跑 median 不够。

## 安全和认证

性能基线里 runtime security channel 是关闭的；认证和 ML-KEM 不应放进 per-image hot path。后续 security-on 要单独测：先 20 张，确认握手是 session-level，再跑 300 张。如果安全开关带来超过约 `5%` 开销，就保留 security-off 作为性能基线，并在文档里写清楚差值。

不要提交板端密码、Tailscale 凭据、私钥、本机地址或临时 SSH 命令里的敏感信息。账号、密码、host、port 只放本地环境变量。

## 提交前检查

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最后一条必须为空。生成的 report、raw log 和临时运行产物不要提交，除非明确要作为证据归档。
