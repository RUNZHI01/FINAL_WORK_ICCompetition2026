# USRP-2922 数据面与 JSCC 路线调研

更新时间：2026-04-28

## 目标口径

根本目标不是“证明 USRP 能发射”，而是：

1. 无线数据面不要成为 TVM / MNN 推理链路的主要瓶颈。
2. 数据面要尽可能发挥 JSCC 的优势，而不是把 JSCC latent 当普通文件做低效、强纠错、bit-exact 传输。

当前已知：

| 项目 | 当前值 | 说明 |
|---|---:|---|
| 业务 latent payload | `33,534 B` | B205mini 历史真实业务口径 |
| raw float32 latent | `1x32x32x32 = 131,072 B` | Tailscale fallback 的 raw float32 口径 |
| TVM 推理 | `~230-250 ms/image` | 板端历史实测 |
| B205mini frozen 无线 E2E | `~9.53 s/image` | `2.5 Msps + repeat=3` 历史口径 |
| USRP-2922 host interface | `1 Gigabit Ethernet` | N210/2922 路线 |
| USRP-2922 16-bit IQ 采样率 | `25 MS/s` | 官方规格上限，实际受主机和网络影响 |
| USRP-2922 8-bit IQ 采样率 | `50 MS/s` | 官方规格上限，实际受主机和网络影响 |
| USRP-2922 实时带宽 | `20 MHz @ 16-bit`, `40 MHz @ 8-bit` | 官方规格 |
| 当前 raw float32 wire blob | `131,231 B` | `1x32x32x32 float32` payload + 现有 JSON metadata |

按 `33,534 B` 估算，若无线数据面不明显阻塞 `250 ms` 推理：

```text
33,534 B * 8 / 0.25 s = 1.07 Mbit/s
```

这只是 payload 下限，不含同步、preamble、pilot、header、FEC、ARQ 和重传。实际工程目标建议定为：

```text
P0: >= 1.5 Mbit/s effective payload
P1: >= 3.0 Mbit/s effective payload
P2: 支持流水线后，无线单图耗时 <= TVM/MNN 推理耗时
```

若直接传 `1x32x32x32 float32`，当前估算结果更严格：

| sample_rate | scheme | payload_rate | airtime |
|---:|---|---:|---:|
| `219 kSps` | `QPSK uncoded` | `0.219 Mbps` | `~4.79 s` |
| `1 Msps` | `QPSK uncoded` | `1.000 Mbps` | `~1.05 s` |
| `2.5 Msps` | `QPSK uncoded` | `2.500 Mbps` | `~420 ms` |
| `5 Msps` | `QPSK uncoded` | `5.000 Mbps` | `~210 ms` |
| `5 Msps` | `QPSK r=3/4` | `3.750 Mbps` | `~280 ms` |
| `10 Msps` | `QPSK r=1/2` | `5.000 Mbps` | `~210 ms` |

结论：

- `219 kSps` 只能做 RF / 同步 smoke，不适合传 raw float32 latent。
- 如果直接传 `131 KB` raw float32，第一阶段至少要瞄准 `5 Msps + QPSK`。
- 如果保留历史 `33,534 B` quant `.npz` payload，速率压力会小很多，更适合先跑闭环。
- 真要发挥 JSCC，不应长期要求 raw float32 byte-exact；应转向 quant/UEP 或 pseudo-analog latent。

术语说明：

- LabVIEW 里的 `IQ rate` 基本等价于 UHD `rate` / complex sample rate / `Sps`。
- `IQ rate` 不等于 payload bit rate；例如 `5 MSps + 2 samples/symbol + QPSK` 的理想 raw bit rate 约为 `5 Mbps`。
- 从 `220 kSps` 跳到 `5 MSps` 对 USRP-2922 和主机短时 streaming 不是主要瓶颈；当前难点在 OTA PHY 同步、定时恢复、均衡和 chunk 可靠性。

## 关键判断

### 1. 继续 bit-exact 文件传输会浪费 JSCC 优势

旧 B205mini 路线本质是：

```text
latent bytes -> FEC/CRC/重复 -> bit-exact 恢复 -> TVM decoder
```

这条路线安全、好调试，但它把 JSCC latent 当普通文件处理。只要要求 SHA256 完全一致，系统就会自然走向：

- 更强 FEC
- 更多 repeat
- 更保守调制
- 更高 ARQ 开销
- 端到端时延上升

这和 JSCC 的核心优势相冲突。DeepJSCC 的价值在于 noisy channel 下 graceful degradation，不是每个 bit 都必须恢复。

### 2. 正确方向是“feature / symbol 层受控失真”

更符合 JSCC 的数据面应分两层：

| 层 | 目标 | 校验口径 |
|---|---|---|
| 控制与元数据 | 必须可靠 | CRC / SHA / ARQ |
| JSCC latent / channel symbols | 允许受控失真 | PSNR / SSIM / LPIPS / task quality |

也就是说，`session_id`、`shape`、`dtype`、`scale`、`normalization`、`chunk map` 必须可靠；但 latent 本体不应长期要求 bit-exact。

### 3. 第一版不应直接跳到完整 neural modem

完整 DeepJSCC 原论文路线是把图像直接映射到 complex channel symbols，并端到端训练 encoder / channel / decoder。当前仓库已有 TVM decoder 和 latent 文件口径，短期内更现实的是：

