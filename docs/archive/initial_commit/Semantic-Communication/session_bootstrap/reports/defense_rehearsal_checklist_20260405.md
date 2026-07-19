# 飞腾杯答辩赛前彩排 Checklist（2026-04-05）

- 用途：答辩前 `10-15` 分钟快速自检；也可作为正式彩排流程单
- 目标：确保“讲法一致、切页顺畅、证据可跳、边界不穿帮”
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## A. 口径检查

- [ ] 开场第一句必须把项目定义成“飞腾多核异构安全语义图像回传系统”，不是单点 benchmark
- [ ] 明确区分两种 mode：
  - `4-core Linux performance mode`
  - `3-core Linux + RTOS demo mode`
- [ ] 性能页只讲 `1850.0 -> 230.3 -> 134.6 ms`
- [ ] 动态尺寸只讲 `MNN 98.2 秒 / 327.3 ms-image`
- [ ] 不把 `242.0 / 345.3` 讲成同一 mode 下的 headline performance
- [ ] 讲 OpenAMP 时只讲控制、安全、准入、监护、停机，不讲加速
- [ ] 讲 OpenAMP 测试时，`TC-002` 可以说已由 live `300/300` 收口；`TC-010` 必须保留为后续扩展

## B. 核心页顺序

- [ ] Page 1：系统身份
  - 建议打开：论文 `图 1.3`
- [ ] Page 2：双模式边界
  - 建议打开：论文 `图 3.3`
- [ ] Page 3：性能主口径
  - 建议打开：论文 `图 5.1`
- [ ] Page 4：控制与安全
  - 建议打开：论文 `图 3.1` 或 `图 5.2`
- [ ] Page 5：系统闭环结论
  - 建议打开：论文 `图 5.3`

## C. 快速跳转入口

- [ ] 性能追问：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- [ ] OpenAMP 总报告：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- [ ] OpenAMP coverage：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- [ ] `TC-002/010` 边界说明：
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- [ ] `1 分钟稿`：
  - `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- [ ] `3 分钟稿`：
  - `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- [ ] `10 问 10 答`：
  - `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- [ ] `30 秒救场卡`：
  - `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- [ ] `5 轮高压追问模拟`：
  - `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`

## D. 现场说法禁区

- [ ] 不说：`OpenAMP 让 TVM 更快`
- [ ] 不说：`所有数字都来自同一种 mode`
- [ ] 不说：`demo mode 也是完整 4-core Linux`
- [ ] 不说：`TC-010 也已经一起收口`
- [ ] 不说：`量化我们没做`
- [ ] 不说：`手写算子我们全都做完了`

## E. 被打断时的保底策略

- [ ] 只给 `1 分钟`：
  - 直接切 `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- [ ] 只给 `30 秒`：
  - 直接切 `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- [ ] 被连续追问：
  - 直接切 `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- [ ] 要看 exact source：
  - 直接切 `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`

## F. 最后一遍口播自检

- [ ] 能在不看稿的情况下完整说出：
  - `4-core Linux performance mode` 证明飞腾多核性能成立
  - `3-core Linux + RTOS demo mode` 证明 OpenAMP 控制边界成立
  - `TVM + MNN` 共同覆盖固定形状极致性能和混合尺寸灵活部署
- [ ] 能在 `20 秒` 内收束成一句：
  - “我们不主张 OpenAMP 让模型更快；我们主张的是性能、控制边界和灵活部署三条线同时成立。”

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- `session_bootstrap/reports/defense_stress_qa_mock_5rounds_20260405.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
