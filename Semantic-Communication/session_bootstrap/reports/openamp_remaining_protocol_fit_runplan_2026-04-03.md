# OpenAMP 剩余协议 / FIT 缺口执行计划（2026-04-03）

## 目的

把当前仍未收口、且明确依赖真实板侧 / 真实协议通道的 OpenAMP 缺口，整理成一页可执行计划。

这份文档只处理这类剩余项：

- `FIT-04`：参数 / 帧篡改（非法 CRC 控制帧）
- `FIT-05`：结果不完整
- `TC-007`：非法 CRC 控制帧
- `TC-008`：deadline 超时
- `TC-009`：输出不完整失败
- `TC-010`：sticky fault + `RESET_REQ/ACK` 恢复

---

## 1. 当前边界

### 已完成的核心闭环

当前已经板级落证：

- `STATUS_REQ/RESP`
- `JOB_REQ/JOB_ACK`
- `HEARTBEAT_ACK`
- `SAFE_STOP`
- `JOB_DONE`
- `FIT-01` wrong SHA
- `FIT-02` input contract
- `FIT-03` heartbeat timeout（保留 `FAIL -> fix -> PASS`）

### 当前仍未完成的部分

- `FIT-04`
- `FIT-05`
- `TC-007`
- `TC-008`
- `TC-009`
- `TC-010`

其中需要特别区分：

- `TC-007/008/009` 与 `FIT-04/05`：属于**可以继续补真机证据**的剩余协议/FIT 项
- `TC-010`：当前仍属于明确 out-of-scope / next-step 扩展，不应在本轮答辩里 overclaim；但如果后续真做，也应按这里的格式补证

---

## 2. 建议优先级

### 第一优先级：`TC-007 / FIT-04`

原因：

- 和当前已有控制帧 / bridge 逻辑最接近
- 与“参数/帧篡改风险”直接对应
- 不依赖重建 runner 完整执行链

### 第二优先级：`TC-009 / FIT-05`

原因：

- 和结果落盘 / output count / `JOB_DONE(failed)` 语义直接相关
- 能补齐“结果不完整风险”这条正式风险项
- 但需要 runner / wrapper / output accounting 配合

### 第三优先级：`TC-008`

原因：

- 需要 deadline enforcement 真实存在
- 当前仓库里已有定义，但是否已进入 live firmware 仍待验证

### 第四优先级：`TC-010`

原因：

- 当前明确不在本轮正式 claim 内
- 即便做，也应作为协议扩展或后续能力，而不是当前答辩收口前提

---

## 3. 各项执行计划

## 3.1 `TC-007` / `FIT-04`：非法 CRC 控制帧

### 目标语义

- 发送坏 CRC 控制帧
- 从核拒收
- 记录 fault
- 形成 protocol log / fault log

### 最小执行路径

1. 确认 live firmware 仍可响应普通 `STATUS_REQ/RESP`
2. 在 bridge 侧构造一帧 **字段合法但 CRC 故意损坏** 的控制消息
3. 发到真实 `/dev/rpmsg0`
4. 观察：
   - 是否被直接丢弃
   - 是否有 fault 计数 / 状态变化
   - 是否存在 follow-up `STATUS_RESP` 可观测差异
5. 落盘：
   - raw frame
   - hexdump
   - pre / post status snapshot
   - protocol trace
   - fit report

### 建议产物路径

- `session_bootstrap/reports/openamp_crc_fault_fit_<timestamp>/`
- `fit_report_FIT-04.md`
- `fit_summary.json`
- `protocol_trace.jsonl`

### Done 标准

- 至少有一次真实坏 CRC 帧发送证据
- 证据能说明“被拒收 / 被记 fault / 未进入正常作业路径”三者之一
- 不再只是 mock 语义

---

## 3.2 `TC-009` / `FIT-05`：结果不完整

### 目标语义

- 模拟写盘失败 / 删部分输出
- 系统标记失败
- `JOB_DONE(failed)` 或等效失败状态可观测
- 保留 output count / result integrity 证据

### 最小执行路径

1. 选择一条当前可跑的 reconstruction path
2. 注入一种最小、可控的“结果不完整”方式，例如：
   - runner 侧提前停止写盘
   - wrapper 侧故意只保留部分输出
   - output count check 故意触发 mismatch
3. 观察：
   - 是否收敛成 `JOB_DONE(failed)` 或等效失败状态
   - 是否把 failure reason 显式落盘
4. 落盘：
   - expected vs actual output count
   - wrapper summary
   - runner summary
   - control trace
   - fit report

### 建议产物路径

- `session_bootstrap/reports/openamp_result_incomplete_fit_<timestamp>/`
- `fit_report_FIT-05.md`
- `fit_summary.json`
- `output_count_log.json`

### Done 标准

- 真实板侧 / runner 链路上出现一次“结果不完整 -> failure 收敛”的正式证据
- 能明确映射到“结果不完整风险”

---

## 3.3 `TC-008`：deadline 超时

### 目标语义

- 设置极短 deadline
- 正常启动作业
- 从核触发 `F006`
- 有 deadline log

### 当前判断

这项是否值得优先做，取决于 live firmware 里 deadline enforcement 是否已经有真实实现基础；否则容易退化成“为了补矩阵而新增临时逻辑”。

### 建议策略

- 若 live firmware 当前没有现成 deadline path，先降优先级
- 不为了补表格在本轮答辩前强造新协议能力

---

## 3.4 `TC-010`：sticky fault + `RESET_REQ/ACK`

### 当前边界

- 当前仍明确不在本轮正式 claim 内
- 不能为了勾 `TC-001/002/003/004/006/010` 而硬说已完成

### 如果后续要做

至少应满足：

1. 先真实触发 sticky fault（如 `F003/F004`）
2. 发送 `RESET_REQ`
3. 收到 `RESET_ACK`
4. 有 `READY` 回归证据
5. 有完整 state transition log

### 当前建议

- 继续保留为后续协议扩展项
- 只在真实需要扩展正式 claim 时再做

---

## 4. 推荐执行顺序（可直接抄给后续会话）

1. 先跑 `TC-007 / FIT-04`（非法 CRC）
2. 再跑 `TC-009 / FIT-05`（结果不完整）
3. 若 live firmware 已具备 deadline 基础，再考虑 `TC-008`
4. `TC-010` 保持最低优先级，除非项目正式决定扩 claim

---

## 5. 关联入口

- `paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/coverage_matrix.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/summary_report.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/reports/project_next_real_blockers_after_docs_freeze_2026-04-03.md`
