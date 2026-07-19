# NI USRP-2922 单向 OTA 打通指南

更新时间：2026-05-01

## 目标

先不用自有调制链，只用 **UHD 官方 C++ examples** 打通：

`TX host -> OTA -> RX host`

第一阶段只做：

- 单向
- 单频点
- 测试波形
- 收 IQ 文件

不要一开始就做：

- 双向双频
- latent 文件承载
- 自有 BPSK/FEC/ARQ

## 为什么先这样做

当前已确认：

- 本机上的两台 `NI USRP-2922 / N210r4 + SBXv3` 均可被 `UHD 4.6` 正常 probe
- 双有线口 host route 已拆开：`.2` 走 `enp4s0`，`.22` 走 `eno1`
- NetworkManager profile 已统一为 `USRP2922-Host` / `USRP2922-Board`；旧 `USRP2922`、`USRP2922-A`、`USRP2922-B` 只作为待清理历史 profile
- 单机近场 OTA 自环只能算 smoke，不适合作为正式链路基线

因此当前主线应切到真正的两机单向 OTA。

网络配置入口：

```bash
# 本机两张网卡同时控制两台 USRP
sudo ./scripts/setup_usrp2922_network.sh local-loopback

# 两端分机部署时分别运行
sudo ./scripts/setup_usrp2922_network.sh host-init
sudo USRP2922_BOARD_IFACE=<iface> ./scripts/setup_usrp2922_network.sh board-init

# 对应停用
sudo ./scripts/setup_usrp2922_network.sh deactivate-local
sudo ./scripts/setup_usrp2922_network.sh deactivate-host
sudo ./scripts/setup_usrp2922_network.sh deactivate-board
```

Fedora 单机入口：

```bash
# 先看 Fedora 当前识别到哪些以太网口
./USRP292x/FedoraUsrpNetwork.sh detect

# 单网口 Fedora 主机控制本机 USRP（当前常见场景）
sudo ./USRP292x/FedoraUsrpNetwork.sh host-init

# 若另一台 Fedora 机器走 board-side 口径
sudo ./USRP292x/FedoraUsrpNetwork.sh board-init

# 查询状态 / 停用
./USRP292x/FedoraUsrpNetwork.sh status
sudo ./USRP292x/FedoraUsrpNetwork.sh deactivate-host
```

说明：

- Fedora 入口本质上只是自动探测网卡名，然后转发到仓库根的 `scripts/setup_usrp2922_network.sh`。
- 当前这台 Fedora 机器实测自动探测到的有线口是 `enp49s0`。
- `host-init` 的默认地址规划仍是 `192.168.10.1/32 -> 192.168.10.2`；`board-init` 仍是 `192.168.10.11/32 -> 192.168.10.22`。

## 2026-04-28 当前冻结基线

说明：本节是当前真正用于汇报和后续链路接入的口径。下面的 `219.298 kSps / tone` 等内容仍然保留，但它们现在只作为 bring-up 历史参考，不再代表当前主线。

### 当前冻结参数

#### RF 与常驻服务

| 项目 | 当前值 |
|---|---:|
| TX USRP args | `addr=192.168.10.2` |
| RX USRP args | `addr=192.168.10.22` |
| center frequency | `500 MHz` |
| sample rate | `5 MSps` |
| TX gain | `25 dB` |
| RX gain | `15 dB` |
| TX antenna | `TX/RX` |
| RX antenna | `RX2` |
| wire format | `sc16` |
| channel | `0` |
| RX control port | `29220` |
| TX control port | `29221` |
| bind addr | `0.0.0.0` |
| setup | `0.5 s` |
| TX `spb` | `1000` |

当前本机常驻进程实际就是按以上参数启动：

- RX: `OtaRxPersistentServer --args addr=192.168.10.22 --port 29220 --rate 5000000 --freq 500000000 --gain 15 --ant RX2`
- TX: `OtaTxPersistentServer --args addr=192.168.10.2 --port 29221 --rate 5000000 --freq 500000000 --gain 25 --ant TX/RX`

#### 数据面与 runner

| 项目 | 当前值 |
|---|---:|
| payload codec | `webp-lossless` |
| latent shape | `1x32x32x32` |
| wire blob format | `[4B meta_len][meta JSON][payload bytes]` |
| modulation | `QPSK` |
| samples/symbol | `2` |
| amplitude | `3000` |
| `chunk_bytes` | `2048` |
| `batch_size` | `20` |
| `decode_workers` | `2` |
| `decode_backend` | `cpp` |
| `cpp_sync_mode` | `header` |
| `artifact_mode` | `minimal` |
| `max_arq_rounds` | `2` |
| `fast_arq_profile` | `on` |

#### round0 保护参数

| 项目 | 当前值 |
|---|---:|
| `warmup_samples` | `250000` |
| `tail_samples` | `250000` |
| `batch_gap_samples` | `250000` |
| `tx_delay_sec` | `0.05 s` |
| `rx_tail_sec` | `0.30 s` |
| `slice_pre_sec` | `0.08 s` |
| `slice_post_sec` | `0.12 s` |
| `search_window_sec` | `0.80 s` |
| `frame_candidates` | `64` |

#### fast-ARQ 的 round1+ 收缩参数

| 项目 | 当前值 |
|---|---:|
| `warmup_samples` | `100000` |
| `tail_samples` | `100000` |
| `batch_gap_samples` | `100000` |
| `rx_tail_sec` | `0.18 s` |
| `slice_pre_sec` | `0.05 s` |
| `slice_post_sec` | `0.08 s` |
| `search_window_sec` | `0.60 s` |

### 当前输入输出格式

