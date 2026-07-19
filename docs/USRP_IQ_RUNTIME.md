# 当前 USRP IQ 直传链路

本文说明 2026-07-17 Cockpit Desktop 的 IQ-direct 路径及其实测执行过程：`上位机图像 -> Deep JSCC latent -> USRP IQ -> 飞腾派 TVM big.LITTLE -> 重建图像`。当前推荐的 `.\demo.ps1 start` 默认使用 QPSK；切到 IQ-direct 或使用兼容 `run-demo-tailscale.*` 入口时，以本文为准。QPSK 不参与本文的时序数据。

## 三个平面

| 平面 | 承载内容 | 实际路径 |
|---|---|---|
| 控制面 | 启动、状态、质量摘要、任务结果和 SSH 编排 | Cockpit 后端经 Tailscale/TCP 访问板卡 |
| 安全面 | 会话密钥、身份认证和任务准入 | ML-KEM 派生密钥，SM4-GCM 保护控制信道；ML-DSA + SM2 双签认证 |
| 数据面 | JSCC latent 对应的连续复数 IQ 样本 | 上位机 TX USRP，经 500 MHz 射频链路，到板端 RX USRP；不经过 Tailscale |

安全信道没有加密射频 IQ payload。AEAD 要求字节流和 tag 被 bit-exact 还原，而 IQ 直传允许 latent 带有小幅模拟误差。当前安全设计保护控制、身份和准入，不能表述成“USRP 数据面已由 ML-KEM 加密”。

## 端到端执行顺序

1. Cockpit 创建批量任务，检查板卡会话、ML-KEM 服务和双签认证状态。
2. 上位机把图片送入 Deep JSCC 编码器，得到 `[1, 32, 32, 32]` 的 latent。相同输入可复用 `encoder_outputs_top300/` 缓存。
3. `_prepare_wire_input_dir()` 将 latent 量化并封装为 transport blob，默认使用 `webp-lossless`，结果写入本轮 `prepared_usrp_inputs/`。这是独立于图片转 latent 的第二层缓存。
4. `AnalogLatentLink.py` 把 32768 个实数按实部、虚部两两组成 16384 个复符号，加入 CFO pilot、同步 pilot 和分段 pilot，再经 RRC 成形并量化为 SC16。
5. 上位机常驻 TX server 复用 UHD device 和 streamer。板端常驻 RX server 先 arm capture，再由 TX 发送单帧。默认采样率 `5 Msps`、`SPS=2`、幅度 `6000`、固定归一化参考峰值 `6`。
6. 板端 decode worker 就地完成 DC 去除、裁剪、匹配滤波、同步、CFO 估计和 latent 恢复，只把摘要返回控制面；通过的 latent 原子发布为 `.npy`。
7. 质量门限要求 `sync_metric >= 0.75`、`pilot_gain_min_over_initial >= 0.85`，并在可用时检查 EVM 和 SNR。低同步或漏帧会触发 ARQ，不合格 latent 不进入 TVM。
8. 长批次按 30 张分为 10 段。段间重置 RX streamer，TX streamer 保持常驻；段内失败项最多再做两轮子集修复。
9. 当前关闭 streaming TVM。只有 300 张全部 accepted，后端才启动板端 big.LITTLE runner。0、1 号小核负责预取和保存，2 号大核执行 TVM 手写算子路径，输出写到 `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/<job>/`。

本轮运行时实际参数为：TX `500 MHz / 5 Msps / 25 dB / TX-RX`，设备地址 `192.168.10.2`；RX `500 MHz / 5 Msps / 15 dB / RX2`，设备地址 `192.168.10.22`。TX 控制端口监听上位机 `127.0.0.1:29221`，板端 RX 控制服务监听 `29220`；Windows 由 Docker bridge 直接发布 TX 端口。

单帧波形为 47888 个样本，纯空口约 `9.58 ms`。RX 实际还要覆盖启动偏移、capture margin 和 `0.040 s` tail，本轮 RX server 的稳定接收时间约 `63.60 ms`。因此“传输/解包”不能用空口时间替代。

## 常驻、分段与重传

`OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0` 保持 TX/RX 服务存活，避免每张图重新创建设备。RX 控制会话最多复用 16 张，防止整批复用后状态逐渐退化。`ANALOG_PIPELINE_DEPTH=1`、`ANALOG_PIPELINE_RF_DECODE_OVERLAP=0` 和 `OPENAMP_IQ_STREAMING_TVM=0` 是当前质量优先配置。

