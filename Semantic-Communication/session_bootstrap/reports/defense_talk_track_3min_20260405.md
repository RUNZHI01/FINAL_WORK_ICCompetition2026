# 飞腾杯 3 分钟压缩答辩讲稿（2026-04-05）

- 用途：3 分钟标准口播版；介于现有 `2 分钟压缩版` 和 `5 分钟完整版` 之间
- 讲法顺序：系统定位 -> 双模式边界 -> 性能结果 -> 安全控制 -> 系统结论
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## 口播正文（约 3 分钟）

“各位老师，我们今天展示的，不是一个单点 TVM 调优项目，而是一套**飞腾多核异构安全语义图像回传系统**。它面向的是弱网巡检和应急场景：上位机先做语义编码和信道扰动模拟，飞腾侧再完成图像重建；同时，我们没有把系统做成一条裸奔的数据链，而是额外补上了 OpenAMP 控制面，让这条执行链可准入、可监护、可安全停机。

这套系统必须分两种模式来讲。第一种是 **4-core Linux performance mode**，它只负责性能主口径；第二种是 **3-core Linux + RTOS demo mode**，它只负责演示和安全控制。为什么必须拆开？因为 `remoteproc` 拉起 RTOS 后，会占用一个 Linux CPU，所以 demo mode 不能再被表述为完整 4 核 Linux。我们主动把这两种模式拆开，就是为了避免 mode mixing。

先看性能模式。在 4 核 Linux 模式下，TVM 主线把单张图像端到端重建时间从 **1850.0 ms** 压到 **230.3 ms**；进一步做 big.LITTLE 异构流水线之后，单张中位时间又压到 **134.6 ms**。这说明飞腾多核上的固定形状主路径已经做实了，而且性能提升来自 TVM current 和流水线本身，不来自 OpenAMP。

再看灵活部署这条线。我们保留了 MNN 作为动态尺寸旁路，在 300 张不同尺寸图像上的端到端总耗时是 **98.2 秒**，平均 **327.3 ms/image**。所以系统不是只追一条最快路径，而是固定形状用 TVM，动态尺寸用 MNN，各自承担不同部署任务。

最后看安全控制。OpenAMP 这条线的价值不是让模型更快，而是证明这条高性能路径不是裸奔的。当前真机证据已经覆盖 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE` 五类消息；同时三项 FIT 已正式收口，分别证明错误 SHA 会被拒绝、非法参数会被拒绝、heartbeat timeout 会触发安全收敛，而且 `FIT-03` 保留了‘发现缺口 -> 修复 -> 复验通过’的完整链路。

所以我们的最终主张很简单：**4-core Linux performance mode** 证明飞腾多核性能成立，**3-core Linux + RTOS demo mode** 证明 OpenAMP 控制面和安全边界成立，MNN 则补上动态尺寸灵活部署。三条线合起来，才是这次作品真正的系统价值。”

## 5 张核心页顺序

1. `图 1.3` 摘要图：先把系统身份定死。
2. `图 3.3` 双模式边界图：主动拆开 performance mode 和 demo mode。
3. `图 5.1` 性能跃迁图：只讲 `1850.0 -> 230.3 -> 134.6 ms/image`。
4. `图 3.1` 状态机或 `图 5.2` 证据包结构图：说明安全控制面不是口头承诺。
5. `图 5.3` 系统闭环总览图：收成“传得回、跑得快、用得稳”。

## 被打断时的 20 秒收尾

“我们不主张 OpenAMP 让 TVM 更快；我们主张的是，4 核 Linux 模式把飞腾多核性能做实了，3 核 Linux + RTOS 模式把控制和安全边界做实了，MNN 又补上了动态尺寸部署。这三条线合起来，才是这件作品的系统价值。”

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_2min_20260320.md`
- `session_bootstrap/reports/defense_talk_track_5min_20260320.md`
- `session_bootstrap/reports/defense_ppt_pages_1_8_cn_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
