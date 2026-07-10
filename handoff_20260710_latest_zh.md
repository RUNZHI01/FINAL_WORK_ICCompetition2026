# 2026-07-10 IQ 直传交接说明

## 交接结论

当前工作目录是 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`，分支为 `feat/restore-248`。Cockpit Desktop 一键测试路径已经恢复到 IQ 直传，链路包含 handwritten TVM 和 big.LITTLE runner。QPSK 已可用并冻结，后续不要改 `USRP292x/RunQpskFileBatchSpoolArq.py`，它只作为回归基线。

当前推荐 profile 是 no-batch RX session、`PERSISTENT_RX_TX_DELAY=0`、Docker TX、板端 `/home/user/venv/bin/python`。IQ 直传 median 已经低于 TVM，但 300 张 p95 和 max 还有长尾，目标还没完成。

最新同代码 no-batch 300 张 A/B 是 `batch-1783691290-300`：`300/300`、fallback `0`。TVM median/p95/max 为 `241.84/253.13/265.85 ms`；IQ median/p95/max 为 `172.71/301.74/8598.55 ms`。这说明正常路径速度够了，剩下问题集中在 RX arm/wait/control stall、runner-side decode response wait，以及少数 `/home` `.npz` 写入 stall。

## 当前代码和提交

最近三次关键提交：

- `bf16f64 perf: add opt-in iq rx batch session`
- `c3938ba fix: close shared iq rx session before decode cleanup`
- `7096a9e docs: record iq rx batch session ab`

`ANALOG_RX_BATCH_SESSION_CONTROL=1` 已实现为 opt-in。50 张效果很好，`batch-1783690852-50` 的 IQ median/p95/max 是 `155.30/217.47/583.30 ms`；但 300 张 `batch-1783690925-300` 的 IQ median/p95/max 是 `162.20/321.68/6828.85 ms`，p95 高于 TVM，也高于 no-batch A/B。因此默认仍保持 `ANALOG_RX_BATCH_SESSION_CONTROL=0`。

`PERSISTENT_RX_TX_DELAY=0.005` 已拒绝。50 张 `batch-1783691806-50` 虽然 `50/50`、fallback `0`，但 IQ median/p95 恶化到 `202.47/306.92 ms`。继续保持 `PERSISTENT_RX_TX_DELAY=0`。

## 推荐运行配置

保持下面这些环境变量，不要把诊断开关混进默认 profile：

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
ANALOG_RX_BATCH_SESSION_CONTROL=0
PERSISTENT_RX_TX_DELAY=0
OPENAMP_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0
```

不要默认打开 streaming TVM、depth-2 overlap、tmpfs 输出、`.npy` 输出、soft completion、burst-miss retry 或 batch RX session。这些都有诊断价值，但目前没有通过 300 张 p95 gate。

## 重启流程

Windows 侧 bash/SSH 辅助命令优先用 Docker，Docker 不可用时用 Windows Git Bash，不要用 WSL。板端手动执行 Python 前先激活虚拟环境：

```bash
source /home/user/venv/bin/activate
```

重启前先全停，避免继承上一轮实验状态：

```powershell
try {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
    -ContentType 'application/json' -Body '{}' -TimeoutSec 60 | Out-Null
} catch {}

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

启动 backend 后，先写入本地板端访问配置，再启动 USRP。账号、密码、host、port 只放本机运行环境或 Cockpit，不要提交进仓库。

Cockpit 测试按钮等价接口：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

不要把完整 `/api/system-status` 输出贴进文档或提交记录，里面可能含本机配置和敏感字段。

## 认证和 ML-KEM

当前性能基线里 runtime security channel 不在 per-image hot path。认证和 ML-KEM 不要和 IQ p95 优化混在同一轮里做。正确做法是先用 security-off profile 固定性能基线，再单独开启 security channel 跑 20 张和 300 张，对比 session-level 开销。如果 security-on 开销超过约 `5%`，性能基线继续保持 security-off，并在文档里记录差值。

## 下一步优化入口

优先级如下：

1. 修正 WAIT timeout cleanup 的计时记录。当前一类失败会先 STOP 成功，但 stage record 可能被原始错误字段覆盖，导致 `rx_server_stop_*` 看起来是 `0`。
2. 处理 RX arm/wait/control stall。batch session 降低了 median，但 300 张 p95 更差，说明单纯复用连接不是最终解。
3. 处理 runner-side decode response wait。多次长尾里板端 reported decode 只有几十毫秒，但 runner 等响应等了几秒。
4. 复测 decoded output placement/format。tmpfs 能压低 `write_npz`，但之前没有改善 300 张 p95，只能作为诊断项。

每次改动前后都要确认 QPSK 没被动到：

```powershell
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

预期输出为空。

## 提交前验证

本地代码验证：

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py USRP292x\AnalogLatentLink.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最近一次完整单测为 `99 passed in 32.81s`。`py_compile` 通过。`git diff --check` 只有 CRLF 提示。QPSK diff 为空。

## 重要文件

- `plan_20260710.md`: 完整 IQ 优化计划和实验记录。
- `handoff_20260710_current_zh.md`: 更长的历史交接。
- `handoff_20260710_final_zh.md`: 上一版稳定交接。
- `USRP292x/RunAnalogLatentBatch.py`: IQ 直传 runner。
- `USRP292x/AnalogLatentLink.py`: IQ decode 和阶段计时。
- `USRP292x/test_analog_latent_link.py`: 当前最重要的单元测试。

生成的 report、raw log、`local_logs`、`analog_latent_runs` 不要混进 git。只把 batch id、关键指标和结论写进文档。
