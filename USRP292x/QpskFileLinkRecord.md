# USRP-2922 QPSK 文件链路快测记录

更新时间：2026-04-27

## 目的

这条链路不是最终 PHY，而是为了快速回答：

```text
1x32x32x32 raw float32 wire blob 是否有机会在 250-350 ms 量级传完？
```

当前控制面仍计划走 Tailscale；USRP 只承担数据面。后续可靠性不做整包 blind repeat，改用 chunk CRC + Tailscale selective ARQ。

## 术语

- `IQ rate` 基本等价于 UHD `rate` / complex sample rate / `Sps`。
- `IQ rate` 不是 payload bit rate。
- 当前 QPSK 快测按 `2 samples/symbol` 估算：

```text
5 MSps / 2 = 2.5 Msymbol/s
QPSK = 2 bit/symbol
ideal raw bit rate ~= 5 Mbps
```

## 输入 payload

使用现有历史 latent：

```text
artifacts/usrp_latent_demo_live/20260425_210417/assets/source_latent.npz
```

该文件内部是：

| 字段 | shape | dtype |
|---|---|---|
| `quant` | `(1, 32, 32, 32)` | `int8` |
| `scale` | `()` | `float32` |
| `zero_point` | `()` | `float32` |

按当前 fallback 口径反量化成 raw float32 后：

| 项目 | 值 |
|---|---:|
| raw float32 payload | `131,072 B` |
| packed wire blob | `131,231 B` |
| metadata | `155 B` |
| sha256(raw payload) | `fa43239bcee7b97ca62f007cc68487560a39e19f74f3dde7486db3f98df8e471` |

## 当前快测 PHY

文件：

- `QpskFileLink.py`
- `RunQpskFileOta.sh`
- `RunQpskFileArqOta.sh`

当前特性：

| 项目 | 状态 |
|---|---|
| 调制 | QPSK |
| chunk | `4096 B`，共 `33` 个 chunk |
| samples/symbol | `2` |
| FEC | 无 |
| ARQ | selective ARQ 本机文件接口已通过，Tailscale 控制面待接 |
| payload repeat | 无 |
| warmup | 可选，当前测试用 `50 ms` random QPSK |
| tail guard | 当前测试用 `50 ms` zero samples，避免 burst EOB 截尾 |
| chunk header | `QFCK / version / flags / seq / total / payload_len / total_len / crc32`，`20 B` |
| 校验 | per-chunk `CRC32` + 离线对比 reference |

当前快测链路没有 FEC/ARQ，不能作为最终协议；它只用于估算吞吐、验证 chunk framing，并给后续 Tailscale ARQ 提供 `missing_chunks` 接口。

## 这不是最终 DeepJSCC PHY

这条 QPSK 链路的定位必须写死：

- 它是当前截止日前的“数字兼容 baseline”。
- 它的输入是当前 fallback 数据面可稳定拿到的 `1x32x32x32 float32 wire blob`。
- 它不是对“DeepJSCC 最终应该走 QPSK”这一命题的背书。

当前仓库实际口径：

- `scripts/tcp_client.py` 会把 `.npz` 中的 `quant/scale/zero_point` 先反量化成 `float32 latent`，再按 `4B meta_len + meta JSON + latent bytes` 打包发送。
- `scripts/tvm_inference_helper.py` 当前接收的也是 `float32 latent`，并在该张量上施加 AWGN 后送入 TVM decoder。
- 因此，当前 USRP292x QPSK 压力测试验证的是“现有 raw-float latent wire format 能否在 USRP 上稳定、较快地传完”，不是“DeepJSCC 原生 complex symbol 已打通”。

如果后续拿到真正的 DeepJSCC complex symbol 输出，正确方向应是：

```text
DeepJSCC encoder -> continuous complex symbols -> framing/pilot/sync
-> USRP complex IQ -> OTA -> sync/CFO/channel estimate
-> recovered complex symbols -> DeepJSCC decoder
```

那时需要新的一条 PHY，而不是把这些 complex symbol 先强行 bit 化再塞回 QPSK。

## 理论时间

`5 MSps / QPSK / 2 samples/symbol / 131,231 B`：

| 项目 | 值 |
|---|---:|
| payload waveform samples | `1,257,880` |
| payload-only airtime | `251.576 ms` |
| warmup samples | `250,000` |
| tail guard samples | `250,000` |
| warmup + payload + tail airtime | `351.576 ms` |
| detected payload airtime | `251.371 ms` |
| effective payload | `4.176 Mbps` |

