# 飞腾杯答辩双人配合卡（主讲 / 操作员，2026-04-05）

- 用途：双人答辩或一人主讲、一人切页时的现场协同卡
- 目标：避免“主讲还没说到，操作员先切走”或“评委追问时没人知道该开哪个文件”
- 角色定义：
  - 主讲：负责口播、控节奏、守边界
  - 操作员：负责切图、开证据、兜底切换

## 1. 开场前 30 秒

- 主讲：
  - 确认今天使用 `3 分钟稿` 还是 `1 分钟稿`
  - 再说一遍三条红线：不混 mode、不把 OpenAMP 讲成加速、不讲穿 `TC-010`
- 操作员：
  - 前台准备：
    - `session_bootstrap/reports/defense_day_onepage_index_20260405.md`
  - 后台常驻：
    - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
    - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
    - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`

## 2. 标准 5 页流程

### Page 1：系统身份

- 主讲负责：
  - 定义项目身份：不是单点 benchmark，而是一套飞腾系统作品
- 操作员负责：
  - 切到论文 `图 1.3`
- 若被打断：
  - 主讲直接改用 `1 分钟稿`
  - 操作员切 `session_bootstrap/reports/defense_talk_track_1min_20260405.md`

### Page 2：双模式边界

- 主讲负责：
  - 明说 `4-core Linux performance mode` 和 `3-core Linux + RTOS demo mode` 不能混写
- 操作员负责：
  - 切到论文 `图 3.3`
- 若评委追问 mode mixing：
  - 主讲只补一句：“两组数字证明的是两件不同的事。”
  - 操作员切 `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`

### Page 3：性能主口径

- 主讲负责：
  - 只讲 `1850.0 -> 230.3 -> 134.6 ms`
  - `MNN` 只作为动态尺寸旁路补一句
- 操作员负责：
  - 切到论文 `图 5.1`
- 若评委要 exact source：
  - 主讲说：“我直接给老师看批准口径页。”
  - 操作员切 `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`

### Page 4：控制与安全

- 主讲负责：
  - 只讲五类消息和三项 FIT，不讲速度
- 操作员负责：
  - 首选切论文 `图 3.1`
  - 若评委要证据，切 `图 5.2` 或 OpenAMP `summary_report`
- 若评委问“OpenAMP 有什么用”：
  - 主讲直接答：“控制边界，不是加速。”
  - 操作员切 `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`

### Page 5：系统结论

- 主讲负责：
  - 把 `TVM + MNN + OpenAMP` 三条线收成一句系统价值
- 操作员负责：
  - 切到论文 `图 5.3`
- 若时间被砍：
  - 主讲直接切 `20 秒` 收口
  - 操作员切 `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`

## 3. 常见追问时谁来做什么

| 场景 | 主讲怎么说 | 操作员怎么切 |
|---|---|---|
| 只问性能 | 只讲 `4-core Linux performance mode` | 开 `truth table` |
| 只问 OpenAMP | 只讲控制边界和 FIT | 开 `summary_report` 或 `coverage_matrix` |
| 问 `TC-002/010` | 讲 `TC-002` 已收口、`TC-010` 仍后置 | 开 `openamp_tc002_tc010_defense_scope_note_2026-04-03.md` |
| 问创新点 | 讲系统级创新，不讲单点算子堆料 | 回论文 `图 5.3` |
| 问 MNN / 量化 | 讲动态尺寸旁路和当前 ROI 判断 | 回论文 `第 4.2 节` |

## 4. 现场失步时的兜底规则

- 主讲说快了：
  - 操作员不要乱切，等主讲说出关键词再切
- 操作员切快了：
  - 主讲先按当前页面往下说，不要现场抱怨或倒回解释
- 两人都卡住：
  - 主讲直接说：“我先把结论讲清楚，再给老师看证据。”
  - 操作员立刻切 `session_bootstrap/reports/defense_day_onepage_index_20260405.md`

## 5. 最后一遍对齐

- 主讲必须记住：
  - `4-core Linux performance mode`
  - `3-core Linux + RTOS demo mode`
  - `TC-010` 不在当前正式 claim 范围内
- 操作员必须记住：
  - 性能 -> `truth table`
  - OpenAMP -> `summary_report`
  - 追问兜底 -> `defense_day_onepage_index_20260405.md`

## 对齐依据

- `session_bootstrap/reports/defense_talk_track_1min_20260405.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- `session_bootstrap/reports/defense_day_onepage_index_20260405.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
