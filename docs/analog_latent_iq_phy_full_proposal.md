# Analog-Latent-IQ PHY for LGJSCC over NI-USRP-2922

这份文档是 `jscc_tran` 分支的完整方案说明。目标不是把 latent 当文件可靠传输，而是把 **LGJSCC Encoder 输出的连续 latent 直接变成 USRP I/Q 波形**。这样真实无线信道的噪声、频偏、相位扰动会直接作用在语义 latent 上，再由 Generator 重建图像，才更符合 DeepJSCC/LGJSCC。

说明：本文保留原完整方案里的旧代码上下文引用。当前 `jscc_tran` 已被整理成独立 handoff 分支，只包含 analog 路线、复用 USRP 服务、控制面加密代码、必要测试和文档，不包含旧 UI、大包、QPSK runner 等完整历史工程。

## 0. 总体结论

新的传输方案应该走这条链路：

```text
图像
 -> LGJSCC Encoder
 -> float latent y
 -> global RMS 归一化
 -> real latent 两两配对成 complex symbol
 -> RRC 成形
 -> sc16 waveform
 -> NI-USRP-2922 发射
 -> NI-USRP-2922 接收
 -> DC 校正 / 同步 / CFO 校正 / matched filter / 增益均衡
 -> recovered noisy latent y_hat
 -> 可选 quant-dequant 兼容层
 -> Generator / TVM 重建
```

不要再走：

```text
latent -> bytes -> QPSK -> CRC -> ARQ -> bit-perfect latent -> Generator
```

QPSK+CRC+ARQ 可以保留为可靠 baseline，但不应该作为 DeepJSCC 主链路。

NI-USRP-2922 本身适合这个方案：官方规格给出 400 MHz-4.4 GHz 频率范围，16-bit 样本下最大实时带宽 20 MHz、最大 I/Q 采样率 25 MS/s，TX/RX 频率精度 2.5 ppm；所以 5 MS/s、sc16、短帧 analog latent 方案是安全且保守的。TX 最大输出功率 17-20 dBm，RX 最大输入功率 0 dBm，因此线缆直连一定要加衰减，空口也要从低增益开始。参考：[NI USRP-2922 Specifications][ni-usrp-2922]。

## 1. 现在代码里可以复用的部分

不需要重写 USRP C++ 收发服务。

`OtaTxPersistentServer.cpp` 本质上只是发送 `sc16` 文件，不关心这个文件是 QPSK 还是别的 waveform。它只检查文件大小是否按 `complex<int16>` 对齐，然后调用 UHD `tx_stream_->send()` 发送。

接收端 `OtaRxPersistentServer.cpp` 也是通用 `sc16` 捕获器，并且支持 `nsamps` 精确采样数捕获。

控制脚本 `OtaRxControl.py` 已支持：

```text
capture --duration
capture --nsamps
```

所以新方案不需要改 C++ 主体。真正新增的是：

```text
USRP292x/AnalogLatentLink.py
USRP292x/RunAnalogLatentBatch.py
```

本 handoff 分支已经保留复用服务：

```text
USRP292x/BuildOtaTools.sh
USRP292x/OtaTxPersistentServer.cpp
USRP292x/OtaRxPersistentServer.cpp
USRP292x/OtaTxPersistentServer.sh
USRP292x/OtaRxPersistentServer.sh
USRP292x/OtaTxControl.py
USRP292x/OtaRxControl.py
```

旧 QPSK 文件链路只作为 reliable baseline。当前独立 handoff 分支没有保留旧 QPSK runner，避免接手的人误用它作为主链路。

## 2. 必须修正的旧链路问题

模型训练链路是：

```text
Encoder -> AWGNChannel -> quantize/dequantize -> Generator
```

AWGN 的定义按 real latent 的均方值来定噪声功率：

```python
pwr = torch.mean(y ** 2, (-3, -2, -1), True) * 2
noise_pwr = pwr * 10 ** (-snr / 10)
noise = torch.sqrt(noise_pwr / 2) * torch.randn_like(y)
```

这说明：**把两个 real latent 值配成一个 complex I/Q symbol 是和原模型信道假设一致的**。

