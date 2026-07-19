# USRP IQ-direct 运行说明

IQ-direct 将 JSCC encoder 输出的连续 latent 映射为 USRP I/Q 波形，在飞腾派恢复 latent 后执行 TVM 重建。统一入口 `.\demo.ps1` 默认使用 QPSK；只有切换到 IQ-direct 或运行 `run-demo-tailscale.*` 兼容入口时才使用本文参数。

## 链路边界

| 平面 | 内容 | 路径 |
|---|---|---|
| 控制面 | 启动、状态、质量摘要和任务结果 | Cockpit 后端经 Tailscale/TCP 访问飞腾派 |
| 安全面 | 会话密钥、设备认证和任务准入 | ML-KEM、SM4-GCM、ML-DSA 与 SM2 |
| 数据面 | JSCC latent 对应的复数 IQ 样本 | 上位机 TX USRP 经射频链路到板端 RX USRP |

安全信道不加密射频 IQ payload。AEAD 要求字节和认证标签完整恢复，IQ-direct 则允许 latent 带有模拟误差。

## 执行顺序

1. Cockpit 检查板卡会话、ML-KEM 服务和双签认证状态。
2. 上位机把图片编码为形状 `[1, 32, 32, 32]` 的 latent；相同输入可以复用 encoder 缓存。
3. `_prepare_wire_input_dir()` 生成本轮 transport blob，并写入 `prepared_usrp_inputs/`。
4. `AnalogLatentLink.py` 将相邻实数配成复符号，加入 CFO pilot、同步 pilot 和分段 pilot，经 RRC 成形后量化为 SC16。
5. 板端 RX 先进入接收状态，上位机常驻 TX server 再发送单帧。
6. 板端完成 DC 去除、匹配滤波、同步、CFO 校正和 latent 恢复，只把质量摘要返回控制面。
7. 质量门限通过后，latent 以 `.npy` 文件发布；失败帧进入 ARQ。
8. 长批次按 30 张分段，失败项最多执行两轮子集修复。
9. 全部图片 accepted 后启动 big.LITTLE TVM runner。0、1 号核负责预取和保存，2 号核执行 TVM 手写算子。

当前关闭 streaming TVM，避免 RF decode 与 TVM 争用板端 CPU 和 I/O。

## PHY 参数

| 参数 | TX | RX |
|---|---:|---:|
| 中心频率 | `500 MHz` | `500 MHz` |
| 采样率 | `5 Msps` | `5 Msps` |
| 增益 | `25 dB` | `15 dB` |
| 端口 | `TX/RX` | `RX2` |
| 设备地址 | `192.168.10.2` | `192.168.10.22` |

其他默认值：`SPS=2`、SC16 幅度 `6000`、归一化参考峰值 `6`。TX 控制服务监听上位机 `127.0.0.1:29221`，板端 RX 控制服务监听 `29220`。

单帧波形为 47888 个样本，名义空口时间约 `9.58 ms`。实际接收还包含启动偏移、capture margin、tail、同步、解码和重试，不能用空口时间代替端到端耗时。

## 重传和质量门限

默认门限：

- `sync_metric >= 0.75`
- `pilot_gain_min_over_initial >= 0.85`
- EVM 可用时 `<= 0.75`
- 估计 SNR 可用时 `>= 3.0 dB`

`OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0` 保持 TX/RX 常驻。RX 控制会话最多复用 16 张，段间重建 RX streamer；TX streamer 保持常驻。

单图在每个 segment pass 中最多执行 1 次初传和 12 次 ARQ。segment repair 会为失败项重新分配尝试预算，因此整轮累计次数可能超过 13。只有全量 accepted 才发布有效批次。

## 300 张实测

以下数据来自 `batch-1784291003-300` 和 `cockpit_usrp_usrp-1784291008`：

| 项目 | 结果 |
|---|---:|
| 点击到完成 | `479.38 s` |
| wire blob 准备 | 约 `145 s`，`0/300` cache hit |
| USRP runner wall | `222.42 s`，`300/300` accepted |
| OTA 尝试 | `1013` 次，首次通过 `106/300` |
| transport | median `198.86 ms`，p95 `251.75 ms` |
| RX receive | median `63.60 ms`，p95 `63.70 ms` |
| decode compute | median `40.54 ms`，p95 `58.98 ms` |
| TVM wrapper wall | `79.95 s` |
| TVM kernel | median `245.17 ms`，p95 `309.24 ms` |

本轮瓶颈主要是冷 wire cache 和 RF 重试。TVM kernel 接近 250 ms，但它不是 USRP 端到端时延。

## 已知限制

- 全局同步指标不能保证每个 payload block 都恢复正确。记录中的 `00002395.jpg` 虽然通过门限，仍出现条纹和细节损失。
- 首发通过率受频点环境、天线位置、收发增益和两台设备本振偏差影响。扩大 pipeline 不能代替射频调试。
- 当前按“USRP 全量 accepted 后再执行 TVM”串行运行，优先保证重建质量。
- encoder 和 wire blob 是两层缓存。UI 中 encoder 完成不表示 wire blob 已经准备完毕。

## 证据位置

- USRP 汇总：`USRP292x/qpsk_batch_spool_arq_runs/cockpit_usrp_usrp-1784291008/batch_spool_summary.json`
- TVM 汇总：`Semantic-Communication/session_bootstrap/reports/openamp3_usrp_1784291008_current_20260717_202943.json`
- 板端 latent：`/home/user/cockpit_usrp_rx/cockpit_usrp_usrp-1784291008_rx/`
- 板端重建：`/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/openamp3_usrp_1784291008_current/`