当前无线数据面和 Tailscale/TCP fallback 已统一成同一种 wire blob：

```text
[4B meta_len][meta JSON][payload bytes]
```

当前真实业务 payload 的关键 metadata 字段：

- `job_id`
- `shape=[1,32,32,32]`
- `dtype=float32`
- `payload_codec=webp-lossless`
- `payload_format=quant-image-codec`
- `sha256`
- `latent_sha256`
- `scale`
- `zero_point`
- `quant_shape=[32,32,32]`
- `quant_dtype=uint8`
- `quant_encoding=identity`
- `layout={channels,height,width,rows,cols}`

QPSK chunk header 当前包含：

- `magic=QFCK`
- `version`
- `seq`
- `total`
- `payload_len`
- `total_len`
- `crc32`

### 无线收发系统执行步骤

1. 上位机先把 `quant latent` 打包成 wire blob；当前推荐 `webp-lossless`，不是 `131 KB raw float32` 压力包。
2. `QpskFileLink.py make` 按 `chunk_bytes=2048` 切块，并映射成 `QPSK sc16`。
3. `RunQpskFileBatchSpoolArq.py` 把最多 `20` 张图拼成一个 `batch_tx.sc16`，相邻 burst 之间插入 `batch_gap_samples`。
4. 控制面先通过 `OtaRxControl.py` 命令常驻 RX 开始 `CAPTURE`。
5. 等 `50 ms` 后，通过 `OtaTxControl.py` 命令常驻 TX 发送 `batch_tx.sc16`。
6. RX 抓整批次原始 IQ 到 `batch_rx.sc16`。
7. C++ decoder 直接从 `batch_rx.sc16` 按 sample range 解码，不再额外写 `rx_slice.sc16`。
8. runner 在进程内完成 merge，不再为每张图额外起 Python merge 子进程。
9. 若 `round0` 已全过，则流程结束；若仍有 `missing_chunks`，则只重发失败 chunk，不整图盲重传。
10. 后续接入板端闭环时，再把恢复出的 wire blob 交给 `usrp_board_recv.py` 做 `unpack -> npz -> optional TVM inference`。

### 当前正式运行命令

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
    --chunk-bytes 2048 \
    --run-id spool_count300_finalwork_webp5_cpp_header_inline_merge_20260428
```

### 当前最新结果

run：

```text
USRP292x/qpsk_batch_spool_arq_runs/spool_count300_finalwork_webp5_cpp_header_inline_merge_20260428
```

| 指标 | 当前值 |
|---|---:|
| result | `300/300 PASS` |
| per image wall | `0.5024 s` |
| payload airtime mean | `53.585 ms` |
| decode mean | `370.0 ms` |
| merge mean | `1.7 ms` |
| other mean | `77.1 ms` |
| wire blob mean | `24005 B` |

结论：

1. 当前主瓶颈已经不是 RF 空口，而是板端 `decode`。
2. 当前冻结 profile 就是后续链路接入的默认 baseline：`500 MHz / 5 MSps / TX25 / RX15 / chunk2048 / batch20 / cpp+header / fast-arq-profile`。
3. 后续若要再压缩 wall，应优先优化 `QpskFileDecode.cpp` 或做常驻 decode，而不是继续盲扫 RF 参数。

### 主 demo 当前状态

这里的“主 demo”指控制面 / 认证面主入口，不是 USRP TUI。

当前状态：

- `start.sh --server-only` 健康检查通过，`/api/health -> {"status":"ok"}`。
- `mlkem_link/tests/test_auth.py + test_tui_remote_tcp_server.py`：`11/11 PASS`。
- `openamp_control_plane_demo/tests/test_server.py -k 'usrp or mlkem or crypto or batch'`：`33/33 PASS`。
- `./tui_start.sh --usrp --smoke` 仍可通过，说明 USRP TUI 入口本身是健康的。

因此当前可以明确写成：

- 主 demo 的控制面 / 认证面仍然健康；
- USRP2922 数据面 baseline 已冻结；
- 下一步工作不是“修主 demo”，而是把这条冻结的数据面正式接进主 demo。

## 最小参数

早期盲测起点：

- `rate = 1 Msps`
- `freq = 1.000 GHz`
- `tx_gain = 0 dB`
- `rx_gain = 10 dB`
- `wave_type = SINE`
- `wave_freq = 100 kHz`
- `TX antenna = TX/RX`
- `RX antenna = RX2`

说明：

- 用户后续若要做 `1 GHz` 附近双频点交换，**也先把一个点打通**，第二个点后置。
- `1.000 GHz` 只是第一轮 bring-up 点，不是最终冻结点。

当前更推荐的 LabVIEW 历史口径：

- `rate = 219.298 kSps`（LabVIEW 约写作 `220 kSps`）
- `freq = 500 MHz`
- `tx_gain = 25 dB`
- `rx_gain = 20 dB`（历史 LabVIEW 为 `25 dB`；当前一米距离实测 `20 dB` 更适合作为起点）
- `wave_type = SINE`
- `wave_freq = 30 kHz`
- `TX antenna = TX/RX`
- `RX antenna = RX2`

说明：

- 用户历史 LabVIEW FM 参数是 `IQ rate 220 kSps / center 500 MHz / TX gain 25 / RX gain 25`。
- UHD/N210 对 `220 kSps` 会量化到约 `219.298 kSps`，这是硬件抽取率限制，不是异常。
- 当前实测 `500 MHz` 明显优于 `1 GHz`，因此后续 Level 0 先围绕 `500 MHz` 做。
- 官方 `rx_samples_to_file --gain` 有 channel-index bug；当前使用 `OtaRxCaptureGain` 显式设置 `channel 0` 的 RX gain。

## 物理要求

- 两台设备各接一副匹配频段的天线
- 两边天线极化方向保持一致
- 初测不要贴得太近，建议先从 `1 m` 左右开始；当前一米距离已用于 `500 MHz` 复测
- 避开金属遮挡和人手贴近天线
- 如果现场干扰重，再改频点，不要先把 gain 拉满

## 发端命令

在 TX 端主机运行：

```bash
DEVICE_ARGS='addr=<tx_usrp_ip>' \
FREQ=500000000 \
RATE=219298 \
GAIN=25 \
AMPL=0.05 \
WAVE_FREQ=30000 \
./USRP292x/OtaTxWaveform.sh
```

## 收端命令

在 RX 端主机运行：

```bash
DEVICE_ARGS='addr=<rx_usrp_ip>' \
FREQ=500000000 \
RATE=219298 \
GAIN=20 \
ANT=RX2 \
OUT_FILE='USRP292x/OtaRxCapture.dat' \
./USRP292x/OtaRxCaptureGain.sh
```

注意：如果继续使用官方 `OtaRxCapture.sh`，`GAIN=''` 是对官方 `rx_samples_to_file` 的临时规避。该 example 在本机 `UHD 4.6 + N210/SBX` 上传 `--gain` 会报 `RX channel 18446744073709551615 out of range`。正式标定 RX gain 时使用 `OtaRxCaptureGain.sh`。

## 收端分析

在 RX 端抓到文件后运行：

```bash
python3 USRP292x/AnalyzeLoopbackCapture.py \
    USRP292x/OtaRxCapture.dat \
    --rate 219298 \
    --expected-tone 30000