真实 USRP 模式下必须关闭软件 AWGN。旧逻辑里重建 latent 时可能会再次加 AWGN，`tvm_inference_helper.py` 也会先 `awgn_channel(latent, snr)`。新方案里这些都要变成：

```text
sim-awgn 模式：加软件 AWGN
real-usrp 模式：不加软件 AWGN
```

本分支实现位置：

```text
scripts/tvm_inference_helper.py
host_pic_to_latent/jscc/src/test_model.py
```

## 3. 新方案文件结构

新增/修改文件：

```text
USRP292x/
  AnalogLatentLink.py          # 核心：latent <-> analog sc16 waveform
  RunAnalogLatentBatch.py      # 批处理 runner，兼容现有 merged_round0.bin 输出约定
  test_analog_latent_link.py   # 软件 loopback 测试

scripts/
  latent_transport.py          # 支持 .pt 里的 raw float latent
  tvm_inference_helper.py      # 增加 channel_mode，real-usrp 时禁用 AWGN

host_pic_to_latent/jscc/src/
  test_model.py                # 保存 Encoder raw float latent
```

复用但不改主体逻辑：

```text
USRP292x/OtaTxPersistentServer.cpp
USRP292x/OtaRxPersistentServer.cpp
USRP292x/OtaTxControl.py
USRP292x/OtaRxControl.py
```

## 4. latent 导出方式

旧 `_save_encoder_output()` 只保存：

```python
quant
scale
zero_point
```

为了做 analog latent-IQ，改成同时保存 raw float latent：

```python
torch.save({
    "latent": y_cpu.float(),          # 原始 Encoder 输出
    "quant": q_tensor,                # 保留：兼容旧链路
    "scale": scale,
    "zero_point": zero_point,
    "snr": self.args.snr,
    "config_str": self.args.config_str,
}, save_path)
```

第一版不要只传 `quant`。新主链路应该以：

```text
latent float32
```

作为信道输入符号。

为了兼容当前 Generator 的训练方式，接收端保留一个可选步骤：

```text
rx_post_quantize = true
```

也就是：

```text
USRP 接收到 y_hat
-> 按 y_hat 当前 min/max 做 quantize/dequantize
-> Generator
```

保留这个选项的原因：当前训练代码里 Generator 看到的是 `AWGN 后又 quant-dequant` 的 latent，而不是完全 raw 的 latent。这个 quant-dequant 是本地兼容层，不是 QPSK 文件传输，不会重新变成传统可靠数字通信。

建议默认：

```text
第一版：rx_post_quantize = true
第二版：对比 rx_post_quantize = false
```

看哪一个重建更稳。

## 5. waveform 设计

### 5.1 基本参数

针对 NI-USRP-2922，第一版用保守参数：

```text
sample_rate Fs: 5 MS/s
sps: 4
RRC rolloff beta: 0.35
RRC span: 8 symbols
sc16 amplitude: 2000-3000
TX gain: 5-10 dB 起步
RX gain: 10-20 dB 起步
center frequency: 根据天线选择；线缆调试可先用 500/900 MHz
```

latent 形状一般是：

```text
[1, 32, 32, 32]
```

也就是：

```text
32768 real values
```

两两配成 complex symbol 后：

```text
16384 complex symbols
```

`sps=4` 后 payload samples：

```text
16384 * 4 = 65536 samples
```

在 5 MS/s 下 payload 时间：

```text
65536 / 5e6 ~= 13.1 ms
```

加上 pilot、sync、guard 后，整帧大约 18-25 ms。即使这样也会比当前 QPSK+chunk+ARQ+大 tail 快很多。

### 5.2 帧格式

第一版帧结构：

```text
[zero_guard]
[cfo_pilot_A]
[cfo_pilot_A_repeat]
[sync_pilot]
[data_block_0]
[mid_pilot_0]
[data_block_1]
[mid_pilot_1]
...
[data_block_N]
[tail_guard]
```

推荐参数：

```text
zero_guard_samples: 4096
cfo_pilot_symbols: 1024
sync_pilot_symbols: 1024
data_block_symbols: 4096
mid_pilot_symbols: 128 或 256
tail_guard_samples: 4096
```

其中：

```text
cfo_pilot_A 和 cfo_pilot_A_repeat 必须完全相同
```

这样可以用重复序列估计 CFO。

