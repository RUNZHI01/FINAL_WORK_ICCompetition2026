# OpenAMP 控制面演示证据说明

- package_date: `2026-03-15`
- mode: `evidence-first`
- goal: `说明 OpenAMP 控制面、FIT 验证和语义重建数据面的证据关系`

## 1. 验证范围

本文件只作为证据说明，不包含现场流程、展示顺序或讲解建议。当前证据包覆盖以下事实：

- 飞腾派上的 OpenAMP 控制固件可以完成 remoteproc / RPMsg bring-up。
- Linux 侧 wrapper 可以基于 firmware `JOB_ACK` 决定是否放行 runner。
- `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT/HEARTBEAT_ACK`、`SAFE_STOP`、`JOB_DONE` 已形成最小控制闭环。
- `FIT-01`、`FIT-02`、`FIT-03` 已有真机证据，其中 `FIT-03` 保留了修复前失败与修复后通过的历史。
- TVM/MNN/PyTorch 性能复现由 `board_deps/scripts/run-isolated-cli-smoke.sh` 和 `docker/run-board-cli-smoke.*` 负责。

## 2. 证据分组

| 分组 | 说明 | 主证据 |
|---|---|---|
| 板级 OpenAMP 状态 | 固件加载、remoteproc、RPMsg channel、userspace demo 路径 | [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md) |
| 最小控制闭环 | 状态查询、作业准入、心跳、停止、完成 | [coverage_matrix.md](coverage_matrix.md) |
| FIT 验证 | 错误 SHA、输入契约违规、心跳超时 watchdog | [coverage_matrix.md](coverage_matrix.md) |
| 语义重建性能 | current / baseline 对照和板端 CLI smoke 口径 | [../../../../board_deps/README.md](../../../../board_deps/README.md) |

## 3. 边界

当前证据包不声明以下能力已经完成：

- `FIT-04` / `FIT-05`
- `RESET_REQ/ACK`
- sticky fault reset
- deadline enforcement
- OpenAMP 控制面对 TVM/MNN/PyTorch 数据面速度的直接加速

OpenAMP 在本仓库中的定位是控制面、安全准入、心跳与状态收敛；性能数字来自数据面运行时与模型产物。
