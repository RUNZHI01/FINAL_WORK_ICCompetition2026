# 2026-07-11 当前状态记录

## 当前结论

当前工作目录为 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`，分支为 `feat/restore-248`。Cockpit Desktop 一键脚本已经可以在 Windows + Git Bash 环境下拉起后端、Electron/Vite、Docker SSH runner、Docker USRP TX runner，以及本地 Docker ML-KEM client runner。USRP 数据面仍按 IQ direct 走 USRP，不经过 Tailscale；Tailscale/TCP 只用于 SSH、状态、认证/加密控制面和日志。

最新手动验证中，`/api/crypto-test` 返回 `status=ok`，`transport_mode=daemon`，`handshake_ms=292.3`，`sha256_match=true`。`/api/crypto-status` 返回 `channel_state=ready`、`auth_enabled=true`、`sig_policy=DUAL_REQUIRED`、`error=null`，TVM 推理耗时约 `250.98 ms`。这说明 ML-KEM + SM4 加密通道、ML-DSA + SM2 认证开关、板端 `tcp_server.py`、Docker 本地 client daemon 已经打通。

## 相对 FINAL_WORK 初版的主要变化

当前分支相对仓库最初提交 `d787901` 已经不是简单修补。Git 统计约 `2323` 个文件变更，核心变化集中在以下几类：

- 删除大量提交/展示噪声，补齐 `board_deps/`、Docker 复现脚本和飞腾派隔离 smoke，形成可交付包。
- 恢复 Cockpit Desktop 下 handwritten TVM + big.LITTLE 的 300 张预录测速口径，Windows 真机验证 median 约 `244 ms`，顶部耗时和推理结果对比卡片可同轮刷新。
- 新增 USRP 双链路：QPSK/CRC/ARQ 保留为可靠兜底；默认 USRP 链路切到 analog latent IQ direct，不再让飞腾派多做一轮 QPSK 解码。
- IQ direct 从单帧 proof 演进到 300 张批量链路：Docker host TX、板端 RX/decode worker、remote-dir latent 发布、TVM 直接消费板端目录，TX/RX server 和 decode worker 常驻。
- Windows 现场路径改为 Docker SSH/TX 优先，Git Bash 只作为 fallback，明确避开 WSL；板端 Python 固定走 `/home/user/venv/bin/python`。
- 安全信道拆成会话级能力：ML-KEM + SM4 加密、ML-DSA + SM2 双认证可通过 Cockpit 控制，不放进每张图的热路径。
- Cockpit UI 已加入板卡地址参数化、USRP/QPSK/IQ 状态、批量进度、结果对比、IQ tail audit、安全信道开关和硬件信息区的重排准备。

## IQ 直传最新状态

当前推荐的 Cockpit USRP/IQ 批量运行目录为 `USRP292x/qpsk_batch_spool_arq_runs/cockpit_usrp_usrp-1783782559`。这是显式重启 persistent USRP TX/RX 后、板端 `OtaRxPersistentServer` 确认使用 `--arm-wait-ms 500 --stop-wait-ms 8000` 的 300 张验证。结果为 USRP transport `300/300`、TVM `300/300`、fallback `0`；TVM median/p95/max 为 `241.20/242.59/259.35 ms`，IQ transport median/p95/max 为 `166.63/198.46/15934.08 ms`。

当前速度口径可以说 IQ direct 的 p95 已经低于 TVM p95，且中位数明显低于 TVM。不要把 max 当成稳态指标；max 仍由少数 RF/RX outlier 主导，本轮有 `4` 个 arm failure、`2` 个 capture-busy recovery、`3` 个 no-sync retry 和 `1` 个 low-sync retry，但都被 ARQ/cleanup 恢复，没有掉出有效重建链路。

默认策略已经调整为更偏演示可靠性：IQ direct 默认 `MLKEM_USRP_MAX_ARQ_ROUNDS=5`，启用 `ANALOG_RETRY_ON_BURST_MISS=1`、`ANALOG_RETRY_ON_LOW_SYNC=1`，`ANALOG_LOW_SYNC_RETRY_THRESHOLD=0.08`，并将 `RX_ARM_WAIT_MS` 提到 `500`。这些默认值已写入 `start-dev.sh`、后端 board-access 默认值、Docker 一键脚本和文档；如果现场已经有旧 USRP server 常驻，必须先 `/api/usrp-control/stop` 再 `/api/usrp-control/start`，否则板端进程会继续沿用旧参数。

## USRP 后接 TVM / MNN / PyTorch

USRP 数据面当前可后接 TVM 和 MNN。TVM 是主展示路径，走 handwritten TVM + big.LITTLE；MNN 路径会在 USRP remote-dir latent 生成后读取同一类板端输入目录，输出独立到 `.../jscc-test-usrp/mnn`。MNN 之前在 USRP 模式下点击后卡住，根因是 `start_mnn_batch_inference()` 在持有 `DashboardState` 锁时 arm ML-KEM security，安全路径内部再次获取同一把锁导致后端自锁。现已改为锁外 arm security，并加了 `test_start_mnn_usrp_batch_arms_security_outside_state_lock` 回归测试。

PyTorch 没有接入 USRP 后接推理。Cockpit 里的 PyTorch 按钮只作为预录参考对照；在 USRP 模式下调用 `/api/run-baseline` 会立即返回 `execution_mode=prerecorded`、`data_transport=prerecorded`，不会启动 USRP transport，也不会消耗板端/USRP 资源。

## 天线与现场环境

当前方案没有针对实验室某个发射/接收天线位置做硬编码特化。代码配置的是频点、采样率、TX/RX gain、幅度、同步门限、pilot/sync 搜索和重试策略，不包含天线坐标、朝向或固定距离假设。

它仍然对现场 RF 条件敏感。换场地后，多径、遮挡、天线极化、距离、增益和 CFO/相位漂移会直接反映到 `sync_metric`、burst 检测、RX wait 和 retry 次数上。演示前至少做一次 20 张 USRP/IQ smoke；如果出现低 sync 或 `299/300` 类问题，优先调整天线摆放、TX/RX gain 和同步门限，不要先改 QPSK。

## 冷启动恢复步骤

从本目录执行，优先用 Git Bash，不用 WSL：

```bash
cd Semantic-Communication/cockpit_desktop
./stop-dev.sh
REMOTE_PASS=user PHYTIUM_PI_PASSWORD=user ./start-dev.sh
```

如果现场板卡地址变化，启动前覆盖地址即可：

```bash
REMOTE_HOST=192.168.x.x PHYTIUM_PI_HOST=192.168.x.x \
REMOTE_USER=user PHYTIUM_PI_USER=user \
REMOTE_PASS=user PHYTIUM_PI_PASSWORD=user \
REMOTE_SSH_PORT=22 PHYTIUM_PI_PORT=22 \
./start-dev.sh
```

脚本会自动从 `board_deps/crypto/public_keys/board-auth-public-keys.tar.gz` 解出本地公钥到 `keys/`，默认启用 `MLKEM_LOCAL_CLIENT_RUNNER=docker`，避免 Windows 本机缺 Tongsuo/liboqs。板端仍需要保留 `/home/user/keys/*`、`/home/user/libtongsuo_sig_bridge.so`、`/home/user/liboqs-dist`、`/home/user/venv/bin/python` 和 TVM 运行环境。

## 板卡地址参数化

一键脚本 `Semantic-Communication/cockpit_desktop/start-dev.sh` 本身不写死 `100.121.87.73`。当前默认地址来自 `session_bootstrap/config/phytium_pi_login.example.env` 和演示 env 快照，里面仍记录验证环境的 `100.121.87.73`。现在后端启动白名单已转发 `REMOTE_HOST`、`PHYTIUM_PI_HOST`、`REMOTE_USER`、`PHYTIUM_PI_USER`、`REMOTE_SSH_PORT`、`PHYTIUM_PI_PORT`，所以现场可用环境变量覆盖，不必改代码。

Cockpit UI 的 `/api/session/board-access` 也支持提交 `host/user/password/port`。密码不要写死进仓库；现场可以在 UI 填，也可以启动前临时设置 `REMOTE_PASS=user` 和 `PHYTIUM_PI_PASSWORD=user`。

## 已知剩余问题

`/api/crypto-status` 里的 ML-KEM 状态已正常，但控制面 live probe 仍可能显示 `PROBE_ERROR`，原因是 `fault_injector.py` 的控制面代理还走本地 SSH helper，没有完全 Docker 化。这不阻断 ML-KEM/TVM/IQ direct 主链路，但会影响仪表盘控制面状态观感。

下一步准备单独检查 Cockpit Dashboard 冗余项：只列清单，先不改 UI，待确认后再动。
