# big.LITTLE 真机结论摘要（2026-03-18）

## 一句话结论

当前默认应引用的 big.LITTLE 真机 apples-to-apples compare 已切到 `session_bootstrap/reports/big_little_compare_20260318_123300.md`：在与历史最佳 current 同 artifact lineage、同 `SNR=10`、同 300 张 latent、同 real-reconstruction 语义、且板态恢复健康后的同轮对照下，serial current median 为 `231.522 ms/image`，pipeline current median 为 `134.617 ms/image`，相对同轮 serial current 吞吐提升 `56.077%`。与此同时，历史最佳直接 current e2e 参考仍是 `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md` 的 `230.339 ms/image`；同日 direct rerun 又出现了 `347.375 -> 295.255 -> 239.233 ms/image`、CPU online `0-2 -> 0-3` 的恢复序列，因此当前最新 validated 结论应固定为：**健康板态时 big.LITTLE 相对 serial current 有显著收益，而板态 / CPU online set 是 primary factor，不只是 artifact lineage。**

## 0. 先把三个 reference 分清楚

当前这条线应同时保留三个不同用途的 reference：
- **健康板态 big.LITTLE compare**：`session_bootstrap/reports/big_little_compare_20260318_123300.md`
  - 回答“在健康板态、同轮对照下，big.LITTLE 是否比 serial current 更好？”
- **历史最佳 direct current e2e**：`session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
  - 回答“current 这代 artifact 的 canonical 直接真机 e2e best reference 是多少？”
- **板态漂移复盘**：`session_bootstrap/reports/big_little_board_state_drift_20260318.md`
  - 回答“为什么同一代 artifact / 同 `SNR=10` 仍会出现 `347.375 -> 239.233 ms/image` 的明显漂移？”

这样后续引用时，就不会再把：
- healthy-board same-run compare；
- historical best direct serial current；
- degraded-board drift evidence

混写成同一种结论。

## 1. 首选 healthy-board apples-to-apples compare

核心报告：
- `session_bootstrap/reports/big_little_compare_20260318_123300.md`
- `session_bootstrap/reports/big_little_compare_20260318_123300.json`
- `session_bootstrap/config/big_little_pipeline.current.bestcurrent_snr10.2026-03-18.phytium_pi.env`

关键结果：
- serial current median: `231.522 ms/image`
- pipeline current median: `134.617 ms/image`
- serial_total_wall_ms: `69323.66`
- pipeline_total_wall_ms: `44413.422`
- serial_images_per_sec: `4.328`
- pipeline_images_per_sec: `6.755`
- throughput_uplift_pct: `56.077`

为什么它现在是默认 headline：
- 仍然固定在历史最佳 current 所在的 `6f236b07...6dc1` artifact lineage 与 `SNR=10` 设置；
- 仍然是同一轮里的 serial current vs pipeline current apples-to-apples compare；
- 但这次引用的是**健康板态**结果，而不是 CPU online 集合受损后的较慢一轮；
- 它与同日 post-reboot direct rerun `239.233 ms/image` 的恢复结果是相互一致的。

## 2. 历史最佳 direct current e2e 仍然保持不变

canonical 直接 current e2e 参考报告：
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`

应固定保留的口径：
- current median: `230.339 ms/image`
- trusted current SHA256: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- `SNR=10`
- baseline/current count: `300 / 300`

因此当前最稳妥的对外说法是：
- **big.LITTLE 默认比较入口**看 `123300` healthy-board compare；
- **historical-best direct current e2e** 仍看 `1758` 这份正式报告。

## 3. 板态漂移现在必须显式写进结论

集中复盘报告：
- `session_bootstrap/reports/big_little_board_state_drift_20260318.md`

这次 drift 调查应固定使用下面这组事实：
- degraded-board direct rerun: `347.375 ms/image`
- same-day intermediate recovery observation: `295.255 ms/image`
- post-reboot direct rerun: `239.233 ms/image`
- degraded-board CPU online: `0-2`（CPU3 offline）
- post-reboot CPU online: `0-3`