单图每个 segment pass 最多执行 1 次初传和 12 次 ARQ。若整段仍有失败，segment repair 会重新给失败项分配尝试预算，所以一张图在整轮中的累计尝试数可能超过 13。只有全量 accepted 才发布有效批次，避免出现进度完成但重建图是彩色噪声的情况。

## 本轮 300 张时序

证据对应 `batch-1784291003-300` 和 `cockpit_usrp_usrp-1784291008`，时间为 Asia/Shanghai。

| 项目 | 结果 |
|---|---:|
| 点击到完成 | `479.38 s`，约 7 分 59 秒 |
| 图片转 latent | `300/300` 缓存命中，接口立即完成 |
| wire blob 准备 | 约 `145 s`，2 workers，`0/300` cache hit |
| USRP runner wall | `222.42 s`，`300/300` accepted |
| OTA 尝试 | `1013` 次，额外尝试 `713` 次，平均 `3.377` 次/图 |
| 首次通过 | `106/300` |
| transport | median `198.86 ms`，p95 `251.75 ms`，max `2985.55 ms` |
| RX server receive | median `63.60 ms`，p95 `63.70 ms` |
| decode compute | median `40.54 ms`，p95 `58.98 ms` |
| TVM wrapper wall | `79.95 s`，`3.752 images/s` |
| TVM kernel | median `245.17 ms`，mean `254.54 ms`，p95 `309.24 ms` |
| 重建图保存 | median `164.16 ms`，与推理流水执行 |

本轮有 453 条质量门限拒绝记录，另有 198 条 low-sync 快速重试。14 次 RX reset 合计只有 `1.66 s`，常驻 server 初始化和段间 reset 不是主要卡点。最慢的一次 decode 为 `2.63 s`，其中 fallback 同步搜索约 `2.56 s`。

### 单张质量反例

本轮 index 8 对应原图 `00002395.jpg` 和重建图 `00000008_recon.png`。这张图用了 11 次 OTA，最终记录的 `sync_metric=0.8919`、pilot ratio `1.0`，因此通过了现有 gate；视觉结果仍有明显条纹和细节损失。

| 对比 | PSNR | SSIM | chroma MAE |
|---|---:|---:|---:|
| 两轮 PyTorch 参考均值 | `26.06 dB` | `0.9791` | `8.48` |
| 本轮 USRP IQ + TVM | `19.84 dB` | `0.8937` | `32.87` |

拉回板端 accepted latent 后，与发送 latent 对比得到相关系数 `0.526`、NMSE `0.951`。四个 payload block 的相关系数分别是 `-0.275 / 0.945 / 0.965 / 0.406`，说明第 0、3 块恢复失败，而中间两块基本正常。作为对照，本轮 index 0、5、9 的 latent 相关系数为 `0.931 / 0.947 / 0.957`。

这证明现有同步峰和 pilot ratio 只能排除明显失步，不能保证每个 payload block 都正确。当前 faded quality 标记也不会立即捕获该样本：绝对阈值只针对严重彩色噪声，相对阈值需要同一 job 至少 10 个已拉取样本。正式展示样本集应暂时排除 `00002395.jpg`；后续 gate 需要增加逐块一致性或 payload 恢复残差，不能只继续抬高全局 sync 阈值。

## 卡点判断

第一处是冷 wire cache。运行目录在 20:23:29 开始生成 blob，直到 20:25:54 才完成；当前 UI 的“上位机到 latent 300/300”没有覆盖这段工作，所以会给人已经完成预处理但链路没启动的错觉。该缓存现已生成，同一批输入下次应命中，但本轮没有做第二次计时，不能把预计值写成实测值。

第二处是 RF 首发通过率。纯空口只占约 10 ms，而 713 次额外尝试消耗了大部分 USRP wall。优化顺序应先检查频点环境、收发增益、天线间距、CFO 和同步门限命中情况，再考虑扩大 pipeline；在首发通过率偏低时并发只会放大板端 CPU、I/O 和尾部等待。

TVM 本身仍接近 250 ms 目标。当前阶段串行会让端到端时间等于“USRP 全量 accepted + TVM 批处理”，这是为重建质量做出的明确取舍。之前的 streaming TVM 实验会与板端 decode 争用资源，尚未恢复为默认配置。

## 证据位置

- USRP 汇总：`USRP292x/qpsk_batch_spool_arq_runs/cockpit_usrp_usrp-1784291008/batch_spool_summary.json`
- TVM 汇总：`Semantic-Communication/session_bootstrap/reports/openamp3_usrp_1784291008_current_20260717_202943.json`
- 板端 decoded latent：`/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-1784291008_rx/`
- 板端重建输出：`/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/openamp3_usrp_1784291008_current/`
