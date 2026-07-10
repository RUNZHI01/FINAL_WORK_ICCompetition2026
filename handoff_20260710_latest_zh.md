# 2026-07-10 最新交接说明

## 当前结论

当前工作目录是 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`，分支为 `feat/restore-248`。最新已提交基线是 `eda3eaf perf: record failed iq decode timing`，分支相对远端领先 21 个提交。IQ 直传已经恢复到 Cockpit Desktop 一键测试路径，链路包含 handwritten TVM 和 big.LITTLE runner；QPSK 已可用并冻结，后续不要改 `USRP292x/RunQpskFileBatchSpoolArq.py`。

最新 300 张 gate 是 `batch-1783686930-300`：`300/300`，fallback `0`。TVM median/p95/max 为 `240.29/242.87/257.55 ms`；IQ total median/p95/max 为 `166.04/288.97/7683.31 ms`。结论很清楚：IQ median 已低于 TVM，但 p95 和 max 还没收干净，主要问题在 RX control tail、runner 等 decode response，以及一次 `/home` `.npz` 写入 stall。

## 当前工作区状态

工作区当前有未提交改动：

- `USRP292x/RunAnalogLatentBatch.py`
- `USRP292x/test_analog_latent_link.py`

这部分是在做 opt-in 的批次级 RX control session 复用，目标是减少每张图反复建立 CAPTURE/WAIT 控制连接造成的 tail。当前代码已经完成本地实现：`ANALOG_RX_BATCH_SESSION_CONTROL=1` / `--rx-batch-session-control` 会在非 pipeline 顺序批次里打开一个 RX control session，跨图片复用，并在 batch 结束关闭；WAIT timeout、capture busy 或 session 失效后会清空 `args.rx_control_session`。本地验证已通过，现场 50/300 张 gate 还没跑。

## 推荐运行配置

保持当前稳定 IQ profile，不要默认打开实验开关：

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

不要默认开启 streaming TVM、depth-2 overlap、tmpfs 输出、`.npy` 输出、soft completion 或 burst-miss retry。它们有诊断价值，但之前会放大 300 张长测的 p95、max 或总 wall time。

## 重启和验证流程

Windows 侧 bash/SSH 辅助命令优先走 Docker，实在不行用 Windows Git Bash，不要用 WSL。板端用户名和密码本地已知，但不要写入仓库；板端 Python 使用 `/home/user/venv/bin/python`，手动上板时先执行 `source /home/user/venv/bin/activate`。

全停后再重启，避免继承上一轮状态：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
  -ContentType 'application/json' -Body '{}'

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Cockpit 按钮等价验证：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

不要把完整 `/api/system-status` 输出贴进文档或提交记录，里面可能含本机配置和敏感字段。

## 下一步

1. 保持 `ANALOG_RX_BATCH_SESSION_CONTROL=1` 为 opt-in。它不能直接默认打开，因为 RX server 单客户端会话被长时间占用时，外部 `STATUS/STOP` 连接会被挡住。
2. 现场先跑 Cockpit 等价 50 张；如果 `50/50`、fallback `0` 且 `rx_capture_control_overhead_ms` p95 改善，再跑 300 张 gate。
3. 提交前本地验证：

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py USRP292x\AnalogLatentLink.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最近一次结果：`98 passed in 32.02s`；`py_compile` 通过；`git diff --check` 只有 CRLF 提示；QPSK diff 为空。

4. 300 张 gate 通过后再更新 `plan_20260710.md`、`handoff_20260710_current_zh.md` 和最终交接文档，并提交。生成的 report、raw log、`local_logs` 不要混进 git。

## 安全和认证

当前性能基线里 runtime security channel 不在 per-image hot path。认证和 ML-KEM 后续要单独 A/B：先 20 张确认握手是 session-level，再跑 300 张。如果 security-on 开销超过约 `5%`，性能基线继续保持 security-off，并在文档里记录差值。

## 重点文件

- `plan_20260710.md`: 完整 IQ 优化计划和历史实验记录。
- `handoff_20260710_current_zh.md`: 当前较详细的历史交接。
- `handoff_20260710_final_zh.md`: 早前稳定版交接。
- `USRP292x/RunAnalogLatentBatch.py`: IQ 直传 runner 和当前 WIP。
- `USRP292x/test_analog_latent_link.py`: 关键单元测试。
