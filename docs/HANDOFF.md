# HANDOFF

更新时间：2026-07-17
代码版本以仓库当前提交为准；需要精确 hash 时运行 `git log -1 --oneline`。

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
| IQ 直传 | 不是主演示路径 | 已接入 Cockpit、板端 remote-dir、TVM big.LITTLE；2026-07-16 严格质量门限下 `300/300` 通过 |
| QPSK | 还在调试和性能对比 | 已能 300/300 跑通，但约 `2.96 s/image`，不再继续优化 |
| 推理引擎 | TVM 主线，MNN/PyTorch 状态不稳定 | TVM 是主路径；MNN 预录和 USRP remote-dir 已恢复；PyTorch 在 USRP 下保留预录参考 |
| Cockpit UI | 控件堆叠，左右栏职责不清，USRP 指标展示不完整 | 左栏管数据面和 IQ 诊断，右栏管地图、硬件、板卡密码、安全信道；USRP 有三阶段进度和独立 benchmark |
| 结果对比 | USRP/批量结果有时不刷新或显示旧状态 | USRP 三种模式会更新推理结果对比框，切换模式会清理旧进度状态 |
| IQ 可靠性 | 弱同步、burst miss、299/300 等问题容易暴露 | 30 张分段、两轮失败子集补传、固定峰值导频和质量门限已完成 300 张回归；RX 停滞后会执行真实 `RESET`，不再只重连控制口 |
| 安全链路 | UI 和真实作用范围不够明确 | 默认启用 ML-KEM+SM4 和 ML-DSA+SM2；API/UI 明确显示作用范围 |
| 安全边界 | 容易被误说成 USRP IQ payload 已加密 | 已明确：USRP IQ 数据面不做 ML-KEM/SM4 payload 加密，安全信道用于控制/认证面准入 |
| 启动环境 | 偏真机 Linux/手动配置，迁到 Windows/容器后状态分散 | `start-dev.sh` 统一默认 USRP IQ、Docker SSH/TX、板端 venv、认证开关和常用 IQ 参数；板端 USRP RX 网口可由 systemd 开机自恢复 |
| 板卡会话 | 地址、密码、目录参数容易散落在脚本里 | Cockpit 可写入 board access；板卡地址、RX 目录、链路模式向参数化收敛 |
| 文档和测试 | 资料分散在运行日志和零散报告里 | 新增/更新 runbook、安全审计、HANDOFF、layout tests、crypto scope/gate/auth 负测 |

## 启动方式

当前仍保留 Git Bash 启动外壳，Bash/SSH 热路径优先走 Docker，不用 WSL。

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026
$env:REMOTE_PASS = 'user'
& 'E:\Software\Scoop\apps\git\current\bin\bash.exe' -lc './Semantic-Communication/cockpit_desktop/start-dev.sh'
```

比赛演示启动不再运行 10 张图片预热。脚本在显示 UI 前只建立板卡会话，拉起 ML-KEM/认证服务和常驻 USRP TX/RX，并等待服务就绪；不会创建隐藏 batch-state 或重建输出。正式 IQ 串行长批次默认每 30 张重建 RX streamer，TX 保持常驻。

IQ 源码同步与日常启动已经分开。修改 `USRP292x/`、encoder 或 TVM helper 后运行一次：

```powershell
pwsh -File .\docker\prepare-iq-board-sync.ps1 -Deploy -Verify `
  -BoardHost 100.121.87.73 -BoardUser user -BoardPassword user
```

同步包和 SSH/SCP 都在 Docker 内处理，不用 WSL。当前 Tailscale 地址可以保留；现场变化时用 `-BoardHost` 覆盖。`-Verify` 只做哈希、`py_compile` 和 runner 入口检查，不会向 `tvm310_safe` 安装 pytest。需要重编译 OTA server 时额外加 `-BuildOta`，并先停掉正在运行的 RX/TX 任务。

启动后：

- 后端：`http://127.0.0.1:8079`
- 前端/Electron/Vite：`http://localhost:5173/#/`
- 板卡默认地址：`100.121.87.73`
- 板卡用户名/密码：`user / user`
- 板端 IQ decode Python：`/home/user/venv/bin/python`