## 6. TX 端算法

输入：

```text
latent y: float32, shape [1, 32, 32, 32]
```

先展开：

```python
x = latent.reshape(-1).astype(np.float32)
```

做 global RMS 归一化。不要做 per-channel mean/std，第一版要尽量贴近模型训练时的 AWGN 假设：

```python
real_rms = np.sqrt(np.mean(x ** 2) + 1e-8)
u = x / real_rms
```

这个 `real_rms` 必须写入 manifest，RX 端要用它恢复尺度。

然后两两配成 complex symbols：

```python
if len(u) % 2:
    u = np.pad(u, (0, 1))

symbols = u[0::2] + 1j * u[1::2]
symbols = symbols.astype(np.complex64)
```

可选做密钥派生的 sign/permutation scrambling：

```python
perm = rng.permutation(len(symbols))
sign = rng.choice([-1.0, 1.0], size=len(symbols))

symbols_tx = sign * symbols[perm]
```

第一版先不开 scrambling，等主链路跑稳后再加。

然后插入 pilot：

```python
frame_symbols = [
    cfo_pilot,
    cfo_pilot,
    sync_pilot,
    data_0,
    mid_pilot,
    data_1,
    mid_pilot,
    ...
]
```

做 RRC 成形：

```python
upsampled = upsample(frame_symbols, sps)
wave = np.convolve(upsampled, rrc_taps, mode="full")
```

前后加 zero guard：

```python
wave = np.concatenate([
    np.zeros(zero_guard_samples, dtype=np.complex64),
    wave,
    np.zeros(tail_guard_samples, dtype=np.complex64),
])
```

转成 sc16：

```python
peak = np.max(np.abs(wave)) + 1e-8
wave_norm = wave / peak
sc16_i = np.clip(np.real(wave_norm) * amp, -32767, 32767).astype(np.int16)
sc16_q = np.clip(np.imag(wave_norm) * amp, -32767, 32767).astype(np.int16)
```

注意 `peak` 要写入 manifest。虽然接收端主要靠 pilot 均衡，但记录它有助于调试。

## 7. RX 端算法

RX 读到的是 `batch_rx.sc16`。

先转 complex：

```python
rx = sc16_i.astype(np.float32) + 1j * sc16_q.astype(np.float32)
rx = rx / amp
```

### 7.1 DC offset correction

不要做：

```python
rx = rx - np.mean(rx)
```

这会破坏 analog latent 的低频/均值结构。

正确做法是只用开头 zero guard 估 DC：

```python
dc = np.mean(rx[:zero_guard_samples])
rx = rx - dc
```

### 7.2 CFO 估计

利用两个重复 CFO pilot：

```python
A = np.sum(rx2 * np.conj(rx1))
f_hat = np.angle(A) / (2 * np.pi * L / Fs)
```

其中 `L` 是两个重复 pilot 之间的样本间隔。然后校正：

```python
n = np.arange(len(rx))
rx = rx * np.exp(-1j * 2 * np.pi * f_hat * n / Fs)
```

2922 的频率精度是 2.5 ppm，两台机器内部时钟未同步时，几百 MHz 到 GHz 频点下的相对频偏不可忽略，所以 CFO 必须每帧估计。参考：[NI USRP-2922 Specifications][ni-usrp-2922]。

### 7.3 matched filter + timing phase

做 matched filter：

```python
mf = np.convolve(rx, np.conj(rrc_taps[::-1]), mode="same")
```

然后在 `phase = 0..sps-1` 中找最大 sync correlation：

```python
best_phase = argmax_phase_corr(mf, sync_pilot, sps)
sym_stream = mf[best_phase::sps]
```

### 7.4 sync 定位

用 sync pilot 做相关：

```python
corr[k] = abs(sum(sym_stream[k:k+L] * conj(sync_pilot)))
start = argmax(corr)
```

定位出 data 起点。

### 7.5 复数增益均衡

用 pilot 估计复数信道增益：

```python
h = np.vdot(pilot_tx, pilot_rx) / np.vdot(pilot_tx, pilot_tx)
data_eq = data_rx / h
```

如果 payload 较长，mid_pilot 可以用来估计相位漂移：

```python
phase_i = angle(vdot(mid_pilot_tx, mid_pilot_rx / h))
```

