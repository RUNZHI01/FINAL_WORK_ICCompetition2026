# 飞腾杯答辩材料包 README（2026-04-05）

- 目的：说明这轮答辩材料补了什么、各文件怎么用、建议按什么顺序打开
- 适用场景：答辩前整理、当天候场、后续继续增补材料时快速找入口
- 当前范围：只覆盖本轮新增的论文配套答辩材料，不替代原始实验报告和 OpenAMP 证据包

## 1. 这套材料解决什么问题

- 论文已经补齐了图、图注和主叙事，但现场答辩还需要更短的口播、更稳定的追问应对和更直接的证据入口。
- 这套材料的目标是把同一套口径压成不同长度、不同场景下都能直接使用的版本，避免现场临时改口。
- 核心约束始终不变：
  - 不把 OpenAMP 讲成加速来源
  - 不混写两种 operating mode
  - 不把 `TC-010` 讲成已正式收口

## 2. 本轮新增材料总表

| 文件 | 用途 | 什么时候用 |
|---|---|---|
| `session_bootstrap/reports/defense_talk_track_3min_20260405.md` | `3 分钟` 标准讲稿 | 正常答辩主流程 |
| `session_bootstrap/reports/defense_ppt_core_pages_1_5_cn_20260405.md` | `5` 张核心页大纲 | 做页结构或改 PPT 时 |
| `session_bootstrap/reports/defense_ppt_pages_1_5_cn_20260405.md` | `5` 张页的逐页正文 | 做 PPT 文案时 |
| `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md` | `10 问 10 答` 速答卡 | 普通追问 |
| `session_bootstrap/reports/defense_talk_track_1min_20260405.md` | `1 分钟` 电梯稿 | 巡场、临时压缩介绍 |
| `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md` | `30 秒` 救场卡 | 被打断、只给一句 |
| `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md` | `5` 轮高压追问模拟 | 赛前对练 |
| `session_bootstrap/reports/defense_rehearsal_checklist_20260405.md` | 赛前彩排清单 | 上场前 `10-15` 分钟 |
| `session_bootstrap/reports/defense_day_onepage_index_20260405.md` | 答辩当天单页总索引 | 当天唯一首页 |

## 3. 推荐使用顺序

1. 平时准备：
   - 先看 `3 分钟稿`
   - 再看 `5 页页稿`
   - 再练 `10 问 10 答`
2. 赛前对练：
   - 先跑一遍 `5 轮高压追问模拟`
   - 再过一遍 `赛前彩排 checklist`
3. 答辩当天：
   - 只开 `单页总索引`
   - 再把 `truth table`、`OpenAMP summary_report`、`coverage_matrix` 常驻在后面几个窗口

## 4. 最关键的 3 句话

- `4-core Linux performance mode` 证明飞腾多核性能成立
- `3-core Linux + RTOS demo mode` 证明 OpenAMP 控制边界成立
- `TVM + MNN` 共同覆盖固定形状极致性能和混合尺寸灵活部署

## 5. 最关键的 3 条禁区

- 不说：`OpenAMP 让 TVM 更快`
- 不说：`所有数字都来自同一种 mode`
- 不说：`TC-010 也已经一起收口`

## 6. 现场最常用的 4 个入口

- 性能 exact source：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- OpenAMP 总报告：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- OpenAMP coverage：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- `TC-002 / TC-010` 边界说明：
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

## 7. 论文侧对齐点

- 主论文：
  - `paper/CICC0903540初赛技术文档.md`
- 最常回跳的图：
  - `图 1.3` 系统身份摘要图
  - `图 3.3` 双模式边界图
  - `图 5.1` 性能跃迁图
  - `图 5.2` 证据包结构图
  - `图 5.3` 系统闭环总览图

## 8. 当前完成状态

- 论文图和主叙事：已补齐并收口
- `1 分钟 / 3 分钟 / 30 秒` 三档口播：已补齐
- `10 问 10 答` 和高压追问：已补齐
- 彩排清单和当天单页索引：已补齐
- operator card 入口：已同步更新
- 高阶任务 4 页 PPT 文案 + 60s demo 脚本 + 5Q&A：已补齐（`ppt_assets/`）
- ReplayGuard 重放防护：已实现并部署（106/106 自测全绿），R7 从 P 级升级为 G 级
- daemon 持久化会话优化（O-1~O-4）：已实现并验证，加密通信 4.43ms/张，占全流程 0.2%

## 9. 入口索引

- operator card：
  - `session_bootstrap/reports/defense_demo_operator_card_20260320.md`
- 当天单页总索引：
  - `session_bootstrap/reports/defense_day_onepage_index_20260405.md`

