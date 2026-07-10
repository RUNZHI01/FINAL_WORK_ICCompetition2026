# 2026-07-10 当前交接说明

## 交接结论

当前工作目录是 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`，分支为 `feat/restore-248`。Cockpit Desktop 一键测试路径已经恢复到 IQ 直传，链路包含 handwritten TVM 和 big.LITTLE runner。QPSK 已经可用并作为回归基线，后续优化不要再改 `USRP292x/RunQpskFileBatchSpoolArq.py`。

最新已提交基线到 `cd8e754 docs: record iq overhead validation`。本文档覆盖随后这轮 IQ 失败清理补丁：`USRP292x/RunAnalogLatentBatch.py` 和 `USRP292x/test_analog_latent_link.py`。如果该文档已经在 git 历史中，说明补丁已随文档一起落库。

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

USRP IQ 数据面走直连 USRP，不走 Tailscale。Tailscale 只用于 SSH、控制、状态和日志。Windows 侧 bash/SSH 辅助命令优先用 Docker，Docker 不可用时用 Windows Git Bash，不要用 WSL。板端 Python 固定使用 `/home/user/venv/bin/python`，手动上板时先激活 `/home/user/venv`。

## 推荐运行配置

保持 IQ 直传默认 profile，不要把实验开关混进基线：

```text
MLKEM_TRANSPORT_MODE=usrp
MLKEM_USRP_MODE=ota
OPENAMP_DEMO_LINK_MODE=iq-direct
JSCC_LINK_MODE=iq-direct
OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp
OPENAMP_USRP_TX_RUNNER=docker
REMOTE_USRP_DECODE_PYTHON=/home/user/venv/bin/python
OPENAMP_DEMO_REMOTE_DECODE_PYTHON=/home/user/venv/bin/python
ANALOG_REMOTE_DECODE_WORKER=1
ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal
ANALOG_RX_TAIL_SEC=0.05
ANALOG_RX_SESSION_CONTROL=1
ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=0
ANALOG_PIPELINE_DEPTH=1
OPENAMP_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_TVM_BATCH_RUNNER=biglittle
SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER=1
```

不要默认打开 streaming TVM、depth-2 overlap、tmpfs 输出、`.npy` 输出、soft completion 或 burst-miss retry。这些路径有诊断价值，但之前会放大 300 张长测的 p95、max 或总 wall time。

## 最新验证数据

可靠 300 张 gate：`batch-1783674397-300`，结果 `300/300`、fallback `0`。TVM median/p95 为 `238.87/245.54 ms`，IQ transport median/p95 为 `175.28/337.46 ms`。

问题定位批次：`batch-1783680558-50`，结果 `50/50`、fallback `0`，但有 `51` 条 stage record。image 29 第一次 attempt 出现 `no sync candidate had a complete frame`，第二次 ARQ 恢复。该批次显示 server capture 仍约 `64 ms`，但 runner 侧 `rx_capture_control_overhead_ms` p95 到 `140.31 ms`，`remote_decode_response_overhead_ms` p95 到 `128.12 ms`。

当前补丁后的 Cockpit 等价 50 张验证：`batch-1783681389-50`，结果 `50/50`、fallback `0`。TVM median/p95 为 `240.73/245.35 ms`，IQ image-level median/p95/max 为 `174.91/269.24/347.72 ms`。stage record 正好 `50` 条，server capture median `64.23 ms`，`rx_capture_control_overhead_ms` p95 `48.65 ms`，`remote_decode_response_overhead_ms` p95 `52.45 ms`。这一轮没有出现 no-sync retry，所以只能证明正常路径没有回退；失败后 STOP/drain 的实际收益还要等下一次出现 no-sync 或用专门故障注入验证。

当前补丁后的 300 张 gate：`batch-1783682083-300`，结果 `300/300`、fallback `0`。TVM median/p95 为 `243.38/255.24 ms`，IQ image-level median/p95/max 为 `174.42/308.45/8377.89 ms`，共有 `305` 条 stage record。主要 tail 是 WAIT timeout 后 STOP 控制命令被旧 5s 客户端 timeout 截断、decode worker response wait 约 `7.27 s` 但板端 reported decode 约 `43 ms`、以及一次真实板端 decode 约 `4.09 s`。STOP 客户端 timeout 已修到覆盖 `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0`；下一轮要验证 STOP log 不再出现 `ERR_TIMEOUT`。

STOP timeout-budget 验证：`batch-1783682666-300`，结果 `300/300`、fallback `0`。TVM median/p95 为 `240.17/243.93 ms`，IQ image-level median/p95/max 为 `172.39/310.55/19107.42 ms`，共有 `302` 条 stage record。image 196 仍出现 WAIT timeout 后 STOP `ERR_TIMEOUT`，说明仅扩大 STOP client timeout 不够。根因更新为旧 RX session 未先关闭；代码已改成 WAIT timeout 后先关闭 session，再 direct STOP。

session-before-STOP 验证：`batch-1783683491-300`，结果 `300/300`、fallback `0`。TVM median/p95 为 `242.38/245.50 ms`，IQ image-level median/p95/max 为 `169.48/299.73/6822.54 ms`，共有 `301` 条 stage record。唯一 retry 是 image 263 arm/status timeout，STOP 日志返回 `OK`。剩余 top tail 主要是板端 reported decode stall 和 runner-side decode response wait。

tmpfs decoded-output 复测：`batch-1783684070-50` 使用 `/dev/shm/cockpit_usrp_rx`，结果 `50/50`、fallback `0`。TVM median/p95 为 `241.53/246.04 ms`，IQ median/p95/max 为 `179.92/360.48/3979.87 ms`。`write_npz` median/p95/max 被压到 `1.446/2.553/2.719 ms`，但总链路仍被 arm-not-ready retry 和 decode response wait 拖慢。tmpfs 继续作为诊断项，不默认推广。

QPSK 参考批次 `batch-1783610673-300` 的 transport 约 `2961.78 ms/image`。IQ 直传已经明显快于 QPSK，后续不要用 QPSK 解码拖慢飞腾派路径。

## 本次 RX 失败清理补丁

补丁目标是修复 “WAIT 已成功但 decode/no-sync 失败后直接重试” 的 RX 状态继承风险。现在 `process_image()` 在 WAIT 成功后会标记 RX 需要失败清理；如果后续 decode 状态失败或抛出 no-sync 异常，会发送 `STOP` 并 drain，再进入 ARQ retry。

涉及文件：

- `USRP292x/RunAnalogLatentBatch.py`: 增加 decode 失败后的 `stop_rx_capture(...)` 清理路径，并记录 `rx_server_stop_cmd_wall_sec` / `rx_server_stop_wait_wall_sec`。
- `USRP292x/RunAnalogLatentBatch.py`: 修正 `stop_rx_capture(...)` 客户端 timeout，避免 8s drain profile 被旧 5s cap 提前切断。
- `USRP292x/RunAnalogLatentBatch.py`: 修正 WAIT timeout cleanup 顺序，先关闭 RX session，再通过 direct STOP 清理。
- `USRP292x/test_analog_latent_link.py`: 增加和更新失败路径测试，覆盖远端 decode 异常、本地 decode status failure、WAIT timeout、arm status timeout 等相邻路径。

已跑过的本地验证：

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

其中 pytest 结果为 `91 passed`，QPSK diff 为空。`git diff --check` 只有既有 CRLF 提示，没有 trailing whitespace 错误。

## 重启和 Cockpit 等价验证

先全停，避免继承上一轮状态：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

重启 backend 后，用和 Cockpit 测试按钮等价的接口触发：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

查询状态时不要直接打印完整 `/api/system-status` 到公开文档，里面可能带本地配置或敏感字段。

## 下一步建议

1. 先决定是否提交当前 RX 失败清理补丁。提交前清理 `Semantic-Communication/session_bootstrap/reports/openamp3_usrp_1783681389_current_*.json/.md` 这类本地运行报告，除非要作为证据归档。
2. 跑一次 300 张 Cockpit 等价 gate，确认 IQ median 仍低于 `200 ms`，p95 尽量低于 `450 ms`，fallback 为 `0`。
3. 下一步集中处理 decode-side tail：板端 reported decode stall 和 runner 等 decode worker response。RX STOP cleanup 目前已经过 300 张验证。
4. 若正常路径继续稳定，下一步再处理 `remote_decode_response_overhead_ms` 和 RX capture/control tail。不要在 RX 状态机稳定前默认开启双缓冲或 streaming TVM。
5. 认证和 ML-KEM 先维持不进 per-image hot path。security-on 要单独跑 20 张和 300 张，对比开销；如果超过约 `5%`，性能基线继续保留 security-off 并记录差值。

## 交接注意事项

不要提交板端密码、Tailscale 凭据、私钥、本机地址或临时 SSH 命令里的敏感信息。账号、密码、host、port 只放本地环境变量。

接手人优先看这几个文件：

- `plan_20260710.md`: IQ 优化路线和历史实验记录。
- `handoff_20260710_final_zh.md`: 上一版完整交接和推荐配置。
- `USRP292x/RunAnalogLatentBatch.py`: 当前 IQ 直传 runner。
- `USRP292x/test_analog_latent_link.py`: 当前最重要的单元测试覆盖。

每次改动 IQ 前后都跑：

```powershell
git status -sb --untracked-files=all
python -m pytest USRP292x/test_analog_latent_link.py -q
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最后一条必须为空。