USRP2922 网口恢复脚本按用途分开。上位机/TX 侧使用：

```powershell
# Windows 上位机先看状态，不改配置
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status

# 管理员 PowerShell 中配置上位机/TX 网口
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target UpperHost -InterfaceAlias "以太网"

# 板端/RX 网口默认开机自恢复；不通时先用快速兜底
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Board -BoardHost 100.121.87.73 -Fast
```

这个入口只用于现场恢复。Windows 上位机侧目标形态是 `192.168.10.1/32` 加 `192.168.10.2/32` 显式路由，不依赖整段 `/24` 子网，避免多网卡时路由跑偏。

板端自启动服务为 `usrp2922-board-autostart.service`，一次性安装入口：

```bash
bash /home/user/USRP292x/InstallBoardUsrp2922Autostart.sh
```

服务会在开机后检查 `eth0 -> 192.168.10.22`，不通时使用快速恢复；完整排障再运行不带 `-Fast` 的 `ConfigureUsrp2922DemoNetwork.ps1 -Target Board`。

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
| `MLKEM_USRP_MAX_ARQ_ROUNDS` | `12` | IQ 弱同步/漏帧兜底重试；严格质量门限下给 RF 抖动留恢复空间 |
| `REMOTE_USRP_RX_DIR` | `/home/user/cockpit_usrp_rx` | TVM/MNN 消费的板端 decoded latent 目录 |
| `REMOTE_RX_RUN_ROOT` | `/dev/shm/usrp292x_remote_runs` | 板端 RX 临时运行目录 |
| `OPENAMP_DEMO_REMOTE_DECODE_PYTHON` | `/home/user/venv/bin/python` | 板端 IQ decode 虚拟环境 |
| `OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT` | `0` | 保持 TX/RX 常驻，减少反复初始化 |
| `OPENAMP_USRP_TX_DOCKER_NETWORK` | Windows `bridge`；Linux `host` | Windows Docker Desktop 直接发布 `127.0.0.1:29221`；Linux 保留 host network |
| `OPENAMP_IQ_SEGMENT_SIZE` | `30` | IQ 串行长批次每段张数；段间重建 RX streamer，并重置常驻 TX 的发送状态 |
| `OPENAMP_IQ_SEGMENT_REPAIR_PASSES` | `2` | 段内首轮失败项的子集补传次数；默认两轮用于覆盖偶发低同步率 |
| `ANALOG_SPS` | `2` | IQ 直传每符号采样数 |
| `ANALOG_AMPLITUDE` | `6000` | 当前验证环境下的 TX 幅度 |
| `ANALOG_TX_NORMALIZATION_REFERENCE_PEAK` | `6` | 固定 IQ 波形归一化参考峰值，使导频功率不随 latent 峰值变化；`0` 恢复旧的逐帧峰值归一化 |
| `ANALOG_RX_TAIL_SEC` | `0.040` | RX capture 尾部保护 |
| `ANALOG_MIN_SYNC_METRIC` | `0.05` | IQ 同步通过阈值 |
| `ANALOG_SYNC_PROFILE` | `fast-first` | 先短窗口同步，失败再 fallback/retry |
| `ANALOG_FAST_SYNC_CANDIDATES` | `4` | fast-first 候选数 |
| `ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS` | `1024` | fast-first 搜索窗口 |
| `ANALOG_FALLBACK_SYNC_CANDIDATES` | `4` | fallback 候选数，演示默认保持轻量 |
| `ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS` | `1024` | fallback 搜索窗口 |
| `ANALOG_IQ_QUALITY_GATE` | `1` | decoded latent 进入 TVM 前做质量门限 |
| `ANALOG_IQ_QUALITY_MIN_SYNC_METRIC` | `0.75` | TVM 前质量门限的同步下限；好 run（如 `1784140407`、`1784139032`）均高于该值，低于该值更可能出现彩色噪点 |
| `ANALOG_IQ_MIN_PILOT_GAIN_RATIO` | `0.85` | mid-pilot 增益塌陷时触发 ARQ/失败；用于阻止弱导频 latent 进入 TVM |
| `ANALOG_IQ_MAX_EVM_RMS` | `0.75` | payload EVM 过高时拒绝坏帧 |
| `ANALOG_IQ_MIN_SNR_DB` | `3.0` | 估计 SNR 过低时拒绝坏帧 |
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
| `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC` | `0.05` | decode 结果软完成等待；`ANALOG_IQ_QUALITY_GATE=1` 时默认压成 0，等待完整 summary 再判定 |
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
| `OPENAMP_IQ_SEGMENT_SIZE=0` | 仅用于回归旧连续模式；长批次可能随时间退化，演示不要开 |
| `OPENAMP_IQ_SEGMENT_REPAIR_PASSES=0` | 保留分段但关闭失败子集补传；只用于分离评估 RESET 和 repair 开销 |
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
| `ANALOG_IQ_QUALITY_GATE=0` | 只能用于定位旧行为；关闭后坏 latent 可能被送入 TVM，出现 300/300 但重建是彩色噪声 |
| `ANALOG_IQ_ALLOW_SOFT_COMPLETE_WITH_QUALITY_GATE=1` | 只能用于性能实验；会在质量门限开启时恢复 soft-complete，可能缺少 sync/pilot 指标，演示不要开 |
| 放宽 `ANALOG_IQ_*` 质量阈值 | 可能提升表面通过率，但会降低重建视觉质量；演示前必须重新跑图像质量 gate |

