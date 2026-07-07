# IQ 直传路线集成状态

记录 `feat/iq-direct-tx` 分支上 analog latent-IQ 直传链路相对于最终目标 `JSCC Enc → IQ → Channel → IQ → JSCC Dec` 的集成进度。给接手者一个明确的"哪些已 wire、哪些待办、风险在哪"的清单。

本文件随实际进度更新。PHY 层设计原理见 [`docs/analog_latent_iq_phy.md`](./docs/analog_latent_iq_phy.md)，完整 0-16 Pro 方案见 [`docs/analog_latent_iq_phy_full_proposal.md`](./docs/analog_latent_iq_phy_full_proposal.md)，jscc_tran 原始 handoff 见 [`JSCC_TRAN_HANDOFF.md`](./JSCC_TRAN_HANDOFF.md)。

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
| **Server 端 IQ 模式分支** | openamp `server.py` 知道走 IQ 而不是 QPSK | `tcp_server.py` / `openamp_control_plane_demo/server.py` 完全不认识 `AnalogLatentLink` | ❌ 未开始 |
| **双机 SSH/SCP 远端 RX** | TX 在控制机，RX 在板卡 | `RunAnalogLatentBatch.py` 当前 reject 除 `local` 外的 `--rx-capture-mode` | ❌ 未开始 |
| **真机硬件验证** | 线缆 + 30 dB 衰减器 → 近距离空口 | 仅软件 loopback 和 `simulate-channel` 注入 | ❌ 未开始 |
| **Cockpit UI IQ 模式标识** | 用户能看到 `link_mode`、`sync_metric`、`evm_rms`、`estimated_cfo_hz` | UI 完全没有 IQ 字段 | ❌ 未开始 |
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

1. **server.py 加 IQ 模式分支**（半天）。`Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py` 当前通过 SSH 调用板卡上的 `tcp_server.py`。IQ 模式下需要改成调用 `RunAnalogLatentBatch.py`。最简方案：加 `JSCC_LINK_MODE={qpsk|iq-direct}` 环境变量，IQ 模式下走完全不同的 `_send_image_via_usrp()` 路径，QPSK 路径不动。
2. **RunAnalogLatentBatch 加 remote-pull / remote-decode**（1 天）。把 `usrp_runtime.py` 里现有的 SSH/SCP 双机流程搬过来，让 TX 在控制机、RX 在板卡也能跑。
3. **线缆 + 30 dB 衰减器实测**（半天-1 天）。这是真正暴露问题的环节：实际 DC offset、本振不锁的相位漂移、TX/RX gain 配对。从低 gain 起步。
4. **近距离空口实测 + TX/RX gain 调优**（1-2 天）。

### P1 — 产品化

5. **Cockpit UI 加 IQ badge**（半天）。`server.py` 状态接口加 `link_mode` 字段，UI 显示 `sync_metric` / `evm_rms` / `estimated_cfo_hz`。
6. **`BuildOtaTools.sh` 决策**：等 IQ 直传稳定后，是否砍掉 QpskFileDecode target？目前两条并存。
7. **远端 decode 路径**：当前 `RunAnalogLatentBatch` 只支持本机 RX + 本机 decode。两机模式下 RX 在板卡，decode 也在板卡，结果 npz scp 回控制机。

### P2 — 优化

8. **sc16_amplitude / sps / RRC beta 调优**：默认 `amp=3000`、`sps=4`、`beta=0.35` 是保守值。真机 EVM 曲线出来后再扫。
9. **robust sync 阈值**：当前 `min-sync-metric=0.25`、`robust-cfo-max-hz=8000`、`robust-cfo-step-hz=500`，对 2922 两台不共本振的场景是否够用要看实际 CFO 分布。

## 风险点

- **真机 DC/CFO**：软件 simulate-channel 验证了 3 kHz CFO 能恢复，5 kHz CFO 走 robust grid 能恢复。但 2922 两台不共享本振的实际 CFO 可能更大、更漂。robust sync grid 上限 8 kHz，超过就失步。
- **clipping**：`sc16_amplitude=3000` 是猜的数字幅度，不等于 RF 输出功率。真机要看 EVM 随 amplitude 的曲线，找到不 clipping 的最大值。
- **RX 输入功率**：NI-USRP-2922 RX 最大输入功率 0 dBm。线缆直连高 gain 会烧前端，必须加衰减器（≥30 dB）从低 gain 起步。
- **量化 latent 兼容性**：当前 `AnalogLatentLink.load_latent` 对 `.pt` 强制要求 `'latent'` 字段。旧 `.pt`（只有 `quant/scale/zero_point`）会被 reject。如果遇到旧 latent，要么重跑 encoder 补 `latent` 字段，要么在 `AnalogLatentLink` 加 dequant fallback（不推荐，违背 IQ 直传跳量化的初衷）。

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
