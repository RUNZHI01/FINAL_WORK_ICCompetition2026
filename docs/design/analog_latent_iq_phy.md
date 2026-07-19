# Analog latent-IQ PHY

IQ-direct 将 LGJSCC encoder 输出的连续 latent 映射为 USRP I/Q 波形。无线信道直接作用在 latent 上，接收端恢复带噪 latent，再交给 TVM generator 重建图像。

QPSK 是默认现场链路；本文只说明 IQ-direct。

## 数据路径

```text
image
 -> LGJSCC encoder
 -> float latent
 -> RMS 归一化
 -> 实数两两组成复符号
 -> 导频与 RRC 成形
 -> SC16 波形
 -> NI USRP-2922 TX/RX
 -> DC、同步、CFO 和复增益校正
 -> noisy latent
 -> TVM generator
 -> reconstructed image
```

主要实现：

| 文件 | 作用 |
|---|---|
| `USRP292x/AnalogLatentLink.py` | 波形成帧、软件信道模拟和接收解码 |
| `USRP292x/RunAnalogLatentBatch.py` | 单图、批量、分段和 ARQ |
| `USRP292x/OtaTxPersistentServer.cpp` | 常驻 SC16 发送服务 |
| `USRP292x/OtaRxPersistentServer.cpp` | 常驻 SC16 接收服务 |
| `scripts/latent_transport.py` | latent transport blob 兼容层 |
| `scripts/tvm_inference_helper.py` | TVM 信道模式和板端重建 |

## Latent 输入

encoder 保存连续 latent，同时保留旧量化字段：

```python
{
    "latent": y_cpu.float(),
    "quant": q_tensor,
    "scale": scale,
    "zero_point": zero_point,
    "snr": self.args.snr,
    "config_str": self.args.config_str,
}
```

IQ-direct 优先读取 `latent`。输入格式支持：

```text
.npz with latent
.npy
.pt with latent
.bin raw float32
.bin latent_transport wire blob
```

## 发送帧

1. 对 latent 使用固定参考峰值做全局 RMS 归一化。
2. 相邻两个实数分别作为复符号的 I、Q 分量。
3. 可选地用会话材料派生 permutation 和 sign scrambling。
4. 添加 zero guard、CFO pilot、同步 pilot、分段 pilot 和 tail guard。
5. 使用 RRC 滤波器成形。
6. 缩放并量化为 SC16。

默认参数：

| 参数 | 值 |
|---|---:|
| sample rate | `5 MS/s` |
| SPS | `2` |
| symbol rate | `2.5 MSym/s` |
| RRC beta | `0.35` |
| RRC span | `8` |
| SC16 amplitude | `6000` |
| normalization reference peak | `6` |
| zero/tail guard | `4096 samples` |
| CFO pilot | `1024 symbols`，重复两次 |
| sync pilot | `1024 symbols` |
| data block | `4096 symbols` |
| mid pilot | `128 symbols` |
| capture margin | `20000 samples` |

`sc16_amplitude` 是数字幅度，不代表 RF 输出功率。线缆直连必须使用衰减器，并从低 TX/RX gain 开始。

## 接收处理

接收端按以下顺序处理：

1. 使用 zero guard 估计并去除 DC。
2. 裁剪有效 capture，执行 RRC 匹配滤波。
3. 搜索同步 pilot，估计定时位置。
4. 通过重复 CFO pilot 估计频偏。
5. 使用分段 pilot 跟踪复增益和相位。
6. 反置乱并恢复 latent。
7. 生成 `decode_summary.json`，记录同步、EVM、SNR 和耗时。

两个 pilot 之间的复增益采用线性插值。两台 USRP-2922 未共享参考时可能出现 kHz 级 CFO，因此不能只依赖整段重复相关。

大频偏网格搜索用于排查两台设备的本振偏差。主演示默认关闭该功能，避免拉长低质量帧的解码尾部；调试参数可通过 `AnalogLatentLink.py --help` 查询。

## 质量门限和 ARQ

IQ-direct 不用 CRC 或原始 latent SHA 判断成功。当前门限为：

- `sync_metric >= 0.75`
- `pilot_gain_min_over_initial >= 0.85`
- EVM 可用时 `<= 0.75`
- 估计 SNR 可用时 `>= 3 dB`

