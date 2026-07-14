# HANDOFF

更新时间：2026-07-13
当前分支：`feat/restore-248`
交接前代码保存点：以当前分支最新提交为准；需要精确 hash 时运行 `git log -1 --oneline`。

## 当前主线

演示主线是 `Cockpit Desktop -> USRP IQ 直传 -> 板端 TVM big.LITTLE 重建`。QPSK 已能稳定跑通，作为可靠 fallback 保留，不建议继续改。预录 TVM/MNN/PyTorch 已恢复；预录模式只走推理进度，不走 USRP 三阶段进度。

默认 UI 分工：

- 左栏：数据面输入模式、QPSK/IQ 选择、IQ 直传诊断、输入/输出目录、批量运行。
- 右栏：地图、硬件状态、板卡密码、安全信道。
- 板卡密码行显示主机、用户、会话密码状态和服务端标识。
- 安全信道显示加密、认证、作用范围和运行状态。

## 相对 FINAL WORK 初版的主要变化

这几天的改动已经不只是参数微调。接手时按下面这些差异理解当前系统：

| 方向 | 初版状态 | 当前状态 |
|---|---|---|
| 主数据面 | 以预录/传统 live 路径为主，USRP 更接近验证链路 | 默认 USRP IQ 直传，QPSK 作为稳定 fallback |
| TVM 指标 | 需要恢复约 250 ms 的 big.LITTLE 预录指标 | 预录 TVM 已恢复，300 张 median `243.30 ms`，mean `252.91 ms` |
| IQ 直传 | 不是主演示路径 | 已接入 Cockpit、板端 remote-dir、TVM big.LITTLE；accepted 300 张 IQ transport p95 `198.46 ms` |
| QPSK | 还在调试和性能对比 | 已能 300/300 跑通，但约 `2.96 s/image`，不再继续优化 |
| 推理引擎 | TVM 主线，MNN/PyTorch 状态不稳定 | TVM 是主路径；MNN 预录和 USRP remote-dir 已恢复；PyTorch 在 USRP 下保留预录参考 |
| Cockpit UI | 控件堆叠，左右栏职责不清，USRP 指标展示不完整 | 左栏管数据面和 IQ 诊断，右栏管地图、硬件、板卡密码、安全信道；USRP 有三阶段进度和独立 benchmark |
| 结果对比 | USRP/批量结果有时不刷新或显示旧状态 | USRP 三种模式会更新推理结果对比框，切换模式会清理旧进度状态 |
| IQ 可靠性 | 弱同步、burst miss、299/300 等问题容易暴露 | 默认 ARQ5、burst-miss retry、low-sync retry；仍需注意现场 RF 环境和天线位置 |
| 安全链路 | UI 和真实作用范围不够明确 | 默认启用 ML-KEM+SM4 和 ML-DSA+SM2；API/UI 明确显示作用范围 |
| 安全边界 | 容易被误说成 USRP IQ payload 已加密 | 已明确：USRP IQ 数据面不做 ML-KEM/SM4 payload 加密，安全信道用于控制/认证面准入 |
| 启动环境 | 偏真机 Linux/手动配置，迁到 Windows/容器后状态分散 | `start-dev.sh` 统一默认 USRP IQ、Docker SSH/TX、板端 venv、认证开关和常用 IQ 参数 |
| 板卡会话 | 地址、密码、目录参数容易散落在脚本里 | Cockpit 可写入 board access；板卡地址、RX 目录、链路模式向参数化收敛 |
| 文档和测试 | 资料分散在运行日志和零散报告里 | 新增/更新 runbook、安全审计、HANDOFF、layout tests、crypto scope/gate/auth 负测 |

## 启动方式

