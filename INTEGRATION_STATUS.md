# IQ 直传路线集成状态

记录 `feat/iq-direct-tx` 分支上 analog latent-IQ 直传链路相对于最终目标 `JSCC Enc → IQ → Channel → IQ → JSCC Dec` 的集成进度。给接手者一个明确的"哪些已 wire、哪些待办、风险在哪"的清单。

本文件随实际进度更新。ML-KEM 安全信道部署指南见 [`docs/mlkem_auth_setup.md`](./docs/mlkem_auth_setup.md)，PHY 层设计原理见 [`docs/analog_latent_iq_phy.md`](./docs/analog_latent_iq_phy.md)，完整 0-16 Pro 方案见 [`docs/analog_latent_iq_phy_full_proposal.md`](./docs/analog_latent_iq_phy_full_proposal.md)，jscc_tran 原始 handoff 见 [`JSCC_TRAN_HANDOFF.md`](./JSCC_TRAN_HANDOFF.md)。

## 当前 live 状态（2026-07-10）

2026-07-07 的远端状态核对已经过期。板端现在已同步 IQ 直传所需的 `/home/user/USRP292x/AnalogLatentLink.py`，并通过 `/home/user/venv/bin/python -m py_compile`。cockpit 的默认 USRP 数据面已经切到 `JSCC_LINK_MODE=iq-direct`，QPSK 保留为可靠 fallback。

最新 cockpit desktop 按钮路径验证：

| 链路 | 批次 | 结果 | 传输指标 | TVM big.LITTLE |
|---|---:|---:|---:|---:|
| IQ 直传 | `batch-1783610422-300` | 300/300，fail 0 | median `202.54 ms`，p95 `598.89 ms`，RF airtime `9.58 ms` | median `241.21 ms` |
| QPSK | `batch-1783610673-300` | 300/300，fail 0 | `2961.78 ms/image`，RF airtime mean `48.02 ms` | median `240.06 ms` |

当前 IQ 链路事实：

- 数据面不经过 Tailscale：Tailscale 只承载 cockpit API、SSH、TX/RX control、日志/状态。
- TX/RX 是常驻服务：host TX `127.0.0.1:29221`，board RX `100.121.87.73:29220`；每张图只发控制命令，不重复拉起 USRP 进程。
- decode 是板端常驻 worker：`AnalogLatentLink.py decode-server` 使用 `/home/user/venv/bin/python`，`ANALOG_DECODE_PIPELINE_WARMUP=1` 提前预热 FFT/import/decode 路径。
- `remote-dir` 模式把 decoded latent 直接写到 `/home/user/cockpit_usrp_rx/<run>_rx`，TVM 直接消费该目录。
- 性能跑时 crypto toggle 关闭；ML-KEM/auth 仍是控制面配置，security-on 性能需要单独测。

剩余核心风险：

- IQ 物理层还存在长尾：300 张里 23 张自动重试，最大 3 attempts；transport median 已低于 250 ms，但 p95 仍有 `598.89 ms`。
- sync/RX 稳定性仍是第一优先级。`ANALOG_MIN_SYNC_METRIC=0.05` 和 `ANALOG_ROBUST_SYNC=0` 是当前低延迟 profile，不是最终 PHY 质量结论。
- QPSK 已经从单张 proof 变成 300/300 可靠 fallback，但 `decode_command` 均值约 `2295.96 ms`，不能作为 250 ms 主链路。

## 安全信道当前状态（2026-07-08）

ML-KEM + SM2 + ML-DSA 控制面 **已端到端打通**，与 IQ 直传数据面相互独立：

- 握手结果：`handshake_ms ≈ 1396.4`、`last_sha256_match=true`、`session_count=1`、`bytes_sent=131072`。
- 策略：`MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`（SM2 + ML-DSA 双签同时校验），默认启用。
- 角色：容器（x86_64）= Initiator/client，飞腾派（aarch64）= Responder/server。
- 入口：`scripts/start_server_auth.sh`（容器端，15 个 `MLKEM_AUTH_*` env 全配齐）。
- 容器端 x86_64 SM2 桥接库已编译并验证（见 [`docs/mlkem_auth_setup.md`](./docs/mlkem_auth_setup.md)）。