## 实测摘要

所有 OTA 测试均为 `.2 TX -> .22 RX`，`500 MHz`，`TX/RX -> RX2`，距离约 `1 m`。

| 测试 | 采样率 | TX/RX gain | 结果 |
|---|---:|---|---|
| 本地无信道自测 | `5 MSps` | N/A | `33/33 chunks exact`, `BER=0` |
| OTA 无 warmup，重解最佳窗口 | `5 MSps` | `25 / 20` | `23/33 chunks exact`, `BER≈0.196`, `effective≈4.28 Mbps` |
| OTA 加 `50 ms` warmup | `5 MSps` | `25 / 20` | `17/33 chunks exact`, `BER≈0.233`, `effective≈4.35 Mbps` |
| OTA 加 `50 ms` warmup | `5 MSps` | `25 / 15` | `16/33 chunks exact`, 部分 chunk 仅少量 bit 错 |
| OTA 加 `50 ms` warmup | `2.5 MSps` | `25 / 15` | `15/33 chunks exact`, `effective≈2.11 Mbps` |
| 加 header/CRC 后旧捕获重解 | `5 MSps` | `25 / 15` | `25/33 crc_ok`, `missing_chunks=[25..32]`，判断为 burst 尾部截断 |
| 加 header/CRC + direct-sync + `50 ms` tail guard | `5 MSps` | `25 / 15` | `33/33 crc_ok`, `BER=0`, `effective=4.176 Mbps` |
| 同口径复测 1 | `5 MSps` | `25 / 15` | `31/33 crc_ok`, `missing_chunks=[11,21]` |
| 同口径复测 2 | `5 MSps` | `25 / 15` | `33/33 crc_ok`, `BER=0` |
| 本机 selective ARQ smoke | `5 MSps` | `25 / 15` | round0 `29/33`，round1 只重发 `[2,11,20,29]` 后 merge `33/33`, `byte_errors=0` |

UHD 日志口径：

| 项目 | 结果 |
|---|---|
| TX underrun | `0` |
| RX overflow | `0` |
| RX timeout | `0` |
| socket buffer warning | 已按 `5 MSps` 长测调整，`wmem_max=4194304` |

最新成功 run：

```text
USRP292x/qpsk_runs/tail_5m_qpsk_raw131k_rx15
```

最新 ARQ run：

```text
USRP292x/qpsk_arq_runs/arq_5m_qpsk_raw131k_rx15
```

关键输出：

```text
chunk_exact=33/33
header_valid=33/33
crc_ok=33/33
missing_chunks=[]
ber=0
detected_airtime_ms=251.371
effective_payload_mbps=4.176
```

ARQ 关键输出：

```text
round0 missing_chunks=[2, 11, 20, 29]
round1 transmitted_chunks=[2, 11, 20, 29]
round1 crc_ok=4/4
merge crc_ok=33/33
merge byte_errors=0
arq_result=PASS
```

结论：

- `131,231 B` wire blob 已经在两台 NI USRP-2922 OTA 上完成多次快测，其中 `2/3` 次 `33/33` chunk byte-exact，`1/3` 次缺 `2` 个 chunk。
- 当前成功口径不依赖 FEC 或 payload repeat；可靠性来自 per-chunk header/CRC、direct-sync 重捕获、TX tail guard，以及选择性重传缺失 chunk。
- 旧 `0/33` 主要是接收端误锁；旧 `25/33` 后 8 个 chunk 丢失主要是 burst 尾部保护不足。
- 本机脚本已经验证 selective ARQ 文件接口：首轮缺失列表可驱动下一轮只发失败 chunk，merge 后恢复完整文件。
- 这还不是最终 Tailscale 集成协议；下一步要把 `missing_chunks` 从本机文件接口接到控制面消息。
- 这也不是最终 DeepJSCC-native PHY；当前 QPSK 结果只能说明“现有 raw-float latent wire blob 可以先用数字链路做稳定 baseline”。

## 2026-04-27 解码优化与 TUI 进展

飞腾派后续部署需要降低 Python 解码端的无效计算。当前已把 `decode_one_frame`
从“每个候选直接解完整 payload”改为“先解 `20 B` chunk header，只有 header
合法且属于当前期望 chunk 时才解完整 payload”。该改动不改变 PHY 和空口格式。

同一份已保存 OTA 抓包回归：