当前仍保留 Git Bash 启动外壳，Bash/SSH 热路径优先走 Docker，不用 WSL。

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\FINAL_WORK_ICCompetition2026
$env:REMOTE_PASS = 'user'
& 'E:\Software\Scoop\apps\git\current\bin\bash.exe' -lc './Semantic-Communication/cockpit_desktop/start-dev.sh'
```

比赛演示默认启用启动预热：`COCKPIT_STARTUP_USRP_WARMUP=1`、`COCKPIT_STARTUP_USRP_WARMUP_COUNT=5`。脚本会先在后端静默跑完 5 张 `USRP IQ + TVM`，清掉隐藏 batch-state，然后才启动/显示 Cockpit Desktop 前端。这样第一张冷启动 decode worker、TVM 和文件路径初始化尾部不会进入评委可见界面。启动前请临时设置 `REMOTE_PASS`，或在脚本提示时输入；若只是调 UI，可设置 `COCKPIT_STARTUP_USRP_WARMUP=0` 跳过。

启动后：

- 后端：`http://127.0.0.1:8079`
- 前端/Electron/Vite：`http://localhost:5173/#/`
- 板卡默认地址：`100.121.87.73`
- 板卡用户名/密码：`user / user`
- 板端 IQ decode Python：`/home/user/venv/bin/python`

USRP2922 网口恢复脚本按用途分开。上位机/TX 侧使用：

```bash
sudo ./USRP292x/SetupUsrp2922UpperHostNetwork.sh
```

板端/RX 侧使用：

```bash
sudo ./USRP292x/SetupUsrp2922BoardNetwork.sh
# 双网口板端如自动探测选错，可显式指定：
sudo env USRP2922_BOARD_IFACE=eth0 ./USRP292x/SetupUsrp2922BoardNetwork.sh
```

通用诊断入口是 `./USRP292x/Usrp2922Network.sh detect|probe|auto-init|status`。不要再使用旧命名入口。

如果重启后 UI 未带入会话，可以在页面里重新保存板卡密码，或用 API 写入：

```powershell
$body = @{
  host = '100.121.87.73'
  user = 'user'
  password = 'user'
  port = '22'
  transport_mode = 'usrp'
  jscc_link_mode = 'iq-direct'
  auth_enabled = $true
  auth_sig_policy = 'DUAL_REQUIRED'
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8079/api/session/board-access' `
  -ContentType 'application/json' -Body $body
