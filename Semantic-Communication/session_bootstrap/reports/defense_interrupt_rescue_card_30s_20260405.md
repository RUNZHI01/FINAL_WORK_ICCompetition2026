# 飞腾杯答辩 30 秒打断救场卡（2026-04-05）

- 用途：老师打断、时间被砍、只允许补一句时使用
- 原则：只答一个结论，不展开过程，不引入新数字
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## 场景 1：老师说“你先别展开，直接说你们最核心的结果”

- 30 秒答法：
  - “我们最核心的结果有三条：第一，`4-core Linux` 模式下把端到端重建从 `1850.0 ms` 压到 `230.3 ms`，流水线进一步到 `134.6 ms`；第二，`3-core Linux + RTOS` 模式下把 OpenAMP 控制面和安全停机做成真机闭环；第三，`MNN` 补上了混合尺寸灵活部署。所以这不是单点 benchmark，而是一件完整的飞腾系统作品。”
- 若还能补一句：
  - “性能、控制、安全和灵活部署这四条线是同时成立的。”

## 场景 2：老师说“别讲系统了，直接说性能”

- 30 秒答法：
  - “性能只看 `4-core Linux performance mode`。这条主口径里，我们把单张图像端到端时间从 `1850.0 ms` 压到 `230.3 ms`，进一步用 `big.LITTLE` 流水线压到 `134.6 ms`。这部分提升来自 `TVM` 主线和异构流水线，不来自 OpenAMP。”
- 若还能补一句：
  - “如果老师要 exact source，我马上切 truth table。”

## 场景 3：老师说“OpenAMP 到底证明了什么”

- 30 秒答法：
  - “OpenAMP 证明的不是加速，而是控制边界。我们已经在真机上打通了 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE`，并收口了错误 SHA、非法参数和心跳超时这三项 FIT，所以这条高性能链路不是裸奔的。”
- 若还能补一句：
  - “我们主动把它和 4 核性能模式分开讲，就是为了避免 mode mixing。”

## 场景 4：老师说“你们的创新点到底是什么”

- 30 秒答法：
  - “我们的创新点不是某一个算子更快，而是把飞腾多核性能、`OpenAMP + RTOS` 控制安全、以及 `TVM + MNN` 双部署路径收成了一套可演示、可追问、可落证的系统。换句话说，我们做的是系统级创新，不是单点优化堆料。”
- 若还能补一句：
  - “这也是为什么我们论文里会同时保留性能页、控制页和证据包结构页。”

## 场景 5：老师说“我现在就想看证据”

- 30 秒答法：
  - “如果老师看性能，我先开 `award_rescue_metric_truth_table_20260319.md`；如果看 OpenAMP，我先开 `openamp_control_plane_evidence_package_20260315/summary_report.md` 和 `coverage_matrix.md`；如果看系统总览，我直接回论文 `图 5.2` 和 `图 5.3`。”
- 若还能补一句：
  - “我们的原则是每个结论都能立刻跳到对应证据，不靠现场口说。”

## 场景 6：老师说“只给你最后 20 秒”

- 20 秒答法：
  - “我们不主张 OpenAMP 让模型更快；我们主张的是，`4-core Linux` 模式把飞腾多核性能做实了，`3-core Linux + RTOS` 模式把控制和安全边界做实了，`TVM + MNN` 又把固定形状和混合尺寸两条部署路径补齐了，这三条线合起来就是这件作品的系统价值。”

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