| 项目 | 优化前 | 优化后 |
|---|---:|---:|
| round0 decode wall time | `12.22 s` | `8.39 s` |
| round0 `crc_ok` | `29/33` | `29/33` |
| round0 `missing_chunks` | `[2,11,20,29]` | `[2,11,20,29]` |
| round1 `crc_ok` | `4/4` | `4/4` |
| merge | `byte_errors=0`, `exact=true` | `byte_errors=0`, `exact=true` |

TUI 接入：

```bash
./tui_start.sh --usrp --smoke
./tui_start.sh --usrp --dry-run --count 3 --run-id tui_dryrun_check
```

结果：

| 检查项 | 结果 |
|---|---|
| USRP TUI 入口 | `USRP292x/UsrpTui.py` |
| `tui_start.sh --usrp --smoke` | PASS |
| `tui_start.sh --usrp --dry-run --count 3` | PASS |
| 默认加密 TUI 入口 | 未改，仍走 `encrypt_tui_start.sh` |

300 次常驻 RX/TX 长测已完成。主机发送缓冲已调整为：

```bash
sudo sysctl -w net.core.wmem_max=4194304
```

当前观测值为 `net.core.wmem_max=4194304`，满足 UHD 对 `5 MSps` 数据面的
`2500000 bytes` 建议值。

## 2026-04-27 300 次常驻 RX/TX 长测

口径：同一份 `131,231 B` raw-float wire blob 重复发送 `300` 次，用于验证链路稳定性；不是 `300` 个不同 latent 样本。

run：

```text
USRP292x/qpsk_batch_arq_runs/batch300_persistent_rxtx_20260427_114323/batch_summary.json
```

参数：

| 项目 | 值 |
|---|---:|
| 设备方向 | `.2 TX -> .22 RX` |
| center frequency | `500 MHz` |
| rate | `5 MSps` |
| modulation | `QPSK` |
| samples/symbol | `2` |
| TX gain | `25 dB` |
| RX gain | `15 dB` |
| RX antenna | `RX2` |
| payload | `131,231 B` wire blob |
| chunk | `4096 B x 33` |
| payload FEC | 无 |
| payload repeat | 无 |
| ARQ | selective ARQ，最多 `2` 轮重传 |

最终结果：

| 指标 | 值 |
|---|---:|
| completed / pass / fail | `300 / 300 / 0` |
| all_pass | `true` |
| final byte_errors / bit_errors | `0 / 0` |
| elapsed | `4280.660 s` |
| total wall | `4279.181 s` |
| wall mean / min / median / max | `14.264 / 10.842 / 15.475 / 21.410 s` |
| ARQ rounds distribution | `1 round: 104`, `2 rounds: 181`, `3 rounds: 15` |
| average rounds | `1.703` |
| payload airtime total / mean | `78.470 s / 261.568 ms` |
| payload airtime min / median / max | `251.371 / 258.981 / 321.291 ms` |
| effective payload over payload airtime | `4.179 Mbps` |
| effective payload over real wall | `0.074 Mbps` |

首轮质量：

| 指标 | 值 |
|---|---:|
| round0 `crc_ok` mean / min / median / max | `31.730 / 25 / 32 / 33` |
| round0 missing chunks mean / min / median / max | `1.270 / 0 / 1 / 8` |
| round0 missing chunks distribution | `{0:104, 1:100, 2:54, 3:14, 4:17, 5:6, 6:3, 7:1, 8:1}` |

结论：

- 当前 QPSK + CRC + selective ARQ 已经完成 `300/300` bit-exact 恢复。
- `payload-only` 空口时间均值约 `261.568 ms`，已经接近 TVM/MNN 单图推理量级。
- 真实 wall 均值仍为 `14.264 s/image`，瓶颈主要是固定 capture window、离线 Python decode 和每图多轮串行控制。
- 后续不要通过增加整包 repeat 或 payload 全量强 FEC 解决；应优先做短窗口、batch burst/spool 和 C++ decode。

## 2026-04-27 Batch RX Spool 与并行 Decode

新增入口：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --count <N> \
    --max-arq-rounds 2 \
    --batch-size 20 \
    --decode-workers 2 \
    --decode-backend cpp \
    --cpp-sync-mode header \
    --artifact-mode minimal