低质量 latent 不进入 TVM。长批次按 30 张分段，段内失败项执行 ARQ；每段结束后可再做两轮失败子集补传。详细运行数据见 [`../USRP_IQ_RUNTIME.md`](../USRP_IQ_RUNTIME.md)。

## AnalogLatentLink CLI

生成波形：

```bash
python3 USRP292x/AnalogLatentLink.py make \
  --input latent.npz \
  --out-sc16 tx_analog.sc16 \
  --manifest frame.json \
  --rate 5000000 \
  --sps 2 \
  --amp 6000 \
  --tx-normalization-reference-peak 6
```

解码接收波形：

```bash
python3 USRP292x/AnalogLatentLink.py decode \
  --rx-sc16 batch_rx.sc16 \
  --manifest frame.json \
  --out-npz received_latent.npz \
  --out-wire merged_round0.bin \
  --summary-json decode_summary.json
```

软件信道模拟：

```bash
python3 USRP292x/AnalogLatentLink.py simulate-channel \
  --tx-sc16 tx_analog.sc16 \
  --manifest frame.json \
  --out-sc16 batch_rx.sc16 \
  --cfo-hz 3000 \
  --snr-db 20 \
  --gain 0.85 \
  --phase-deg 25 \
  --dc-real 0.015 \
  --dc-imag -0.010 \
  --summary-json simulate_channel_summary.json
```

CLI 默认启用 `rx_post_quantize`。Cockpit profile 设置 `ANALOG_RX_POST_QUANTIZE=0`，直接使用恢复后的连续 latent。

## Batch runner

软件 loopback：

```bash
python3 USRP292x/RunAnalogLatentBatch.py \
  --input latent.npz \
  --count 1 \
  --run-root USRP292x/analog_latent_runs \
  --run-id smoke \
  --dry-run
```

加入 CFO 和 AWGN：

```bash
python3 USRP292x/RunAnalogLatentBatch.py \
  --input latent.npz \
  --count 1 \
  --run-root USRP292x/analog_latent_runs \
  --run-id sim_cfo_3k_snr20 \
  --dry-run \
  --sim-cfo-hz 3000 \
  --sim-snr-db 20
```

真实设备：

```bash
export JSCC_CHANNEL_MODE=real-usrp
python3 USRP292x/RunAnalogLatentBatch.py \
  --input latent.npz \
  --count 1 \
  --run-root USRP292x/analog_latent_runs \
  --run-id rf_001
```

runner 支持 `local`、`remote-pull` 和 `remote-decode`。Cockpit 使用 `remote-decode`：板端就地恢复 latent，上位机只读取状态和摘要，不拉取原始 IQ capture。

## TVM 信道模式

`scripts/tvm_inference_helper.py` 支持：

```text
sim-awgn   推理前注入软件 AWGN
real-usrp  直接使用 USRP 恢复的 latent
none       不注入 AWGN，用于链路验证
```

真实 USRP 模式必须设置 `JSCC_CHANNEL_MODE=real-usrp`，避免二次添加软件噪声。

## 数据面置乱与加密边界

可选 scrambling 由会话材料派生，只改变 complex latent symbols 的顺序和符号：

```text
symbols_tx = sign * symbols[perm]
```

帧元数据只记录 fingerprint 和 seed hash，不保存会话材料。scrambling 不是 AES-GCM 或 SM4-GCM 加密，不能作为数据面保密性声明。

控制面继续使用 ML-KEM、SM4-GCM、ML-DSA 和 SM2。不要对 analog IQ payload 直接使用 GCM；任意 bit 错误都会使认证失败，与 noisy latent 的连续退化模型不兼容。

## 验证要求

- 软件 loopback：`sync_success=true`，输出能进入现有 TVM 流程。
- 软件信道：检查 CFO 估计、同步、EVM、SNR 和 latent MSE 随信噪比变化。
- 线缆测试：使用至少 30 dB 衰减，从低增益开始。
- 空口测试：记录天线位置、频点、增益、重试次数和重建质量。

DC 只能用 zero guard 估计；不要用整帧均值。不要在 RX 后再次添加软件 AWGN，也不要用原始 latent SHA 判断 analog payload 是否成功。
