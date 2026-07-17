# USRP IQ 直传链路汇报口径

更新时间：2026-07-17

这份文档供今晚进度同步、PPT 修改和答辩准备使用。当前主演示路径已经固定为：

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
| 4. 无线发送 | 上位机 USRP | Docker host network 内常驻 TX server 使用 N210/USRP-2922 发射，默认 `500 MHz`、`5 Msps`、TX gain `25`、`TX/RX` 端口；Windows 只通过轻量代理访问 TCP 控制口 | TX server 状态、发送记录 |
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
- Cockpit 显示前严格预热 10 张，要求累计 `10/10` 完成；首轮不足时只补跑剩余数量，不降低质量门限。

## 指标应如何解释

| 指标 | 当前可用数字 | 含义 |
|---|---:|---|
| 单帧名义空口时长 | 约 `9.58 ms` | 只计算波形样本数除以 `5 Msps`，不含等待、同步、解码和重试 |
| IQ 传输/解包 | median `411.59 ms`，p95 `3423.45 ms` | 300 张严格可靠性 profile；长尾主要来自质量门限和 ARQ |
| TVM 核心推理 | median `245.42 ms`，mean `254.71 ms` | 300 张严格 profile；这是最接近“单张重建推理速度”的数字 |
| 最新一键冷启动 | IQ `10/10`，TVM `10/10`，约 `99.6 s` | job `cockpit_usrp_usrp-1784286235`；主机服务与容器全关后复现 |
| 预录 TVM 参考线 | median `243.30 ms`，mean `252.91 ms` | 不含 USRP，用于证明 handwritten + big.LITTLE 的约 250 ms 指标已恢复 |
| 100 张整批演示 | 点击到完成 `240.19 s` | 包含编码、261 次 OTA 尝试、板端解码、TVM 和图片保存 |
| QPSK 对照 | 约 `2.96 s/image` | 可靠字节链路，速度明显慢于 IQ 主线 |

不要把 `243 ms` 写成“USRP 端到端单张时延”。它是 TVM 核心执行时间。整批演示时间还受上位机编码、RF 重试和 PNG 保存影响。

## 控制面、数据面与安全边界

Tailscale 承载 SSH、状态、控制命令、日志和结果拉取。真正的 latent/IQ 数据面走两台 USRP 之间的射频链路，不经过 Tailscale；板端解码后直接写入 remote-dir，也不会把原始 IQ capture 拉回上位机。

ML-KEM、SM4、ML-DSA 和 SM2 当前用于会话准入与控制信道。USRP IQ payload 不是 AEAD ciphertext。原因很直接：AEAD 要求 bit-exact 字节恢复，任意 bit 错误都会导致 tag 校验失败；模拟 JSCC 链路则依靠“允许小误差”换取更低的数据面开销。

答辩时可以说：“安全信道先认证设备并授权任务，语义数据面再通过 USRP 发送。”不能说“无线 IQ payload 已被 ML-KEM+SM4 加密”。

## PPT 需要修改的内容

1. 主架构图改成控制面和数据面两条线。控制面标 Tailscale、ML-KEM+SM4、ML-DSA+SM2；数据面标 JSCC latent 和 USRP RF。
2. IQ 直传页补上 RMS 归一化、复数配对、导频、RRC、同步/CFO/增益恢复。不要画成 encoder 输出直接接天线。
3. 可靠性页写清常驻 TX/RX、30 张分段、ARQ12、两轮失败子集补传、质量门限和 RX RESET。
4. 性能页分四行展示空口、传输/解包、TVM core、整批墙钟。约 250 ms 只标在 TVM core 上。
5. TVM 页注明 handwritten artifact、SHA 匹配和大核 2 推理；小核 0、1 负责预取与保存。
6. 安全页明确控制/认证面准入边界，并解释为什么连续 IQ 数据面没有直接套 AEAD。
7. 演示流程页改成“上电与网口检查 -> 一键启动 -> 隐藏预热 10/10 -> 正式批次 -> 图片对比”。

## 书面材料需要同步的点

- 把“USRP 数据经过 Tailscale”改为“控制面经过 Tailscale，RF 数据面不经过”。
- 把“取消 QPSK 后不再需要同步和纠错”改为“取消字节级 QPSK/CRC，保留模拟同步、质量门限和 ARQ”。
- 指标表注明样本数、median/mean/p95 和统计边界。
- 图像质量同时说明原图-TVM与 PyTorch-TVM口径，不能把两组 PSNR/SSIM 混写。
- 写入默认频率 `500 MHz`、采样率 `5 Msps`、`sps=2`、TX/RX gain `25/15`，并注明现场天线位置和频谱环境会影响重试次数。
- 把 QPSK 定位为 fallback，不要删除或继续改动其主逻辑。

## 今晚可直接汇报的进度

- IQ 主链路已接入 Cockpit，默认认证、加密和 USRP IQ 直传均开启。
- 300 张严格质量门限回归达到 `300/300` accepted，TVM 核心仍在约 245 ms。
- 修复了 RX 服务“端口仍在但 UHD 收不到样本”时只重连控制口的问题，现在会执行真实 RESET。
- 修复了板端 RX server 启动成功但 SSH 命令等待约 60 秒的问题，改为 `setsid -f` 后启动约 4.6 秒返回。
- 一键启动改为累计预热 `10/10` 才显示 UI；首轮不足时只补跑剩数量。最新全关后冷启动约 `99.6 s` 通过。
- 上位机 TX 的 USRP UDP 数据面改走 Docker host network；只有 `29221` TCP 控制命令经轻量代理返回 Windows。这两段都不经 Tailscale。
- 板端同步包已于 2026-07-17 重新生成并部署，关键文件 SHA-256 一致，`tvm310_safe` 运行时检查通过。