剩余的安全面相关任务：

- 容器健康检查脚本标准化（当前散落在 `/tmp/test_*.py`），需要落到 `scripts/`。
- 板端 `tcp_server` 自启动已经在 server.py SSH 阶段拉起，但没有 systemd/开机自启，重启板卡需要重新拉。
- `control_guard_state=PROBE_ERROR` 和 `board status endpoint unavailable: timed out` 是 OpenAMP 控制面心跳问题，**与 ML-KEM 数据面无关**，单独追踪。



## 目标链路对照

| 路线 | 链路 |
|---|---|
| 旧 QPSK（保留为 baseline） | `JSCC Enc → 实数 latent → 量化 → QPSK Mod → Channel → QPSK Demod → CRC/ARQ → 反量化 → 实数 latent → JSCC Dec` |
| 新 IQ 直传（目标） | `JSCC Enc → 实数 latent → I/Q 配对 → RRC → Channel → 匹配滤波/CFO/相位均衡 → I/Q 还原 → JSCC Dec` |

IQ 直传跳过量化、QPSK 调制、CRC/ARQ。8-bit 量化引入的等效噪声 SNR ≈ 37.5 dB（基于 20 张 Places365 真实 encoder 输出实测），远高于 JSCC 典型工作 SNR 1–15 dB，所以跳量化不需要重训模型——Generator 在训练时见到的 `y_dequant + AWGN` 与 IQ 直传喂的 `y_raw + AWGN` 差距不可察觉。

## 模块级状态

| 模块 | 目标 | 当前实现 | 状态 |
|---|---|---|---|
| Encoder 输出 raw float latent | 直接喂给 TX 不经过量化 | `host_pic_to_latent/jscc/src/test_model.py` 的 `torch.save` 增加 `'latent': y_cpu.float()` 字段 | ✅ 完成 |
| 实数→I/Q 配对 + RRC + sc16 | TX 调制 | `USRP292x/AnalogLatentLink.py:latent_to_complex_symbols`、`symbols_to_rrc_waveform`、`waveform_to_sc16` | ✅ 完成 |
| sc16 → USRP TX → 空口 → USRP RX → sc16 | 真实无线信道 | 复用现有 `OtaTxPersistentServer` / `OtaRxPersistentServer`（C++），由 `RunAnalogLatentBatch.py` wire | ⚠️ 仅 `--rx-capture-mode=local` |
| RX sc16 → 同步/CFO/相位均衡 → noisy latent | 解调 | `AnalogLatentLink.py:decode` 含 robust CFO-grid fallback、mid-pilot 线性相位跟踪 | ✅ 完成 |
| noisy latent → TVM/Generator 重建 | 端到端 | `scripts/tvm_inference_helper.py:apply_channel` 支持 `--channel-mode real-usrp`，跳过软件 AWGN | ⚠️ 单元通，未与 server 集成 |
| `latent_transport.py` 支持 `.pt` raw latent | batch runner 直接吃 encoder 输出 | `scripts/latent_transport.py:_load_float32_latent` 已支持 `.pt/.npz/.npy/.bin`；同时修复了 `_torch_load` 未定义的潜伏 bug | ✅ 完成 |
| **Server 端 IQ 模式分支** | openamp `server.py` 知道走 IQ 而不是 QPSK | `usrp_runtime.py` 加 `JSCC_LINK_MODE` 开关 + 31 个 `ANALOG_*` env 变量；`server.py` 通过 `env_or_arg_pairs` 透传；IQ 模式切到 `RunAnalogLatentBatch.py`，QPSK 路径不动 | ✅ 完成 |
| **双机 SSH/SCP 远端 RX** | TX 在控制机，RX 在板卡 | `RunAnalogLatentBatch.py` 加 SSH ControlMaster + SCP 流程，支持 `local` / `remote-pull` / `remote-decode` 三档；TX 始终在控制机 | ✅ 完成（待真机回归） |
| **真机硬件验证** | 线缆 + 30 dB 衰减器 → 近距离空口 | 仅软件 loopback 和 `simulate-channel` 注入 | ❌ 未开始 |
| **Cockpit UI IQ 模式标识** | 用户能看到 `link_mode`、`sync_metric`、`evm_rms`、`estimated_cfo_hz` | `usrp_runtime.py` 在 wrapper_summary 加 `link_mode` + `iq_radio_metrics` 聚合；前端 `types.ts` 加 `JsccLinkMode` / `IqRadioMetrics` + extract helpers；`DashboardPageMinimal.tsx` 在 USRP 模式下渲染紫色 IQ 直传 / 橙色 QPSK 兜底 badge + 样本/同步率/sync/EVM/CFO 内联指标 | ✅ 完成（待真机回归） |
| **控制面与数据面解耦** | ML-KEM 走控制面，latent 走 USRP，互不耦合 | `tcp_client.py`/`tcp_server.py` 当前既传 latent 字节又传 manifest | ⚠️ 已设计未实施 |

