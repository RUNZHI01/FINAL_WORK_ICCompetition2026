# FIT-02 输入契约正式案例卡：历史 `batch=4` vs 固定 `batch=1`

> 日期：2026-04-03  
> 用途：把历史 realcmd 故障 `batch=4` vs 固定 `batch=1` 改写成答辩 / 证据包可直接引用的正式 `FIT-02` 输入契约案例。  
> 正式结论：我们没有回避这次历史失败，而是把它前移成了 admission gate 的输入契约校验样例。mock 层保留原始 `batch=4` 样本，真机层用当前已实现的 `expected_outputs=2` 触发 `ILLEGAL_PARAM_RANGE`，两者共同收口“输入契约违规风险”。

## 1. 历史故障原样

历史真实失败来自 `full current` 一次 realcmd 执行：

- `FULL_CURRENT_CMD` 当时传入 `--batch_size 4`
- TVM VM 运行时报告模型入口标注为 `R.Tensor((1, 32, 32, 32), dtype="float32")`
- 随后在 `match_cast` 路径报出 `input_shape[i] == reg (4 vs. 1)`

这说明模型入口 `batch` 维度是编译期固定常量 `1`，运行时把它改成 `4` 会在真正进入 TVM 后才失败。原始结论保留在：

- `session_bootstrap/PROGRESS_LOG.md`

## 2. FIT-02 设计目标

设计文档一开始就把这类问题定义为输入契约风险，而不是单次偶发调参事故：

- `TC-004`：构造 `batch=4` 或非法 shape，期望前置拒绝
- `FIT-02`：提交 `batch=4` / 非法 shape，期望在进入 TVM 前被拦截

对应文档：

- `paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`
- `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`

## 3. 现在这条风险怎样被正式收口

### 3.1 mock 层保留原始 `batch=4` 样本

最早的 mock `FIT-02` 仍然保留了历史原型：

- injected fault：`构造 batch=4，触发固定 batch=1 契约拒绝`
- result：`DENY`
- fault：`F002 / INPUT_CONTRACT_INVALID`

证据：

- `session_bootstrap/reports/openamp_mock_examples/smoke_20260313_p0p1/deny_input/fit_report_FIT-02.md`

### 3.2 真机层使用当前已实现的输入契约字段

真实板级 `FIT-02` 最终采用的是当前 firmware 已实现的 `JOB_REQ.expected_outputs` 准入检查：

- injected fault：`expected_outputs=2`
- board response：`JOB_ACK(DENY, ILLEGAL_PARAM_RANGE)`
- wrapper result：`denied_by_control_hook`
- runner：未启动
- post status：仍为 `READY / active_job_id=0`

证据：

- `session_bootstrap/reports/openamp_phase5_fit02_input_contract_success_2026-03-15.md`
- `session_bootstrap/reports/openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md`

## 4. 为什么这两层证据可以合并为同一张正式案例卡

这里需要明确说清楚这是一条工程归一化口径：

- 设计层的通用风险名是“输入契约违规”，历史原型是 `batch=4` 撞上固定 `batch=1`
- mock 层直接保留了这个原型，因此能回答“这个风险最初到底是什么”
- 真机 `release_v1.4.0` 的 `JOB_REQ` 并没有单独暴露 literal `batch` 字段，但已经暴露了同一 admission boundary 上的“计数 / 范围”契约字段 `expected_outputs`
- 因而答辩中的正式说法应是：我们把“运行时 batch 错配”这类输入契约故障，收敛成了进入 runner 之前的 admission-gate 拒绝

进一步说：

- mock 里的 `F002 / INPUT_CONTRACT_INVALID` 对应设计期的泛化契约故障
- 真机里的 `F009 / ILLEGAL_PARAM_RANGE` 对应 release 实现中的具体参数范围故障

这不是在伪造“真机直接复现 literal batch 字段”，而是在如实说明：当前真机已经把同类输入契约 / 计数越界风险前置到控制面门禁。

## 5. 三层证据链

| 层级 | 注入样本 | 观测结果 | 现在可以对外讲的含义 |
|---|---|---|---|
| 历史真实故障 | `--batch_size 4` | 进入 TVM 后因 `4 vs. 1` 失败 | 原始风险客观存在，而且曾经是 runtime 才暴露 |
| mock `FIT-02` | `batch=4` | `DENY(F002)` | 设计上已经把该风险改写成前置输入契约拒绝 |
| 真机 `FIT-02` | `expected_outputs=2` | `JOB_ACK(DENY, F009)`，runner 未启动 | 当前板级实现已经把同类契约 / 范围违规挡在 admission gate 外 |

## 6. 答辩可直接引用口径

### 10 秒版

我们把历史上一次真实出现的 `batch=4` 对固定 `batch=1` 错配，正式升级成了 `FIT-02` 输入契约案例；现在这类非法请求会在 runner 启动前被控制面拒绝，而不是跑进 TVM 后才报错。

### 20 秒版

这个案例不是凭空设计出来的。最早 realcmd 确实发生过 `batch=4` 撞上模型固定 `batch=1` 的运行时失败，所以我们把它抽象成 `FIT-02` 输入契约风险。mock 里保留了原始 `batch=4` 样本；真机里则用当前协议已经实现的 `expected_outputs=2` 做同类门禁验证，最终拿到 `JOB_ACK(DENY, ILLEGAL_PARAM_RANGE)`，并且 runner 根本没有启动。

## 7. 使用边界

这张案例卡只支持下面这句正式主张：

- 历史 `batch=4` vs 固定 `batch=1` 已被正式收敛为 `FIT-02` 输入契约风险，并且当前真机已经能在 admission gate 前置拒绝同类参数 / 计数违规请求

这张案例卡不支持下面这种过度表述：

- “当前真机已经直接发送 literal `batch=4` 字段并完成了同字段复现”

## 8. 直接引用入口

- 历史原始故障：`session_bootstrap/PROGRESS_LOG.md`
- 设计定义：`paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`
- 赛题对齐主叙事：`paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
- mock 原始样例：`session_bootstrap/reports/openamp_mock_examples/smoke_20260313_p0p1/deny_input/fit_report_FIT-02.md`
- 真机正式收证：`session_bootstrap/reports/openamp_phase5_fit02_input_contract_success_2026-03-15.md`
- 真机 bundle：`session_bootstrap/reports/openamp_input_contract_fit_20260315_014542/fit_report_FIT-02.md`
