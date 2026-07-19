# 飞腾杯答辩高压追问模拟（5 轮，2026-04-05）

- 用途：赛前对练、现场候场默读、被评委连续追问时校准口径
- 使用原则：每轮先回答主问题，再补边界；如果评委继续追，就切证据，不要现场即兴发挥
- 红线：不把 OpenAMP 讲成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## 第 1 轮：你们到底是系统作品，还是拿 TVM 调优包装了一层壳？

- 评委主问：
  - “我听下来像是你们把 TVM 调快了，然后外面套了个演示界面。这怎么能算系统作品？”
- 推荐应答：
  - “如果我们只做 TVM 调优，那确实只能算 benchmark。但我们现在有三条同时成立的线：第一，`4-core Linux` 模式下把飞腾多核性能做实；第二，`3-core Linux + RTOS` 模式下把 OpenAMP 控制面、安全停机和 FIT 收证做实；第三，用 `MNN` 补上了混合尺寸灵活部署。也就是说，我们做的是数据面、控制面和展示证据链同时闭环的一套系统。”
- 若评委继续追问：
  - “你们的系统性到底体现在哪？”
- 续答：
  - “体现在每个结论都能落到对应证据：性能去 `truth table`，控制去 `OpenAMP summary_report` 和 `coverage_matrix`，系统总览回论文 `图 5.3`。”
- 不能说：
  - “主要创新还是 TVM 更快，别的都是附带的。”
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 5.3`
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`

## 第 2 轮：为什么你们有那么多数字？是不是口径不稳定？

- 评委主问：
  - “你们一会儿说 `230.3`，一会儿说 `242.0`，一会儿又说 `345.3`，这是不是说明你们口径不稳定？”
- 推荐应答：
  - “不是。我们现在明确按 operating mode 分口径。`230.3 / 134.6` 属于 `4-core Linux performance mode`，证明性能主线；`242.0 / 345.3` 属于 `3-core Linux + RTOS demo mode` 的公平复测，证明演示模式下系统仍可运行；两者不是同一 mode，所以不能混写。”
- 若评委继续追问：
  - “那为什么不只保留一组数字？”
- 续答：
  - “因为这两组数字证明的是两件不同的事。我们主动拆开，恰恰是为了不把模式边界讲乱。”
- 不能说：
  - “数字差不多，影响不大。”
- 立刻跳转：
  - `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 3.3`

## 第 3 轮：OpenAMP 到底有什么用？如果不加它是不是照样能跑？

- 评委主问：
  - “不加 OpenAMP 你们的模型是不是也能跑？那它到底贡献了什么？”
- 推荐应答：
  - “模型推理当然可以在纯 Linux 性能模式下跑，但那只是高性能链路，不是受控系统。OpenAMP 的作用是把这条链路做成可准入、可监护、可安全停机的系统，并且已经在真机上证明了五类消息和三项 FIT 都能落证。”
- 若评委继续追问：
  - “那你们是不是在用 OpenAMP 换性能？”
- 续答：
  - “不是。我们明确不这么主张。OpenAMP 负责控制边界，性能提升来自 TVM 主线和异构流水线。”
- 不能说：
  - “OpenAMP 让我们的飞腾推理更快。”
- 立刻跳转：
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
  - `paper/CICC0903540初赛技术文档.md` 中 `图 3.1`

## 第 4 轮：你们没有做 INT8 / FP16，是不是优化深度不够？

- 评委主问：
  - “现在很多队伍都会上量化，你们没把 `INT8 / FP16` 做成主结果，是不是优化深度不够？”
- 推荐应答：
  - “这条线我们评估过，但当前板态下 ROI 不高。我们没有看到足够强的 `FP16 / INT8` 硬件加速路径，而且实测 `low precision` 也没有赢过当前正式最优配置。所以这次我们把资源放在更确定的 TVM 主线、OpenAMP 控制闭环和 MNN 动态尺寸路线，而不是把量化硬讲成主结果。”
- 若评委继续追问：
  - “那你们是不是根本没做？”
- 续答：
  - “不是。我们做了探索，也把结果写进论文了；只是当前结果不值得被讲成正式 headline。”
- 不能说：
  - “板卡完全不支持，所以我们一点都没试。”
- 立刻跳转：
  - `paper/CICC0903540初赛技术文档.md` 第 `4.2` 节 `MNN` 小节
  - `session_bootstrap/logs/smoke_mnn_matrix_20260404.log`

## 第 5 轮：你们的 OpenAMP 测试是不是还没全做完？

- 评委主问：
  - “我看你们还提到 `TC-010`，是不是说明 OpenAMP 这条线其实还没收口？”
- 推荐应答：
  - “要分开说。当前正式 claim 范围内，`P0` 和 `FIT-01 / FIT-02 / FIT-03` 已经收口；`TC-002` 也已经由 live reconstruction `300/300` 证据收口。`TC-010` 则仍属于 `RESET_REQ/ACK` 和 sticky fault reset 的后续扩展，我们没有把它 overclaim 成已完成能力。”
- 若评委继续追问：
  - “那你们为什么不把它做完再来答辩？”
- 续答：
  - “因为我们当前更重要的是把已经成立的系统价值讲准确，而不是把边界能力讲穿。我们宁可把 `TC-010` 明确列成后续扩展，也不把它说成已经闭环。”
- 不能说：
  - “差不多已经做完了。”
- 立刻跳转：
  - `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
  - `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`

## 收口提醒

- 高压场景下，优先守住这三句：
  - `性能看 4-core Linux performance mode`
  - `控制与安全看 3-core Linux + RTOS demo mode`
  - `TC-010 不在当前正式 claim 范围内`

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_judge_qa_10_cn_20260405.md`
- `session_bootstrap/reports/defense_interrupt_rescue_card_30s_20260405.md`
- `session_bootstrap/reports/award_rescue_metric_truth_table_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
