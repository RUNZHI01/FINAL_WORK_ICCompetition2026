# 飞腾杯答辩 Deck Outline（Pages 1-8）

## Page 1

- Title: `不是 generic TVM 项目，而是飞腾多核弱网安全语义视觉回传系统`
- Core message: 开场先把项目定位定死。作品核心不是“把一个模型跑快”，而是“在飞腾平台上完成弱网语义视觉回传，并同时给出多核性能路径与安全控制路径”。
- Evidence / report to cite:
  - `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
  - `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md`
- Speaker note: 第一页不要先讲 TVM 参数或 OpenAMP 协议，先讲系统目标、平台、场景和为什么它符合飞腾杯。

## Page 2

- Title: `场景问题：弱网下为什么要做语义视觉回传`
- Core message: 系统解决的是“弱网条件下把视觉语义高效、安全地回传到飞腾侧完成重建”的问题；语义通信让回传对象从原始像素转向紧凑 latent，天然适合弱网、边缘和受限带宽场景。
- Evidence / report to cite:
  - `paper/CICC0903540初赛技术文档.md`
  - `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
- Speaker note: 用“发送端语义编码 + 信道扰动 + 飞腾侧重建回传”讲场景，不要把这一页做成框架介绍页。

## Page 3

- Title: `系统架构：数据面与控制面分离的飞腾多核系统`
- Core message: 数据面保持现有可信链路，上位机负责编码与传输，飞腾 Linux 侧负责 trusted current TVM 解码；控制面交给 OpenAMP/RTOS，负责 admission、heartbeat、safe stop 和 fault accounting。
- Evidence / report to cite:
  - `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- Speaker note: 明确一句话，“OpenAMP 不是拿来搬 latent 大张量，而是拿来做控制面和安全边界”。

## Page 4

- Title: `性能模式：4-core Linux 上的可信 headline`
- Core message: 真正用于性能 headline 的是 `4-core Linux performance mode`。健康板态下，TVM serial current 为 `231.522 ms/image`，big.LITTLE pipeline 为 `134.617 ms/image`，同轮吞吐 uplift `56.077%`；PyTorch default reference 为 `484.183 ms/image`。
- Evidence / report to cite:
  - `session_bootstrap/reports/big_little_compare_20260318_123300.md`
  - `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`
  - `session_bootstrap/reports/big_little_real_run_summary_20260318.md`
  - `session_bootstrap/reports/pytorch_default_reference_source_20260319.md`（若尚未归档，先按 checklist 补齐）
- Speaker note: 这页要明确说“headline performance 来自 4-core Linux mode”，并主动说明 OpenAMP 不对这页的速度数字背书。

## Page 5

- Title: `演示模式：3-core Linux + RTOS 的 OpenAMP 安全控制面`
- Core message: 为了展示安全控制面，需要把 `remoteproc` 拉起到 `running`，此时一个 Linux CPU 会离线给 RTOS / control plane 使用；因此 demo mode 应被诚实表述为 `3-core Linux + RTOS`，它的价值是安全与控制，不是 headline performance。
- Evidence / report to cite:
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
  - `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log`
- Speaker note: 这一页是防误解页。主动告诉评委“我们知道 remoteproc 有占核代价，所以把 performance mode 和 demo mode 明确拆开了”。

## Page 6

- Title: `安全可靠不是口头承诺：OpenAMP 控制闭环与 FIT`
- Core message: OpenAMP 控制面不是 mock。当前已有板级 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT_ACK`、`SAFE_STOP`、`JOB_DONE` 证据，并且 `FIT-01`、`FIT-02`、`FIT-03` 已正式收口。
- Evidence / report to cite:
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
  - `session_bootstrap/reports/openamp_phase5_fit01_wrong_sha_success_2026-03-15.md`
  - `session_bootstrap/reports/openamp_phase5_fit02_input_contract_success_2026-03-15.md`
  - `session_bootstrap/reports/openamp_phase5_fit03_timeout_gap_2026-03-15.md`
  - `session_bootstrap/reports/openamp_phase5_fit03_watchdog_success_2026-03-15.md`
- Speaker note: 重点讲“拒绝错误 SHA、拒绝非法参数、heartbeat timeout fail->fix->pass”，这才是“安全”两个字的证据来源。

## Page 7

- Title: `为什么这是一件飞腾系统作品`
- Core message: 这项工作同时覆盖了飞腾杯更看重的三层内容：弱网语义通信系统任务、飞腾多核性能利用、异构 RTOS 控制与安全治理。因此它不是“单框架 benchmark”，而是一个有平台理解的系统级作品。
- Evidence / report to cite:
  - `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
  - `session_bootstrap/reports/big_little_real_run_summary_20260318.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- Speaker note: 这里把 Page 4 的多核性能和 Page 5-6 的控制面安全拼起来，形成“飞腾多核系统能力”而不是“两块互不相干的结果”。

## Page 8

- Title: `最后一页：该主张什么，不该主张什么`
- Core message: 应主张“4-core Linux performance mode 的 TVM headline”和“3-core Linux + RTOS demo mode 的 OpenAMP 安全控制面”这两条线；不应主张“OpenAMP 让 TVM 更快”或“所有数字来自同一种 operating mode”。
- Evidence / report to cite:
  - `session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md`
  - `session_bootstrap/reports/big_little_board_state_drift_20260318.md`
  - `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log`
- Speaker note: 结束页主动交代边界，会显著减少被评委抓住 mode mixing、control-plane overclaim、CPU tradeoff 这三类风险。

## 附录页入口（新增）

若评委继续追问质量、资源、SNR 或 profiling 边界，直接接：

- `session_bootstrap/reports/defense_appendix_pages_9_12_judge_evidence_20260330.md`

## 附录切换规则（主讲时直接照用）

- 被问“是不是拿质量换速度” → 切附录 Page 9
- 被问“资源占用、部署代价、artifact 大小” → 切附录 Page 10
- 被问“不同 SNR/弱网变化下稳不稳” → 切附录 Page 11
- 被问“有没有拿到真正 per-op profiling” → 切附录 Page 12

## 页面级统一要求

- 每一页都优先使用“飞腾多核弱网安全语义视觉回传系统”或其同义表述，不用“TVM/MNN optimization project”做主标题。
- 所有性能数字必须带 operating mode 标签。
- 只在讲 Page 4 时使用 `231.522 / 134.617 / +56.077% / 484.183` 这组性能数字。
- 只在讲 Page 5-6 时使用 OpenAMP/remoteproc/FIT 证据。
- 若 `484.183 ms/image` 的本地原始报告仍未补归档，导出正式 deck 前不得删除其来源说明。
