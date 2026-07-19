# OpenAMP 答辩讲稿 / PPT 结构提纲

- audience: `评委 / 答辩老师 / 技术复核人`
- presentation_style: `证据驱动，live 可选`
- recommended_length: `10~12 min full version` / `5 min compressed version`

## 1. 建议 PPT 页结构

| 页码 | 标题 | 核心信息 | 推荐证据 / 画面 | 讲述重点 |
|---|---|---|---|---|
| 1 | 为什么今天不做现场试错 | 这是已完成真机证据的 defense，而不是再做一轮实验 | [summary_report.md](summary_report.md) | 开场就声明：不 reboot，不做新 fault injection，结论以证据包为准 |
| 2 | 系统角色与边界 | OpenAMP 控制面是 trusted current 的执行入口，不是单独炫协议 | [summary_report.md](summary_report.md) / [coverage_matrix.md](coverage_matrix.md) | 先讲“它为谁服务”，再讲“它能做什么” |
| 3 | 总结论页 | `P0 已板级闭环；P1 FIT-01/02/03 最终 PASS` | [summary_report.md](summary_report.md) | 把评委先带到总判定，避免细节先行 |
| 4 | Act 1: trusted boot 与在线基线 | cold boot / RPMsg demo 路径已板级验证，且 2026-03-17 最新 live 已确认 8115 上 current / baseline 双路径都已成功执行；这页也是当前 `TC-002` 的 live reconstruction 收口入口 | [../openamp_demo_live_dualpath_status_20260317.md](../openamp_demo_live_dualpath_status_20260317.md) / [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md) / [../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md](../openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md) / [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md) | 强调“今天 live 只从已在线状态开始” |
| 5 | Act 2: STATUS -> JOB -> HEARTBEAT | 最小控制协议不是 echo，而是会改变 guard state | [coverage_matrix.md](coverage_matrix.md) | 讲 `READY -> JOB_ACTIVE` 和 `heartbeat_ok=1` |
| 6 | Act 2: wrapper-backed smoke + JOB_DONE | firmware `ALLOW` 会真实放行 runner，作业完成后会回到 clean `READY` | [../openamp_wrapper_hook_board_smoke_success_2026-03-14.md](../openamp_wrapper_hook_board_smoke_success_2026-03-14.md) / [../openamp_phase5_job_done_success_2026-03-15.md](../openamp_phase5_job_done_success_2026-03-15.md) | 这是“控制面影响真实执行”的证据 |
| 7 | Act 3: FIT 总表 | 三个正式 FIT 已收口，且 FIT-03 保留历史 FAIL | [coverage_matrix.md](coverage_matrix.md) | 一页打全局，再展开单项 |
| 8 | Act 3: wrong SHA / invalid param | admission gate 不只会放行，也会拒绝 | [../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md](../openamp_phase5_fit01_wrong_sha_success_2026-03-15.md) / [../openamp_phase5_fit02_input_contract_success_2026-03-15.md](../openamp_phase5_fit02_input_contract_success_2026-03-15.md) | 强调 `denied_by_control_hook`、runner 未启动 |
| 9 | Act 3: FIT-03 fail -> fix -> pass | 旧 live firmware 的缺口没有被掩盖，修复后用相同探针顺序复验通过 | [../openamp_phase5_fit03_timeout_gap_2026-03-15.md](../openamp_phase5_fit03_timeout_gap_2026-03-15.md) / [../openamp_phase5_fit03_watchdog_success_2026-03-15.md](../openamp_phase5_fit03_watchdog_success_2026-03-15.md) | 这是最强的可信度页 |
| 10 | Act 4: 性能价值 | trusted current 在 payload 与 e2e 两个口径都显著优于 baseline | [../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_compare_currentsafe_chunk4_refresh_20260313_1758.md) / [../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md](../inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md) | 把 OpenAMP 放在整机价值链里讲 |
| 11 | 为什么说它是 safe reliable positioning | 同一个 trusted SHA 既有性能结论，也有 wrong-SHA / contract / watchdog 保护 | [coverage_matrix.md](coverage_matrix.md) / [../../PROGRESS_LOG.md](../../PROGRESS_LOG.md) | 讲“高性能 + 可审计执行边界” |
| 12 | 边界与下一步 | 不主张 `FIT-04/05`、`TC-010` 对应的 `RESET_REQ/ACK`、deadline、sticky reset | [README.md](README.md) / [summary_report.md](summary_report.md) / [../openamp_tc002_tc010_defense_scope_note_2026-04-03.md](../openamp_tc002_tc010_defense_scope_note_2026-04-03.md) | 主动讲边界，减少被动追问 |

