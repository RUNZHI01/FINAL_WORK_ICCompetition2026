# 飞腾杯 2 分钟压缩答辩讲稿（2026-03-20）

- 用途：被打断时的压缩版口播；或今晚排练时先走 2 分钟，再展开 5 分钟版
- 讲法顺序：定位 -> 双模式 -> 性能 -> 安全 -> 收尾
- 红线：不把 OpenAMP 说成加速来源；不混写两种 operating mode

## 口播正文（约 2 分钟）

“各位老师，我们今天展示的，不是一个 generic TVM 调优项目，而是一套**飞腾多核弱网安全语义视觉回传系统**。在这个系统里，上位机负责语义编码与传输，飞腾侧负责高性能重建，同时用 OpenAMP/RTOS 给执行链补上可审计的控制边界。

这套系统必须分成两种 operating mode 来讲。第一种是 **4-core Linux performance mode**，它只负责性能 headline；第二种是 **3-core Linux + RTOS demo mode**，它只负责答辩演示和安全控制面。我们为什么要明确拆开？因为 `remoteproc0=running` 时，RTOS 控制面会占掉一个 Linux CPU，日志上会看到 Linux 在线核从 `0-3` 变成 `0-2`，所以这两种模式不能混写。

先看性能模式。在当前批准的 rescue 口径里，PyTorch default 对照锚点是 **484.183 ms/image**；健康板态、同轮 apples-to-apples compare 下，TVM serial current 是 **231.522 ms/image**；进一步做 big.LITTLE pipeline 后，current 降到 **134.617 ms/image**，相对同轮 serial current 的吞吐 uplift 是 **56.077%**。这说明飞腾多核上的 trusted current 数据面已经给出了可信 headline performance。

再看 demo mode。OpenAMP 的价值不是让模型更快，而是证明这条高性能路径不是裸奔的。当前真机证据已经覆盖 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT_ACK`、`SAFE_STOP` 和 `JOB_DONE`，三项正式 FIT 也已经收口：错误 SHA 会被拒绝，非法参数会被拒绝，heartbeat timeout 保留了 fail -> fix -> pass 的完整链路。最近 live 状态还确认，**8115** 这块板上 `current` 和 `baseline` 双路径都完成过 **300/300**。这部分当前只作为 `TC-002` 的 live reconstruction 收口；`TC-010` 对应的 `RESET_REQ/ACK` 和 sticky fault reset 仍不在本轮正式 claim。

所以我们的最终主张很简单：**4-core Linux performance mode** 证明飞腾多核性能成立，**3-core Linux + RTOS demo mode** 证明 OpenAMP 安全控制面成立。性能和安全分模式成立，合起来才是这次作品的系统价值。”

## 必说数字

- `4-core Linux performance mode`: `484.183 -> 231.522 -> 134.617 ms/image`，`+56.077%`
- `3-core Linux + RTOS demo mode`: `8115`，`current 300/300`，`baseline 300/300`

## 被打断时的 20 秒收尾

“我们不主张 OpenAMP 让 TVM 更快；我们主张的是，两种 operating mode 分别把性能和安全做实了。4-core Linux mode 给出 `484.183 -> 231.522 -> 134.617 ms/image`，3-core Linux + RTOS mode 给出 OpenAMP 控制闭环和 FIT 证据；其中 `300/300` 只用于收口 `TC-002`，不把 `TC-010` 说成已经闭环，这两条线合起来才是飞腾系统作品。”

## 对齐依据

- `session_bootstrap/reports/defense_talk_track_5min_20260320.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md`
- `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