```

先看三件事：

- 文件不是空的
- `strongest_non_dc_hz` 不是贴着直流
- `peak_near_expected_hz` 明显落在 `30 kHz` 附近

## 扫参顺序

如果第一次没打通，按这个顺序调：

1. 保持频点不变，只调天线朝向和距离
2. 先固定 `500 MHz / 219.298 kSps / wave_freq 30 kHz / RX2`
3. 修复 RX gain 设置后，再扫 `rx_gain: 10 -> 15 -> 20 -> 25 dB`
4. `tx_gain: 10 -> 15 -> 20 -> 25 dB`
5. `wave_freq: 30 kHz -> 50 kHz -> 80 kHz`
6. 最后才改中心频点

不要一开始就：

- `tx_gain=30+ dB`
- `rx_gain=30+ dB`
- 双向同时开

## 当前边界

- 当前两台设备都能被本机 UHD 发现和 probe。
- `.2 TX -> .22 RX` 官方例程已经能完成 OTA tone 抓包。
- 官方 tone example 本身不能报 BER；BER/PER 由后续 QPSK 文件链路统计。
- 当前主要问题已经从“RX gain 不可控”推进到“QPSK chunk 链路已可用，下一步做多轮稳定性和 selective ARQ”。
- 推荐 Level 0 tone 工作点：`500 MHz / 219.298 kSps / tone 30 kHz / TX gain 25 / RX gain 20 / RX2 / 距离约 1 m`。

## UDP socket buffer

当前主机：

```text
net.core.wmem_max = 4194304
net.core.rmem_max = 50000000
```

UHD 警告希望 send buffer 达到 `2500000 bytes`。当前 `wmem_max=4194304` 已满足 `5 MSps` 长测；如果换机或重启后恢复默认值，重新执行：

```bash
sudo sysctl -w net.core.wmem_max=4194304
```

当前短时 benchmark 结果：

| 设备 | 方向 | 采样率 | 结果 |
|---|---|---:|---|
| `.2` | TX only | `1 Msps` | `underruns=0` |
| `.2` | TX only | `5 Msps` | `underruns=0` |
| `.2` | TX only | `10 Msps` | `underruns=0` |
| `.22` | RX only | `5 Msps` | `overruns=0` |
| `.22` | RX only | `10 Msps` | `overruns=0` |

说明：这是 host↔USRP streaming 能力 smoke，不等价于 OTA BER/PER。

## Level 1 QPSK 文件快测

当前已新增：

- `EstimateLatentAirtime.py`：估算 `1x32x32x32` payload 的空口时间。
- `QpskFileLink.py`：生成 chunked QPSK sc16 波形并离线解码。
- `RunQpskFileOta.sh`：官方 `tx_samples_from_file` + `OtaRxCaptureGain` + QPSK 解码编排。
- `RunQpskFileArqOta.sh`：本机文件接口 selective ARQ 编排，后续替换为 Tailscale 控制消息。
- `RunQpskFileBatchArq.py`：多图/多 payload 批量 selective ARQ 编排，用于 300 次长测。
- `UsrpTui.py`：USRP 数据面 TUI，已通过 `tui_start.sh --usrp` 接入。
- `OtaRxPersistentServer.cpp` / `OtaRxControl.py`：常驻 RX + TCP/Tailscale 控制面。
- `OtaTxPersistentServer.cpp` / `OtaTxControl.py`：常驻 TX + TCP/Tailscale 控制面。
- `RunQpskFileBatchSpoolArq.py`：batch RX spool + per-image slice decode + selective ARQ 编排。
- `QpskFileLinkRecord.md`：记录当前 QPSK 快测结论。
- `decode_summary.json`：每次 run 的机器可读解码结果，包含 `missing_chunks` 和 `crc_ok_indices`。

当前 QPSK 快测口径：

| 项目 | 值 |
|---|---:|
| wire blob | `131,231 B` |
| chunk | `4096 B x 33` |
| rate | `5 MSps` 优先，`2.5 MSps` 对照 |
| samples/symbol | `2` |
| modulation | QPSK |
| FEC | 无 |
| ARQ | 无 |
| payload repeat | 无 |
| warmup | `50 ms` random QPSK，可保留 |
| tail guard | `50 ms` zero samples，避免 burst 尾部截断 |
| chunk header | `seq / total / len / crc32` |

当前结论：

- 本地无信道自测可 `33/33 chunks exact`。
- 最新 OTA `tail_5m_qpsk_raw131k_rx15*` 口径下，`2/3` 次 `33/33 crc_ok`、`1/3` 次 `31/33 crc_ok`。
- 口径为 `.2 TX -> .22 RX`、`500 MHz`、`5 MSps`、`TX gain 25`、`RX gain 15`、`RX2`、`131,231 B wire blob`。
- payload-only detected airtime 为 `251.371 ms`，effective payload 为 `4.176 Mbps`。
- 旧失败主要来自接收端误锁和 burst 尾部截断；direct-sync + per-chunk CRC + tail guard 已解决本轮问题。
- selective ARQ 已补齐少量缺失 chunk，并通过 `300/300` 长测；下一步应压缩真实 wall time。
- 本机 ARQ smoke 已通过：round0 缺 `[2,11,20,29]`，round1 只重发这 4 个 chunk，merge 后 `33/33`、`byte_errors=0`。
- `tui_start.sh --usrp --smoke` 和 `tui_start.sh --usrp --dry-run --count 3` 已通过，证明 USRP TUI 入口和批量 runner 接口可用。
- 常驻 RX 首版已通过：`RX_CONTROL_HOST=127.0.0.1` 控制本机 RX server，`persistent_rx_arq_defaults_5m_qpsk_raw131k_rx15` round0 `33/33 crc_ok`。
- 常驻 RX/TX 首版已通过：`persistent_rxtx_arq_retry_5m_qpsk_raw131k_rx15` round0 `32/33 crc_ok`，round1 只重发 `[6]` 后 merge `exact=true`。
- 300 次长测已完成：`batch300_persistent_rxtx_20260427_114323`，`300/300 PASS`，最终 merge 后 `byte_errors=0`、`bit_errors=0`、`all_pass=true`。当前 `net.core.wmem_max=4194304` 已满足 `5 MSps` 长测前置条件。

补充说明：

- 这里的 QPSK 链路是当前 USRP292x bring-up 和压力测试 baseline，不是最终 DeepJSCC PHY 结论。
- 当前仓库稳定 I/O 口径仍是 `quant .npz -> float32 latent -> wire blob`；如果后续拿到 DeepJSCC 编码器直接输出的 `continuous complex symbols`，则应改走“complex symbols -> framing/pilot/sync -> USRP IQ -> OTA -> recovered symbols -> decoder”的正线，而不是先强行改成 bit/QPSK。

### 300 次常驻 RX/TX 长测

口径说明：本轮是同一份 `131,231 B` raw-float wire blob 重复发送 `300` 次，用于验证 USRP292x 链路稳定性和耗时；不是 `300` 个不同样本的数据集覆盖测试。

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
| ARQ | per-chunk CRC + selective retransmission，最多 `2` 轮 ARQ |

结果：

| 指标 | 值 |
|---|---:|
| completed / pass / fail | `300 / 300 / 0` |
| final byte / bit errors | `0 / 0` |
| all_pass | `true` |
| started / finished | `2026-04-27T11:43:23+0800 -> 2026-04-27T12:54:44+0800` |
| elapsed | `4280.660 s` |
| total wall | `4279.181 s` |
| wall mean / min / median / max | `14.264 / 10.842 / 15.475 / 21.410 s` |
| ARQ rounds distribution | `1 round: 104`, `2 rounds: 181`, `3 rounds: 15` |
| average rounds | `1.703` |
| payload airtime total / mean | `78.470 s / 261.568 ms` |
| payload airtime min / median / max | `251.371 / 258.981 / 321.291 ms` |
| effective payload over payload airtime | `4.179 Mbps` |
| effective payload over real wall | `0.074 Mbps` |

首轮接收质量：

| 指标 | 值 |
|---|---:|
| round0 `crc_ok` mean / min / median / max | `31.730 / 25 / 32 / 33` |
| round0 missing chunks mean / min / median / max | `1.270 / 0 / 1 / 8` |
| round0 missing chunks distribution | `{0:104, 1:100, 2:54, 3:14, 4:17, 5:6, 6:3, 7:1, 8:1}` |

结论：

- 可靠性层已经能支持 `131 KB` 压力 payload 的 `300/300` bit-exact 恢复。
- 当前最终 BER 口径是 merge 后 `0`，不是裸 PHY 每轮 BER；失败 chunk 被 CRC 识别后走 selective ARQ。
- 真正拖慢单图 wall 的不是空口 payload airtime，而是固定 RX capture window、离线 decode 和多轮控制开销。
- 下一步优化优先级应是 C++ decode、短重传窗口和 batch burst/spool，而不是增加 payload FEC 或整包 repeat。

### Batch RX Spool Smoke

第一版 batch-spool 入口：

```bash
RX_CONTROL_HOST=127.0.0.1 \
RX_CONTROL_PORT=29220 \
TX_CONTROL_HOST=127.0.0.1 \
TX_CONTROL_PORT=29221 \
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --count 20 \
    --max-arq-rounds 2 \
    --batch-size 20 \
    --decode-workers 2
