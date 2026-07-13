# HANDOFF

更新时间：2026-07-13
当前分支：`feat/restore-248`
交接前代码保存点：`7c23ded docs(cockpit): record security identity layout`

## 当前主线

演示主线是 `Cockpit Desktop -> USRP IQ 直传 -> 板端 TVM big.LITTLE 重建`。QPSK 已能稳定跑通，作为可靠 fallback 保留，不建议继续改。预录 TVM/MNN/PyTorch 已恢复；预录模式只走推理进度，不走 USRP 三阶段进度。

默认 UI 分工：

- 左栏：数据面输入模式、QPSK/IQ 选择、IQ 直传诊断、输入/输出目录、批量运行。
- 右栏：地图、硬件状态、板卡密码、安全信道。
- 板卡密码行显示主机、用户、会话密码状态和服务端标识。
- 安全信道显示加密、认证、作用范围和运行状态。

## 启动方式

当前仍保留 Git Bash 启动外壳，Bash/SSH 热路径优先走 Docker，不用 WSL。

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\FINAL_WORK_ICCompetition2026
& 'E:\Software\Scoop\apps\git\current\bin\bash.exe' -lc './Semantic-Communication/cockpit_desktop/start-dev.sh'
```

启动后：

- 后端：`http://127.0.0.1:8079`
- 前端/Electron/Vite：`http://localhost:5173/#/`
- 板卡默认地址：`100.121.87.73`
- 板卡用户名/密码：`user / user`
- 板端 IQ decode Python：`/home/user/venv/bin/python`

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

`start-dev.sh` 已默认设置：

```text
MLKEM_TRANSPORT_MODE=usrp
JSCC_LINK_MODE=iq-direct
MLKEM_AUTH_ENABLED=1
MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
MLKEM_CIPHER_SUITE=SM4_GCM
MLKEM_USRP_MAX_ARQ_ROUNDS=5
REMOTE_USRP_RX_DIR=/home/user/cockpit_usrp_rx
REMOTE_RX_RUN_ROOT=/dev/shm/usrp292x_remote_runs
OPENAMP_DEMO_REMOTE_DECODE_PYTHON=/home/user/venv/bin/python
OPENAMP_IQ_STREAMING_TVM=0
ANALOG_PIPELINE_DEPTH=1
ANALOG_PIPELINE_RF_DECODE_OVERLAP=0
```

不要默认打开 streaming TVM、tmpfs 目录实验、decode worker restart、short STOP、short RX wait。这些路径都测过，不适合作为演示默认。

## 当前指标

可汇报的基准：

| 路径 | 样本 | 传输/解包 | TVM 重建 | 备注 |
|---|---:|---:|---:|---|
| 预录 TVM big.LITTLE | 300 | 无 USRP | median `243.30 ms`, mean `252.91 ms`, p95 `311.88 ms` | 250 ms 参考线 |
| USRP IQ 直传 accepted profile | 300 | median `166.63 ms`, p95 `198.46 ms`, max `15934.08 ms` | median `241.20 ms`, p95 `242.59 ms`, max `259.35 ms` | 当前速度结果，max 是已恢复的 RF/RX outlier |
| QPSK fallback | 300 | `2961.78 ms/image` | median `240.06 ms`, p95 `242.88 ms` | 稳定但慢，不再优化 |

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