```text
JSCC latent -> normalization -> complex symbol mapping -> USRP OTA -> soft / float latent estimate -> TVM/MNN decoder
```

这属于 feature-domain analog / pseudo-analog 方向，能先复用现有 decoder 和 `1x32x32x32` 形状。

### 4. 队长建议对应的工程判断

如果 DeepJSCC 编码器输出本来就是连续复数信道符号，那么最终正确路径确实不是：

```text
bit -> QPSK -> bit
```

而应当是：

```text
image -> DeepJSCC encoder -> continuous complex symbols
      -> framing / pilot / sync -> USRP complex IQ samples
      -> OTA
      -> sync / CFO correction / channel estimate
      -> recovered complex symbols -> DeepJSCC decoder -> image
```

这点在理论和工程口径上都成立，因为 USRP/UHD 的原生数据面就是 complex baseband IQ samples。

但当前仓库的运行时事实要单独写清楚：

- `scripts/tcp_client.py` 当前会把 `.npz` 里的 `quant/scale/zero_point` 反量化成 `float32 latent` 后再发送。
- `scripts/tvm_inference_helper.py` 当前接收的也是 `float32 latent`，并在实数 latent 上加 AWGN 后送入 TVM decoder。
- 也就是说，当前我们手里的稳定 I/O 口径是 `latent tensor / raw float32 bytes`，不是已经确认可直接上空口的 `complex channel symbols`。

因此当前应区分两条路线：

| 路线 | 当前定位 | 说明 |
|---|---|---|
| `QPSK + CRC + selective ARQ` | 截止日前可交付 baseline | 用现有 `131 KB raw float32` 或 `33 KB quant payload` 快速验证 USRP2922 吞吐、稳定性和控制面接口 |
| `DeepJSCC-native complex IQ` | 后续正线 | 前提是拿到真实 complex symbol 输出，并补齐 normalization、pilot、sync、CFO、channel estimation 和 decoder 输入语义 |

结论不是“QPSK 错了”，而是“QPSK 只适合作为数字兼容 baseline，不应误写成最终 JSCC PHY”。

## 建议路线

### P0: 官方例程双机链路基线

目标：

- `.2 TX -> .22 RX`
- 单频点，例如 `1.000 GHz`
- `tx_waveforms` + `rx_samples_to_file`
- 测出目标 tone 的 SNR / EVM-like 指标

验收：

- RX 文件中目标音调明显可见
- 能扫 `TX gain / RX gain / distance / freq`
- 固定一个“不会过载”的起始 operating point

当前阻塞：

- 官方 `rx_samples_to_file --gain` 在 N210/SBX 上报：

```text
multi_usrp: RX channel 18446744073709551615 out of range
```

处理方向：

1. 先绕开 `--gain` 参数，验证 RX capture。
2. 若仍要设 gain，写一个最小 C++ wrapper，用 UHD API 显式设置 `channel=0` 和 gain element。

### P1: 最小数字链路，但以吞吐为第一指标

目标：

- 不急着接 TVM。
- 先传 PRBS payload，测 BER / packet loss / effective payload Mbps。
- 调制可以先用 BPSK/QPSK，采样率从 `1 Msps`、`2.5 Msps`、`5 Msps` 往上扫。
- 若为了快速判断 `1x32x32x32` 量级，可先用 `EstimateLatentAirtime.py` 生成现有 wire blob 并按 `131,231 B` 估算。

建议指标：

| 指标 | P0 门槛 | P1 目标 |
|---|---:|---:|
| effective payload | `>= 1.0 Mbit/s` | `>= 3.0 Mbit/s` |
| 单图 33,534 B 传输耗时 | `<= 300 ms` | `<= 150 ms` |
| BER after sync/equalization | 可测 | 随 gain/freq 有曲线 |
| PER | 可测 | 支持小包 ARQ |

设计注意：

- packet header 必须可靠。
- payload 不要一开始就 repeat=3，也不要整包 blind repeat。
- ARQ 只补 missing chunks，不要整图盲重发。
- 记录每轮实际空口耗时，不只记录 PASS/FAIL。
- 板端是 ARM，第一版避免 payload 全量复杂 FEC；CRC + selective ARQ 优先。
- FEC 后置：先只保护短 header，或后续只对重要 chunk 使用轻量码率。

### P1.5: 低冗余 selective ARQ

当前快测 QPSK 结果说明：`5 MSps` 的 host streaming 可以支撑，且 OTA 中出现连续 byte-exact chunk，但全包仍不可靠。错误形态更像 chunk 同步 / 定时 / burst 稳定性问题，而不是均匀随机 BER。

因此第一版可靠链路不应靠高冗余 FEC 或整包重复，而应采用：

```text
USRP data plane:
  chunk(seq, total, len, crc32, payload)
  QPSK transmit once

Tailscale control plane:
  RX -> TX missing_chunk_bitmap / nack_list
  TX -> RX retransmit only failed chunks
```

约束：

| 项目 | 第一版策略 |
|---|---|
| payload FEC | 初始不加 |
| header 保护 | 可以强保护，因为 header 很短 |
| chunk 校验 | `crc32` 必须有 |
| ARQ | 选择性重传失败 chunk |
| repeat | 禁止整包 blind repeat |
| ARM 侧复杂度 | 避免 payload 全量 Viterbi / RS 级联 |
| JSCC 兼容 | 后续低重要 chunk 可弱保护或不重传 |