```

实现边界：

- 仍使用现有常驻 RX/TX server。
- 每个 ARQ round 按 `--batch-size` 切成若干 batch TX sc16 文件，RX 每个 batch 用一次 capture 覆盖。
- capture 结束后按发送时间表切成 per-image `rx_slice.sc16`。
- per-image decode 可通过 `--decode-workers` 并行，但当前硬限制为 `<=2`。
- 这还不是最终 continuous streaming daemon；它是低风险的 batch-spool 过渡实现。
- `RunQpskFileBatchSpoolArq.py` 已内置资源保护：`--batch-size` 最大 `20`，`--decode-workers` 最大 `2`，子进程 `OMP/BLAS` 线程数固定为 `1`。

实测：

| run | count | decode workers | result | elapsed | per image |
|---|---:|---:|---|---:|---:|
| `spool_count3_smoke_20260427_132130` | `3` | `1` | `3/3 PASS` | `26.754 s` | `8.918 s` |
| `spool_count10_smoke_20260427_132219` | `10` | `1` | `10/10 PASS` | `89.784 s` | `8.978 s` |
| `spool_count10_parallel4_20260427_132436` | `10` | `4` | `10/10 PASS` | `33.602 s` | `3.360 s` |
| `spool_count20_parallel4_20260427_132542` | `20` | `4` | `20/20 PASS` | `58.209 s` | `2.910 s` |
| `spool_count20_batch20_workers2_profile_20260427_192735` | `20` | `2` | `20/20 PASS` | `98.640 s` | `4.932 s` |
| `spool_count300_batch20_workers2_profile_20260427_193533` | `300` | `2` | `300/300 PASS` | `1552.168 s` | `5.174 s` |

注意：上表 `decode-workers=4` 只作为历史性能探针保留，不再作为推荐配置。它在扩展到 `300` 张时造成明显 I/O/CPU/SSH 压力，后续实验必须按 `decode-workers<=2` 控制。

`count=20 / batch-size=20 / decode-workers=2` profiling 关键指标：

| 指标 | 值 |
|---|---:|
| ARQ rounds distribution | `1 round: 4`, `2 rounds: 16` |
| round0 / round1 wall | `85.520 / 13.103 s` |
| round0 RX duration / TX send wall | `8.332 / 7.968 s` |
| round0 decode wall | `73.387 s` |
| round0 merge wall | `1.559 s` |
| payload airtime mean | `263.710 ms` |

这组结果是当前安全约束内的优先参考：`4.932 s/image`。它说明 batch-spool 已明显优于逐图常驻 RX/TX，但主要瓶颈仍是 Python decode。

`count=300 / batch-size=20 / decode-workers=2` 全量关键指标：

| 指标 | 值 |
|---|---:|
| result | `300/300 PASS` |
| final byte / bit errors | `0 / 0` |
| elapsed / per image | `1552.168 s / 5.174 s` |
| ARQ rounds distribution | `1:22`, `2:236`, `3:42` |
| payload airtime mean | `269.334 ms` |
| round0 / round1 / round2 wall | `1282.220 / 239.665 / 29.916 s` |
| round0 decode wall sum | `1101.081 s` |

这组结果是当前最可信的安全全量口径：比逐图常驻 RX/TX 的 `14.264 s/image` 快约 `2.76x`，但离历史 `parallel4` smoke 仍有差距。

`count=20 / decode-workers=4` 关键指标：

| 指标 | 值 |
|---|---:|
| ARQ rounds distribution | `1 round: 11`, `2 rounds: 8`, `3 rounds: 1` |
| round0 / round1 / round2 RX wall | `8.332 / 1.744 / 0.458 s` |
| round0 / round1 / round2 TX wall | `7.938 / 1.350 / 0.066 s` |
| payload airtime mean | `256.348 ms` |
| RX timeout / overflow | `0 / 0` |

结论：

- batch-spool + safe 2-worker profiling 已把 `131 KB` 压力 payload 的 wall 从逐图常驻 RX/TX 的 `14.264 s/image` 降到全量 `5.174 s/image`。
- `decode-workers=4` 证明仍有并行空间，但不满足当前稳定性约束。
- 当前主要剩余瓶颈是 Python decode、sc16 文件落盘/切片和 round 级串行等待。
- 下一步如果继续压低 wall，应做 C++ decode、减少中间文件、以及真正 continuous RX ring/spool。

300 张 batch-spool 尝试记录：

| run | 结果 | 处理 |
|---|---|---|
| `spool_count300_parallel4_20260427_142238` | 失败，N210/UHD `num_samps` 超出 `0x0fffffff` 限制 | 必须分 batch |
| `spool_count300_batch100_parallel4_20260427_142544` | 失败，RX server 捕获 deadline 不足 | batch 不应过大 |
| `spool_count300_batch50_parallel4_20260427_143603` | 中止，主机/SSH 明显卡顿，产物约 GB 级 | 不再使用 `decode-workers=4` |

后续重跑 `300` 张前置条件：

1. 先用 `count=20 / batch-size<=20 / decode-workers<=2` 验证。
2. 增加 checkpoint/resume 和分 batch summary，避免一次失败丢失全部进度。
3. 未得到明确确认前，不启动 300 张全量 RF 测试。

## 常驻 RX/TX 控制面

构建：

```bash
./USRP292x/BuildOtaTools.sh
```

RX 侧启动 server。双机时 `BIND_ADDR=0.0.0.0`，控制端用 RX 主机 Tailscale IP 连接：

```bash
DEVICE_ARGS='addr=192.168.10.22' \
RATE=5000000 \
FREQ=500000000 \
GAIN=15 \
ANT=RX2 \
BIND_ADDR=0.0.0.0 \
PORT=29220 \
./USRP292x/OtaRxPersistentServer.sh
```

TX 侧启动 server。双机时控制端用 TX 主机 Tailscale IP 连接：

```bash
DEVICE_ARGS='addr=192.168.10.2' \
RATE=5000000 \
FREQ=500000000 \
GAIN=25 \
ANT=TX/RX \
BIND_ADDR=0.0.0.0 \
PORT=29221 \
./USRP292x/OtaTxPersistentServer.sh
```

控制命令：

```bash
python3 USRP292x/OtaRxControl.py --host <rx_tailscale_ip> --port 29220 ping
python3 USRP292x/OtaRxControl.py --host <rx_tailscale_ip> --port 29220 status
python3 USRP292x/OtaRxControl.py --host <rx_tailscale_ip> --port 29220 stop
python3 USRP292x/OtaRxControl.py --host <rx_tailscale_ip> --port 29220 quit
python3 USRP292x/OtaTxControl.py --host <tx_tailscale_ip> --port 29221 ping
python3 USRP292x/OtaTxControl.py --host <tx_tailscale_ip> --port 29221 status
python3 USRP292x/OtaTxControl.py --host <tx_tailscale_ip> --port 29221 quit
```

TUI / demo 入口已同步到当前常驻 RX/TX 和 batch-spool 路线：

```bash
# 启动本机常驻 RX/TX server；已运行时会直接报告 already running
./tui_start.sh --usrp --start-persistent-rxtx

