# 飞腾杯 5 分钟答辩讲稿（2026-03-20）

- 用途：今晚队内排练的 5 分钟口播版
- 讲法原则：先讲系统定位，再讲双模式，再讲性能与安全；不把 OpenAMP 说成性能加速来源

## 开场钩子（约 30 秒）

“各位老师，我们今天展示的，不是一个 generic TVM 调优项目，而是一套**飞腾多核弱网安全语义视觉回传系统**。这套系统解决的是弱网条件下的视觉语义回传问题：上位机先做语义编码和传输，飞腾侧负责高性能重建，同时我们还给这条执行链补上了可审计的安全控制面。今天我会用 5 分钟把两件事讲清楚：第一，飞腾多核上它确实更快；第二，这个更快的执行链不是裸奔的，而是有 OpenAMP 控制边界的。” 

## 问题（约 35 秒）

“这个题目不能只讲模型跑得快。真实场景是弱网、边缘和受限带宽，回传的不是原始像素，而是更紧凑的语义信息；飞腾侧要把它可靠地重建出来。所以系统目标有两个：一是把飞腾多核算力真正用起来，二是让执行过程具备准入、监护和安全停止能力。这也是为什么我们最后把项目重构成系统叙事，而不是继续讲成单点 benchmark。” 

## 系统定义（约 45 秒）

“我们的系统是**数据面和控制面分离**的。数据面保持现有可信链路：上位机负责语义编码与传输，飞腾 Linux 侧运行 trusted current TVM 重建路径。控制面则交给 OpenAMP 和 RTOS，它不搬大张量，不重写推理链路，而是负责 admission、heartbeat、safe stop 和 fault accounting。换句话说，Linux/TVM 负责把结果做出来，OpenAMP/RTOS 负责保证这条高性能路径在可控、可拒绝、可监护的边界内运行。” 

## 两种模式解释（约 50 秒）

“这里最关键的是，我们明确拆成两种 operating mode。第一种是 **4-core Linux performance mode**，这条线只负责性能 headline。第二种是 **3-core Linux + RTOS demo mode**，这条线只负责答辩演示和安全控制面。为什么必须拆开？因为当 `remoteproc0=running` 时，RTOS 控制面会占掉一个 Linux CPU，日志上会看到 Linux 在线核从 `0-3` 变成 `0-2`。所以我们非常明确地告诉评委：demo mode 是真实存在的，但它不是 4 核纯 Linux 性能模式，两个模式不能混写。” 

## 性能亮点（约 60 秒）

“先看性能模式，也就是 4-core Linux performance mode。在当前批准的 rescue 口径里，PyTorch default 对照锚点是 **484.183 ms/image**。在健康板态、同轮 apples-to-apples compare 下，TVM serial current 是 **231.522 ms/image**；进一步做 big.LITTLE pipeline 之后，current 降到 **134.617 ms/image**，相对同轮 serial current 的吞吐 uplift 是 **56.077%**。这页结论只说明一件事：飞腾多核上的 trusted current 数据面已经给出了可信 headline performance。这里我们主动强调，**OpenAMP 不是加速来源**，性能提升来自 TVM current 和 big.LITTLE pipeline 路径本身。” 

## 控制面与安全亮点（约 85 秒）

“再看 demo mode，也就是 3-core Linux + RTOS。OpenAMP 这条线的价值不是让模型更快，而是证明这条高性能执行链有安全控制边界。当前真机证据已经覆盖了 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT_ACK`、`SAFE_STOP` 和 `JOB_DONE`。其中一个关键证据是 wrapper-backed board smoke，它证明 Linux wrapper 不是自己伪造放行，而是基于真实 firmware 的 `JOB_ACK(ALLOW)` 才让 runner 继续执行。最新 live 状态还确认，8115 这块板上 current 和 baseline 双路径都已经完成过 `300/300`，说明这不是离线 mock，而是真实在线系统。这里对外只把它当作 `TC-002` 的 live reconstruction 收口，证明正常作业闭环已经有真机证据；`TC-010` 对应的 `RESET_REQ/ACK` 和 sticky fault reset 仍明确不在本轮正式 claim 内。再往前一步，我们还有三项正式 FIT：错误 SHA 会被 admission gate 拒绝，非法参数会被 contract gate 拒绝，heartbeat timeout 则保留了 **fail -> fix -> pass** 的完整历史链。也就是说，我们不是只展示一个能收发消息的 OpenAMP demo，而是在展示一个**可准入、可拒绝、可监护、可安全停止**的最小控制闭环。” 

## 收尾（约 35 秒）

“所以最后一句话，我们主张的不是‘OpenAMP 让 TVM 更快’，也不是‘这只是一个框架优化项目’。我们主张的是：这是一套**飞腾多核弱网安全语义视觉回传系统**。在 **4-core Linux performance mode** 下，它给出了 `484.183 -> 231.522 -> 134.617 ms/image` 的清晰性能层次和 `56.077%` 的同轮吞吐提升；在 **3-core Linux + RTOS demo mode** 下，它给出了 OpenAMP 控制面、FIT 和板级闭环证据。性能和安全分模式成立，合起来才是这次作品的系统价值。” 

## 对齐依据

- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/award_rescue_execution_checklist_20260319.md`
- `session_bootstrap/reports/defense_deck_outline_20260319.md`
- `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
