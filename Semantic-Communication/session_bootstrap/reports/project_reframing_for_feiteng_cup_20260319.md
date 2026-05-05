# 飞腾杯项目重构说明（2026-03-19）

## 一句话定位

本项目当前对外应统一定位为：

> **一个面向弱网场景的飞腾多核安全语义视觉回传系统：上位机负责语义编码与传输，飞腾 Linux 侧负责高性能重建，OpenAMP/RTOS 负责异构控制面与安全执行边界。**

## 两种 operating modes

### 1. 4-core Linux performance mode

- 用途：对外性能 headline、系统吞吐能力、TVM current 的主结果。
- 推荐数字：
  - TVM serial current: `231.522 ms/image`
  - TVM big.LITTLE pipeline current: `134.617 ms/image`
  - same-run uplift: `56.077%`
  - PyTorch default reference: `484.183 ms/image`
- 证据入口：
  - `session_bootstrap/reports/big_little_compare_20260318_123300.md`
  - `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`
  - `session_bootstrap/reports/big_little_real_run_summary_20260318.md`
  - `session_bootstrap/reports/pytorch_default_reference_source_20260319.md`（归档后）
- 解释方式：这是“性能模式”，强调飞腾多核上的高性能重建能力，不把 OpenAMP 说成加速来源。

### 2. 3-core Linux + RTOS demo mode

- 用途：答辩演示、安全控制面、OpenAMP 最小闭环、FIT 证据。
- 关键事实：
  - OpenAMP control plane 已经存在且有板级闭环证据；
  - `remoteproc0=running` 时，日志可见 `CPU3: shutdown` / `psci: CPU3 killed`，Linux 在线核从 `0-3` 变为 `0-2`；
  - 因此该模式必须诚实表述为 **3-core Linux + RTOS**，不是“仍然完整 4-core Linux 的同态模式”。
- 证据入口：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
  - `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log`
- 解释方式：这是“演示 / 安全模式”，强调 admission、heartbeat、safe stop、fault handling，不拿来背书 headline performance。

## 应该主张什么

- 应主张这是一个 **飞腾多核弱网安全语义视觉回传系统**，而不是单点推理框架调优。
- 应主张 `4-core Linux performance mode` 下的 TVM headline：
  - serial current `231.522 ms/image`
  - pipeline current `134.617 ms/image`
  - uplift `56.077%`
  - PyTorch default reference `484.183 ms/image`
- 应主张 `3-core Linux + RTOS demo mode` 下的 OpenAMP control plane 已有板级闭环、FIT 和 live evidence。
- 应主张系统采用 **data plane / control plane separation**：
  - Linux/TVM 负责高性能数据面；
  - OpenAMP/RTOS 负责安全控制面。

## 不应该主张什么

- 不应再把项目主叙事写成“TVM/MNN 优化项目”。
- 不应宣称 OpenAMP / RTOS 让 TVM 推理更快。
- 不应把 `4-core Linux performance mode` 的数字和 `3-core Linux + RTOS demo mode` 的数字混写在同一张对比图里而不标 mode。
- 不应忽略 `remoteproc` 的 CPU 代价，或暗示 control plane 是零成本。
- 不应主张超出当前证据边界的能力，例如：
  - `RESET_REQ/ACK`
  - `FIT-04/05`
  - deadline enforcement 全量收口
  - “OpenAMP 承担大张量数据搬运”

## 建议对外 closing sentence

> 我们当前展示的不是一个 generic benchmark，而是一套在飞腾平台上可落地的系统方案：4-core Linux mode 提供多核高性能语义视觉重建，3-core Linux + RTOS mode 提供 OpenAMP 安全控制面与可审计执行边界，两者共同组成弱网场景下的飞腾多核安全语义视觉回传系统。
