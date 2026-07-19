# USRP 链路与安全边界

系统支持 QPSK 和 IQ-direct 两种 USRP 数据面。`.\demo.ps1` 默认选择 QPSK；IQ-direct 用于连续 latent 的模拟传输实验。

```text
Cockpit
  -> 上位机 JSCC 编码
  -> USRP 射频链路
  -> 飞腾派 latent 恢复
  -> TVM 重建
  -> Cockpit 结果展示
```

## 两种数据面

| 项目 | QPSK | IQ-direct |
|---|---|---|
| 输入 | 量化后的可靠字节 | 连续 latent |
| 无线表示 | QPSK 符号 | latent 的 I/Q 分量 |
| 完整性 | CRC、ARQ 和字节解包 | 同步、导频、质量门限和 ARQ |
| 误差模型 | 成功帧按字节恢复 | 允许 latent 保留小幅模拟误差 |
| 现场用途 | 默认演示链路 | 可切换实验链路 |

IQ-direct 仍需要 RRC、同步、CFO 校正、信道增益估计和重传。它省去的是可靠字节封装和 QPSK 映射，不是所有物理层处理。

## 执行位置

| 阶段 | 位置 | 输出 |
|---|---|---|
| 会话准入 | 上位机与飞腾派 | ML-KEM 会话、SM2/ML-DSA 双签状态 |
| JSCC 编码 | 上位机 | `float32` latent |
| 成帧和发送 | 上位机与 TX USRP | SC16 波形、发送记录 |
| 接收和恢复 | RX USRP 与飞腾派 | decoded latent、同步和质量摘要 |
| TVM 重建 | 飞腾派 | PNG、推理统计和任务结果 |
| 结果展示 | 上位机 | 进度、PSNR/SSIM 和重建对比 |

IQ-direct 的详细帧结构和参数见 [`design/analog_latent_iq_phy.md`](design/analog_latent_iq_phy.md)，运行数据见 [`USRP_IQ_RUNTIME.md`](USRP_IQ_RUNTIME.md)。

## 控制面和数据面

Tailscale 承载 SSH、状态、控制命令、日志和结果拉取。latent/IQ 数据由两台 USRP 通过真实射频链路传输，不通过 Tailscale 文件传输。

ML-KEM 建立会话材料，SM4-GCM 保护控制消息，ML-DSA 与 SM2 用于设备身份认证和任务准入。USRP IQ payload 不是 AEAD ciphertext，因为 AEAD 要求 bit-exact 恢复，而模拟 JSCC 允许 latent 带有误差。

准确表述是：

> 安全信道先认证设备并授权任务，语义数据面再通过 USRP 发送。

不要表述为“无线 IQ payload 已由 ML-KEM 和 SM4 加密”。`handshake_ms` 是会话建立的墙钟时间；历史 `decrypt_ms` 还可能包含板端等待、网络接收和结果读取，二者都不能作为 IQ 数据面密码算法耗时。

## 指标说明

- TVM kernel median 约 `245 ms`，表示板端单张重建核心执行时间，不是 USRP 端到端时延。
- IQ-direct 的空口时间约 `9.58 ms`，未包含等待、同步、解码和重试。
- QPSK 实测约 `2.96 s/image`，作为可靠字节链路使用。
- 首页 PSNR/SSIM 在 USRP TVM 任务成功后显示固定 300 张审计均值；右下角重建对比工具按当前拉取图片实时计算。

## IQ-direct 可靠性配置

- TX/RX 和 decode worker 常驻。
- 长批次按 30 张分段，段间重建 RX streamer。
- 单图支持 ARQ，失败子集最多补传两轮。
- 默认门限为 sync metric `0.75`、pilot gain ratio `0.85`、EVM `0.75`、估计 SNR `3 dB`。
- RX 停滞时向常驻服务发送 `RESET`，不只重连 TCP 控制口。
- 默认关闭 RF decode 与 TVM 的重叠流水线。
- 启动阶段只建立会话和常驻服务，不发送图片。

## 相关文档

- 现场操作：[`../scripts/demo/STARTUP.md`](../scripts/demo/STARTUP.md)
- 输出目录：[`USRP_OUTPUT_LAYOUT.md`](USRP_OUTPUT_LAYOUT.md)
- 安全信道：[`security/mlkem_auth_setup.md`](security/mlkem_auth_setup.md)