# 查询常驻 RX/TX 状态
./tui_start.sh --usrp --persistent-status

# 关闭常驻 RX/TX server
./tui_start.sh --usrp --stop-persistent-rxtx

# 打开 Textual 操作台，内含 Start/Status/Stop Persistent RX/TX 按钮
./tui_start.sh --usrp
```

### 2026-05-01 双机 TUI 统一编排口径

从这一天开始，USRP TUI 的推荐口径不再只是假设“本机同时接 TX/RX 两台设备”，而是显式区分本机角色：

| 模式 | 说明 | 典型用途 |
|---|---|---|
| `Local RX/TX` | 本机同时拥有 TX 和 RX 两个常驻 server | 单机回环、实验室并机 bring-up |
| `Local TX` | 本机拥有 TX；远端主机拥有 RX | 当前主推的双机 OTA 数据面 |
| `Local RX` | 本机拥有 RX；远端主机拥有 TX | 给另一台机器做 RX 侧部署、自检与排障 |

双机时推荐把 **TX 端** 作为唯一编排端，原因有三：

1. TX 端天然拥有待发送 payload、manifest 与 batch runner。
2. RX 端只需要保持常驻、按命令 capture，并把抓到的 IQ 产物回传。
3. 误码率 / merge / 最终 PASS 统计应统一留在 TX 端，避免两机分别留一半证据。

因此后续统一流程应写成：

1. TX 端通过 Tailscale 控制面拉起远端常驻 RX。
2. TX 端轮询远端 RX `ping/status`，确认服务 ready。
3. TX 端本地生成 `batch_tx.sc16` 并启动本地常驻 TX。
4. TX 端命令远端 RX 开始 `capture`。
5. TX 端等待固定 `tx_delay_sec` 后命令本地 TX 发送。
6. TX 端等待远端 RX `wait` 完成。
7. 远端 RX 将 `batch_rx.sc16` 通过 Tailscale 回传到 TX 端。
8. TX 端本地完成 `decode -> merge -> BER / byte_errors / exact` 统计。
9. TX 端统一负责 `quit/stop`，清理本地 TX 与远端 RX。

注意：

- `Local RX` 模式主要用于远端 RX 主机自检，不是最终 demo 的主控入口。
- 正式 demo 时，建议只在 **TX 端** 打开 TUI；RX 端只保留 helper / server 角色。
- 双机模式下，`batch_rx.sc16` 的权威副本必须最终回到 TX 端 run dir，后续 decode 不再依赖“直接在 RX 端本地解码”。
- 若要让 TX 端自动拉起远端 RX 并自动回传文件，远端机器必须预先具备 **非交互 SSH/Tailscale SSH 能力**；否则 TUI 应直接 fail-fast，不等待密码输入。

当前 demo 默认：

| 项目 | 默认值 |
|---|---|
| batch runner | `RunQpskFileBatchSpoolArq.py` |
| run root | `USRP292x/qpsk_batch_spool_arq_runs/` |
| decode backend | `cpp` |
| C++ mode | `header` |
| artifact mode | `minimal` |
| batch size / decode workers | `20 / 2` |

双机统一编排新增建议字段：

| 字段 | 作用 |
|---|---|
| `local_role_mode` | `local-rxtx / local-tx / local-rx` |
| `tx_control_host` | TX 常驻 server 的控制地址；`Local TX` 时通常为 `127.0.0.1` |
| `rx_control_host` | RX 常驻 server 的控制地址；双机时为远端 RX 主机 Tailscale IP |
| `remote_rx_ssh_target` | 远端 RX 主机的 SSH/Tailscale 目标 |
| `remote_project_root` | 远端仓库根路径 |
| `remote_run_root` | 远端 capture 临时产物目录 |
| `remote_pull_mode` | `scp` 或后续更轻量的回传方式 |

发送端使用常驻 RX/TX：

```bash
RX_CONTROL_HOST=<rx_tailscale_ip> \
RX_CONTROL_PORT=29220 \
TX_CONTROL_HOST=<tx_tailscale_ip> \
TX_CONTROL_PORT=29221 \
RATE=5000000 \
FREQ=500000000 \
TX_GAIN=25 \
RX_GAIN=15 \
bash USRP292x/RunQpskFileArqOta.sh
```

双机时后续推荐口径不是“本机 runner 直接 decode 远端路径”，而是：

```text
remote RX capture -> tailscale/scp 回传 batch_rx.sc16 -> local decode/merge
```

也就是说，控制消息和数据产物必须分开看：

- 控制面：`OtaRxControl.py / OtaTxControl.py`
- 产物回传：`tailscale ssh/scp` 或等价的可靠文件回收通道

只有这样，`Local TX` 模式才能真正做到：

- 在 TX 端统一留 `summary / merge / BER`
- 在 RX 端尽量少保留重资产文件
- 同一套 TUI 可以直接复制到另一台机器，只切换 `local_role_mode` 与 host 参数即可

当前边界：

- 常驻 RX 已避免每图重新打开 RX USRP；实现上是 USRP 对象常驻、每次 capture 新建 RX streamer，避免 N210 streamer 复用超时。
- 常驻 TX 已避免每图重新打开 TX USRP；round0 `1,757,880` samples 发送 wall 约 `0.307 s`。

### 资源占用控制

`RunQpskFileBatchSpoolArq.py` 已新增 `--artifact-mode`：

| mode | 行为 | 用途 |
|---|---|---|
| `minimal` | 默认；发送/解码后删除 `batch_tx.sc16`、`batch_rx.sc16`、`tx_qpsk.sc16`、`rx_slice.sc16` | 常规 demo / 小批量测速 |
| `full` | 保留全部中间文件 | 问题复盘、调同步、留证 |
| `board` | 在 `minimal` 基础上最终删除 decoded/merged bin，只留 summary/log/manifest | 板端或 TF 卡压力环境 |

刚才 `spool_count20_cpp_header_20260427_202642` 是旧 full-like 产物口径，目录约 `841 MB`，主要由 sc16 中间文件构成：

| 部分 | 量级 |
|---|---:|
| `round0` batch TX/RX | `312 MB` |
| `round1` batch TX/RX | `72 MB` |
| `round2` batch TX/RX | `11 MB` |
| per-image `tx_qpsk.sc16` / `rx_slice.sc16` | 每图约 `18-34 MB` |

后续默认 `minimal` 会删除这些大文件，保留 summary/log/manifest 和小的 decoded/merge 结果；20 张同口径预计可从 `~841 MB` 降到百 MB 以内。若要完整复盘 RF 原始波形，显式加 `--artifact-mode full`。

`minimal` smoke 已验证：

| run | result | elapsed | directory | cleanup |
|---|---|---:|---:|---:|
| `spool_count1_cpp_header_minimal_20260427_203622` | `1/1 PASS` | `2.500 s` | `664 KB` | 删除 sc16 `57.551 MB` |
- 如果只启用常驻 RX 而 TX 仍走官方 `tx_samples_from_file`，默认 `RX_DURATION=5.5`、`SEARCH_START_SEC=1.0`、`SEARCH_END_SEC=5.3`，用于覆盖 TX 官方例程初始化时间。
- 如果 RX/TX 都常驻，默认 `RX_DURATION=2.3`、`SEARCH_START_SEC=0.05`、`SEARCH_END_SEC=2.20`。
- 这一步证明 Tailscale 控制面形态可行，但还不是最终低延迟数据面；下一步应做 batch burst/spool、短重传窗口和解码热路径优化。

后续不要用整包 blind repeat 解决可靠性。下一步应加入：

1. Tailscale 控制面读取 `decode_summary.json` 并返回 missing list。
2. TX 只重传失败 chunk。
3. 对比 `33 KB quant payload` 与 `131 KB raw float32 wire blob`。
4. 优化重传轮 warmup/tail guard。

### 重传轮短窗口参数机制

`RunQpskFileBatchSpoolArq.py` 现已支持“`round0` 保持稳定基线，`round1+` 单独缩短保护开销”的参数机制。目标不是提高裸 PHY，而是减少“只缺少量 chunk 的后续轮次”仍然支付完整保护时间的浪费。

新增入口：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --fast-arq-profile
```