```

当前实现：

- 每个 ARQ round 把待发送图片按 `--batch-size` 切成若干批，每批拼成一个 `batch_tx.sc16`。
- RX 对每个 batch 用一次 `batch_rx.sc16` capture 覆盖。
- 按发送时间表切出 per-image `rx_slice.sc16`。
- 每张图继续复用 `QpskFileLink.py decode` 和 `merge`。
- ARQ round 只把失败图的 missing chunks 重新拼成下一轮 batch。
- `--decode-workers` 使用多个子进程并行跑 per-image decode，但当前脚本硬限制为 `<=2`。
- `--batch-size` 当前脚本硬限制为 `<=20`。
- 解码子进程会强制 `OMP_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`、`MKL_NUM_THREADS=1`、`NUMEXPR_NUM_THREADS=1`、`VECLIB_MAXIMUM_THREADS=1`。
- 默认 `--artifact-mode minimal` 会自动删除 `batch_tx.sc16`、`batch_rx.sc16`、`tx_qpsk.sc16` 和 `rx_slice.sc16`；需要完整 RF 留证时显式使用 `--artifact-mode full`。

实测仍是同一 `131,231 B` wire blob 重复发送，用于链路和调度压力测试。

| run | count | decode workers | result | elapsed | per image |
|---|---:|---:|---|---:|---:|
| `spool_count3_smoke_20260427_132130` | `3` | `1` | `3/3 PASS` | `26.754 s` | `8.918 s` |
| `spool_count10_smoke_20260427_132219` | `10` | `1` | `10/10 PASS` | `89.784 s` | `8.978 s` |
| `spool_count10_parallel4_20260427_132436` | `10` | `4` | `10/10 PASS` | `33.602 s` | `3.360 s` |
| `spool_count20_parallel4_20260427_132542` | `20` | `4` | `20/20 PASS` | `58.209 s` | `2.910 s` |
| `spool_count20_batch20_workers2_profile_20260427_192735` | `20` | `2` | `20/20 PASS` | `98.640 s` | `4.932 s` |
| `spool_count300_batch20_workers2_profile_20260427_193533` | `300` | `2` | `300/300 PASS` | `1552.168 s` | `5.174 s` |

注意：`decode-workers=4` 是历史 smoke 数据，不再推荐复现。扩展到 `300` 张时它会带来过高 I/O/CPU 压力，并干扰 SSH/Tailscale 操作稳定性。

`spool_count20_batch20_workers2_profile_20260427_192735` 是当前安全边界内的 profiling 口径：

| 指标 | 值 |
|---|---:|
| result | `20/20 PASS` |
| elapsed / per image | `98.640 s / 4.932 s` |
| ARQ rounds distribution | `1 round: 4`, `2 rounds: 16` |
| payload airtime mean | `263.710 ms` |
| round0 active / wall | `20 / 85.520 s` |
| round0 RX duration / TX send wall | `8.332 s / 7.968 s` |
| round0 decode wall | `73.387 s` |
| round0 merge wall | `1.559 s` |
| round1 active / wall | `16 / 13.103 s` |
| round1 decode wall | `7.468 s` |

判断：在 `decode-workers<=2` 的安全约束下，batch-spool 已从逐图常驻 RX/TX 的 `14.264 s/image` 降到 `4.932 s/image`。瓶颈仍主要是 `QpskFileLink.py decode`，不是空口 payload airtime。

`spool_count300_batch20_workers2_profile_20260427_193533` 是当前最可信的安全全量口径：

| 指标 | 值 |
|---|---:|
| result | `300/300 PASS` |
| elapsed / per image | `1552.168 s / 5.174 s` |
| final byte / bit errors | `0 / 0` |
| image ARQ rounds distribution | `1:22`, `2:236`, `3:42` |
| payload airtime mean / median | `269.334 / 266.795 ms` |
| round0 active / batches / wall | `300 / 15 / 1282.220 s` |
| round1 active / batches / wall | `278 / 14 / 239.665 s` |
| round2 active / batches / wall | `42 / 3 / 29.916 s` |
| round0 decode wall sum | `1101.081 s` |
| round1 decode wall sum | `141.610 s` |
| round2 decode wall sum | `15.357 s` |

判断：batch-spool 在安全 `2-worker` 约束下，相比逐图常驻 RX/TX 的 `14.264 s/image` 提升到 `5.174 s/image`。全量结果仍显示 round0 一次成功率偏低，且 decode wall 是主要瓶颈。

`spool_count20_parallel4_20260427_132542`：

| 指标 | 值 |
|---|---:|
| round0 / round1 / round2 active images | `20 / 9 / 1` |
| ARQ rounds distribution | `1 round: 11`, `2 rounds: 8`, `3 rounds: 1` |
| round0 RX capture wall | `8.332 s` |
| round0 TX send wall | `7.938 s` |
| payload airtime mean | `256.348 ms` |
| RX timeout / overflow | `0 / 0` |

对比：

| 方案 | 口径 | per image |
|---|---|---:|
| 常驻 RX/TX，逐图 capture/decode | `batch300_persistent_rxtx_20260427_114323` | `14.264 s` |
| batch-spool，串行 decode | `spool_count10_smoke_20260427_132219` | `8.978 s` |
| batch-spool，安全 2-worker profiling | `spool_count20_batch20_workers2_profile_20260427_192735` | `4.932 s` |
| batch-spool，安全 2-worker 300 全量 | `spool_count300_batch20_workers2_profile_20260427_193533` | `5.174 s` |
| batch-spool，并行 decode 历史探针 | `spool_count20_parallel4_20260427_132542` | `2.910 s` |

结论：batch-spool 已验证“多图共享 RX capture + selective ARQ”可行；并行 decode 进一步证明当前 Python 离线 decode 是主要 wall 瓶颈之一。但 `parallel4` 不满足当前资源约束，后续默认按 `decode-workers<=2 / batch-size<=20` 执行。

300 张 batch-spool 失败/中止记录：

| run | 问题 |
|---|---|
| `spool_count300_parallel4_20260427_142238` | 单次 capture 太长，触发 N210/UHD `num_samps` 限制 |
| `spool_count300_batch100_parallel4_20260427_142544` | batch 仍过大，RX server capture deadline 不足 |
| `spool_count300_batch50_parallel4_20260427_143603` | 资源压力过高，用户中止；后续禁止 `decode-workers=4` 全量运行 |

## 2026-04-27 C++ 解码器离线验证

这里的“解码”不是 FEC 解码。当前空口没有 Viterbi / RS / LDPC；C++ 解码器做的是：

```text
sc16 IQ -> frame search -> QPSK hard decision -> QFCK chunk header parse -> CRC32 -> missing_chunks
```

新增文件：

- `QpskFileDecode.cpp`：当前固定 QPSK chunk 协议的 C++ 解码 CLI。
- `BuildOtaTools.sh`：已加入 `QpskFileDecode` 构建。
- `RunQpskFileBatchSpoolArq.py`：新增 `--decode-backend python|cpp` 和 `--cpp-sync-mode header|hybrid|sync`。

模式口径：

| mode | 用途 | 说明 |
|---|---|---|
| `hybrid` | 对齐旧 Python 结果 | 使用训练同步 + header 候选 fallback，适合做控制变量回归 |
| `header` | 性能路径 | 使用控制面可预共享的 manifest/chunk header 元数据做 header pilot，速度最快 |
| `sync` | 实验路径 | 只用重复训练段粗同步；当前不作为推荐入口 |

离线 smoke 使用已有 300-run 的 `image_0000/round0/rx_slice.sc16`：

| decoder | 结果 | wall |
|---|---:|---:|
| Python `QpskFileLink.py decode` | `27/33 crc_ok` | `7.341 s` |
| C++ `--sync-mode hybrid` | `27/33 crc_ok` | `4.9-5.0 s` |
| C++ `--sync-mode header` | `33/33 crc_ok` | `0.64 s` |

前 `8` 张 round0 离线 header-mode 扫描：

| 指标 | 值 |
|---|---:|
| wall mean / min / max | `0.650 / 0.642 / 0.665 s` |
| full-pass images | `5/8` |
| 与 Python 相比 | 多数 chunk CRC 数提升，少数图片 missing 集合不同 |

判断：

- 若要求与旧 Python 指标严格可比，使用 `--cpp-sync-mode hybrid`，预计单图 decode 只提升约 `1.4-1.6x`。
- 若接受“控制面预共享 manifest，header 作为 pilot”的协议假设，使用 `--cpp-sync-mode header`，当前样本 decode command 约 `11x` 加速。
- 端到端不会等比例加速，因为仍有 RX capture、TX send、ARQ round 和文件 I/O；按现有 `round0 decode wall sum=1101.081 s` 粗估，header-mode 若不恶化 ARQ，有机会把全量 `5.174 s/image` 压到约 `1.5-2.5 s/image`，需要下一轮小批量 OTA 实测确认。

### C++ header-mode `count=20` OTA 小批量

run：

```text
USRP292x/qpsk_batch_spool_arq_runs/spool_count20_cpp_header_20260427_202642/batch_spool_summary.json
```

命令口径：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
  --count 20 \
  --batch-size 20 \
  --decode-workers 2 \
  --decode-backend cpp \
  --cpp-sync-mode header \
  --max-arq-rounds 2 \
  --run-id spool_count20_cpp_header_20260427_202642
```

