# 飞腾杯答辩当天单页总索引（2026-04-05）

- 用途：答辩当天只开这一页，按场景跳转到对应材料
- 使用方式：先看“当前处于什么场景”，再打开对应文档，不现场搜索文件名
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## 1. 正常开场讲解

- 若时间约 `3 分钟`：
  - 打开：`session_bootstrap/reports/defense_talk_track_3min_20260405.md`
  - 配合：`session_bootstrap/reports/defense_ppt_pages_1_5_cn_20260405.md`
- 若时间只剩 `1 分钟`：
  - 打开：`session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- 若只剩一张主图：
  - 回论文：`paper/CICC0903540初赛技术文档.md` 中 `图 1.3`

## 2. 被评委打断

- 若只给 `30 秒`：
  - 打开：`session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- 若连续高压追问：
  - 打开：`session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- 若只是普通追问：
  - 打开：`session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`

## 3. 评委只看性能

- 主入口：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- 配套主图：
  - 论文 `图 5.1`
- 只需一句话时：
  - `4-core Linux performance mode` 下，`1850.0 -> 230.3 -> 134.6 ms`

## 4. 评委只看 OpenAMP / 安全控制

- 主入口：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- 证据矩阵：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- 配套主图：
  - 论文 `图 3.1`
  - 论文 `图 5.2`
- 只需一句话时：
  - OpenAMP 证明的是控制边界，不是性能加速

## 5. 评委追问 `TC-002 / TC-010`

- 主入口：
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- 当前标准说法：
  - `TC-002` 已由 live reconstruction `300/300` 收口
  - `TC-010` 仍属后续扩展，不在当前正式 claim 范围内

## 6. 评委追问 MNN / 动态尺寸 / 量化

- 主入口：
  - 论文 `第 4.2 节`
  - 论文 `图 4.8`
  - 论文 `图 4.10`
- 当前标准说法：
  - `MNN` 是混合尺寸旁路，正式结果为 `98.2 秒 / 327.3 ms-image`
  - `low precision` 实测没有优于当前正式最优配置，所以没有把量化讲成主结果

## 7. 评委追问“你们到底创新在哪”

- 主入口：
  - 论文 `图 5.3`
  - `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- 当前标准说法：
  - 创新点不是单个算子更快，而是飞腾多核性能、OpenAMP 控制安全、`TVM + MNN` 双部署路径和证据链同时成立

## 8. 答辩前最后 10 分钟

- 打开：
  - `session_bootstrap/reports/defense_rehearsal_checklist_20260405.md`
- 必查三件事：
  - mode 边界有没有说乱
  - `TC-010` 有没有讲穿
  - OpenAMP 有没有被误讲成加速来源

## 9. 最后 20 秒统一收口

- 标准说法：
  - “我们不主张 OpenAMP 让模型更快；我们主张的是，`4-core Linux` 模式把飞腾多核性能做实了，`3-core Linux + RTOS` 模式把控制和安全边界做实了，`TVM + MNN` 又把固定形状和混合尺寸两条部署路径补齐了，这三条线合起来就是这件作品的系统价值。”

## 10. 本页对应入口总表

- `3 分钟稿`：
  - `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `1 分钟稿`：
  - `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- `5 页页稿`：
  - `session_bootstrap/reports/defense_ppt_pages_1_5_cn_20260405.md`
- `10 问 10 答`：
  - `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- `30 秒救场卡`：
  - `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- `5 轮高压追问模拟`：
  - `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- `赛前彩排 checklist`：
  - `session_bootstrap/reports/defense_rehearsal_checklist_20260405.md`
- `truth table`：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `OpenAMP summary_report`：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `TC-002/010 口径说明`：
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- `session_bootstrap/reports/defense_rehearsal_checklist_20260405.md`