行为：

- `round0` 继续使用当前默认参数，不动基线。
- `round1+` 若未显式指定覆盖值，则使用更短的重传轮默认值：
  - `warmup_samples=100000`
  - `tail_samples=100000`
  - `batch_gap_samples=100000`
  - `rx_tail_sec=0.18`
  - `slice_pre_sec=0.05`
  - `slice_post_sec=0.08`
  - `search_window_sec=0.60`

也可以分别单独覆盖：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --arq-warmup-samples 100000 \
    --arq-tail-samples 100000 \
    --arq-batch-gap-samples 100000 \
    --arq-rx-tail-sec 0.18 \
    --arq-slice-pre-sec 0.05 \
    --arq-slice-post-sec 0.08 \
    --arq-search-window-sec 0.60
```

说明：

- 这一步只改变重传轮调度与保护时间，不改变 `QPSK + chunk + CRC + selective ARQ` 协议本身。
- 当前已完成 `py_compile`、`--dry-run` 和首轮小批量 OTA 验证。

`count=20 / batch-size=20 / decode-workers=2 / --decode-backend cpp --cpp-sync-mode header --artifact-mode minimal --fast-arq-profile`：

| 指标 | 值 |
|---|---:|
| run | `spool_count20_cpp_header_fastarq_20260427_213839` |
| result | `20/20 PASS` |
| final byte / bit errors | `0 / 0` |
| elapsed / per image | `21.374 s / 1.069 s` |
| ARQ rounds distribution | `1:13`, `2:7` |
| payload airtime mean | `254.816 ms` |
| round0 wall | `18.826 s` |
| round1 wall | `2.531 s` |
| run directory size | `8.4 MB` |

对比上一版 `cpp+header` 小批量 `spool_count20_cpp_header_20260427_202642`：

- 单图 wall `1.265 -> 1.069 s`，下降约 `15.5%`。
- ARQ 分布由 `1:9, 2:10, 3:1` 收敛到 `1:13, 2:7`。
- 后续轮总 wall 由 `5.622 + 0.940 = 6.562 s` 降到 `2.531 s`，下降约 `61.4%`。

结论：

- `round0` 基线未被破坏；主要收益来自 `round1+` 固定保护开销明显下降。
- 这组结果足够支持把“重传轮短窗口”保留为默认优化方向。
- 在此基础上已经完成一轮 `chunk_bytes` 小范围扫参，当前优先候选已从历史 `4096` 收口到 `2048`。

同口径 sweep：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --count 10 \
    --batch-size 10 \
    --decode-workers 2 \
    --decode-backend cpp \
    --cpp-sync-mode header \
    --artifact-mode minimal \
    --fast-arq-profile \
    --chunk-bytes <2048|4096|8192>
```