这组结果说明：
- 同一代 trusted current artifact、同 `SNR=10`，真机 direct rerun 仍可随板态显著摆动；
- 因此这轮 performance drift 的 primary factor 是**板态 / CPU online set**；
- 旧的较慢 compare 不应再主要归因成“artifact lineage 退化”。

## 4. 配套 pipeline 本体证据

匹配健康板态 compare 的 pipeline wrapper 报告：
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`
- `session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.json`

关键结果：
- status: `ok`
- processed_count: `300`
- artifact_sha256_match: `true`
- big_cores: `[2]`
- little_cores: `[0,1]`
- total_wall_ms: `44413.422`
- images_per_sec: `6.755`

阶段级 affinity 结论保持不变：
- **preloader** → LITTLE `[0,1]`
- **inferencer** → BIG `[2]`
- **postprocessor** → LITTLE `[0,1]`
- 当前证据支持的是**阶段 / worker 级 affinity + pipeline overlap**，不是逐个 TVM 算子级绑核。

## 5. 更早同日 compare / profiling 现在的地位

这些材料仍有价值，但现在应降级为**支持性证据**：
- `session_bootstrap/reports/big_little_compare_20260318_095615.md`
  - serial current `344.721 ms/image`
  - pipeline current `254.791 ms/image`
  - throughput uplift `35.298%`
  - 现应与板态漂移报告一起解读为 degraded-board 时代的 compare 证据，而不是默认 headline
- `session_bootstrap/reports/big_little_compare_20260318_051326.md`
  - throughput uplift: `36.937%`
- `session_bootstrap/reports/big_little_compare_20260318_053619.md`
  - throughput uplift: `36.54%`
- `session_bootstrap/reports/resource_profile_big_little_current_20260318_052922.md`
  - 继续保留为同日 current pipeline 路径的资源使用支持证据

## 6. 本轮真正修掉的 blocker

为把这条线从“可跑脚手架”推进到“真机闭环”，本轮实际修掉了：
- topology suggestion 文件不是纯 JSON，导致 auto-apply 失败
- wrapper 远端 runner 变量注入过脆，导致无声秒退
- 远端 current artifact 漂移，SHA 与 trusted current 不一致
- 远端读取 `.pt` latent 输入缺少 torch sidecar 路径
- `safe_join_process()` 只等 5 秒，导致 worker 被父进程过早终止
- resource-profile wrapper 对远端 tool probe 返回码误判

相关修复提交：
- `69e7644` — `fix: accept mixed-output topology suggestion files`
- `0c3b548` — `fix: unblock real big.LITTLE first run`
- `0633789` — `fix: avoid early big.LITTLE worker termination`
- `6730224` — `fix: relax resource profile tool probe`
- `bebc0a0` — `fix: tolerate noisy resource probe exit codes`

## 7. 后续默认引用顺序

如果后面只想快速引用这条线，推荐按下面顺序：
1. 结论摘要：`session_bootstrap/reports/big_little_real_run_summary_20260318.md`
2. 首选 healthy-board compare：`session_bootstrap/reports/big_little_compare_20260318_123300.md`
3. 匹配 pipeline wrapper 报告：`session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`
4. 历史最佳 direct current e2e 参考：`session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
5. 板态漂移复盘：`session_bootstrap/reports/big_little_board_state_drift_20260318.md`
6. 更早同日 compare：`session_bootstrap/reports/big_little_compare_20260318_095615.md` / `session_bootstrap/reports/big_little_compare_20260318_051326.md` / `session_bootstrap/reports/big_little_compare_20260318_053619.md`
7. 真机 profiling 与 runbook：`session_bootstrap/reports/resource_profile_big_little_current_20260318_052922.md` / `session_bootstrap/runbooks/big_little_pipeline_runbook_2026-03-18.md`