然后对两个 pilot 之间的数据做线性相位插值校正。

### 7.6 complex symbols 还原成 real latent

得到 payload symbols 后：

```python
flat_hat = np.empty(n_real, dtype=np.float32)
flat_hat[0::2] = np.real(symbols_hat[:n_complex])
flat_hat[1::2] = np.imag(symbols_hat[:n_complex])
```

如果做了 scrambling：

```python
symbols_unscrambled = np.empty_like(symbols_hat)
symbols_unscrambled[perm] = sign * symbols_hat
```

最后恢复尺度：

```python
x_hat = flat_hat * real_rms
latent_hat = x_hat.reshape(original_shape).astype(np.float32)
```

## 8. manifest 设计

每一帧都生成一个 `manifest.json`，metadata 通过可靠控制面传输，不走 analog 数据面。

建议字段：

```json
{
  "version": 1,
  "phy": "analog-latent-iq",
  "job_id": "image_0000",
  "shape": [1, 32, 32, 32],
  "dtype": "float32",
  "n_real": 32768,
  "n_complex": 16384,

  "normalization": "global_real_rms",
  "real_rms": 0.123456,

  "sample_rate": 5000000,
  "sps": 4,
  "rrc_beta": 0.35,
  "rrc_span": 8,
  "sc16_amplitude": 3000,

  "zero_guard_samples": 4096,
  "tail_guard_samples": 4096,
  "cfo_pilot_symbols": 1024,
  "sync_pilot_symbols": 1024,
  "data_block_symbols": 4096,
  "mid_pilot_symbols": 128,

  "cfo_seed": 1001,
  "sync_seed": 1002,
  "mid_pilot_seed": 1003,

  "tx_waveform_samples": 90112,
  "capture_nsamps": 105000,

  "rx_post_quantize": true,
  "payload_is_bit_exact": false
}
```

注意最后这个字段：

```json
"payload_is_bit_exact": false
```

这很重要。analog latent 方案不是 bit-perfect 传输，不能再用原始 SHA 判断成功与否。成功标准应该是：

```text
同步成功
CFO/相位/增益估计成功
恢复出 shape 正确的 noisy latent
Generator 能重建图像
```

## 9. 加密/安全层如何处理

ML-KEM / AES-GCM / SM4-GCM 代码应该保留，但只用于控制面和 metadata。

`secure_channel.py` 里定义的是可靠字节帧：

```text
4B length + payload
ML-KEM handshake
EncryptedPayload.to_bytes()
```

`crypto.py` 里 AES-GCM / SM4-GCM 是 AEAD，保证机密性和完整性。

这和 analog latent 数据面天然冲突：GCM 只要一个 bit 错就会认证失败，而 DeepJSCC 的目标正是允许 noisy latent 被 Generator 尽量恢复。

所以方案应该写成：

```text
控制面：
  ML-KEM 建立会话密钥
  AES-GCM / SM4-GCM 保护 manifest、参数、job_id、nonce、anti-replay

数据面：
  analog latent-IQ 直接通过 USRP 传输
  可选用会话密钥派生 permutation/sign scrambling
  不对 analog payload 做 GCM 认证
```

对外表述：

```text
系统采用双平面安全设计：控制面使用 ML-KEM + AEAD 保护会话参数与元数据；数据面采用密钥派生的 latent 置乱和模拟 JSCC 传输，以保持 DeepJSCC 的连续信道特性。
```

不要说：

```text
analog I/Q payload 被 AES-GCM 加密传输
```

这不成立。

## 10. `AnalogLatentLink.py` 设计

CLI：

```bash
python3 USRP292x/AnalogLatentLink.py make \
  --input latent.npz \
  --out-sc16 tx_analog.sc16 \
  --manifest manifest.json \
  --rate 5000000 \
  --sps 4 \
  --amp 3000

python3 USRP292x/AnalogLatentLink.py decode \
  --rx-sc16 batch_rx.sc16 \
  --manifest manifest.json \
  --out-npz received_latent.npz \
  --out-wire merged_round0.bin \
  --summary-json decode_summary.json
```

内部模块：

