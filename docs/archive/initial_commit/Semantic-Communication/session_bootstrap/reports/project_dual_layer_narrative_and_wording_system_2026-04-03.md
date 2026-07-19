# 项目“双层口径 / 双层主叙事”正式说明（2026-04-03）

## 目的

把任务板中仍未勾掉的两项：

- 建立“双层口径”体系
- 建立“双层主叙事”体系

合并成一份可直接引用的正式说明，明确：

1. **主展示面**到底说什么
2. **历史优化证据链**保留什么
3. 两层之间如何切换，避免主画面和历史材料互相打架

---

## 1. 核心定义

### 第一层：主展示面（front-stage wording）

这是所有面向评委 / Demo / 答辩 / 总结页 / 口播时默认采用的说法。

它的目标不是“把所有历史都讲出来”，而是：

- 用当前**最稳定、最可信、最可复核**的一套结果代表项目
- 避免旧 SHA、旧 benchmark、旧板态、旧阶段性数字把主画面搅乱

### 第二层：历史优化证据链（back-stage evidence lineage）

这是所有历史阶段、旧 SHA、旧 benchmark、旧比较、旧故障、旧板态漂移证据的留档层。

它的作用不是抢主叙事，而是：

- 回答“你们是怎么走到今天这一步的”
- 保留工程真实性
- 作为里程碑、演进链和失败-修复历史的证据

---

## 2. 第一层：主展示面应该固定说什么

### 2.1 项目主标题 / 主定位

主展示面统一采用：

> **基于飞腾平台的安全可靠图像语义通信系统**

如果需要更技术化版本，则采用：

> **基于飞腾平台的安全可靠图像语义通信系统：TVM 高性能解码、OpenAMP 异构监护与端到端验证**

### 2.2 主展示面的系统角色切分

- `TVM`：高性能解码主线
- `OpenAMP`：异构监护、heartbeat、参数校验、安全停止
- `SHA guard`：trusted artifact 身份校验与非法镜像拒绝执行
- `FIT / coverage / risk analysis`：安全可靠工程化证明链

### 2.3 主展示面的正式数字

主展示面只允许默认引用：

- trusted current SHA：`6f236b07...6dc1`
- payload 正式口径：`1846.9 -> 130.219 ms`
- 真实端到端正式口径：`1850.0 -> 230.339 ms/image`

### 2.4 主展示面的 Demo 口径

- `4-core Linux performance mode`：只讲 headline performance
- `3-core Linux + RTOS demo mode`：只讲 control plane / safety / live operator flow
- `8115 / 300 / 300`：只作为 live reconstruction 与 `TC-002` 收口证据
- `TC-010 / RESET_REQ/ACK / sticky fault reset`：明确不在当前正式 claim 内

---

## 3. 第二层：历史优化证据链保留什么

第二层不删历史，但必须把历史材料明确降到“证据链”角色，而不是主画面角色。

### 3.1 应保留的历史内容

- 旧 trusted current SHA 与对应阶段成果
- 早期 payload / reconstruction benchmark
- 旧 target 选择与 safe runtime 收敛历史
- batch 契约错误、watchdog 缺口等真实故障样本
- degraded-board 漂移证据
- baseline / current 不同阶段的 apples-to-apples compare
- big.LITTLE 演进链与板态差异证据

### 3.2 历史材料的正确用途

- 讲里程碑
- 讲工程演进
- 讲失败-修复历史
- 讲为什么当前主口径可信

### 3.3 历史材料的错误用途

- 把旧 SHA 当成当前正式身份
- 把旧 benchmark 当成当前 headline performance
- 把 degraded-board 数字混进主画面
- 把旧阶段性的 `PyTorch live` / `baseline live` 表述拿来覆盖当前第三幕默认 compare 口径

---

## 4. 双层主叙事如何共存

### 4.1 对外主叙事

对外主叙事采用：

> 我们做的不是一个单纯把 cGAN 解码器跑快的优化项目，而是一个基于飞腾平台的安全可靠图像语义通信系统：TVM 负责高性能解码，OpenAMP 负责异构监护与控制面安全边界，SHA guard、coverage 和 FIT 负责把系统可信性做实。

### 4.2 对内 / 追问时的成长叙事

当需要回答“你们是怎么做到的”时，再展开第二层：

> 我们是从 TVM / MNN 优化图像语义通信系统起步，先把 safe runtime、target 收敛、payload 与 real reconstruction benchmark 做硬，再把历史真实故障改写成 FIT，把 OpenAMP 引入为控制面与安全监护层，最终把单点性能成果升级成一个符合飞腾赛题要求的系统作品。

### 4.3 一句话边界

- 第一层负责“今天默认怎么讲”
- 第二层负责“为什么今天这套讲法成立”

---

## 5. 切换规则

### 默认使用第一层的场景

- PPT 首页 / 总结页
- 2 分钟 / 5 分钟讲稿
- Demo 首屏 / 第三幕 / operator card
- 评委第一轮总问答

### 需要切到第二层的场景

- 被追问历史优化路线
- 被追问旧数据为什么和现在不同
- 被追问为什么当前数字可信
- 需要解释 failure -> fix -> pass、板态漂移、历史 benchmark 差异

---

## 6. 对现有仓库材料的影响

### 应继续作为第一层入口的文档

- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

### 应继续作为第二层证据链入口的文档

- `session_bootstrap/PROGRESS_LOG.md`
- `session_bootstrap/runbooks/artifact_registry.md`
- `session_bootstrap/reports/big_little_real_run_summary_20260318.md`
- `session_bootstrap/reports/big_little_board_state_drift_20260318.md`
- 历史 benchmark / profiling / fault repair 报告

---

## 7. 对任务板更准确的解释

这意味着任务板里“建立双层口径 / 双层主叙事”这两项，现在更准确的状态是：

- **文档定义层已经可以认为完成**
- 剩余只是后续材料是否持续遵守这套切分，而不是这套体系本身还没定义

---

## 8. 关联文档

- `paper/飞腾赛题对齐与系统重构建议_2026-03-13.md`
- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
- `session_bootstrap/PROGRESS_LOG.md`
- `session_bootstrap/runbooks/artifact_registry.md`
- `session_bootstrap/reports/openamp_demo_docs_closure_summary_2026-04-03.md`