## 软件验证已通过的项目

`feat/iq-direct-tx` 分支当前 commit 上：

- `pytest USRP292x/test_analog_latent_link.py` 8/8 通过（clean loopback、CFO/AWGN 注入、robust sync、mid-pilot 相位跟踪、keyed scramble）
- `RunAnalogLatentBatch.py --dry-run` 软件 loopback：`sync_metric=0.9999`，`evm_rms=0.016`，`latent_mse_vs_tx=2.9e-4`
- `simulate-channel` 通道扫描（5 组）：

  | 场景 | sync | sync_metric | CFO 估计 (Hz) | EVM | latent MSE | sync mode |
      |---|---|---|---|---|---|---|
  | clean | ✅ | 0.9999 | 0.0 | 0.015 | 2.9e-4 | normal |
  | 20 dB SNR | ✅ | 0.9985 | 0.0 | 0.040 | 1.7e-3 | normal |
  | 3 kHz CFO + 20 dB | ✅ | 0.9985 | 3001.6 | 0.043 | 1.9e-3 | normal |
  | 5 kHz CFO + 10 dB | ✅ | 0.9866 | 4999.8 | 0.120 | 1.5e-2 | robust-cfo-grid |
  | 3 kHz CFO + 5 dB | ✅ | 0.9589 | 3001.6 | 0.210 | 4.5e-2 | normal |

  EVM 和 MSE 随 SNR 平滑退化，符合 JSCC 设计预期。CFO 估计误差 < 2 Hz。

- `latent_transport.py` round-trip：`.pt` raw latent、`.pt` quant+latent、`.pt` webp-lossless、`.npz` uint8 webp-lossless、`.npz` int8 webp-lossless、`.npy`、`.bin` 全部通过
- `tvm_inference_helper.py:apply_channel`：`sim-awgn` 与原 `awgn_channel` 同 RNG seed 完全一致（旧行为零回归）；`real-usrp`/`none` 输出 === 输入；无效模式 raise `ValueError`；模式字符串 trim+lower 规范化

## 剩余工作（按优先级）

### P0 — 真机可跑

