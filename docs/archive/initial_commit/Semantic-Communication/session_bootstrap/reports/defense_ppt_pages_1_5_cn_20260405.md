# 飞腾杯答辩 PPT 页稿（Page 1-5，2026-04-05）

- 用途：直接据此制作 `3 分钟版` 答辩 PPT
- 讲法原则：先系统身份，再模式边界，再性能，再安全，再总收尾
- 口径红线：不把 OpenAMP 说成加速来源；不混写两种 operating mode；不把 `TC-010` 讲成已正式收口

## Page 1

- 页标题：`飞腾多核异构安全语义图像回传系统`
- 主图：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 1.3`
- 页内文案：
  - 不是单点 TVM benchmark，而是一套系统方案
  - 上位机负责语义编码与信道扰动模拟
  - 飞腾侧负责重建，RTOS 负责控制与安全
  - 目标：`传得回、跑得快、用得稳`
- 讲者备注：
  - 第一句就把项目身份定死
  - 不要先讲调优细节或 OpenAMP 协议
- 过渡句：
  - “这套系统最关键的地方，是我们把性能和安全按两种模式分开取证。”

## Page 2

- 页标题：`双模式边界：性能和安全不能混写`
- 主图：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 3.3`
- 页内文案：
  - `4-core Linux performance mode`：只负责正式性能口径
  - `3-core Linux + RTOS demo mode`：只负责 OpenAMP 控制面、安全和演示闭环
  - `remoteproc` 拉起 RTOS 后，会占用一个 Linux CPU
  - 所以两种模式必须分开表述、分开引用数字
- 讲者备注：
  - 这一页的作用是防止评委把所有数字当同一种 mode
  - 主动讲清边界，后面就不容易被抓 mode mixing
- 过渡句：
  - “先看性能模式，也就是 4 核 Linux 下已经锁定的可信结果。”

## Page 3

- 页标题：`性能主口径：4-core Linux 上的可信结果`
- 主图：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 5.1`
- 页内文案：
  - 初始端到端：`1850.0 ms/image`
  - TVM 主线：`230.3 ms/image`
  - big.LITTLE 流水线：`134.6 ms/image`
  - MNN 动态尺寸旁路：`98.2 s / 327.3 ms/image`
- 讲者备注：
  - 只主张这页的性能主口径
  - 明说：性能提升来自 TVM 主线和异构流水线，不来自 OpenAMP
  - MNN 在这页只作为动态尺寸补充，不和 TVM 抢主线
- 过渡句：
  - “但我们不是只做出了一条更快的链路，下一页要说明这条链路为什么不是裸奔的。”

## Page 4

- 页标题：`安全控制不是口头承诺`
- 主图优先级：
  - 首选：`paper/CICC0903540初赛技术文档.md` 中 `图 3.1`
  - 备选：`paper/CICC0903540初赛技术文档.md` 中 `图 5.2`
- 页内文案：
  - 五类消息：`STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE`
  - 三项 FIT 已收口：错误 SHA、非法参数、心跳超时
  - `FIT-03` 保留 `发现缺口 -> 修复 -> 复验通过`
  - 结论：系统可准入、可拒绝、可监护、可安全停机
- 讲者备注：
  - 这页不要讲速度
  - 重点是“OpenAMP 不让模型更快，但让系统可控”
- 过渡句：
  - “所以最后一页要把性能、灵活部署和安全边界三条线收成一个系统结论。”

## Page 5

- 页标题：`结论：这是一件飞腾系统作品`
- 主图：
  - `paper/CICC0903540初赛技术文档.md` 中 `图 5.3`
- 页内文案：
  - 数据面：TVM 固定形状 + MNN 动态尺寸
  - 控制面：OpenAMP + RTOS 提供准入、监护和安全停机
  - 展示面：`dashboard` 与证据包支撑答辩追问
  - 最终主张：性能、灵活部署、安全边界三者同时成立
- 收尾句：
  - `4-core Linux mode` 证明飞腾多核性能成立
  - `3-core Linux + RTOS mode` 证明 OpenAMP 控制边界成立
  - 合起来才是这件作品的系统价值

## 导页时长建议

- Page 1：25 秒
- Page 2：30 秒
- Page 3：45 秒
- Page 4：45 秒
- Page 5：35 秒

## 被追问时的切页顺序

- 被问“是不是拿质量换速度” -> 切 `图 4.11`
- 被问“为什么弱网下要做语义通信” -> 切 `图 4.12`
- 被问“具体证据都放在哪里” -> 切 `图 5.2`

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
- `session_bootstrap/reports/defense_ppt_core_pages_1_5_cn_20260405.md`
- `session_bootstrap/reports/defense_ppt_pages_1_8_cn_20260319.md`