注意：`ANALOG_PRECONNECT_CONTROL=1`、`ANALOG_RX_SESSION_CONTROL=1`、`ANALOG_RX_BATCH_SESSION_CONTROL=1` 现在是启动脚本默认值，不再按早期 runbook 的“纯实验”口径处理。若要改它们，必须重新跑 20/300 张硬件回归。

## 当前指标

可汇报的基准：

| 路径 | 样本 | 传输/解包 | TVM 重建 | 备注 |
|---|---:|---:|---:|---|
| 预录 TVM big.LITTLE | 300 | 无 USRP | median `243.30 ms`, mean `252.91 ms`, p95 `311.88 ms` | 250 ms 参考线 |
| USRP IQ 热启动验收（2026-07-17） | 100 | `104.061 s` 总计，261 次 OTA，`100/100` accepted | core wall `85.212 s`，median `244.92 ms`，mean `261.75 ms` | 点击到完成 `240.19 s`；POST `0.857 s`；CPU/MEM 峰值 `92.38%/62.56%` |
| USRP IQ 严格可靠性 profile | 300 | median `411.59 ms`, p95 `3423.45 ms`, `300/300` accepted | median `245.42 ms`, mean `254.71 ms`, p95 `301.73 ms` | 30 张分段；11 次 RESET 共 `448.69 ms`；10 次 worker 清理共 `522.72 ms` |
| USRP IQ 历史速度 profile | 300 | median `166.63 ms`, p95 `198.46 ms`, max `15934.08 ms` | median `241.20 ms`, p95 `242.59 ms`, max `259.35 ms` | 历史 accepted 速度记录，不代表当前严格可靠性默认值 |
| QPSK fallback | 300 | `2961.78 ms/image` | median `240.06 ms`, p95 `242.88 ms` | 稳定但慢，不再优化 |

2026-07-17 的全关冷启动记录 `cockpit_usrp_usrp-1784286235` 曾用 10 张隐藏任务验证整条链路，约 `99.6 s` 后显示 UI。当前启动脚本已经取消图片预热，只建立板卡会话，拉起 ML-KEM/认证服务和常驻 USRP TX/RX，并等待服务就绪。首次正式任务仍可能承担模型和运行时冷启动，演示前应留出一次人工冒烟测试时间。

