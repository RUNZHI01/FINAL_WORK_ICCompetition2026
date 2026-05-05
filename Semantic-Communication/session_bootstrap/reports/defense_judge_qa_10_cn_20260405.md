# 飞腾杯答辩评委追问速答卡（10 问 10 答，2026-04-05）

- 用途：评委追问时的现场速答，不替代正式讲稿
- 使用原则：先给一句短答，再补一句边界，最后再跳证据
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## 1. 你们到底是在做语义通信系统，还是只是在做 TVM 优化？

- 短答：我们做的是一套飞腾多核异构安全语义图像回传系统，`TVM` 只是其中的数据面主路径之一。
- 展开一句：上位机负责语义编码和信道扰动模拟，飞腾侧负责重建，`RTOS + OpenAMP` 负责控制与安全，所以这不是单点 benchmark。
- 不能说：`我们主要就是把 TVM 跑快了`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 1.3`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 5.3`

## 2. 为什么你们一定要分成两种 operating mode 来讲？

- 短答：因为 `remoteproc` 拉起 `RTOS` 后会占用一个 Linux CPU，所以演示模式和性能模式不是同一个板态。
- 展开一句：`4-core Linux performance mode` 只负责性能主口径，`3-core Linux + RTOS demo mode` 只负责 OpenAMP 控制面、安全和演示闭环，这两组数字不能混写。
- 不能说：`这些数字都是同一种 mode 下测出来的`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 3.3`
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`

## 3. OpenAMP 到底带来了什么？是不是它让 TVM 更快了？

- 短答：不是。OpenAMP 的价值是让系统可准入、可监护、可安全停机，不是让模型更快。
- 展开一句：性能提升来自 `TVM` 主线和 `big.LITTLE` 流水线；OpenAMP 负责 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE` 这些控制能力。
- 不能说：`OpenAMP 带来了性能加速`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 3.1`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`

## 4. 你们是不是拿图像质量换了速度？

- 短答：没有。我们的主结果是“更快，同时质量保持在可接受且稳定的区间”。
- 展开一句：论文主口径里，`TVM` 主线把端到端重建时间从 `1850.0 ms/image` 压到 `230.3 ms/image`，`big.LITTLE` 进一步到 `134.6 ms/image`；同时图像质量指标维持在 `PSNR 35.66 dB / SSIM 0.9728`。
- 不能说：`我们没测质量，但肉眼看起来差不多`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 4.11`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 4.5`

## 5. 为什么要同时保留 TVM 和 MNN？是不是说明 TVM 没做好？

- 短答：不是。两者承担的是不同部署任务，不是互相替代关系。
- 展开一句：`TVM` 负责固定形状的极致性能主路径，`MNN` 负责混合尺寸图像的灵活部署旁路；当前 `MNN` 在 `300` 张混合尺寸图像上是 `98.2 秒 / 327.3 ms/image`，优势是无需预缩放。
- 不能说：`MNN 比 TVM 更快，所以我们换主线了`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 4.10`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 4.8`

## 6. 既然你们在做优化，为什么没有把 INT8 / FP16 做成主结果？

- 短答：因为当前板态下这条线的 ROI 不高，实测也没有赢过正式最优配置。
- 展开一句：这块板上我们没有看到足够强的 `FP16 / INT8` 硬件加速路径，当前论文里也已经写明 `low precision` 配置实测为 `99.1 秒`，没有优于正式最优的 `98.2 秒`，所以我们没有把量化讲成主结果。
- 不能说：`板卡完全不支持，所以我们一点都没试`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 第 `4.2` 节 `MNN` 小节
  - `session_bootstrap/logs/smoke_mnn_matrix_20260404.log`

## 7. 手写算子优化你们到底做了没有？

- 短答：做了，而且保留了有正收益的算子版本，但没有继续把它当成当前最高优先级主线。
- 展开一句：项目里已经保留了正收益 lane，例如 `transpose1 v7 (-1.97%)` 和 `variance4 v18 (-0.99%)`；后续决定是暂停继续深挖，先把 Demo 和 OpenAMP 主线收口。
- 不能说：`我们已经把所有关键算子都手写优化完了`。
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 第 `4.1.2` 节
  - `session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md`

## 8. 你们的 OpenAMP 测试是不是都跑通了？

- 短答：当前正式 claim 范围内，`P0` 和 `FIT-01 / FIT-02 / FIT-03` 都已收口；但 `TC-010` 不能讲成已完成。
- 展开一句：`TC-002` 已由真实 `300/300` reconstruction live 证据收口；`TC-010` 仍属于 `RESET_REQ/ACK` 和 sticky fault reset 的后续扩展，我们没有把它 overclaim 成当前正式能力。
- 不能说：`TC-001 到 TC-010 现在已经全部正式跑通`。
- 立刻跳转：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

## 9. 你们为什么有很多性能数字？到底哪个才是正式对外口径？

- 短答：正式对外口径只认带 `mode tag` 的数字，而且不同 mode 的数字不能混写。
- 展开一句：性能页只用 `4-core Linux performance mode` 下的 `1850.0 / 230.3 / 134.6 ms`；OpenAMP 演示页只用 `3-core Linux + RTOS demo mode` 的 live 事实；如果评委追问 exact source，我们直接翻 truth table。
- 不能说：`这些数字差不多，哪个顺手就讲哪个`。
- 立刻跳转：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
  - `session_bootstrap/reports/defense_talk_track_3min_20260405.md`

## 10. 如果我现在就要看你们的证据包，你们先点哪里？

- 短答：先点总报告，再点 coverage matrix，最后按问题切到专项报告。
- 展开一句：如果问性能，就去 `truth table`；如果问控制面，就去 `OpenAMP summary_report` 和 `coverage_matrix`；如果问系统总览，就回论文 `图 5.2` 和 `图 5.3`。
- 不能说：`证据比较散，我们现场翻一翻`。
- 立刻跳转：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 5.2`

## 收口句

- 如果评委只给一句话时间，统一答法：
  - `4-core Linux performance mode` 证明飞腾多核性能成立。
  - `3-core Linux + RTOS demo mode` 证明 OpenAMP 控制边界成立。
  - `TVM + MNN` 共同证明系统既能跑固定形状极致性能，也能承担混合尺寸灵活部署。

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_ppt_pages_1_5_cn_20260405.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
