# OpenAMP `TC-002 / TC-010` 答辩口径收口说明（2026-04-03）

> 用途：把总清单里仍写作“`TC-002/010` 需按最终答辩口径补齐”的那一项拆开说明，避免后续继续把 **已可引用的 `TC-002` live reconstruction 证据** 和 **当前明确不应 overclaim 的 `TC-010` sticky reset** 混成一个未决黑箱。

## 1. 结论先行

- `TC-002`：**按当前最终答辩口径，已经有可直接引用的 live 证据，不必再伪造一个新的“专门 TC-002 harness”**。
- `TC-010`：**当前仍不应宣称已完成**。`RESET_REQ/ACK`、sticky fault reset 仍属于明确写出的 out-of-scope / next-step 扩展项，应保留为后续协议扩展，而不是在答辩里说成已经闭环。

因此，总清单中这一项的真实状态应该解释为：

> `TC-002` 已完成答辩口径收口；`TC-010` 仍未纳入当前正式主张，故“`TC-001/002/003/004/006/010` 全部跑通”这一句 **仍不能整体勾完成**。

---

## 2. `TC-002` 为什么现在可以算“答辩口径已补齐”

设计文档里，`TC-002` 的定义是：

- 名称：`正常单次 reconstruction 作业`
- 预期：`提交 300 张 reconstruction 作业`
- 判定：`输出数匹配，status 回 READY`
- 证据：`output manifest`

来源：`paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`

### 2.1 当前仓库里已经存在的直接证据

1. `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
   - 明确写出：`current 路径已在 8115 上成功跑通，并完成真实 reconstruction 300/300`
   - 同时记录：baseline 经 signed sideband 进入真机执行后，也完成 `300/300`
   - 这说明 OpenAMP demo mode 下的 live reconstruction 不是 mock，而是真实板上跑通的作业闭环。

2. `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
   - 已把上面的 live 事实吸收到统一 OpenAMP evidence package 中
   - 对外口径已写成：`8115 是当前唯一有效 demo 实例，current 已成功跑通，baseline 也已通过 signed sideband 进入真机执行，两侧 reconstruction 均完成 300/300`

3. 板侧原始日志仍保留了 `300/300` 完成记录，例如：
   - `session_bootstrap/reports/big_little_compare_20260318_123300.serial.raw.log`
   - `session_bootstrap/reports/resource_profile_trusted_current_20260312_001/target.command.log`

### 2.2 这意味着什么

`TC-002` 的关键不是“必须另外起一个叫 `TC-002` 的孤立脚本”，而是：

- reconstruction 作业确实进了真机执行链
- 输出数完成到 `300/300`
- 该结论已经被上收进统一 evidence package / demo 口径

所以对答辩来说，更诚实也更稳的说法是：

> `TC-002` 已由现有 live reconstruction 证据收口，入口统一引用 `openamp_demo_live_dualpath_status_20260317.md` 与 OpenAMP evidence package，而不是再临时制造一套新的“TC-002 专用演示脚本”。

---

## 3. `TC-010` 为什么现在必须明确写成“边界”，而不是继续含混成“待补齐”

设计文档中，`TC-010` 的定义是：

- 名称：`sticky fault + reset 恢复`
- 前提：先触发 `F003/F004`
- 操作：发送 `RESET_REQ`
- 预期：`RESET_ACK`，状态回 `READY`
- 证据：`state transition log`

来源：`paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`

但当前仓库里已经反复写明：**不要对外宣称 `RESET_REQ/ACK` 或 sticky fault reset 已闭环**。

直接证据包括：

- `session_bootstrap/reports/openamp_demo_qa_card_m13_20260319.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`

这些文档都把以下内容列为**当前不主张**：

- `FIT-04/05`
- `RESET_REQ/ACK`
- deadline enforcement
- sticky fault reset

### 3.1 这不是“缺一份文档”问题，而是功能边界问题

`TC-010` 不能被收口，不是因为没人把文字整理好，而是因为：

- 当前正式板级主张并没有把 `RESET_REQ/ACK` 做成已闭环能力
- 现有答辩材料还在主动提醒“不要 overclaim 这条能力”

所以正确动作不是把 `TC-010` 硬往“已完成”上贴，而是把它从“模糊待补齐”改写成：

> `TC-010` 当前仍属于后续协议扩展 / sticky reset 能力，不在本轮正式答辩闭环范围内。

---

## 4. 建议同步到总清单/追踪板的表述

建议把原先那句：

> `TC-002/010` 仍需按最终答辩口径补齐

拆成两层：

1. `TC-002`：已由 live reconstruction `300/300` 证据完成答辩口径收口
2. `TC-010`：当前仍属 `RESET_REQ/ACK` / sticky fault reset 扩展，不纳入本轮正式 claim

这样能避免两个问题：

- 把已经能说清楚的 `TC-002` 永远挂在“未完成”里
- 反过来把当前明确不能 claim 的 `TC-010` 误导成“好像只差补一页材料就能算通过”

---

## 5. 对外一句话口径

如果评委问“核心测试是不是都跑通了”，建议回答：

> 当前正式闭环的核心证据已经覆盖 payload / reconstruction 正常作业、错误 SHA 拒绝、输入契约拒绝、heartbeat watchdog，以及 `STATUS_REQ/RESP` 等最小控制面；其中 reconstruction 这条线有真实 `300/300` live 证据。`RESET_REQ/ACK` 和 sticky fault reset 仍属于后续扩展能力，我们没有把它说成已经完成。

---

## 6. 入口索引

- 设计矩阵：`paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`
- live reconstruction 状态：`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- 统一证据包：`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md`
- 总报告：`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- coverage matrix：`session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