100 张热启动验收对应 `batch-1784222195-100` / `cockpit_usrp_usrp-1784222195`。该轮保持 `sync metric >= 0.75`、`pilot gain ratio >= 0.85`：261 次 OTA 中 100 次通过，116 次被质量门限拒绝后重试，45 次未形成可用同步。点击到完成共 `240.19 s`，数据只能作为热启动记录，不能推断当前无图片预热时的冷启动耗时。

给写文档同学的典型值口径：

| 可写项 | 推荐写法 |
|---|---|
| 主链路 | USRP IQ 直传 + 板端 TVM big.LITTLE 重建 |
| 100 张演示时长 | 热启动点击到完成 `240.19 s`，即约 4 分钟；`100/100` accepted，fallback `0` |
| IQ 传输/解包 | 当前严格 300 张 profile：median `411.59 ms`，p95 `3423.45 ms`，`300/300` accepted；历史速度 profile 可单独标注 median `166.63 ms` |
| TVM 重建 | 当前严格 300 张 profile：median `245.42 ms`，mean `254.71 ms`，p95 `301.73 ms` |
| 250 ms 参考线 | 预录 TVM 300 张 median `243.30 ms`，mean `252.91 ms` |
| QPSK 对照 | 约 `2.96 s/image`，作为稳定 fallback，不作为速度主线 |
| 图像质量 | PSNR `37.0445`，SSIM `0.97494`，artifact SHA matched |
| Cockpit 双口径质量 | PyTorch-TVM `35.6942 dB / 0.97284`（归档参考均值）；原图-TVM `22.1991 dB / 0.94213`（最近一次 30 张审计），均不是本轮 100 张逐图审计 |
| 安全口径 | ML-KEM+SM4 和 ML-DSA+SM2 用于控制/认证面准入；USRP IQ payload 不宣称已加密 |

图像质量按当前 accepted IQ/TVM 路径保持：

```text
PSNR = 37.0445
SSIM = 0.97494
artifact SHA matched
```

## 重建图对比工具

Cockpit 的“板端输出目录”下有“本次重建对比图”按钮。它按需启动上位机服务 `scripts/board_image_compare_server.py`，默认地址为 `http://127.0.0.1:8786/`。页面左侧是原图目录和预览，右侧是倒序 job 选择、板端重建目录和预览；当前序号两侧同步切换，重建图只有点击“拉取”后才走 SFTP。

| 输出类别 | 板端目录 |
|---|---|
| 预录 PyTorch / TVM | `/home/user/Downloads/jscc-test/jscc/infer_outputs` |
| 预录 MNN | `/home/user/Downloads/jscc-test/mnn_benchmark_outputs` |
| USRP QPSK TVM | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` |
| USRP IQ 直传 TVM | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` |

完整的五类来源、MNN USRP 叶目录和历史迁移证据见 [`USRP_OUTPUT_LAYOUT.md`](./USRP_OUTPUT_LAYOUT.md)。2026-07-17 已从 `/home/user/Downloads/jscc-test-usrp/tvm` 迁移 244 个历史 job；复跑 dry-run 得到 244 个 `already_moved`，一个无分类证据的 retry job 留在旧目录。

实现边界：

- 服务和缓存都在上位机，板端不新增常驻进程；缓存目录是 `artifacts/board_image_cache/`。
- SFTP 复用单个连接，不调用板端 shell。CPU/内存达到 85% 时暂停新下载，达到 90% 时中止扫描，低于 80% 后恢复。
- 质量辅助默认关闭。打开后按 PSNR、SSIM 和色度误差自动标记疑似彩色噪点图；标记是筛查提示，不替代人工查看。
- 原图配对必须读取 `USRP292x/qpsk_batch_spool_arq_runs/cockpit_usrp_<id>/image_*/manifest.json`。IQ 直传任务也写在这个历史命名目录中；使用 `analog_latent_runs` 会配错原图并产生假低分。
- 2026-07-16 真板抽查：239 个历史 job 可列出，最新 job 为 300 对；未缓存单张拉取约 `1.23 s`，采样时板端 CPU `1.2%`、内存 `55.6%`。样本 0 正确映射到 `00000215.jpg`，PSNR `23.15 dB`、SSIM `0.936`，视觉内容一致。