注意：在比较 `chunk_bytes` 之前，`RunQpskFileBatchSpoolArq.py` 的 merge 路径已修正为显式透传 `--chunk-bytes`；否则非 `4096` 配置可能被错误统计。

| chunk_bytes | result | elapsed / per image | ARQ rounds | average rounds | payload airtime mean |
|---|---|---:|---|---:|---:|
| `2048` | `10/10 PASS` | `10.602 s / 1.060 s` | `1:10` | `1.0` | `291.717 ms` |
| `4096` | `10/10 PASS` | `11.137 s / 1.114 s` | `1:6`, `2:4` | `1.4` | `255.196 ms` |
| `8192` | `10/10 PASS` | `14.173 s / 1.417 s` | `1:1`, `2:6`, `3:3` | `2.2` | `263.999 ms` |

当前判断：

- `2048` 的 payload airtime 更长，但 round0 一次成功率最好，因此真实 wall 最低。
- `4096` 仍可保留为历史控制组；如果后续物理层扫参使 round0 成功率上升，再回头比较也合理。
- `8192` 在当前链路上不推荐作为默认值。

下一步顺序：

1. `chunk_bytes=2048` 的 `300` 张全量已经通过，可先把它视为当前默认基线。
2. 再串行扫 `RX gain / rate`，每次只跑一个 OTA run，避免争用同一常驻 RX/TX server。
3. 之后再接 Tailscale missing-list 控制消息，不直接并行推进多个变量。