当前快测记录见 `USRP292x/QpskFileLinkRecord.md`。

### P2: JSCC-aware unequal protection

这是最适合当前项目的中期方向。

做法：

1. latent 分组时按重要性排序。
2. 高重要组使用更强保护：
   - header
   - scale / zero_point
   - low-frequency / high-energy latent channels
   - decoder 对质量更敏感的 channel
3. 低重要组使用弱保护或无 ARQ。
4. 丢包后不强行重传全量，只补会显著影响重建质量的 chunk。

需要补的实验：

- 对 `1x32x32x32` latent 做 channel ablation：
  - 每次清零 / 加噪 / 量化一组 channel
  - 测 PSNR / SSIM / LPIPS
  - 形成 latent channel importance map
- 基于 importance map 做 UEP：
  - 重要 chunk: stronger FEC + ARQ
  - 普通 chunk: lighter FEC
  - 低价值 chunk: no ARQ

收益：

- 比 bit-exact 全量 ARQ 更符合 JSCC。
- 仍能保留工程可控性，不需要马上重训完整 DeepJSCC 模型。

### P3: pseudo-analog latent transmission

目标：

```text
float latent -> scale/clip -> I/Q symbols -> OTA -> equalize -> float latent -> decoder
```

优点：

- 可以直接利用 JSCC 的 graceful degradation。
- 不再把每个 bit 当硬约束。
- 如果链路 SNR 足够，空口时延可显著低于强 FEC bitstream。

风险：

- 需要严肃处理 AGC / normalization / CFO / timing / channel estimate。
- TVM/MNN decoder 是否能容忍真实 RF 失真，需要实测。
- 需要建立 PSNR/SSIM/LPIPS 质量闭环，不能只看 SHA。

建议实现顺序：

1. 离线仿真：对 latent 加 AWGN / fading / clipping，跑 TVM/MNN 重建质量。
2. 文件级 baseband：生成 complex64 waveform，先不接 UHD。
3. USRP OTA：官方 file TX/RX 或最小 UHD streamer。
4. 质量闭环：恢复 latent 后直接进 decoder。

### P4: OFDM-guided JSCC

如果要更正式地贴近 JSCC 文献，OFDM-guided DeepJSCC 是更接近实际无线信道的方向。

它的核心价值：

- 把 OFDM、multipath channel、channel estimation / equalization 放进可微链路。
- 比“纯 CNN 自己学无线”更稳定。
- 对 clipping 和 channel mismatch 更鲁棒。

但这不是今晚/明天的第一实现。当前应先把两台 2922 的官方例程和最小数字链路跑通，再决定是否把 OFDM 作为下一阶段。

## 推荐优先级

| 优先级 | 方向 | 为什么 |
|---|---|---|
| P0 | 锁定当前 QPSK 默认基线 | `cpp+header + fast-arq-profile` 已到 `1.069 s/image`，现在要先把 `chunk_bytes` 与首轮成功率收口 |
| P0 | `chunk_bytes=2048` 做 `count=20` 复验 | 小范围 sweep 里它是唯一 `10/10 round0 PASS`，应先确认不是偶然值 |
| P0 | Tailscale missing-list 控制消息 | 替换本机文件接口，但必须独立端口/显式开关，避免干扰现有 demo 通讯 |
| P0 | 串行扫 `RX gain / rate` | 软件侧参数收口后，再一项一项动 RF 变量，避免再次把常驻链路打乱 |
| P1 | 缩短 RX capture window / batch burst | 当前真实 wall 主要被固定 capture 和离线 decode 拖住 |
| P1 | C++ decode hot path 默认化 | Python/Numpy 不是完全不可用，但当前离线解码确实是固定成本；C++ 更适合后续飞腾派部署 |
| P1 | 33KB quant `.npz` 真实 payload | `131 KB raw float32` 是压力包，真实闭环应尽快回到业务 payload |
| P1 | 确认是否存在可直接发射的 complex symbol 输出 | 没有这个前提，就不能把现有链路直接改写成 DeepJSCC-native IQ |
| P2 | latent importance / UEP | 用最小代价发挥 JSCC |
| P2 | TVM/MNN 重建闭环 | 前面稳定后再接，不把模型闭环和 RF 基线调试混在一起 |
| P3 | pseudo-analog latent | 真正从 bit-exact 过渡到 JSCC 风格 |
| P4 | OFDM-guided JSCC | 更学术完整，但实现复杂度高 |

## 2026-04-27 执行计划补充

### 1. Tailscale 控制面是否会干扰 demo

不会天然干扰，但必须遵守隔离原则：

- `RX/TX persistent control` 使用独立端口，例如 `29220 / 29221`。
- Tailscale missing-list 消息使用独立 helper 或独立 API route，不复用当前 Cockpit 加密 TUI 的会话状态。
- 默认 demo 入口继续不启用 USRP ARQ 控制消息，只有显式设置 `RX_CONTROL_HOST / TX_CONTROL_HOST` 或未来的 `USRP_CONTROL_MODE=tailscale-arq` 才进入。
- 控制消息只传 `session_id / file_id / round / missing_chunks / crc_ok_indices` 这类小 JSON，带宽影响可忽略；真正风险是端口冲突和状态机串扰，而不是 Tailscale 流量本身。