结果：

| 指标 | 值 |
|---|---:|
| result | `20/20 PASS` |
| elapsed / per image | `25.307 s / 1.265 s` |
| final byte / bit errors | `0 / 0` |
| ARQ rounds distribution | `1:9`, `2:10`, `3:1` |
| payload airtime mean / median | `255.937 / 258.981 ms` |
| round0 active / wall / decode wall | `20 / 18.724 s / 6.558 s` |
| round1 active / wall / decode wall | `11 / 5.622 s / 1.716 s` |
| round2 active / wall / decode wall | `1 / 0.940 s / 0.288 s` |
| RX timeout / overflow | `0 / 0` |
| run directory size | `841 MB` |

判断：

- C++ header-mode 小批量比 Python safe 2-worker profiling 的 `4.932 s/image` 快约 `3.9x`。
- 相比安全 300 全量 `5.174 s/image`，当前小批量口径快约 `4.1x`；但这还不能直接外推到 300，全量前仍应补 checkpoint/resume 或 artifact slimming。
- 空口 payload airtime 仍在 `~256 ms/image`，主要剩余开销是 batch capture、TX send、ARQ 轮次、merge 和大文件落盘。
- 本轮目录 `841 MB` 是旧 full-like 产物口径；当前 runner 默认已切到 `artifact-mode=minimal`，后续会删除 sc16 大文件，避免 20 张接近 1GB。
- `spool_count1_cpp_header_minimal_20260427_203622` 已验证 minimal 模式：`1/1 PASS`，目录 `664 KB`，自动删除 sc16 `57.551 MB`。