## 安全边界

当前方案保护控制面和准入流程，USRP IQ 数据面保持 Deep JSCC 的模拟语义传输。不要把 IQ 数据面说成已经被 ML-KEM/SM4 加密。

### 后量子加密与认证作用位置

| 机制 | 作用位置 | 实际作用 |
|---|---|---|
| ML-KEM-768 | 安全信道建立阶段 | 协商共享密钥；它是密钥封装机制，不直接加密业务数据 |
| ML-DSA-65 + SM2 | 握手认证阶段 | 对握手 transcript 做双签名，验证板端身份并阻止伪装或中间人接入 |
| SM4-GCM | 安全信道消息传输阶段 | 使用派生的会话密钥加密控制消息，并通过 AEAD tag 检测篡改 |
| USRP IQ 链路 | 无线数据面 | 不经过 ML-KEM/SM4 封装，直接传输 Deep JSCC 生成的复数 latent |

实际流程：

1. 上位机连接板端安全服务，ML-KEM 完成会话密钥协商。
2. 板端使用 ML-DSA 和 SM2 对握手上下文签名，上位机必须同时验签通过。
3. 双方通过 Finished 消息确认持有同一会话密钥，随后由 SM4-GCM 保护安全信道内的控制和准入消息。
4. 安全信道就绪后才允许启动 USRP 任务；图像经 JSCC 编码为复数 latent，再通过 USRP 发送。

其中 ML-KEM 和 ML-DSA 提供后量子能力；SM4-GCM 负责实际消息的机密性与完整性，SM2 作为现有国密身份认证手段参与双签名。ML-KEM 本身不能证明对端身份，因此不能省略签名认证。

准确说法：

- TCP/ML-KEM 路径：latent payload、ACK、结果经 ML-KEM 派生密钥和 SM4/AES AEAD 保护。
- USRP IQ 直传路径：ML-KEM + SM4 + ML-DSA + SM2 用作控制/认证面准入 gate；IQ 无线数据面仍是 USRP RF 链路。

为什么不能直接把 AEAD 套到 IQ 数据面：

- AEAD 处理的是字节流，输出是 `ciphertext + tag`，要求接收端 bit-exact 还原。
- JSCC/IQ 直传处理的是连续 latent 复符号，允许无线链路带来小幅模拟误差，再由 TVM 重建吸收误差。
- 如果对 IQ 数据面做 AEAD，任意 1 bit 错误都会导致 tag 校验失败，必须重新引入强纠错、重传和比特同步，链路会退回传统可靠数字传输，失去 IQ 直传的低时延优势。

答辩推荐口径：

> 当前方案不是把 USRP IQ 数据面包装成密码学加密链路，而是把安全职责放在控制面、会话面和身份认证面。ML-KEM + SM4-GCM/AES-GCM AEAD 保护 TCP 安全信道中的元数据、控制结果、ACK 和重建结果；ML-DSA + SM2 认证板端身份并绑定握手 transcript。USRP 数据面传输的是 JSCC 编码后的连续语义 latent，不是原图明文字节，但这不等价于密码学保密。

可选扩展：

- `AnalogLatentLink.py` 已有 `ANALOG_SCRAMBLE_KEY` / `--scramble-key` 机制，可对 IQ symbol 做 keyed permutation/sign scrambling。
- 这只能作为数据面扰码或混淆增强来讲，不能叫标准加密，除非后续把 key 从安全信道派生并完成整链路回归。

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

板端 SSH 频繁断开或内存异常偏高
2026-07-17 冷启动排查发现 KDE `baloo_file_extractor` 占用约 45% 内存并处于 D 状态，导致 SSH 和安全服务不稳。现场若复现，先执行 `balooctl disable`，再终止残留 `baloo_file_extractor`；当次处理后板端 used memory 从约 `1510 MB` 降到 `1090 MB`。

