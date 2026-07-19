# USRP IQ 直传链路汇报口径

更新时间：2026-07-18

本文记录 USRP IQ-direct 可选链路、实测指标和安全边界。推荐入口 `start-demo.ps1` 默认使用 QPSK；切到 IQ-direct 或使用兼容 `run-demo-tailscale.*` 入口时，链路为：

```text
Cockpit Desktop
  -> 上位机 JSCC 编码
  -> USRP IQ 直传
  -> 飞腾派 IQ 恢复
  -> handwritten TVM + big.LITTLE 重建
  -> Cockpit 结果与指标展示
```

QPSK 仍可运行，但只保留作可靠字节链路对照，不再参与本轮优化。

## 链路分阶段说明

| 阶段 | 执行位置 | 处理内容 | 输出/验收点 |
|---|---|---|---|
| 1. 会话准入 | 上位机 + 飞腾派 | ML-KEM-768 建立密钥，SM4-GCM 保护控制信道；SM2 和 ML-DSA-65 双签认证板端 | Cockpit 显示加密、认证和板卡就绪 |
| 2. 图像编码 | 上位机 | 原图经 Deep JSCC encoder 得到 `float32` latent，当前形状通常为 `1x32x32x32` | latent manifest、编码进度 |
| 3. IQ 成帧 | 上位机 | latent 展平后按全局 RMS 归一化，每两个实数配成一个复数 I/Q 符号；加入 CFO、同步和中插导频，再做 RRC 成形和 `sc16` 转换 | 波形、manifest、名义空口时长 |
| 4. 无线发送 | 上位机 USRP | Docker 内常驻 TX server 使用 N210/USRP-2922 发射，默认 `500 MHz`、`5 Msps`、TX gain `25`、`TX/RX` 端口；Windows 以 bridge 直接发布 TCP 控制口 | TX server 状态、发送记录 |
| 5. 射频传播 | 两台 USRP 之间 | IQ 波形直接经过实际无线信道；这一段不经过 Tailscale | 频谱仪可观察中心频率和占用带宽 |
| 6. 无线接收 | 飞腾派 USRP | 常驻 RX server 使用 `192.168.10.22`、RX gain `15`、`RX2` 接收 `sc16` 样本 | 收样本数、timeout、capture 文件 |
| 7. IQ 恢复 | 飞腾派 | 零保护段估计 DC，随后做 RRC 匹配滤波、定时/同步、CFO 校正、复增益和相位跟踪，再还原 noisy latent | sync、pilot gain、EVM、SNR、decode 时间 |
| 8. 质量控制 | 上位机编排 + 飞腾派解码 | 质量门限拒绝弱同步或高误差帧；单图 ARQ、30 张分段和失败子集补传处理偶发漏帧 | accepted 数必须等于任务数，fallback 必须为 0 |
| 9. TVM 重建 | 飞腾派 | decoded latent 保存在 `/home/user/cockpit_usrp_rx/...`，handwritten TVM artifact 在大核 2 推理；小核 0、1 负责预取和 PNG 保存 | TVM core median/mean/p95、artifact SHA |
| 10. 结果展示 | 飞腾派 + 上位机 | 图片写入 `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/.../reconstructions`；Cockpit 更新三阶段进度、链路诊断和图片对比入口 | 重建目录、PSNR/SSIM、结果卡片 |

## 为什么 IQ 直传成立

Deep JSCC encoder 输出的是连续实数 latent，不是已经调制好的射频波形。IQ 直传把相邻两个 latent 值分别放入复符号的 I、Q 分量，让无线信道的幅度、相位和噪声直接作用在语义表示上。接收端允许 latent 有小幅模拟误差，再由生成器完成图像重建。

相比 QPSK，IQ 直传省掉了量化到可靠字节、QPSK 映射、CRC 校验和字节解包。不过它并非“不做处理”：导频、RRC、同步、CFO、信道增益估计、质量门限和重传仍然需要。当前质量优先配置的主要代价正是门限拒绝和 ARQ，而不是名义空口时长。

## 当前可靠性设计

- TX/RX 和 decode worker 常驻，避免每张图重复初始化 UHD 与 Python 运行时。
- 正式长批次按 30 张分段。段边界重建 RX streamer，TX streamer 保持常驻并清空旧状态。
- 单图最多 12 轮 ARQ；每段首轮失败项最多再做 2 轮子集补传。
- 默认门限为 sync metric `>= 0.75`、pilot gain ratio `>= 0.85`、EVM `<= 0.75`、估计 SNR `>= 3 dB`。
- RX 停滞后会关闭旧会话并向常驻 RX server 发送真实 `RESET`，不再只重连 TCP 控制口。
- 默认关闭 RF decode 与 TVM 的重叠流水线。真板测试中资源争用使总耗时和 p95 变差，串行路径的图像质量更稳定。
- Cockpit 显示前只建立板卡会话，拉起安全服务与常驻 USRP TX/RX，并等待服务就绪；启动阶段不发送图片。

