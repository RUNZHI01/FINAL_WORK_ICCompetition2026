# 文档索引

初始化、启动和无硬件复现从仓库根目录的 [`README.md`](../README.md) 开始。现场操作只需查看 [`scripts/demo/STARTUP.md`](../scripts/demo/STARTUP.md)。

## 运行说明

| 文档 | 内容 |
|---|---|
| [`../scripts/demo/STARTUP.md`](../scripts/demo/STARTUP.md) | Windows 冷启动、20 张演示和故障处理 |
| [`USRP_OUTPUT_LAYOUT.md`](USRP_OUTPUT_LAYOUT.md) | QPSK、IQ-direct 和预录任务的板端输出目录 |
| [`USRP_IQ_RUNTIME.md`](USRP_IQ_RUNTIME.md) | IQ-direct 执行顺序、实测数据和已知限制 |
| [`../board_deps/README.md`](../board_deps/README.md) | 板端离线依赖、校验和恢复方式 |
| [`../docker/README.md`](../docker/README.md) | 容器复现、板端 smoke 和维护入口 |

## 技术说明

| 文档 | 内容 |
|---|---|
| [`USRP_LINK_BRIEFING.md`](USRP_LINK_BRIEFING.md) | QPSK、IQ-direct、控制面和安全边界 |
| [`design/analog_latent_iq_phy.md`](design/analog_latent_iq_phy.md) | Analog latent-IQ PHY 的帧结构和解码流程 |
| [`security/mlkem_auth_setup.md`](security/mlkem_auth_setup.md) | ML-KEM、SM4-GCM、ML-DSA 与 SM2 的部署和密钥约束 |

## 统一口径

- 默认现场链路是 QPSK，IQ-direct 是可切换链路。
- ML-KEM、SM4-GCM、ML-DSA 和 SM2 保护控制信道、设备认证和任务准入。
- QPSK/IQ 数据面走两台 USRP 之间的射频链路，不经过 Tailscale。
- USRP IQ payload 不是 ML-KEM 或 SM4 密文。
- 首页固定 PSNR/SSIM 与右下角实时重建对比是两组不同指标。

`Semantic-Communication/session_bootstrap/reports/` 中仍被程序读取的 JSON 和日志属于运行数据，不作为阅读入口。