TX 容器存在但 `127.0.0.1:29221` 不可达
Windows 应只有直接发布端口的 `cockpit-usrp-tx-29221` 容器，`docker port cockpit-usrp-tx-29221` 应显示 `127.0.0.1:29221`。若仍出现旧的 `cockpit-usrp-tx-proxy-29221`，停掉两个旧容器后重跑 `start-demo.ps1`；不要在 Windows 强制设置 host network。

USRP 卡在 299/300 或显示未进入有效重建链路
优先看 IQ sync/ARQ 日志和 summary 中的 `iq_segment_resets`。当前默认为单图 ARQ12、30 张分段、2 次失败子集补传；只有全部 accepted 后才启动 TVM。若 RX server 端口仍在但连续收不到 UHD 样本，runner 会关闭旧会话并发送真实 `RESET`。若 RESET 返回 `unknown command`，Cockpit 会退出旧服务、从同步源码重建并重启。

MNN/PyTorch 与 USRP
TVM 是主路径。MNN 已接 USRP remote-dir latent；PyTorch 在 USRP 模式下仍作为预录参考，不启动 USRP 传输。

## 不建议改动

- 不要再改 QPSK 主逻辑。
- 不要默认启用 `OPENAMP_IQ_STREAMING_TVM`。
- 不要缩短 STOP/RX drain 超时。
- 不要把 `REMOTE_USRP_RX_DIR` 改到 tmpfs 当默认。
- 不要把运行日志、`keys/`、`nul`、`cockpit_desktop/logs/` 提交进 git。

## 文件组织现状

源码和文档入口已整理完成，接手时按下面划分：

| 路径 | 状态 |
|---|---|
| `Semantic-Communication/cockpit_desktop/` | Cockpit Electron/React 主 UI |
| `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/` | Cockpit 后端和 OpenAMP/USRP 编排入口 |
| `USRP292x/` | QPSK/IQ USRP 数据面、persistent TX/RX、analog latent runner |
| `mlkem_link/` | ML-KEM/SM4 安全信道和认证实现 |
| `scripts/` | TCP client/server、TVM/MNN/PyTorch 辅助脚本 |
| `docker/` | Docker/演示启动脚本 |
| `docs/` | 当前 README、现场 STARTUP、HANDOFF、设计说明和安全部署说明 |
| `logs/`、`runtime_logs/`、`local_logs/`、`.logs/`、`tmp/`、`artifacts/` | 运行输出或临时产物，不作为源码入口 |
| `keys/` | 本地认证公钥/密钥材料，不要提交私钥 |

不要再移动 `Semantic-Communication/`、`USRP292x/`、`mlkem_link/` 这些源码目录，很多脚本仍依赖现有相对路径。新增说明文档放入 `docs/`；临时计划、对话记录和过程审计不进入交付仓库。

## 验证命令

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026

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

- `docs/README.md`：当前仓库总览、典型指标和板端备份边界。
- `docs/USRP_LINK_BRIEFING.md`：USRP 分阶段链路、指标和安全边界。
- `docs/PPT_USRP_SECURITY_UPDATES.md`：PPT 中加密认证与 USRP 的 3 页修改意见。
- `docs/DOCUMENT_USRP_SECURITY_UPDATES.md`：技术文档第 5、6 章的差量修改意见。
- `docs/INITIAL_COMMIT_DOCUMENTS.md`：最初提交的文档归档和逐文件清单。
- `docs/runbooks/STARTUP.md`：现场断电后最短启动流程。
- `docs/HANDOFF.md`：交接、默认参数、实验开关和验证命令。
- `docs/security/mlkem_auth_setup.md`：ML-KEM/SM4 与认证通道部署说明。
- `docs/design/analog_latent_iq_phy.md`：analog latent-IQ PHY 设计说明。

## 去 Git Bash 的判断

现在不建议在赛前大改。若必须做，先做最小档：新增 `start-dev.ps1` / `stop-dev.ps1`，只替换 Cockpit 日常启动外壳，预计 2-4 小时。Docker 容器内部继续用 Bash。完全移除本机 Bash 假设需要排查 `*.sh`、`nohup/env/cygpath/MSYS2_*` 和路径转换，至少 1-2 天，还要跑硬件 smoke。
