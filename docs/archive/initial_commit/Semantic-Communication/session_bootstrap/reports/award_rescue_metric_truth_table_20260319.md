# Award Rescue Metric Truth Table（2026-03-19）

今夜改 PPT / 报告时，性能与演示数字只从本页复制。每个数字都必须带 `mode tag`，且只引用本页列出的路径。

## A. 4-core Linux performance mode

用途：headline performance / 多核重建能力。这里的数字只对应 Linux 侧 4 核性能口径，不对应 OpenAMP demo mode。

| Metric name | Value | Mode tag | What it proves | What it does NOT prove | Exact report/source path to cite |
|---|---|---|---|---|---|
| PyTorch default reference | `484.183 ms/image` | `4-core Linux performance mode` / reference anchor | 当前 rescue pack 已批准用它作为 PyTorch default 对照锚点。 | 不证明原始 PyTorch benchmark 报告已补归档；当前仍是 approved source note，不是最终 raw benchmark evidence。 | `session_bootstrap/reports/pytorch_default_reference_source_20260319.md` |
| TVM serial current（healthy-board same-run compare） | `231.522 ms/image` | `4-core Linux performance mode` | 健康板态、同轮 apples-to-apples compare 下，TVM serial current 已稳定到约 `231 ms/image`。 | 不证明 OpenAMP 带来加速；不替代 historical-best direct current e2e `230.339 ms/image`；不适用于 degraded board 或 demo mode。 | `session_bootstrap/reports/big_little_real_run_summary_20260318.md`；`session_bootstrap/reports/big_little_compare_20260318_123300.json` |
| TVM big.LITTLE pipeline current（healthy-board same-run compare） | `134.617 ms/image` | `4-core Linux performance mode` | 健康板态下，big.LITTLE pipeline 是当前批准的 same-run performance headline。 | 不证明逐算子级绑核；不证明 OpenAMP / RTOS 参与性能提升；不意味着所有板态都能复现该数值。 | `session_bootstrap/reports/big_little_real_run_summary_20260318.md`；`session_bootstrap/reports/big_little_pipeline_bestcurrent_snr10_current_20260318_123421.md`；`session_bootstrap/reports/big_little_compare_20260318_123300.json` |
| Same-run throughput uplift vs serial current | `56.077%` | `4-core Linux performance mode` | 在同轮 healthy-board compare 中，pipeline 相对 serial current 吞吐提升 `56.077%`。 | 不证明相对 PyTorch 也是同口径 uplift；不消除板态敏感性；不允许把 OpenAMP 写成 TVM 加速来源。 | `session_bootstrap/reports/big_little_compare_20260318_123300.md`；`session_bootstrap/reports/big_little_real_run_summary_20260318.md` |

## B. Board-State Drift Sequence

用途：解释板态漂移 / CPU online set 变化，不作为 headline performance。这个分组是风险边界，不是对外主性能页。

| Metric name | Value | Mode tag | What it proves | What it does NOT prove | Exact report/source path to cite |
|---|---|---|---|---|---|
| Same-day direct current rerun drift sequence | `347.375 -> 295.255 -> 239.233 ms/image`；CPU online `0-2 -> 0-3` | `board-state drift investigation` | 同一 artifact lineage、同 `SNR=10` 下，板态 / CPU online set 就足以把 direct current rerun 从 `347.375` 恢复到 `239.233 ms/image`。 | 不证明 artifact lineage 自身发生了同量级退化；不应作为默认 headline performance。 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md`；`session_bootstrap/reports/big_little_real_run_summary_20260318.md` |
| Degraded-board direct rerun | `347.375 ms/image` | `board-state drift investigation` / degraded board | CPU3 offline、Linux online `0-2` 时，current direct rerun 会显著变慢。 | 不代表 healthy-board performance；不应用来否定 big.LITTLE headline。 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md` |
| Intermediate recovery observation | `295.255 ms/image` | `board-state drift investigation` / recovery transition | 恢复过程里存在中间态，不是只有“坏板态”与“好板态”两点。 | 不应单独作为 headline；也不应被写成新的 canonical reference。 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md` |
| Post-reboot healthy-board direct rerun | `239.233 ms/image` | `board-state drift investigation` / post-reboot healthy board | reboot 后 CPU online 恢复到 `0-3`，direct current rerun 会回到与 healthy-board headline 相一致的区间。 | 不等同于 same-run big.LITTLE pipeline headline `134.617 ms/image`；不等同于 demo mode。 | `session_bootstrap/reports/big_little_board_state_drift_20260318.md`；`session_bootstrap/reports/big_little_real_run_summary_20260318.md` |

## C. 3-core Linux + RTOS demo mode

用途：OpenAMP control-plane live / 答辩演示。`remoteproc0` 运行时会占掉一个 Linux CPU 给 RTOS 控制面使用，所以这一模式的数字不能与上面的 `4-core Linux performance mode` headline 混写。

| Metric name | Value | Mode tag | What it proves | What it does NOT prove | Exact report/source path to cite |
|---|---|---|---|---|---|
| remoteproc occupancy boundary | `remoteproc0=running` 时 Linux 在线核会从 `0-3` 变为 `0-2`；答辩口径应写为 `3-core Linux + RTOS demo mode` | `3-core Linux + RTOS demo mode` | OpenAMP / RTOS control plane 是真实板级存在的，而且它有明确 CPU 占用边界。 | 不证明这是 `4-core Linux performance mode`；不允许把 demo-mode live 数字与 `484.183 / 231.522 / 134.617 / 56.077%` 混成一张 headline performance 图。 | `session_bootstrap/reports/cpu3_state_watch_20260318_144316.log`；`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`；`session_bootstrap/reports/project_reframing_for_feiteng_cup_20260319.md` |

## Copy-Paste Rule

- 性能页只使用 `A` 组，并保留 `4-core Linux performance mode` 标签。
- 漂移解释页只使用 `B` 组，并明确写成 board-state / CPU-online 风险边界。
- OpenAMP 演示页只使用 `C` 组，并明确写成 `3-core Linux + RTOS demo mode`。
- 若一页同时出现 `A` 与 `C`，必须显式写出“different operating modes, not directly mixable”。
