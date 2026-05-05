# 飞腾杯答辩 PPT 页稿（Page 1-8）

- 用途：今晚直接据此搭建答辩 PPT
- 口径要求：统一使用“飞腾多核弱网安全语义视觉回传系统”叙事；严格区分 `4-core Linux performance mode` 与 `3-core Linux + RTOS demo mode`
- 数字边界：仅使用已锁定的 `484.183 / 231.522 / 134.617 / 56.077%`

## Page 1

- 页标题：`飞腾多核弱网安全语义视觉回传系统`
- 页核心信息：先把项目身份定死，这不是单点 TVM 调优，而是一套面向弱网场景、部署在飞腾平台上的系统方案。
- 页内文案：
  - 作品目标不是“把一个模型跑快”，而是完成弱网条件下的语义视觉回传与重建。
  - 上位机负责语义编码与传输，飞腾侧负责高性能重建与结果回传。
  - 系统同时覆盖多核性能路径和安全控制路径，不把两者混成一个卖点。
  - 因此项目应被表述为飞腾多核系统作品，而不是 generic benchmark。
- 讲者备注 / 过渡句：第一页先讲“我们在做什么”，下一页再讲“为什么弱网场景必须做语义回传”。

## Page 2

- 页标题：`场景问题：弱网下为什么要做语义视觉回传`
- 页核心信息：真实问题不是传图，而是在带宽受限、链路波动的条件下，把有价值的视觉语义可靠回传到飞腾侧完成重建。
- 页内文案：
  - 弱网、边缘、受限带宽场景下，直接回传原始像素代价高、鲁棒性差。
  - 系统把回传对象从原始图像转为更紧凑的语义特征 latent。
  - 发送端先做语义编码、量化与传输组织，接收端在飞腾侧完成解码重建。
  - 这样既降低链路压力，也把飞腾多核算力真正用在重建任务上。
- 讲者备注 / 过渡句：问题定义清楚后，下一页说明这套系统在飞腾平台上是怎么分层落地的。

## Page 3

- 页标题：`系统架构：数据面与控制面分离`
- 页核心信息：系统不是把所有功能塞进一条链路，而是明确拆成高性能数据面和安全控制面。
- 页内文案：
  - 数据面保持现有可信主路径：上位机负责编码与传输，飞腾 Linux 侧运行 trusted current TVM 重建链路。
  - 控制面交给 OpenAMP/RTOS，负责 admission、heartbeat、safe stop、fault accounting。
  - 控制面只传 `job_id`、`expected_sha256`、`input_shape`、心跳等小控制消息。
  - OpenAMP 不搬大张量，也不改写数据面推理链路。
  - 一句话概括：Linux/TVM 负责“把结果做出来”，OpenAMP/RTOS 负责“让执行链可控可审计”。
- 讲者备注 / 过渡句：架构边界说明白之后，下一页直接解释为什么我们必须把答辩口径拆成两种 operating mode。

## Page 4

- 页标题：`双模式设计：性能模式与演示模式分开表述`
- 页核心信息：为了避免 mode mixing，性能主张和安全演示必须分模式成立、分模式取证。
- 页内文案：
  - `4-core Linux performance mode` 只负责 headline performance。
  - `3-core Linux + RTOS demo mode` 只负责 OpenAMP 安全控制面演示。
  - 当 `remoteproc` 拉起 RTOS 后，会占用一个 Linux CPU，因此 demo mode 不能再被表述为完整 4 核 Linux。
  - 两种模式分别解决“跑得快”和“跑得稳、跑得可控”两类问题。
  - 这也是我们主动避免把性能数字和控制面证据混写的原因。
- 讲者备注 / 过渡句：先看性能模式，这一页只讲 `4-core Linux performance mode` 下已经锁定的可信结果。

## Page 5

