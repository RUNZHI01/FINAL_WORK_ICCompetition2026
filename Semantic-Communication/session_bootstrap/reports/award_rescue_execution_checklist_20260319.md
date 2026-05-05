# 飞腾杯冲奖救援执行清单（2026-03-19）

## 目的

把“项目重构叙事”从策略口号落成接下来 48 小时可执行的文档与答辩动作。此清单默认是 **docs-first / evidence-led** 执行单，不要求改代码行为。

## 已锁定工程事实

以下事实在本轮文档、答辩稿、PPT 和讲述口径里必须保持一致：

| 主题 | 已锁定事实 | 当前证据入口 |
|---|---|---|
| TVM healthy-board serial current | `231.522 ms/image` | `session_bootstrap/reports/big_little_compare_20260318_123300.md` / `session_bootstrap/reports/big_little_real_run_summary_20260318.md` |
| TVM big.LITTLE pipeline current | `134.617 ms/image` | `session_bootstrap/reports/big_little_compare_20260318_123300.md` / `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md` |
| big.LITTLE 吞吐提升 | `56.077%` | `session_bootstrap/reports/big_little_compare_20260318_123300.md` |
| PyTorch default reference | `484.183 ms/image` | 当前作为已验证救援事实使用；**今夜必须把对应原始报告路径补归档到 `session_bootstrap/reports/`**，避免外部 deck 出现无来源数字 |
| OpenAMP 控制面存在且已板级闭环 | `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT_ACK`、`SAFE_STOP`、`JOB_DONE` 已有真机证据 | `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md` / `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md` |
| remoteproc 运行代价 | `remoteproc0` 拉起 RTOS 控制面时，会看到 `CPU3: shutdown`、Linux 在线核从 `0-3` 变为 `0-2`；答辩上应表述为 **3-core Linux + RTOS demo mode** | `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log` / `session_bootstrap/reports/big_little_board_state_drift_20260318.md` |

## 执行红线

- 不再把项目讲成“一个 generic TVM/MNN 优化项目”。
- 不把 `4-core Linux performance mode` 和 `3-core Linux + RTOS demo mode` 的数字混写成同一种口径。
- 不宣称 OpenAMP / RTOS 让推理更快；OpenAMP 当前卖点是 **control plane / safety / admission / heartbeat / safe stop**。
- 不把 `remoteproc` 的 CPU 代价说成“几乎没有代价”或“零代价”。
- 不在外部版本里使用没有本地证据路径的性能数字。

## P0 今晚（0-6 小时）

| ID | 任务 | Owner | 输入材料 | 输出文件 | 预计时间 | Done 标准 |
|---|---|---|---|---|---|---|
| P0-1 | 冻结新定位句与双模式定义 | `[Owner]` | `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`、`session_bootstrap/reports/big_little_real_run_summary_20260318.md`、`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md` | `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md` | `25 min` | 对外一句话定位、`4-core Linux performance mode`、`3-core Linux + RTOS demo mode` 三项文字全部定稿 |
| P0-2 | 冻结 pages 1-8 的故事顺序 | `[Owner]` | 上述重构 note、`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`、`session_bootstrap/reports/big_little_compare_20260318_123300.md` | `session_bootstrap/reports/defense_deck_outline_20260319.md` | `45 min` | 每页都能回答“为什么这是飞腾多核弱网安全语义视觉回传系统，而不是 generic optimization” |
| P0-3 | 建立 48h 执行清单并明确 owner 占位 | `[Owner]` | 当前清单所列事实与证据路径 | `session_bootstrap/reports/award_rescue_execution_checklist_20260319.md` | `20 min` | 所有 P0/P1 项均带输入、输出、时长、done 标准 |
| P0-4 | 补归档 `PyTorch default 484.183 ms/image` 的原始来源 | `[Owner]` | 当前已验证但未入库的 benchmark 报告或原始导出记录 | 建议新增：`session_bootstrap/reports/pytorch_default_reference_source_20260319.md` | `30 min` | 在 repo 内能给出一个明确路径，说明 `484.183 ms/image` 来自哪份原始结果 |
| P0-5 | 明确 remoteproc 占核证据并写进答辩边界 | `[Owner]` | `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log`、`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md` | 建议新增：`session_bootstrap/reports/openamp_mode_split_note_20260319.md` 或直接吸收入 deck speaker notes | `25 min` | deck 中至少一页显式写出“OpenAMP demo mode = 3-core Linux + RTOS；remoteproc 运行会占掉一个 Linux CPU” |
| P0-6 | 做一次 claims 审核 | `[Owner]` | 新 deck outline、新 reframing note、README 指针块 | 本地 review 记录；如需落文档可新增 `session_bootstrap/reports/award_rescue_claim_review_20260319.md` | `20 min` | 删除所有“OpenAMP 加速 TVM”“双模式数字混写”“generic TVM 项目”表述 |