## 2. 建议口头版本

### 10~12 分钟完整版

1. 先报总判定，再说明今天不把答辩变成新实验。
2. 用 `openamp_demo_live_dualpath_status_20260317.md` 先把最近一次 live 板端事实定住：**8115 是唯一有效 demo 实例，current 已成功跑通，baseline 也已通过 signed sideband 进入真机执行，且两侧 recent live reconstruction 均为 `300/300`。** 这页同时就是当前 `TC-002` 的正式收口入口。
3. 用 Act 1 立住“系统真实在线”。
3. 用 Act 2 讲“控制面不只是收发消息，而是会影响 runner 放行和状态回收”。
4. 用 Act 3 讲“安全性有正式 FIT，而且 FIT-03 的失败历史没有被藏起来”。
5. 用 Act 4 讲“为什么这套控制面值得做”，即为高性能 trusted current 提供安全执行边界。
6. 最后主动讲 out-of-scope，避免评委把问题扩到未收口范围，尤其明确 `TC-010` 仍停在 `RESET_REQ/ACK` / sticky fault reset 扩展。

### 5 分钟压缩版

1. 一页总判定。
2. 一页 Act 1 + Act 2 合并图。
3. 一页 FIT 总表，其中重点只讲 `FIT-03 fail -> fix -> pass`。
4. 一页性能结果 + safe reliable positioning。
5. 一页边界。

## 3. 每幕一句话主结论

- Act 1：`这不是 mock，板级 cold boot 和在线基线都已有真机证据。`
- Act 2：`控制面已经能真实控制 admission、heartbeat 与状态回收。`
- Act 3：`wrong SHA、非法参数、heartbeat timeout 都有正式板级证据，其中 FIT-03 保留了失败历史。`
- Act 4：`OpenAMP 的价值，是为高性能 trusted current 提供可审计、可拒绝、可监护的执行边界。`

## 4. 高频追问口径

### Q1. 为什么不现场 reboot 一次？

推荐回答：

> 因为 cold boot 已经有正式板级 evidence。今天再 reboot 一次，并不会提升证据强度，反而会把答辩变成新的操作风险。  
> 所以我们把 live 限制在不扰动系统的在线确认。

### Q2. 你怎么证明 wrapper 不是自己伪造 ALLOW？

推荐回答：

> wrapper-backed board smoke 里已经明确记录 `source=firmware_job_ack`，而且 runner 是在收到这条真实 `ALLOW` 后才被放行的。  
> 这不是本地 bypass。

### Q3. FIT-03 为什么要同时展示 FAIL 和 PASS？

推荐回答：

> 因为这能证明我们不是把缺口藏起来，而是在真实板级证据上确认缺口、修复缺口、再用同一探针顺序复验。  
> 这比只展示最终 PASS 更可信。

### Q4. OpenAMP 和性能结论有什么关系？

推荐回答：

> OpenAMP 不直接让模型变快；性能提升来自 trusted current artifact。  
> OpenAMP 的价值在于给这个高性能 artifact 提供 admission gate、输入契约 gate 和 heartbeat watchdog 的执行边界。

### Q5. 还有哪些没做？

推荐回答：

> 当前不主张 `FIT-04/05`、`RESET_REQ/ACK`、deadline enforcement、sticky fault reset。  
> `TC-002` 已由 live reconstruction `300/300` 收口；`TC-010` 对应的 `RESET_REQ/ACK` / sticky fault reset 仍不在本轮正式 claim。  
> 这次 defense 聚焦的是已经完成并有板级证据的最小控制闭环与三项正式 FIT。

## 5. 备份页建议

如果答辩允许附录，建议额外放三页备份：

1. `coverage_matrix.md` 截图页
2. `FIT-03` pre-fix FAIL / post-fix PASS 并排页
3. trusted current SHA `6f236b07...6dc1` 与性能结果对照页