- 页标题：`性能模式：4-core Linux 上的可信 headline`
- 页核心信息：真正用于对外性能主张的，是 `4-core Linux performance mode` 下的飞腾多核重建结果。
- 页内文案：
  - PyTorch default reference：`484.183 ms/image`
  - TVM serial current：`231.522 ms/image`
  - TVM big.LITTLE pipeline current：`134.617 ms/image`
  - 相对同轮 serial current 吞吐 uplift：`56.077%`
  - 这组数字全部来自 `4-core Linux performance mode`，OpenAMP 不是速度来源。
- 讲者备注 / 过渡句：性能线说明“飞腾多核确实跑起来了”，下一页再说明演示模式到底证明了什么。若评委立即追问“加速是不是牺牲了质量”，不要在主线页硬展开，直接切附录 Page 9。

## Page 6

- 页标题：`演示模式：3-core Linux + RTOS 的安全控制面`
- 页核心信息：启用 OpenAMP 后，系统进入诚实表述的 `3-core Linux + RTOS demo mode`，其价值是控制与安全，不是 headline performance。
- 页内文案：
  - `remoteproc` 拉起 RTOS 后，一个 Linux CPU 会让渡给控制面，因此该模式必须单独标注。
  - 这条线的目标不是追求最快，而是展示高性能数据面背后的安全执行边界。
  - OpenAMP 已承担状态查询、任务放行、心跳监护、安全停止、任务完成回报等控制职责。
  - 因此 demo mode 展示的是“系统可控可治理”，而不是“OpenAMP 让推理更快”。
- 讲者备注 / 过渡句：控制面不是概念描述，下一页给出它已经收口的板级闭环和 FIT 证据。若评委追问“启用控制面后还有多少 Linux 资源可用”，可以先讲完主线，再切附录 Page 10 的资源画像。

## Page 7

- 页标题：`安全证据：OpenAMP 控制闭环与 FIT 已收口`
- 页核心信息：OpenAMP 控制面不是 mock，它已经在真机上形成最小安全闭环，并且有正式故障注入验证。
- 页内文案：
  - 当前已有 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT_ACK`、`SAFE_STOP`、`JOB_DONE` 板级证据。
  - `FIT-01` 证明错误 SHA 会被 admission gate 拒绝。
  - `FIT-02` 证明非法输入参数会被 contract gate 拒绝。
  - `FIT-03` 完成 heartbeat timeout 的 `fail -> fix -> pass` 闭环。
  - 结论是：系统已经具备可准入、可拒绝、可监护、可安全停止的最小控制能力。
- 讲者备注 / 过渡句：把性能页和安全页合起来，才能说明这不是单框架 benchmark，而是一件飞腾系统作品。若评委追问“弱网条件变化时系统稳不稳”，主线里先不给新表，直接切附录 Page 11。

## Page 8

- 页标题：`结论：该主张什么，不该主张什么`
- 页核心信息：答辩收尾要主动交代边界，既把系统价值讲完整，也避免 overclaim。
- 页内文案：
  - 应主张：这是一个飞腾多核弱网安全语义视觉回传系统。
  - 应主张：`4-core Linux performance mode` 给出了 `484.183 -> 231.522 -> 134.617 ms/image` 的清晰性能层次。
  - 应主张：`3-core Linux + RTOS demo mode` 给出了 OpenAMP 控制面和 `FIT-01/02/03` 证据。
  - 不应主张：OpenAMP 让 TVM 更快；也不应把两种 mode 的结果混写成同一口径。
  - 最终系统价值来自两条线的组合：飞腾多核性能利用 + 异构控制与安全治理。
- 讲者备注 / 过渡句：以上是我们对项目价值和边界的完整主张，老师如果关注性能可追问 Page 5，如果关注安全控制可继续看 Page 6-7；如果继续追问质量、资源、SNR 或 profiling 边界，直接切 `defense_appendix_pages_9_12_judge_evidence_20260330.md`，顺序默认是：质量→Page 9，资源→Page 10，SNR→Page 11，profiling 边界→Page 12。