```python
load_latent()
rrc_taps()
symbols_to_waveform()
waveform_to_sc16()
sc16_to_complex()
matched_filter()
find_sync()
estimate_channel_gain()
recover_payload_symbols()
pack_received_wire_blob()
```

`pack_received_wire_blob()` 用已有 `latent_transport.py` 格式生成新的 float32 raw wire blob。`latent_transport.py` 支持 `float32-raw`、`pack_transport_frame()`、`unpack_transport_frame()`。

`_load_float32_latent()` 增加 `.pt` 支持：

```python
if path.endswith(".pt"):
    payload = _torch_load(path)
    if "latent" in payload:
        arr = payload["latent"]
        if hasattr(arr, "detach"):
            arr = arr.detach().cpu().numpy()
        return arr.astype(np.float32), {
            "shape": list(arr.shape),
            "dtype": "float32",
        }
```

## 11. `RunAnalogLatentBatch.py` 设计

这个 runner 的目标是兼容现有后续流程的输出约定。

设置：

```bash
export MLKEM_USRP_RUNNER_SCRIPT=/path/to/USRP292x/RunAnalogLatentBatch.py
export USRP_RUN_ROOT=/path/to/USRP292x/analog_latent_runs
export JSCC_CHANNEL_MODE=real-usrp
```

`RunAnalogLatentBatch.py` 对每个输入 latent 做：

```text
1. AnalogLatentLink.py make
2. OtaRxControl.py capture --nsamps manifest["capture_nsamps"]
3. sleep 5-10 ms
4. OtaTxControl.py send --file tx_analog.sc16
5. OtaRxControl.py wait
6. AnalogLatentLink.py decode
7. 输出 image_0000/merged_round0.bin
8. 更新 batch_spool_summary.json
```

注意：必须用 `--nsamps`，不要用很长的 `--duration`。

新 runner 应使用：

```text
tx_delay_sec: 0.005-0.010 s
capture_nsamps: tx_waveform_samples + 10000 到 20000 samples
wait_timeout: capture_nsamps / Fs + 1.0 s
```

输出目录保持兼容：

```text
run_dir/
  image_0000/
    tx_analog.sc16
    batch_rx.sc16
    manifest.json
    decode_summary.json
    merged_round0.bin
  batch_spool_summary.json
```

只要按这个格式输出，后面的远端 decode/TVM 流程可以尽量少改。

## 12. TVM / Generator 侧修改

`tvm_inference_helper.py` 增加参数：

```python
parser.add_argument(
    "--channel-mode",
    choices=["sim-awgn", "real-usrp", "none"],
    default=os.environ.get("JSCC_CHANNEL_MODE", "sim-awgn"),
)
```

推理时：

```python
latent = load_npz(input_payload)

if channel_mode == "sim-awgn":
    model_input, channel_metrics = awgn_channel(latent, snr)
else:
    model_input = latent.astype(np.float32)
    channel_metrics = {
        "channel_mode": channel_mode,
        "awgn_injected": False,
    }

output = fn(runtime_tensor(model_input, dev))
```

真实 USRP 模式运行：

```bash
export JSCC_CHANNEL_MODE=real-usrp
```

`test_model.py` 里也做类似开关：

```python
if real_usrp:
    y_noisy = y_dequant.unsqueeze(0)
else:
    y_noisy = self.AWGNChannel(y_dequant.unsqueeze(0), snr)
```

## 13. 第一版参数表

| 参数 | 建议值 |
| --- | ---: |
| `Fs` | 5 MS/s |
| `sps` | 4 |
| `symbol_rate` | 1.25 MSym/s |
| `rrc_beta` | 0.35 |
| `rrc_span` | 8 |
| `sc16_amp` | 3000 |
| `zero_guard_samples` | 4096 |
| `tail_guard_samples` | 4096 |
| `cfo_pilot_symbols` | 1024，重复 2 次 |
| `sync_pilot_symbols` | 1024 |
| `data_block_symbols` | 4096 |
| `mid_pilot_symbols` | 128 |
| `TX gain` | 5-10 dB 起步 |
| `RX gain` | 10-20 dB 起步 |
| `rx_post_quantize` | true |
| `AWGN software injection` | real-usrp 模式下关闭 |
| `ARQ` | 不用于 analog payload |
| `CRC/SHA` | 只用于 metadata / 文件记录，不作为 payload 成功标准 |