1. ~~**server.py 加 IQ 模式分支**~~ ✅ 已完成（2026-07-07）。`usrp_runtime.py` 加 `JSCC_LINK_MODE` env 开关，qpsk 走原路，iq-direct 切到 `RunAnalogLatentBatch.py`；31 个 `ANALOG_*` env 变量透传到 CLI。QPSK baseline 完整保留，见 `_resolve_link_mode()` 安全 fallback。
2. ~~**RunAnalogLatentBatch 加 remote-pull / remote-decode**~~ ✅ 已完成（2026-07-07）。`RunAnalogLatentBatch.py` 重构 `process_image`，支持 SSH ControlMaster + SCP + 远端 Python decode；TX 始终在控制机，RX 在板卡。dry-run 软件回归通过：`sync_metric=0.99989`，`evm_rms=0.0155`，`latent_mse_vs_tx=2.3e-4`。
3. **线缆 + 30 dB 衰减器实测**（半天-1 天）。这是真正暴露问题的环节：实际 DC offset、本振不锁的相位漂移、TX/RX gain 配对。从低 gain 起步。
4. **近距离空口实测 + TX/RX gain 调优**（1-2 天）。

### P1 — 产品化

5. ~~**Cockpit UI 加 IQ badge**~~ ✅ 已完成（2026-07-07）。后端：`usrp_runtime.py` 在 `wrapper_summary` 加 `link_mode` + `iq_radio_metrics`（sync_metric/evm_rms/estimated_cfo_hz/sync_success_ratio 跨 round_records 聚合）；`diagnostics` 也加 `link_mode` 字段。前端：`types.ts` 加 `JsccLinkMode` / `IqRadioMetrics` 类型 + `extractJsccLinkMode/extractIqRadioMetrics` helper；`DashboardPageMinimal.tsx` 在 USRP 模式下渲染紫色 "IQ 直传" / 橙色 "QPSK 兜底" badge，附带样本/同步率/sync/EVM/CFO 内联指标。
6. **`BuildOtaTools.sh` 决策**：等 IQ 直传稳定后，是否砍掉 QpskFileDecode target？目前两条并存。
7. ~~**远端 decode 路径**~~ ✅ 已合并到 P0-2：`RunAnalogLatentBatch.py` 的 `remote-decode` 模式调板卡上的 `AnalogLatentLink.py decode`，npz/wire/summary SCP 回控制机。

### P2 — 优化

8. **sc16_amplitude / sps / RRC beta 调优**：默认 `amp=3000`、`sps=4`、`beta=0.35` 是保守值。真机 EVM 曲线出来后再扫。
9. **robust sync 阈值**：当前 `min-sync-metric=0.25`、`robust-cfo-max-hz=8000`、`robust-cfo-step-hz=500`，对 2922 两台不共本振的场景是否够用要看实际 CFO 分布。

## 风险点

- **真机 DC/CFO**：软件 simulate-channel 验证了 3 kHz CFO 能恢复，5 kHz CFO 走 robust grid 能恢复。但 2922 两台不共享本振的实际 CFO 可能更大、更漂。robust sync grid 上限 8 kHz，超过就失步。
- **clipping**：`sc16_amplitude=3000` 是猜的数字幅度，不等于 RF 输出功率。真机要看 EVM 随 amplitude 的曲线，找到不 clipping 的最大值。
- **RX 输入功率**：NI-USRP-2922 RX 最大输入功率 0 dBm。线缆直连高 gain 会烧前端，必须加衰减器（≥30 dB）从低 gain 起步。
- **量化 latent 兼容性**：当前 `AnalogLatentLink.load_latent` 对 `.pt` 强制要求 `'latent'` 字段。旧 `.pt`（只有 `quant/scale/zero_point`）会被 reject。如果遇到旧 latent，要么重跑 encoder 补 `latent` 字段，要么在 `AnalogLatentLink` 加 dequant fallback（不推荐，违背 IQ 直传跳量化的初衷）。

## 2026-07-07 远端接收端现状核对

仅做只读核对，目标主机：`100.121.87.73`（`user/user`）。

- **远端实际运行目录不是 FINAL_WORK 仓库树。**
  当前可直接确认在用的顶层文件/目录是：
  - `/home/user/USRP292x`
  - `/home/user/tvm_inference_helper.py`
  - `/home/user/latent_transport.py`