### Demo/TUI 入口更新

`tui_start.sh --usrp` 已更新到当前 USRP292x batch-spool 路线：

| 项目 | 当前默认 |
|---|---|
| runner | `RunQpskFileBatchSpoolArq.py` |
| decode backend | `cpp` |
| C++ mode | `header` |
| artifact mode | `minimal` |
| batch size / decode workers | `20 / 2` |

常驻 RX/TX 可直接从 demo 启停：

```bash
./tui_start.sh --usrp --start-persistent-rxtx
./tui_start.sh --usrp --persistent-status
./tui_start.sh --usrp --stop-persistent-rxtx
```

交互 TUI 中也有 `Start Persistent RX/TX`、`Persistent Status`、`Stop Persistent RX/TX` 按钮，避免再手敲 `OtaRxPersistentServer.sh` / `OtaTxPersistentServer.sh`。

## 不再采用的做法

明确不要回到旧路线：

- 不做整包 blind repeat。
- 不做 payload 全量强 FEC 作为第一版。
- 不做 `RS + Conv` 级联覆盖全部 payload。
- 不用“重复 N 次直到 SHA 过”为主线指标。

原因：

- 板端是 ARM，payload 全量 FEC/Viterbi/RS 会带来明显解码压力。
- 当前错误更像 chunk 同步 / 定时 / burst 稳定性问题，ARQ 比盲目加 FEC 更有效。
- JSCC 方向本身也不适合长期要求所有 latent bit 都 byte-exact。

## 下一步指标

第一版可靠链路目标：

| 指标 | 目标 |
|---|---:|
| payload FEC | 初始无，最多后续轻量 `r=3/4` |
| header 保护 | 允许强保护，因为 header 很短 |
| chunk CRC | 已有 |
| ARQ | 本机文件接口已通过，Tailscale selective ARQ 待接 |
| payload repeat | 禁止整包 blind repeat |
| ARM 解码 | 避免 payload 级复杂 FEC |
| 33 KB quant payload | 优先闭环候选 |
| 131 KB raw float32 | 继续作为吞吐压力测试 |

下一步实现顺序：

