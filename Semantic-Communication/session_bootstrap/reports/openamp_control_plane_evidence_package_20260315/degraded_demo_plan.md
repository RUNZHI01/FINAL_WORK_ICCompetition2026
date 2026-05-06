# OpenAMP 控制面离线验证说明

- package_date: `2026-03-15`
- mode: `evidence-first`
- purpose: `说明在无板卡或板卡不可达时仍可核验的证据范围`

## 1. 可核验证据

无板卡环境下可以核验以下内容：

- Docker 镜像构建、依赖检查、Python 最小测试集、API smoke、Electron smoke。
- prerecorded 重建图像是否为真实样例而非占位图。
- OpenAMP 控制面历史证据、覆盖矩阵和 FIT 摘要。
- `board_deps/` 中板端运行时、模型、输入和固件产物的完整性。

## 2. 需要板卡的验证

以下内容需要飞腾派、Tailscale 网络和板卡 SSH 访问：

- 原生 Electron 真机链路。
- TVM/MNN/PyTorch 三路 CLI 性能复现。
- 板端 firmware / DTB 安装或替换。

## 3. 边界

无板卡验证只能证明源码包、镜像、预录 UI、API 和证据文件自洽；它不替代板端性能复现，也不产生新的真机 FIT 结论。

板端性能复现的唯一推荐入口是：

- Windows PowerShell: `docker/run-board-cli-smoke.ps1`
- Linux / WSL: `docker/run-board-cli-smoke.sh`

默认每条路径处理 300 个输入，并在板端隔离目录中写出 `logs/demo-kpi-summary.json`。