因此下一步接 Tailscale 时应先做旁路 helper，不直接改现有 demo 主通讯路径。

### 2. 解码是否需要 C++

可以做，而且值得做。当前 Python 解码已经做过“先解 header 再解 payload”的优化，但批量长测里仍有明显固定成本：

- 每轮都要读取 `rx_capture.sc16`、搜索窗口、解 QPSK、校验 chunk。
- Python/Numpy 对向量计算不一定慢，但当前逻辑包含大量候选遍历、JSON/文件 I/O 和逐 chunk bookkeeping。
- 后续如果部署到飞腾派，C++ 解码更容易控制内存、线程和实时性。

当前已落地：

1. `QpskFileDecode.cpp` 已实现当前固定协议的 C++ CLI：输入 `rx_capture.sc16 + manifest.json`，输出 `decoded_wire_blob.bin + decode_summary.json`。
2. Python 保留 orchestration / merge / batch summary。
3. `RunQpskFileBatchSpoolArq.py` 已支持 `--decode-backend python|cpp` 和 `--cpp-sync-mode header|hybrid|sync`。

模式取舍：

| mode | 定位 | 当前离线结果 |
|---|---|---|
| `hybrid` | 控制变量，对齐旧 Python | `image_0000/round0` 为 `27/33 crc_ok`，约 `5.0 s` |
| `header` | 性能路径，利用控制面 manifest/chunk metadata | 同样本 `33/33 crc_ok`，约 `0.64 s` |
| `sync` | Schmidl-only 实验路径 | 当前不作为推荐入口 |

`header` mode 与最终“双平面”架构一致：控制面可以可靠预共享 manifest、chunk length、CRC 等小元数据，USRP 数据面只承载 payload burst。但它和旧 Python 结果不是严格同一控制变量，下一步应先跑小批量 OTA，不直接启动 300 全量。

小批量 OTA 已验证：`spool_count20_cpp_header_20260427_202642`，`20/20 PASS`，`25.307 s`，`1.265 s/image`，ARQ 分布 `1:9, 2:10, 3:1`，RX timeout/overflow `0/0`。这说明 C++ header-mode 能显著降低当前 batch-spool 的真实 wall，但目录仍有 `841 MB`，全量前必须继续做产物瘦身。

产物瘦身已进入 runner：`--artifact-mode minimal` 默认删除 sc16 中间文件；`--artifact-mode board` 面向板端/TF 卡，只保留 summary/log/manifest。扩大到 300 或上板端前，应默认使用 `minimal` 或 `board`，只有 RF 问题复盘时才用 `full`。

### 3. TVM/MNN 闭环后置

短期不急着接 TVM/MNN。当前顺序应是：

1. 固定 `cpp+header + fast-arq-profile` 软件基线，并先复验 `chunk_bytes=2048`。
2. 接 Tailscale missing-list 控制消息，确认不干扰默认 demo。
3. 再串行扫 `RX gain / rate`，并继续压缩 capture window / batch burst 的固定成本。
4. 再把 `33,534 B quant .npz` 接回 TVM/MNN 重建闭环。

### 4. 300 次长测结果

`batch300_persistent_rxtx_20260427_114323` 已完成：

| 指标 | 值 |
|---|---:|
| 口径 | 同一 `131,231 B` raw-float wire blob 重复 `300` 次 |
| completed / pass / fail | `300 / 300 / 0` |
| final byte / bit errors | `0 / 0` |
| wall mean / min / median / max | `14.264 / 10.842 / 15.475 / 21.410 s` |
| ARQ rounds distribution | `1:104`, `2:181`, `3:15` |
| payload airtime mean | `261.568 ms` |
| effective payload over payload airtime | `4.179 Mbps` |
| effective payload over real wall | `0.074 Mbps` |

判断：

- 当前无线空口 payload 时间已经不是最主要矛盾，真实 wall 主要被 capture window、离线 decode 和逐图串行控制拖住。
- Tailscale missing-list 本身只传小 JSON，不会成为吞吐瓶颈；接入时的重点是状态隔离和端口隔离。
- C++ decode 值得作为下一阶段 P0/P1 之间的工程优化，因为它直接面向后续飞腾派部署。

### 5. Batch-spool smoke 结果

`RunQpskFileBatchSpoolArq.py` 已完成第一版验证：

| 指标 | 值 |
|---|---:|
| 当前安全 profiling | `spool_count20_batch20_workers2_profile_20260427_192735` |
| safe result | `20/20 PASS` |
| safe per image wall | `4.932 s` |
| safe payload airtime mean | `263.710 ms` |
| safe ARQ rounds distribution | `1:4`, `2:16` |
| 当前安全 300 全量 | `spool_count300_batch20_workers2_profile_20260427_193533` |
| safe full-volume result | `300/300 PASS` |
| safe full-volume per image wall | `5.174 s` |
| safe full-volume ARQ rounds distribution | `1:22`, `2:236`, `3:42` |
| 历史最快 smoke | `spool_count20_parallel4_20260427_132542` |
| historical per image wall | `2.910 s` |

判断：