## 14. 验证路线

### 阶段 1：纯软件 loopback

不接 USRP，先做：

```text
latent -> make waveform -> decode waveform -> latent_hat
```

要求：

```text
sync_success = true
latent_mse 很小
Generator 输出正常
```

这个阶段没有 CFO、没有真实噪声，主要验证 reshape、RRC、manifest、pack/unpack 没错。

### 阶段 2：软件 AWGN loopback

在 waveform 上加软件 CFO/AWGN：

```python
rx = tx * exp(j 2π f_offset n / Fs) + noise
```

测试：

```text
CFO = 500 Hz / 1 kHz / 3 kHz
SNR = 20 / 15 / 10 / 5 dB
```

要求：

```text
estimated_cfo 接近真实 CFO
sync 成功率接近 100%
PSNR/MS-SSIM 随 SNR 下降而平滑下降
```

### 阶段 3：线缆 + 衰减器

强烈建议先线缆，不要直接空口。

```text
TX -> 30 dB 或更高衰减 -> RX
```

要求：

```text
clipping_ratio 接近 0
sync_success > 99%
CFO 估计稳定
latent_mse 可接受
重建图像无明显崩坏
```

### 阶段 4：近距离空口

低增益、短距离测试：

```text
TX gain 从 5 dB 开始
RX gain 从 10 dB 开始
逐步调高
```

记录：

```text
TX gain
RX gain
estimated_snr
estimated_cfo
EVM
latent_mse
PSNR
MS-SSIM
LPIPS
wall_time
airtime
```

### 阶段 5：和旧 QPSK 对比

最终做三组：

```text
A. sim-awgn
B. qpsk-reliable
C. analog-latent-iq
```

展示重点：

```text
qpsk-reliable：质量高但耗时长，不体现 DeepJSCC 抗噪
analog-latent-iq：耗时短，质量随信道平滑退化，更符合 DeepJSCC
```

## 15. 关键坑位

第一，不要在 RX 后再加软件 AWGN。真实 USRP 已经是信道。

第二，不要用整帧均值消 DC。只能用 zero guard 估 DC。

第三，不要把 analog payload 做 AES-GCM/SM4-GCM 加密。GCM 是 bit-exact 认证机制，和 noisy analog latent 冲突。

第四，不要用原始 latent 的 SHA 判断 analog payload 是否成功。应该对“接收到的 latent”重新计算 SHA，只作为文件完整性记录。

第五，不要一开始用高 TX gain。2922 RX 最大输入功率是 0 dBm，线缆直连尤其危险。参考：[NI USRP-2922 Specifications][ni-usrp-2922]。

第六，不要一开始追求 `sps=2` 或更高 sample rate。先用 5 MS/s + sps=4 跑稳，再优化速度。

第七，不要默认 per-channel normalization。第一版用 global RMS，更贴近代码里的 AWGNChannel。

## 16. 最终实现优先级

按这个顺序开工：

```text
P0：修改 test_model.py，导出 raw float latent
P1：写 AnalogLatentLink.py，完成 make/decode 软件 loopback
P2：给 tvm_inference_helper.py 加 channel_mode，real-usrp 禁用 AWGN
P3：写 RunAnalogLatentBatch.py，复用 OtaTx/Rx persistent server
P4：跑线缆 + 衰减器实验
P5：跑近距离空口实验
P6：加入 mid-pilot 相位跟踪
P7：加入 key-derived scrambling
P8：整理 qpsk-reliable vs analog-latent-iq 对比实验
```

一句话总结：

```text
新的传输方案不要再围绕 QPSK 文件链路做小修小补，而是把现有 USRP C++ 服务当作通用 sc16 收发器，在 Python 层新增 AnalogLatentLink，把 LGJSCC latent 直接映射成连续 I/Q 符号；控制面继续安全可靠，数据面保持 analog noisy latent，这样才既快又符合 DeepJSCC。
```

[ni-usrp-2922]: https://www.ni.com/docs/en-US/bundle/usrp-2922-specs/page/specs.html?srsltid=AfmBOoq32lAktM8bNUGffEKq4zLGfUY-ciYP1jTyJivnwI04V40YTr7i "USRP-2922 Specifications - NI"