`300` 张全量 run：

```text
USRP292x/qpsk_batch_spool_arq_runs/spool_count300_cpp_header_fastarq_chunk2048_20260427_220219
```

| 指标 | 值 |
|---|---:|
| result | `300/300 PASS` |
| elapsed / per image | `309.276 s / 1.031 s` |
| ARQ rounds distribution | `1:300` |
| average rounds | `1.0` |
| payload airtime mean | `291.717 ms` |

这说明当前 `2048` 配置不只是小样本更好，而是在 `300` 张规模下也保持了首轮全过。

### Tailscale 控制消息边界

把 `missing_chunks` 改成 Tailscale 控制面消息不会天然干扰当前 demo，但必须按旁路方式接入：

- 独立端口 / 独立 helper，不复用 Cockpit 加密 TUI 的会话状态。
- 默认 demo 不启用 USRP ARQ 控制消息；只有显式配置 `RX_CONTROL_HOST / TX_CONTROL_HOST` 或未来的 `USRP_CONTROL_MODE=tailscale-arq` 才启用。
- 控制消息只携带小 JSON：`session_id`、`file_id`、`round`、`missing_chunks`、`crc_ok_indices`。
- 先做本机文件接口等价替换，再接真实双机 Tailscale IP。

### C++ decode 状态

当前 Python 解码不是“语言一定慢”的问题，但批量测试里确实有固定成本。已新增 C++ CLI：

```text
rx_capture.sc16 + manifest.json -> decoded_wire_blob.bin + decode_summary.json
```

构建：

```bash
./USRP292x/BuildOtaTools.sh
```

batch-spool 显式切换：

```bash
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
    --decode-backend cpp \
    --cpp-sync-mode header \
    --decode-workers 2
```

模式说明：

| mode | 用途 |
|---|---|
| `hybrid` | 离线对齐旧 Python 结果，适合做控制变量 |
| `header` | 生产性能路径，使用控制面可预共享 manifest/chunk metadata 做 header pilot |
| `sync` | Schmidl-only 实验路径，当前不推荐 |

已有离线 smoke：同一 `image_0000/round0/rx_slice.sc16` 上，Python `decode` 为 `27/33 crc_ok, 7.341 s`；C++ `hybrid` 为 `27/33 crc_ok, ~5.0 s`；C++ `header` 为 `33/33 crc_ok, ~0.64 s`。

`header` mode 小批量 OTA 已通过：

| run | count | result | elapsed | per image | ARQ rounds |
|---|---:|---|---:|---:|---|
| `spool_count20_cpp_header_20260427_202642` | `20` | `20/20 PASS` | `25.307 s` | `1.265 s` | `1:9`, `2:10`, `3:1` |

该结果比 Python safe 2-worker profiling 的 `4.932 s/image` 快约 `3.9x`，且 RX timeout / overflow 为 `0 / 0`。下一步若扩大到 300，应先处理 checkpoint/resume 和产物瘦身；本轮 20 张目录已经约 `841 MB`。

ARM 侧约束：

- 不要第一版就对 payload 做全量复杂 FEC。
- Header 很短，可以强保护。
- Payload 第一版优先 `CRC32 + selective ARQ`。
- 如果后续需要 FEC，优先考虑低复杂度、轻冗余，或只保护重要 chunk。