- batch-spool 证明 `14.264 s/image` 不是硬件空口极限，而是逐图 capture/decode 的软件调度成本。
- `decode-workers=2` 安全全量已把 wall 降到 `5.174 s/image`，可作为后续保守预算。
- `decode-workers=4` 并行 decode 从 `~9 s/image` 拉到 `~3 s/image`，说明 Python decode 热路径值得迁到 C++；当前 C++ header-mode 离线单图 decode 约 `0.65 s`。
- `decode-workers=4` 不再作为推荐配置；当前安全边界是 `decode-workers<=2 / batch-size<=20 / 子进程线程数=1`。
- `count=20 / batch-size=20 / decode-workers=2 / --decode-backend cpp --cpp-sync-mode header` 小批量 OTA 已通过，当前 per-image wall 为 `1.265 s`。
- 下一阶段若考虑 300 全量，应先补 checkpoint/resume 和 artifact slimming，避免再次产生过大的中间文件。
- 随后应把 batch-spool 从文件切片过渡到 continuous RX ring/spool，减少 sc16 落盘和重复读取。

### 6. fast-arq + chunk_bytes 当前收口

`round1+` 短窗口已通过：`spool_count20_cpp_header_fastarq_20260427_213839`，`20/20 PASS`，`21.374 s`，`1.069 s/image`，ARQ 分布 `1:13, 2:7`。这说明当前真实 wall 还能继续压，但关键不再是盲目并行，而是减少固定保护开销并提高 round0 一次成功率。

随后已完成 `chunk_bytes` 小范围 sweep。注意在 sweep 前已修正 `RunQpskFileBatchSpoolArq.py merge_image()` 的 `--chunk-bytes` 透传，避免非 `4096` 配置被错误统计。

| chunk_bytes | result | per image wall | ARQ rounds | average rounds | payload airtime mean |
|---|---|---:|---|---:|---:|
| `2048` | `10/10 PASS` | `1.060 s` | `1:10` | `1.0` | `291.717 ms` |
| `4096` | `10/10 PASS` | `1.114 s` | `1:6`, `2:4` | `1.4` | `255.196 ms` |
| `8192` | `10/10 PASS` | `1.417 s` | `1:1`, `2:6`, `3:3` | `2.2` | `263.999 ms` |

当前判断：

1. `2048` 是现阶段最优候选默认值。它的空口 airtime 更长，但 round0 一次成功率最好，真实 wall 最低。
2. `4096` 保留为历史控制组，不再默认假设它是最优点。
3. `8192` 当前不推荐，长 chunk 放大了 retransmission penalty。
4. 真实 OTA sweep 必须串行执行，不再对同一套常驻 RX/TX server 并发发起任务。

## 下一轮实操建议

### A. 短期两小时目标

1. 用 `cpp+header + fast-arq-profile + chunk_bytes=2048` 先做 `count=20` 复验。
2. 保持 `decode-workers=2 / batch-size<=20 / artifact-mode=minimal`，不再启动并发 OTA sweep。
3. 记录：
   - round0 一次成功率
   - ARQ rounds distribution
   - per image wall
   - payload airtime mean
   - run directory size

### B. 当晚目标

1. 若 `2048` 在 `count=20` 仍稳定，再串行扫 `RX gain / rate`，一次只改一个变量。
2. 把 `cpp header-mode` 继续作为默认热路径，不回退到 Python decode 做大批量。
3. 评估 `33,534 B quant .npz` 真实 payload，相比 `131,231 B raw float32` 的 wall 改善幅度。

### C. 第一版“不会阻塞推理”的目标

按 `33,534 B` 计算：

| 目标 | 含义 |
|---|---|
| `<= 250 ms/image` | 无线不比 TVM 慢 |
| `>= 1.1 Mbit/s payload` | 理论最低 |
| `>= 1.5 Mbit/s payload` | 工程最低 |
| `>= 3.0 Mbit/s payload` | 比较像样 |

如果仍要求 bit-exact，这个目标需要：

- 低开销 FEC
- 小窗口 ARQ
- RX 常驻
- TX/RX 流水
- 避免整包重复

如果转向 JSCC-aware，则可以把目标拆成：

- header / metadata bit-exact
- latent quality acceptable
- PSNR/SSIM 达标
- 关键 chunk 必要时补发

## 2026-04-28 latent 图片编解码首轮实验

目的：验证“先把 latent 当图片压缩，再经数据面发送，接收端解压后重建”这条思路是否值得继续推进。这里关注的是**最终重建质量**，而不是 latent 是否 bit-exact。

实验入口：

```bash
/home/zhangzw0170/.venvs/jscc-codec/bin/python scripts/latent_image_codec_experiment.py \
    --input-glob '/tmp/jscc-test-extract/jscc-test/encoder_outputs/*_latent.pt' \
    --jscc-root /tmp/jscc-test-extract/jscc-test \
    --default-config-str 6_6_6_6_6_6_6 \
    --limit 12 \
    --output /tmp/latent_codec_jscc_full.json
```

样本：

- 使用 `jscc-test.zip` 中 `12` 个真实 encoder 输出。
- latent 形状不是固定 `1x32x32x32`，而是 `32xH xW`，例如 `32x54x80`、`32x80x74`、`32x50x38`。
- 评估口径是“图片编解码后的重建结果 vs 原始 latent 重建结果”的 `PSNR / SSIM`。