## 接下来 24-48 小时（答辩材料收口）

| ID | 任务 | Owner | 输入材料 | 输出文件 | 预计时间 | Done 标准 |
|---|---|---|---|---|---|---|
| D1 | 做 page-ready 统一指标表 | `[Owner]` | `123300` compare、pipeline wrapper、PyTorch default source note | 建议新增：`session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md` | `40 min` | 表中至少包含 `484.183 / 231.522 / 134.617 / +56.077%`，并且每个数字都标注 operating mode |
| D2 | 做 page-ready 证据图清单 | `[Owner]` | `openamp_control_plane_evidence_package_20260315`、`openamp_demo_live_dualpath_status_20260317.md`、`cpu3_state_watch_20260318_144316.log` | 建议新增：`session_bootstrap/reports/award_rescue_evidence_pack_20260320.md` | `60 min` | 每页 PPT 都能指向一个截图或表格，不需要现场临时翻日志 |
| D3 | 产出 5 分钟版本讲稿 | `[Owner]` | `defense_deck_outline_20260319.md` | 建议新增：`session_bootstrap/reports/defense_talk_track_5min_20260320.md` | `35 min` | 任一队员按文稿讲 5 分钟，不会把项目讲回“TVM 调优项目” |
| D4 | 产出 2 分钟压缩版结论卡 | `[Owner]` | 重构 note、metric truth table | 建议新增：`session_bootstrap/reports/defense_talk_track_2min_20260320.md` | `20 min` | 能在被打断时用 2 分钟完整讲清“定位-双模式-性能-安全” |
| D5 | 检查 README / 入口索引可达性 | `[Owner]` | `README.md`、`session_bootstrap/README.md` | 本轮已先补入口；如后续新增更多 rescue docs，再追加 pointer | `10 min` | 新人打开根 README 或 `session_bootstrap/README.md`，30 秒内能找到 rescue docs |

## P1 本周（不抢今晚，但必须排上）

| ID | 任务 | Owner | 输入材料 | 输出文件 | 预计时间 | Done 标准 |
|---|---|---|---|---|---|---|
| P1-1 | 做正式 PPT 图版与统一版式 | `[Owner]` | `defense_deck_outline_20260319.md`、metric truth table、evidence pack | 正式答辩 deck（外部文件名待定） | `2-4 h` | 8 页主 deck 完整、数字统一、模式标注完整 |
| P1-2 | 做最终 demo operator 卡 | `[Owner]` | OpenAMP 四幕 runbook、双模式定义、degraded fallback 文档 | 建议新增：`session_bootstrap/reports/defense_demo_operator_card_20260320.md` | `45 min` | 上台操作时明确知道什么时候走 live cue，什么时候只展示证据 |
| P1-3 | 做“为什么不是 generic optimization”附录页 | `[Owner]` | 重构 note、赛题对齐建议、OpenAMP 总报告 | 建议新增：`session_bootstrap/reports/system_positioning_appendix_20260320.md` | `30 min` | 评委追问时能直接展示系统级任务、弱网语义回传、多核/控制面的关系 |
| P1-4 | 做 mode separation appendix | `[Owner]` | `cpu3_state_watch_20260318_144316.log`、board-state drift 复盘、OpenAMP live 状态 | 建议新增：`session_bootstrap/reports/performance_vs_demo_mode_appendix_20260320.md` | `30 min` | 附录里明确说明为什么 headline performance 必须引用 4-core Linux mode |
| P1-5 | 最终 claims 审核 + 彩排修订 | `[Owner]` | 正式 deck、2 分钟 / 5 分钟文稿、operator 卡 | 建议新增：`session_bootstrap/reports/final_claim_audit_20260320.md` | `30 min` | 所有对外版本统一到同一套数字、边界和 mode wording |

## 默认讲法（建议直接复用）

> 我们当前对外不再把项目讲成 generic TVM/MNN 优化，而是讲成 **飞腾多核弱网安全语义视觉回传系统**。  
> 性能 headline 使用 `4-core Linux performance mode`：healthy-board TVM serial current `231.522 ms/image`，big.LITTLE pipeline `134.617 ms/image`，相对同轮 serial uplift `56.077%`，PyTorch default reference 为 `484.183 ms/image`。  
> 安全与演示 headline 使用 `3-core Linux + RTOS demo mode`：OpenAMP control plane 已有板级闭环证据，但 `remoteproc` 运行会占掉一个 Linux CPU，因此不能把该模式的数字与 4-core performance mode 混写。

## 今晚收工前自检

- `project_reframing_for_feiteng_cup_20260319.md` 已定稿
- `defense_deck_outline_20260319.md` 已定稿
- `484.183 ms/image` 的来源已补到 repo 内部路径
- deck 里已显式写出两种 operating modes
- 所有人都知道：**OpenAMP 是 control plane，不是 performance accelerator**