## 指标应如何解释

| 指标 | 当前可用数字 | 含义 |
|---|---:|---|
| 单帧名义空口时长 | 约 `9.58 ms` | 只计算波形样本数除以 `5 Msps`，不含等待、同步、解码和重试 |
| IQ 传输/解包 | median `411.59 ms`，p95 `3423.45 ms` | 300 张严格可靠性 profile；长尾主要来自质量门限和 ARQ |
| TVM 核心推理 | median `245.42 ms`，mean `254.71 ms` | 300 张严格 profile；这是最接近“单张重建推理速度”的数字 |
| 历史全链路冷启动 | IQ `10/10`，TVM `10/10`，约 `99.6 s` | job `cockpit_usrp_usrp-1784286235`；这是旧图片预热方案的记录，不代表当前启动时间 |
| 预录 TVM 参考线 | median `243.30 ms`，mean `252.91 ms` | 不含 USRP，用于证明 handwritten + big.LITTLE 的约 250 ms 指标已恢复 |
| 100 张整批演示 | 点击到完成 `240.19 s` | 包含编码、261 次 OTA 尝试、板端解码、TVM 和图片保存 |
| QPSK 对照 | 约 `2.96 s/image` | 推荐入口默认的可靠字节链路，速度明显慢于 IQ-direct |

不要把 `243 ms` 写成“USRP 端到端单张时延”。它是 TVM 核心执行时间。整批演示时间还受上位机编码、RF 重试和 PNG 保存影响。

## 控制面、数据面与安全边界

Tailscale 承载 SSH、状态、控制命令、日志和结果拉取。真正的 latent/IQ 数据面走两台 USRP 之间的射频链路，不经过 Tailscale；板端解码后直接写入 remote-dir，也不会把原始 IQ capture 拉回上位机。

ML-KEM、SM4、ML-DSA 和 SM2 当前用于会话准入与控制信道。USRP IQ payload 不是 AEAD ciphertext。原因很直接：AEAD 要求 bit-exact 字节恢复，任意 bit 错误都会导致 tag 校验失败；模拟 JSCC 链路则依靠“允许小误差”换取更低的数据面开销。

答辩时可以说：“安全信道先认证设备并授权任务，语义数据面再通过 USRP 发送。”不能说“无线 IQ payload 已被 ML-KEM+SM4 加密”。

安全状态中的耗时字段也要按边界解释：`handshake_ms` 是建立会话的墙钟时间，受冷启动和服务复用影响；历史 `decrypt_ms` 还包含等待板端执行、网络接收和结果读取，不是纯 SM4-GCM 解密时间。USRP 模式只使用安全会话做准入，不能用这两个字段推导 IQ 数据面密码开销。

## 相关文档

- 现场操作见 [`runbooks/STARTUP.md`](./runbooks/STARTUP.md)。
- 安全信道部署见 [`security/mlkem_auth_setup.md`](./security/mlkem_auth_setup.md)。
- 输出目录见 [`USRP_OUTPUT_LAYOUT.md`](./USRP_OUTPUT_LAYOUT.md)。

## 当前可汇报进度

- IQ-direct 已接入 Cockpit；选择该链路时，认证和加密控制面仍默认开启。
- 300 张严格质量门限回归达到 `300/300` accepted，TVM 核心仍在约 245 ms。
- 修复了 RX 服务“端口仍在但 UHD 收不到样本”时只重连控制口的问题，现在会执行真实 RESET。
- 修复了板端 RX server 启动成功但 SSH 命令等待约 60 秒的问题，改为 `setsid -f` 后启动约 4.6 秒返回。
- 一键启动会在显示 UI 前确认板卡、安全服务和 USRP 控制端口就绪，不再运行隐藏图片任务。
- 上位机 TX 的 USRP UDP 数据面由本机 Docker 容器访问物理 USRP；Windows 通过 bridge 直接映射 `29221` TCP 控制口，Linux 默认使用 host network。这些本机链路均不经 Tailscale。
- 板端同步包已于 2026-07-17 重新生成并部署，关键文件 SHA-256 一致，`tvm310_safe` 运行时检查通过。