- **远端 `/home/user/USRP292x` 仍以 QPSK 链路为主。**
  已确认存在：
  - `/home/user/USRP292x/RunQpskFileBatchSpoolArq.py`
  - `/home/user/USRP292x/QpskFileLink.py`

  已确认不存在：
  - `/home/user/USRP292x/AnalogLatentLink.py`
  - `/home/user/USRP292x/RunAnalogLatentBatch.py`
  - `/home/user/USRP292x/test_analog_latent_link.py`

  结论：远端接收端 **尚未同步 IQ 直传 runner**，当前 USRP 数据面仍是 QPSK 主线。

- **远端辅助脚本已部分更新。**
  `/home/user/tvm_inference_helper.py` 已包含 `channel_mode` / `real-usrp` 分支；`/home/user/latent_transport.py` 已支持 `float32-raw` 与 `webp-lossless`。这说明 **推理辅助层与 wire blob 辅助层有更新**，但没有与 IQ 直传 USRP runner 一起成套落地。

- **远端 encoder/test_model 仍是旧口径。**
  发现的历史 repo 样本：
  - `/home/user/iccomp_repo_cli_20260506_034850/repo/host_pic_to_latent/jscc/src/test_model.py`
  - `/home/user/iccomp_repo_cli_20260506_035921/repo/host_pic_to_latent/jscc/src/test_model.py`

  这批文件时间为 `2026-05-04`，内容仍以 `quant/scale/zero_point` 和反量化路径为主，未确认具备 FINAL_WORK 当前的 raw `latent` 保存与 `real-usrp` 消费逻辑。

- **当前判断**
  远端不是“完全没更新”，但状态是：
  - `tvm_inference_helper.py` / `latent_transport.py` 有更新
  - `USRP292x` 核心 runner 仍停留在 QPSK
  - `test_model.py` 仍接近旧量化口径

  因此远端接收端 **还不是一套完整可用的 IQ 直传接收环境**。

- **后续同步原则**
  1. 继续以 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026` 为唯一主修改面。
  2. 真正同步远端前，先在本地 FINAL_WORK 内冻结一版 IQ 直传所需文件集合。
  3. 远端同步时默认只做覆盖/新增，不主动删除远端历史文件；确需清理时单独审计。

## 软件验证复现命令

无 USRP 硬件时验证 IQ 直传链路：

```bash
# 1. 软件 loopback 单元测试
python -m pytest USRP292x/test_analog_latent_link.py -v

# 2. 生成合成 latent
python -c "
import numpy as np, os
os.makedirs('USRP292x/analog_latent_runs/_smoke_input', exist_ok=True)
arr = np.random.default_rng(42).standard_normal((1, 4, 8, 8)).astype(np.float32)
np.savez('USRP292x/analog_latent_runs/_smoke_input/latent.npz', latent=arr)
"

# 3. 软件 loopback batch
python USRP292x/RunAnalogLatentBatch.py \
  --input USRP292x/analog_latent_runs/_smoke_input/latent.npz \
  --count 1 \
  --run-root USRP292x/analog_latent_runs \
  --run-id smoke --dry-run

# 4. CFO + AWGN 通道扫描
python USRP292x/RunAnalogLatentBatch.py \
  --input USRP292x/analog_latent_runs/_smoke_input/latent.npz \
  --count 1 \
  --run-root USRP292x/analog_latent_runs \
  --run-id sim_cfo3k_snr20 --dry-run \
  --sim-cfo-hz 3000 --sim-snr-db 20 --sim-gain 0.85 --sim-phase-deg 25

# 5. 检查 decode_summary
cat USRP292x/analog_latent_runs/<run-id>/image_0000/decode_summary.json
```

期望：`sync_success=true`、`sync_metric>0.95`、`estimated_cfo_hz` 接近注入值、`latent_mse_vs_tx` 随 SNR 平滑上升。

## 控制面/数据面/安全面划分

IQ 直传不修改这个划分，只替换数据面的具体实现：

```text
控制面：ML-KEM 握手、job_id、nonce/anti-replay、manifest 签名
        → tcp_client.py / tcp_server.py / mlkem_link/
        → AES-GCM / SM4-GCM 保护 manifest 字节