1. Tailscale 控制面读取 `decode_summary.json` 并发送 missing list。
2. 将 `RunQpskFileArqOta.sh` 的本机文件接口拆成 TX/RX 两端可调用的控制消息。
3. 对比 `33,534 B quant payload` 与 `131,231 B raw float32 blob` 的总耗时。
4. 已在 `RunQpskFileBatchSpoolArq.py` 落地 `round1+` 参数分离与 `--fast-arq-profile`：
   - `round0` 保持稳定基线；
   - `round1+` 可单独缩短 `warmup/tail/batch-gap/rx-tail/slice/search-window`。
5. `count=20 / batch-size=20 / decode-workers=2 / --decode-backend cpp --cpp-sync-mode header --fast-arq-profile` 小批量 OTA 已通过：
   - run=`spool_count20_cpp_header_fastarq_20260427_213839`
   - `20/20 PASS`
   - `21.374 s / 1.069 s per image`
   - ARQ 分布 `1:13, 2:7`
   - 相比上一版 `cpp+header` 小批量 `1.265 s/image` 再降约 `15.5%`
   - round1+ wall `6.562 -> 2.531 s`
6. `RunQpskFileBatchSpoolArq.py` 的 `merge_image()` 已补齐 `--chunk-bytes` 透传；此前若 `chunk_bytes != 4096`，merge 口径可能把本来可恢复的 run 误判成 `missing_chunks`。
7. 以上述修正为前提，已完成小范围 `chunk_bytes` 扫参：

| chunk_bytes | count | result | elapsed / per image | ARQ rounds | average rounds | payload airtime mean | run dir size |
|---|---:|---|---:|---|---:|---:|---:|
| `2048` | `10` | `10/10 PASS` | `10.602 s / 1.060 s` | `1:10` | `1.0` | `291.717 ms` | `3.1 MB` |
| `4096` | `10` | `10/10 PASS` | `11.137 s / 1.114 s` | `1:6`, `2:4` | `1.4` | `255.196 ms` | `3.9 MB` |
| `8192` | `10` | `10/10 PASS` | `14.173 s / 1.417 s` | `1:1`, `2:6`, `3:3` | `2.2` | `263.999 ms` | `5.8 MB` |

8. 当前判断：
   - `2048` 虽然 header 开销更高、payload airtime 从 `255.196 ms` 升到 `291.717 ms`，但它在这轮 `10/10` 中全部首轮通过，因此真实 wall 最低。
   - `4096` 仍可作为历史控制组和保守基线，但 round0 一次成功率已明显落后于 `2048`。
   - `8192` 在当前链路上不合适；单包更长后，少量 chunk 失效就会把后续轮成本放大。
9. 当前推荐顺序：
   - 先用 `cpp+header + fast-arq-profile + chunk_bytes=2048` 做 `count=20` 复验；
   - 若结论稳定，再串行扫 `RX gain / rate`，不并发启动多个 OTA run；
   - TVM/MNN 闭环前继续把 `.npz` 语义和重建路径写清楚，不把 raw float32 压力测试误写成最终唯一 payload。

### `chunk_bytes=2048` 300 张全量

在上述小范围 sweep 后，已直接按当前推荐口径扩大到 `300` 张：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
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
USRP292x/qpsk_batch_spool_arq_runs/spool_count300_cpp_header_fastarq_chunk2048_20260427_220219
```

结果：

| 指标 | 值 |
|---|---:|
| result | `300/300 PASS` |
| all_pass | `true` |
| elapsed / per image | `309.276 s / 1.031 s` |
| ARQ rounds distribution | `1:300` |
| average rounds | `1.0` |
| payload airtime mean / median | `291.717 / 291.717 ms` |
| round0 wall | `309.075 s` |
| run directory size | `91.9 MB` |

对比上一版安全 `300` 全量 `spool_count300_batch20_workers2_profile_20260427_193533`：

| 指标 | 旧值 | 新值 |
|---|---:|---:|
| per image wall | `5.174 s` | `1.031 s` |
| total elapsed | `1552.168 s` | `309.276 s` |
| speedup | `1.0x` | `5.02x` |
| ARQ rounds distribution | `1:22`, `2:236`, `3:42` | `1:300` |

判断：

- `chunk_bytes=2048 + cpp+header + fast-arq-profile` 已经不是“小样本偶然值”，而是当前可复现的 `300` 张默认基线。
- 当前主要收益不只是 decode 加速，还包括首轮成功率被抬到了 `300/300 round0 PASS`。
- 在这一口径下，下一步优化重点应从“先保证能过”切到“继续压固定开销”和“接控制面消息”。
