# 文档索引

先看仓库根目录的 [`README.md`](../README.md)。首次初始化、日常启动和无硬件复现都从那里进入。

## 现场运行

| 文档 | 用途 |
|---|---|
| [`runbooks/STARTUP.md`](runbooks/STARTUP.md) | Windows 上位机冷启动、20 张演示和故障处理 |
| [`USRP_OUTPUT_LAYOUT.md`](USRP_OUTPUT_LAYOUT.md) | QPSK、IQ-direct 和预录任务的板端输出目录 |
| [`USRP_IQ_RUNTIME.md`](USRP_IQ_RUNTIME.md) | IQ-direct 的执行顺序、实测记录和限制 |

现场默认链路是 QPSK。IQ-direct 保留为可切换链路；两种模式共用 Cockpit、控制面认证和板端 TVM 重建。

## 技术说明

| 文档 | 内容 |
|---|---|
| [`USRP_LINK_BRIEFING.md`](USRP_LINK_BRIEFING.md) | 数据面、控制面和安全边界 |
| [`design/analog_latent_iq_phy.md`](design/analog_latent_iq_phy.md) | analog latent-IQ PHY 的波形处理 |
| [`security/mlkem_auth_setup.md`](security/mlkem_auth_setup.md) | ML-KEM、SM4-GCM、ML-DSA 与 SM2 的部署和密钥约束 |
| [`../board_deps/README.md`](../board_deps/README.md) | 板端离线依赖、校验和恢复材料 |
| [`../docker/README.md`](../docker/README.md) | 容器复现和兼容入口 |

`Semantic-Communication/session_bootstrap/reports/` 中保留的报告会被演示后端读取，不是普通的过程文档。旧计划、交接稿和材料修改意见已移到仓库外的归档索引。

## 口径

- ML-KEM、SM4-GCM、ML-DSA 和 SM2用于设备认证、任务准入及控制信道保护。
- USRP QPSK/IQ 数据走真实射频链路，不经过 Tailscale。
- 不把 USRP IQ payload 描述为 ML-KEM 或 SM4 密文。
- TVM 完成状态以后端任务结果为准；重建对比页按拉取到的图片实时计算 PSNR 和 SSIM。