结果：

| codec | mean encoded bytes | ratio vs quant bytes | exact latent | recon PSNR vs baseline | recon SSIM vs baseline |
|---|---:|---:|---:|---:|---:|
| `png` | `96,430.8 B` | `0.7122` | `12/12` | `inf` | `1.0000` |
| `webp-lossless` | `91,292.7 B` | `0.6729` | `12/12` | `inf` | `1.0000` |
| `jpeg-q95` | `67,612.5 B` | `0.4994` | `0/12` | `50.56 dB` | `0.9984` |
| `jpeg-q85` | `38,464.1 B` | `0.2835` | `0/12` | `39.10 dB` | `0.9808` |
| `jpeg-q75` | `27,608.2 B` | `0.2038` | `0/12` | `33.31 dB` | `0.9428` |

判断：

1. `PNG / WebP lossless` 已经证明“latent 作为图片容器”这条路是可行的，而且在这批真实样本上可以**零质量损失**地把 quant bytes 再压到约 `67% - 71%`。
2. `WebP lossless` 当前优于 `PNG`，可作为后续 source-codec 的首选候选。
3. `JPEG q95` 虽然不是 bit-exact，但平均 `50.56 dB / 0.9984 SSIM` 已经非常高，说明“允许轻微有损，换显著降载”这条路有工程价值。
4. `JPEG q85` 继续把载荷压到原 quant bytes 的 `28.35%`，平均 `39.10 dB / 0.9808 SSIM`，已经接近“看业务是否接受”的决策点。
5. 因此队长提的方向本质上是**源编码优先**：不要只盯着 RF 侧 bit-exact 和 ARQ，把 latent 本身先压小，往往比继续死抠 QPSK 链路时延更划算。

对当前 USRP292x 的意义：

- 当前 `1.031 s/image` 基线仍然是“raw-float 压力包 + QPSK + ARQ”口径，不代表真实 JSCC 业务载荷必须这么重。
- 如果后续业务侧确认可以接受 `lossless WebP` 或高质量 `JPEG`，无线数据面的字节压力会显著下降，真实 wall 还有继续压缩空间。
- 这类优化不会替代现有 QPSK/ARQ baseline；它是 baseline 之上的 payload slimming。

下一步建议：

1. 用真实 `1x32x32x32` 业务 latent 再做一轮同样实验，确认这批 `jscc-test.zip` 结果不是特例。
   该项已在下一节通过 `finalWork.zip` 完成复验。
2. 优先评估 `WebP lossless` 和 `JPEG q95/q85` 三档。
3. 若业务允许有损，不再把“latent bit-exact”作为唯一成功标准，而是改成 `PSNR / SSIM / 任务效果` 联合判定。

## 2026-04-28 `finalWork.zip` 业务口径复验

`finalWork.zip` 不是零散素材，而是一套更接近交付形态的 JSCC 包：