数据面：latent 字节
        QPSK 模式 → latent_transport wire blob → TCP → tcp_server.py → TVM
        IQ 模式  → AnalogLatentLink sc16 → USRP → RunAnalogLatentBatch → TVM

安全面：不要对 analog payload 做 GCM
        analog latent 是 noisy 的，bit-exact 认证必然失败
        keyed-permutation-sign scrambling 可以作用在 latent symbols 上
        但 scramble ≠ encryption，scramble 保持 analog noisy 特性
```

## 当前分支与提交

- 分支：`feat/iq-direct-tx`（基于 `main`）
- IQ 直传相关 commit：
  - `feat: add IQ-direct analog latent TX path alongside QPSK baseline`（PHY + 三处增量补丁）
- QPSK baseline 相关 commit：见 `main` 分支历史

## 已知问题（Known Issues）

| 模块 | 现象 | 影响范围 | 临时方案 |
|---|---|---|---|
| OpenAMP 控制面 | `control_guard_state=PROBE_ERROR`，`error: "board status endpoint unavailable: timed out"` | Cockpit Dashboard 控制面卡片变红，**不影响** ML-KEM 握手和 latent 数据面 | 重启 server.py 或忽略；与 ML-KEM 通道相互独立 |
| 远端板端 USRP292x | `/home/user/USRP292x/` 仍是 QPSK 主线，没有 `AnalogLatentLink.py` / `RunAnalogLatentBatch.py` | IQ 直传模式切到板端会找不到 runner | 真机 IQ 实测前先把 FINAL_WORK 仓库的 `USRP292x/AnalogLatentLink.py`、`RunAnalogLatentBatch.py`、`test_analog_latent_link.py` 同步过去 |
| 远端板端 test_model.py | `/home/user/iccomp_repo_cli_*/repo/host_pic_to_latent/jscc/src/test_model.py` 仍是 `quant/scale/zero_point` 旧口径 | 旧 encoder 输出不带 `'latent'` raw 字段，`AnalogLatentLink.load_latent` 会 reject | 用 FINAL_WORK 内的 test_model.py 重新跑 encoder |
| 容器 x86_64 SM2 keygen | vanilla OpenSSL 3.0.2 不支持 SM2 keygen via `EVP_PKEY_Q_keygen("SM2")`，返回 `rc=-1` | 无法在容器内重新生成 SM2 keypair | keygen 在板端 Tongsuo 里完成；容器只验签 |
| Tailscale SSH | 到 `100.121.87.73` 偶发超时 | 批量 SCP 失败 | 在控制机用 retry loop（3-5 次重试），或启用 SSH ControlMaster 复用连接 |

## 2026-07-08 集成快照

- ✅ ML-KEM `DUAL_REQUIRED` 握手打通（容器 → 板端，1.4 s 量级，SHA-256 校验通过）
- ✅ 容器 x86_64 `libtongsuo_sig_bridge.so` 编译并加载通过（apt-get + gcc 一行命令）
- ✅ `scripts/start_server_auth.sh` 入口（15 个 `MLKEM_AUTH_*` env 全配齐）
- ✅ `mlkem_link/auth.py` 偏移 bug 已修复（commit 在 `feat/iq-direct-tx`）
- ✅ IQ 直传 server 端 wire：`JSCC_LINK_MODE` 开关 + 31 个 `ANALOG_*` env
- ✅ IQ 直传双机 SSH/SCP RX：`local` / `remote-pull` / `remote-decode` 三档
- ✅ Cockpit UI IQ badge（紫色 IQ / 橙色 QPSK）
- ⏳ IQ 直传真机线缆 + 30 dB 衰减器实测（待做）
- ⏳ 远端 `/home/user/USRP292x/` 同步 IQ runner（待做）
- ❌ OpenAMP 控制面 PROBE_ERROR（与 ML-KEM 数据面独立追踪）