```

## 推荐运行参数

`start-dev.sh` 当前默认值如下，接手时以这里为准：

| 参数 | 默认值 | 用途 |
|---|---|---|
| `REMOTE_HOST` | `100.121.87.73` | 当前验证环境板卡地址，比赛现场可覆盖 |
| `REMOTE_USER` | `user` | 板卡 SSH 用户 |
| `MLKEM_TRANSPORT_MODE` | `usrp` | Cockpit 默认进入 USRP 模式 |
| `OPENAMP_DEMO_INPUT_SOURCE_MODE` | `usrp` | 默认从 USRP 数据面取输入 |
| `JSCC_LINK_MODE` | `iq-direct` | USRP 数据面默认 IQ 直传 |
| `OPENAMP_DEMO_LINK_MODE` | `iq-direct` | 后端 runner 选择 IQ 直传 |
| `MLKEM_AUTH_ENABLED` | `1` | 默认开启认证面 |
| `MLKEM_AUTH_SIG_POLICY` | `DUAL_REQUIRED` | SM2 和 ML-DSA 都要通过 |
| `MLKEM_AUTH_SERVER_ID` | `phytium-board` | UI 中显示的服务端标识 |
| `MLKEM_CIPHER_SUITE` | `SM4_GCM` | TCP 安全信道默认密码套件 |
| `MLKEM_USRP_MAX_ARQ_ROUNDS` | `5` | IQ 弱同步/漏帧兜底重试 |
| `REMOTE_USRP_RX_DIR` | `/home/user/cockpit_usrp_rx` | TVM/MNN 消费的板端 decoded latent 目录 |
| `REMOTE_RX_RUN_ROOT` | `/dev/shm/usrp292x_remote_runs` | 板端 RX 临时运行目录 |
| `OPENAMP_DEMO_REMOTE_DECODE_PYTHON` | `/home/user/venv/bin/python` | 板端 IQ decode 虚拟环境 |
| `OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT` | `0` | 保持 TX/RX 常驻，减少反复初始化 |
| `COCKPIT_STARTUP_USRP_WARMUP` | `1` | 显示 Cockpit 前先做 USRP IQ + TVM 启动预热 |
| `COCKPIT_STARTUP_USRP_WARMUP_COUNT` | `5` | 启动预热张数 |
| `COCKPIT_STARTUP_USRP_WARMUP_TIMEOUT_SEC` | `360` | 预热完成等待上限 |
| `ANALOG_SPS` | `2` | IQ 直传每符号采样数 |
| `ANALOG_AMPLITUDE` | `6000` | 当前验证环境下的 TX 幅度 |
| `ANALOG_RX_TAIL_SEC` | `0.040` | RX capture 尾部保护 |
| `ANALOG_MIN_SYNC_METRIC` | `0.05` | IQ 同步通过阈值 |
| `OPENAMP_IQ_STREAMING_TVM` | `0` | 默认不边收边跑 TVM |
| `ANALOG_PIPELINE_DEPTH` | `1` | 默认串行推进，避免队列尾部扩大 |
| `ANALOG_PIPELINE_RF_DECODE_OVERLAP` | `0` | 默认不让 RF/decode 重叠 |
| `RX_ARM_WAIT_MS` | `500` | 等 RX capture 就绪的确认窗口 |
| `ANALOG_PRECONNECT_CONTROL` | `1` | 预连接控制面，减少反复建连 |
| `ANALOG_RX_SESSION_CONTROL` | `1` | 保持 RX 控制会话，当前启动脚本默认开启 |
| `ANALOG_RX_BATCH_SESSION_CONTROL` | `1` | 批量复用 RX 会话 |
| `ANALOG_RETRY_ON_BURST_MISS` | `1` | 捕获突发缺失时重试 |
| `ANALOG_RETRY_ON_LOW_SYNC` | `1` | sync metric 低于阈值时重试 |
| `ANALOG_LOW_SYNC_RETRY_THRESHOLD` | `0.08` | low-sync retry 阈值 |
| `ANALOG_REMOTE_DECODE_RESULT_MODE` | `remote-dir` | 板端就地解码并通过目录交付 latent |
| `ANALOG_REMOTE_DECODE_RESPONSE_MODE` | `minimal` | 减小 decode worker 响应体 |
| `ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY` | `1` | 响应只带 summary，降低控制面负载 |
| `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC` | `0.05` | decode 结果软完成等待 |
| `ANALOG_REMOTE_DECODED_FORMAT` | `npy` | decoded latent 默认写 `.npy` |
| `ANALOG_DECODE_PIPELINE_WARMUP` | `1` | 启动时预热板端 decode worker |
| `ANALOG_REMOTE_CLEANUP_MODE` | `skip` | 热路径不做后台清理，演示后手动清 |
| `ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS` | `1` | 提前建目录，减少热路径 SSH 抖动 |
| `ANALOG_RX_SC16_MMAP` | `1` | RX sc16 读取使用 mmap |
| `ANALOG_RX_CLIPPING_DECIMATION` | `8` | clipping 统计降采样 |
| `ANALOG_RX_POST_QUANTIZE` | `0` | 不写旧 quant/scale/zero_point 诊断数组 |
| `ANALOG_ROBUST_SYNC` | `0` | 不默认启用慢速 robust CFO fallback |
| `ANALOG_RX_WAIT_TIMEOUT_SEC` | `1.0` | RX WAIT 当前超时预算 |
| `ANALOG_RX_ARM_STATUS_TIMEOUT_SEC` | `0.5` | RX arm 状态确认超时 |
| `RX_STOP_WAIT_MS` | `8000` | 保守 STOP 等待 |
| `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC` | `8.0` | 保守 RX drain |

## 实验开关

以下开关不能作为演示默认。要做 A/B 时单独开启，并记录批次号。

| 开关 | 不默认启用的原因 |
|---|---|
| `OPENAMP_IQ_STREAMING_TVM=1` / `USRP_IQ_STREAMING_TVM=1` | 已试过边收边推理，板端 CPU/IO 争用使总耗时和 p95 变差 |
| `ANALOG_PIPELINE_RF_DECODE_OVERLAP=1` | 目标是“收下一批时解上一批”，但当前收益不稳，容易扩大尾部 |
| `ANALOG_PIPELINE_DEPTH>1` | 深队列增加并发复杂度；之前未形成稳定收益 |
| `ANALOG_REMOTE_DECODE_REQUEST_TIMEOUT_SEC` | 适合定位 decode worker 卡顿；默认开启会把 timeout/restart 成本带入 p95 |
| `ANALOG_REMOTE_DECODE_RESTART_ON_TIMEOUT=1` | 能恢复卡住的 worker，但 restart 会拖长尾部 |
| `ANALOG_REMOTE_DECODE_PUBLISH_EVENT=1` | 用于观察板端文件发布细节；热路径不需要 |
| `ANALOG_REMOTE_STALL_SNAPSHOT=1` | 用于抓 stall 快照；演示时会增加诊断动作和日志噪声 |
| `REMOTE_USRP_RX_DIR=/dev/shm/...` | tmpfs 能降低文件写尾部，但容量、清理和重启一致性风险更高 |
| `RX_STOP_WAIT_MS=200` 等 short STOP | 已失败过 300 张 gate，不能做默认 |
| `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=0.2` 等 short drain | 容易留下 RX 残留状态，影响下一轮 |
| `ANALOG_RX_WAIT_TIMEOUT_SEC<1.0` | 会更快暴露等待超时，但容易放大 retry 和 p95；当前默认保留 `1.0` |
| `ANALOG_ROBUST_SYNC=1` | 可以救部分弱同步帧，但慢速 CFO fallback 会明显拖慢尾部 |

注意：`ANALOG_PRECONNECT_CONTROL=1`、`ANALOG_RX_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_CONTROL=1` 现在是启动脚本默认值，不再按早期 runbook 的“纯实验”口径处理。若要改它们，必须重新跑 20/300 张硬件回归。

## 当前指标

可汇报的基准：

| 路径 | 样本 | 传输/解包 | TVM 重建 | 备注 |
|---|---:|---:|---:|---|
| 预录 TVM big.LITTLE | 300 | 无 USRP | median `243.30 ms`, mean `252.91 ms`, p95 `311.88 ms` | 250 ms 参考线 |
| USRP IQ 直传 accepted profile | 300 | median `166.63 ms`, p95 `198.46 ms`, max `15934.08 ms` | median `241.20 ms`, p95 `242.59 ms`, max `259.35 ms` | 当前速度结果，max 是已恢复的 RF/RX outlier |
| QPSK fallback | 300 | `2961.78 ms/image` | median `240.06 ms`, p95 `242.88 ms` | 稳定但慢，不再优化 |

给写文档同学的典型值口径：

| 可写项 | 推荐写法 |
|---|---|
| 主链路 | USRP IQ 直传 + 板端 TVM big.LITTLE 重建 |
| IQ 传输/解包 | median `166.63 ms`，p95 `198.46 ms`；不要用单次 max 表示典型体验 |
| TVM 重建 | median `241.20 ms`，p95 `242.59 ms` |
| 250 ms 参考线 | 预录 TVM 300 张 median `243.30 ms`，mean `252.91 ms` |
| QPSK 对照 | 约 `2.96 s/image`，作为稳定 fallback，不作为速度主线 |
| 图像质量 | PSNR `37.0445`，SSIM `0.97494`，artifact SHA matched |
| 安全口径 | ML-KEM+SM4 和 ML-DSA+SM2 用于控制/认证面准入；USRP IQ payload 不宣称已加密 |

图像质量按当前 accepted IQ/TVM 路径保持：

```text
PSNR = 37.0445
SSIM = 0.97494
artifact SHA matched
```

## 安全边界

不要把 USRP IQ 数据面说成已经被 ML-KEM/SM4 加密。

准确说法：

- TCP/ML-KEM 路径：latent payload、ACK、结果经 ML-KEM 派生密钥和 SM4/AES AEAD 保护。
- USRP IQ 直传路径：ML-KEM + SM4 + ML-DSA + SM2 用作控制/认证面准入 gate；IQ 无线数据面仍是 USRP RF 链路。

`/api/crypto-status` 已返回：

```text
security_scope=control_gate
security_scope_label=控制/认证面准入
data_plane_encrypted=false
tcp_payload_encrypted=false
usrp_payload_encrypted=false
```

已有测试证明：

- 错误 peer public key 会导致 SM2/ML-DSA 验签失败。
- USRP Current 在 ML-KEM control gate 不可用时不会启动 USRP data plane launcher。

## 常见问题

`board status endpoint unavailable: WinError 10061`
表示板端 status/tcp server 没在对应端口接收连接。UI 仍能显示板卡会话和安全作用范围，但安全通道实时状态会是 idle/error。需要检查板端 tcp server 或让 Cockpit 触发重置安全信道。

硬件面板 CPU/MEM 卡住
通常是遥测轮询暂停或板端状态服务不可达。跑 USRP 批量时本来会推迟部分 SSH 轮询，避免干扰热路径。

USRP 卡在 299/300 或显示未进入有效重建链路
优先看 IQ sync/ARQ 日志。当前默认已启用 ARQ5、burst-miss retry、low-sync retry，仍可能受天线位置和现场 RF 环境影响。

MNN/PyTorch 与 USRP
TVM 是主路径。MNN 已接 USRP remote-dir latent；PyTorch 在 USRP 模式下仍作为预录参考，不启动 USRP 传输。

## 不建议改动

- 不要再改 QPSK 主逻辑。
- 不要默认启用 `OPENAMP_IQ_STREAMING_TVM`。
- 不要缩短 STOP/RX drain 超时。
- 不要把 `REMOTE_USRP_RX_DIR` 改到 tmpfs 当默认。
- 不要把运行日志、`keys/`、`nul`、`cockpit_desktop/logs/` 提交进 git。

## 文件组织现状

源码边界还算清楚，但根目录历史交接文档和运行残留偏多。接手时按下面划分：

| 路径 | 状态 |
|---|---|
| `Semantic-Communication/cockpit_desktop/` | Cockpit Electron/React 主 UI |
| `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/` | Cockpit 后端和 OpenAMP/USRP 编排入口 |
| `USRP292x/` | QPSK/IQ USRP 数据面、persistent TX/RX、analog latent runner |
| `mlkem_link/` | ML-KEM/SM4 安全信道和认证实现 |
| `scripts/` | TCP client/server、TVM/MNN/PyTorch 辅助脚本 |
| `docker/` | Docker/演示启动脚本 |
| `docs/` | 现在应该优先看这里的 runbook 和安全审计 |
| `handoff_20260710*.md`、`JSCC_TRAN_HANDOFF.md`、`plan_20260710.md` | 历史交接和计划，保留参考，不是当前入口 |
| `logs/`、`runtime_logs/`、`local_logs/`、`.logs/`、`tmp/`、`artifacts/` | 运行输出或临时产物，不作为源码入口 |
| `keys/` | 本地认证公钥/密钥材料，不要提交私钥 |
| `nul` | Windows 误生成文件，保持不提交 |

目前不建议赛前重排文件树。真正需要清理时，先只归档旧 handoff 文档和运行日志，不要移动 `Semantic-Communication/`、`USRP292x/`、`mlkem_link/` 这些路径，很多脚本仍依赖现有相对路径。

## 验证命令

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\FINAL_WORK_ICCompetition2026

python -m pytest mlkem_link/tests/test_auth.py::TestTranscript `
  mlkem_link/tests/test_auth.py::TestWireCodec `
  mlkem_link/tests/test_auth.py::TestSignVerify `
  mlkem_link/tests/test_auth.py::TestFinished -q

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_crypto_runtime.py -q

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_run_demo_inference_with_usrp_transport_uses_local_usrp_job_with_mlkem_control `
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_run_demo_inference_with_usrp_transport_blocks_when_mlkem_control_unavailable `
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_get_crypto_status_marks_usrp_security_as_control_gate `
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_get_crypto_status_marks_tcp_security_as_payload_encryption -q

cd Semantic-Communication/cockpit_desktop
node --test src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs
npm run typecheck
```

## 文档入口

- `docs/cockpit_usrp_qpsk_tvm_runbook.md`：USRP/IQ/QPSK 运行记录和参数历史。
- `docs/security_crypto_auth_audit_20260713.md`：加密与认证作用范围审计。
- `docs/analog_latent_iq_phy.md`：analog latent-IQ PHY 设计说明。

## 去 Git Bash 的判断

现在不建议在赛前大改。若必须做，先做最小档：新增 `start-dev.ps1` / `stop-dev.ps1`，只替换 Cockpit 日常启动外壳，预计 2-4 小时。Docker 容器内部继续用 Bash。完全移除本机 Bash 假设需要排查 `*.sh`、`nohup/env/cygpath/MSYS2_*` 和路径转换，至少 1-2 天，还要跑硬件 smoke。