- 客户端侧：`finalWork/客户端/jscc-test/encoder_outputs/*.pt`
- 服务端侧：`finalWork/服务端/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- 模型权重：`finalWork/*/jscc-test/export/compressed_gan.pt`

其中客户端的 `5` 个 latent 样本都是真实 `32x32x32`、单文件 `34,798 B`，并带有：

- `quant: uint8[32,32,32]`
- `config_str: 6_6_6_6_6_6_6`
- 不同的 `scale / zero_point`

这组数据比上一节的“变尺寸 encoder 输出”更贴近我们当前 `1x32x32x32` 数据面目标，因此更适合作为后续 payload slimming 的第一组验收样本。

实验入口：

```bash
/home/zhangzw0170/.venvs/jscc-codec/bin/python scripts/latent_image_codec_experiment.py \
    --input-glob '/tmp/finalWork_extract/finalWork/客户端/jscc-test/encoder_outputs/*_latent.pt' \
    --jscc-root /tmp/jscc-test-extract/jscc-test \
    --default-config-str 6_6_6_6_6_6_6 \
    --limit 5 \
    --output /tmp/latent_codec_finalwork.json
```

结果：

| codec | mean encoded bytes | ratio vs quant bytes | ratio vs raw float32 | exact latent | recon PSNR vs baseline | recon SSIM vs baseline |
|---|---:|---:|---:|---:|---:|---:|
| `png` | `24,360.8 B` | `0.7434` | `0.1859` | `5/5` | `inf` | `1.0000` |
| `webp-lossless` | `23,478.8 B` | `0.7165` | `0.1791` | `5/5` | `inf` | `1.0000` |
| `jpeg-q95` | `18,138.8 B` | `0.5536` | `0.1384` | `0/5` | `49.63 dB` | `0.9986` |
| `jpeg-q85` | `10,866.0 B` | `0.3316` | `0.0829` | `0/5` | `38.19 dB` | `0.9829` |
| `jpeg-q75` | `8,102.0 B` | `0.2473` | `0.0618` | `0/5` | `32.61 dB` | `0.9512` |

结论更新：

1. 上一节“latent 可当图片压缩”的判断不是偶然值；在真实 `32x32x32` 业务口径上同样成立。
2. `WebP lossless` 现在已经是最稳妥的第一候选：
   - 对 quant latent 完全无损；
   - 平均从 `32,768 B` 压到 `23,478.8 B`；
   - 相比 `131,072 B raw float32`，只剩约 `17.9%` 的字节量。
3. `JPEG q95` 是有损方案中的强候选：平均 `18.1 KB`，但重建仍有 `49.63 dB / 0.9986 SSIM`。
4. 因此下一步工程重点不该只是“继续抠 RF 参数”，而应并行推进一个**可开关的 source-codec shim**：
   - 默认 `WebP lossless`
   - 可选 `JPEG q95`
   - 保持现有 USRP 文件接口不变，只在输入/输出两侧加 encode/decode

新的近期顺序：

1. 保持当前 `QPSK + ARQ` 基线不动，作为数字兼容 transport。
2. 先把 `quant latent -> WebP lossless -> OTA -> WebP decode -> decoder` 这条链打通。
3. 再评估 `JPEG q95` 是否值得作为“更低载荷但轻微有损”的第二档模式。
4. 若这条线成立，后续再决定是否继续推进 `UEP / pseudo-analog / DeepJSCC-native IQ`。

### 2026-04-28 工程落地状态

当前 host/board 脚本已补齐第一版 source-codec shim：

1. 新增 `scripts/latent_transport.py`，统一承载
   - `float32-raw`
   - `webp-lossless`
   两种 payload codec，并保持 wire frame 仍为 `[4B meta_len][meta JSON][payload bytes]`。
2. `scripts/tcp_client.py`、`scripts/tcp_server.py`、`scripts/usrp_send.py`、`scripts/usrp_board_recv.py` 已接入 `payload_codec` 元数据。
3. 板端 TVM 入口现在既可直接吃 `latent=np.float32`，也可吃 `quant/scale/zero_point` 的 `.npz`，因此 `webp-lossless` 解包后无需再改 TVM helper。
4. 本地回归已通过：
   - `float32-raw` roundtrip
   - `webp-lossless` roundtrip
   - `webp-lossless` 在关闭 latent sha 校验时的尽力恢复路径

这意味着下一步不再是“先写协议”，而是直接把真实 `quant latent` 生成为 wire blob，然后接到现有 `RunQpskFileBatchSpoolArq.py` / persistent RX/TX 主线验证真实 wall。

### 2026-04-28 `finalWork` 真实 payload 300 张 OTA

本轮没有再用 `131 KB raw float32` 压力包，而是把 `finalWork.zip` 中 `5` 个真实 `32x32x32` quant latent 打成 `webp-lossless` wire blob，再循环到 `300` 张：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --input-dir USRP292x/payloads/finalwork_webp5 \
    --pattern '*.bin' \
    --cycle-inputs \
    --count 300 \
    --batch-size 20 \
    --decode-workers 2 \
    --decode-backend cpp \
    --cpp-sync-mode header \
    --artifact-mode minimal \
    --fast-arq-profile \
    --chunk-bytes 2048
```

run：

```text
USRP292x/qpsk_batch_spool_arq_runs/spool_count300_finalwork_webp5_cpp_header_inline_merge_20260428
```

结果：

| 指标 | 值 |
|---|---:|
| result | `300/300 PASS` |
| all_pass | `true` |
| elapsed / per image | `150.725 s / 0.502 s` |
| ARQ rounds distribution | `1:300` |
| average rounds | `1.0` |
| payload airtime mean / median | `53.585 / 55.938 ms` |
| wire blob size range | `21,657 - 25,763 B` |
| wire blob mean | `24,005 B` |
| decode / merge / other mean | `370.0 / 1.7 / 77.1 ms` |
| run directory size | `28 MB` |

分样本 airtime：

| payload | blob bytes | airtime mean |
|---|---:|---:|
| `00000208` | `22,212 B` | `49.203 ms` |
| `00000209` | `24,845 B` | `55.938 ms` |
| `00000210` | `21,657 B` | `48.315 ms` |
| `00000211` | `25,548 B` | `57.062 ms` |
| `00000212` | `25,763 B` | `57.406 ms` |

与上一版 `131 KB raw float32` 的 `300` 张默认基线 `spool_count300_cpp_header_fastarq_chunk2048_20260427_220219` 相比：

| 指标 | raw float32 | `finalWork + webp-lossless` |
|---|---:|---:|
| per image wall | `1.031 s` | `0.502 s` |
| payload airtime mean | `291.717 ms` | `53.585 ms` |
| wall speedup | `1.0x` | `2.05x` |
| airtime reduction | `0%` | `81.6%` |

结论：

1. `WebP lossless` 不只是离线压缩实验有效，已经在真实 OTA batch runner 上完成 `300/300` 验证。
2. 当前 `0.502 s/image` 已显著优于此前 `raw float32` 口径，说明近期主要收益来自 payload 收缩，再叠加板端 `no-slice decode + inline merge` 优化。
3. 后续若继续追求速度，优先级应是：
   - 接入更多真实 latent 样本；
   - 若业务允许，再评估 `JPEG q95`；
   - 最后再考虑更激进的 PHY/协议改动。

### 如何理解 `9.53 s -> 0.502 s`

这个数字跨度很大，但**不是“单靠换设备”或“单靠压缩”得到的单变量提升**。更准确的分解如下：

| 阶段 | 日期 | 口径 | 单图 wall |
|---|---|---|---:|
| B205mini 历史 fallback | `2026-04-23` | `33KB latent` + `continuous rx_spool` | `~9.53 s` |
| USRP-2922 新主线（未做 source-codec） | `2026-04-27` | `131KB raw float32` + `batch-spool + cpp/header + fast-arq + chunk2048` | `1.031 s` |
| USRP-2922 新主线 + 真实业务 payload | `2026-04-28` | `finalWork + webp-lossless`，均值 `24KB` | `0.574 s` |
| USRP-2922 新主线 + 板端去切片/去 merge 子进程 | `2026-04-28` | `finalWork + webp-lossless + no-slice decode + inline merge` | `0.502 s` |

因此应把收益拆成三段理解：

1. `9.53 -> 1.031 s`
   - 主要来自链路组织和实现重写：
   - `persistent RX/TX`
   - `batch-spool`
   - `C++ header decode`
   - `fast-arq-profile`
   - `chunk_bytes=2048`
   - `300/300 round0 PASS`
2. `1.031 -> 0.574 s`
   - 主要来自 payload 收缩：
   - `131 KB raw float32`
   - 变为 `~24 KB webp-lossless` 真实业务 wire blob
3. `0.574 -> 0.502 s`
   - 主要来自板端 I/O/merge 收口：
   - `decode` 直接从 `batch_rx.sc16` 按 sample range 读取，不再写 `rx_slice.sc16`
   - `merge` 改为 runner 进程内完成，不再为每张图额外起一个 Python 子进程
   - 实测 `merge` 均值从 `74.3 ms/image` 降到 `1.7 ms/image`

对外表述时，推荐写成：

> `2026-04-23` 的 `~9.53 s/image` 到 `2026-04-28` 的 `0.502 s/image`，是 “USRP-2922 + persistent/batch 链路 + C++ decode + fast ARQ + WebP lossless payload slimming + 板端 no-slice/inline-merge 优化” 共同叠加的结果，不是单靠换设备。

### 当前链路的理论下界（工程口径）

如果问题不是“香农极限”，而是“当前这套 `USRP-2922 + QPSK + batch-spool` 工程链路还能压到哪”，可以把下界拆成 4 层：

| 层级 | 含义 | 估计值 |
|---|---|---:|
| 裸 PHY 下界 | `5 Msps`、`sps=2`、uncoded QPSK、均值 `24,005 B` wire blob 直接上空口 | `38.4 ms/image` |
| 当前帧结构下界 | 加上现有 sync/header/chunk framing 后的真实 payload airtime | `53.6 ms/image` |
| 当前 round0 RF 下界 | 再加 `warmup + tail + batch gap + tx_delay + rx_tail` | `218.6 ms/image` |
| 当前实现 wall | 本轮 `300/300` 实测 | `502.4 ms/image` |

由此可得：

1. 当前 `0.502 s/image` 中，**真正的 payload airtime 只有约 `53.6 ms`**。
2. 即便不改 payload，只看当前 round0 保护参数，RF floor 也大约是 `218.6 ms/image`。
3. 当前 `300/300` 实测分项均值已经比较清楚：
   - `decode_total_wall_sec_mean ~= 370.0 ms/image`
   - `merge_wall_sec_mean ~= 1.7 ms/image`
   - `estimated_non_airtime_non_decode_non_merge ~= 77.1 ms/image`
4. 这说明此前的切片 I/O 和逐图 merge 子进程已经基本被压平，**decode 才是当前板端主瓶颈**。

这意味着：

- 只靠继续扫 `rate/gain/chunk_bytes` 这类参数，现实目标大约是 `0.45 - 0.50 s/image`。
- 若想稳定压到 `0.40 s/image` 甚至更低，主要矛盾已经不是 RF，而是**板端/解码侧实现**。

### 板端优先级

既然 payload airtime 已经只剩几十毫秒，下一阶段的优化重点应该明确转到板端：

1. `QpskFileDecode.cpp` 继续作为默认热路径，不回退 Python decode。
2. `rx_slice.sc16` 和逐图 `merge` 子进程已经去掉；下一步若还要压时间，应优先优化 `QpskFileDecode.cpp` 本体或把 decode 常驻化。
3. 默认使用 `artifact-mode board|minimal`，避免 TF 卡 / 板端磁盘被中间产物拖慢。
4. 若后续接飞腾板，先优化 decode / merge / bookkeeping，再考虑更激进的 RF 参数。

一句话：**当前链路再往下压，板端性能比 RF 扫参更重要。**

## 参考资料

- NI USRP-2922 Specifications: <https://download.ni.com/support/manuals/375868c.pdf>
- Ettus USRP2 / N2x0 Manual: <https://files.ettus.com/manual/page_usrp2.html>
- Ettus Bandwidths and Sampling Rates: <https://kb.ettus.com/About_USRP_Bandwidths_and_Sampling_Rates>
- Deep Joint Source-Channel Coding for Wireless Image Transmission: <https://arxiv.org/abs/1809.01733>
- Deep Joint Source Channel Coding for Wireless Image Transmission with OFDM: <https://arxiv.org/abs/2101.03909>
- OFDM-guided Deep Joint Source Channel Coding for Wireless Multipath Fading Channels: <https://arxiv.org/abs/2109.05194>
- Entropy-Aware Adaptive Rate Control DeepJSCC: <https://arxiv.org/abs/2306.02825>
