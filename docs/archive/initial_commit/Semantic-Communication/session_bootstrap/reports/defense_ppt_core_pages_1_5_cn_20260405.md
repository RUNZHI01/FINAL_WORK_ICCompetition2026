# 飞腾杯答辩核心页稿（Page 1-5，2026-04-05）

- 用途：当答辩时间只有 `3 分钟左右` 时，直接按这 `5` 张页讲
- 设计原则：每一页只承担一个结论；先系统身份，再模式边界，再性能，再安全，再总收尾
- 数字边界：性能页只讲 `1850.0 / 230.3 / 134.6`；动态尺寸只讲 `98.2 s / 327.3 ms/image`

## Page 1

- 页标题：`飞腾多核异构安全语义回传系统`
- 主图：`paper/CICC0903540初赛技术文档.md` 中 `图 1.3`
- 页核心信息：
  - 先把项目身份定死，这不是单点 benchmark，而是一套系统方案
  - 上位机负责语义编码与传输，飞腾侧负责重建，RTOS 负责控制与安全
  - 一句话目标：`传得回、跑得快、用得稳`
- 过渡句：下一页直接说明为什么这套系统必须分两种 operating mode 来讲

## Page 2

- 页标题：`双模式边界：性能和安全分开取证`
- 主图：`paper/CICC0903540初赛技术文档.md` 中 `图 3.3`
- 页核心信息：
  - `4-core Linux performance mode` 只负责正式性能口径
  - `3-core Linux + RTOS demo mode` 只负责 OpenAMP 控制面、安全和演示闭环
  - `remoteproc` 会占掉一个 Linux CPU，所以两种模式不能混写
- 过渡句：模式边界定住以后，性能页只讲 4 核 Linux 的固定形状主路径

## Page 3

- 页标题：`性能主口径：4-core Linux 上的可信结果`
- 主图：`paper/CICC0903540初赛技术文档.md` 中 `图 5.1`
- 页核心信息：
  - 初始端到端：`1850.0 ms/image`
  - TVM 主线：`230.3 ms/image`
  - big.LITTLE 流水线：`134.6 ms/image`
  - MNN 动态尺寸旁路：`98.2 s / 327.3 ms/image`
- 讲者备注：
  - 这页只主张性能主口径
  - 不把 OpenAMP 说成速度来源
- 过渡句：性能成立以后，下一页回答“这条链路为什么不是裸奔的”

## Page 4

- 页标题：`安全控制不是口头承诺`
- 主图优先级：
  - 首选：`paper/CICC0903540初赛技术文档.md` 中 `图 3.1`
  - 备选：`paper/CICC0903540初赛技术文档.md` 中 `图 5.2`
- 页核心信息：
  - OpenAMP 已覆盖 `STATUS_REQ/RESP`、`JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP`、`JOB_DONE`
  - 三项 FIT 已正式收口：错误 SHA、非法参数、心跳超时
  - `FIT-03` 不是一次通过，而是 `发现缺口 -> 修复 -> 复验通过`
- 过渡句：性能和安全分别成立后，最后一页把三条线收成一个系统结论

## Page 5

- 页标题：`结论：这是一件飞腾系统作品`
- 主图：`paper/CICC0903540初赛技术文档.md` 中 `图 5.3`
- 页核心信息：
  - 数据面：TVM 固定形状 + MNN 动态尺寸
  - 控制面：OpenAMP + RTOS 提供准入、监护和安全停机
  - 展示面：`dashboard` 与证据包保证答辩可追问、可切证据
  - 最终主张：性能、灵活部署、安全边界三者同时成立
- 收尾句：
  - `4-core Linux mode` 证明飞腾多核性能成立
  - `3-core Linux + RTOS mode` 证明 OpenAMP 控制边界成立
  - 合起来才是本作品的系统价值

## 若被追问时的跳转

- 被问“是不是拿质量换速度” -> 跳 `图 4.11`
- 被问“为什么弱网下要做语义通信” -> 跳 `图 4.12`
- 被问“评审具体该看哪些证据” -> 跳 `图 5.2`

## 对齐依据

- `paper/CICC0903540初赛技术文档.md`
- `session_bootstrap/reports/defense_ppt_pages_1_8_cn_20260319.md`
- `session_bootstrap/reports/defense_deck_outline_20260319.md`
- `session_bootstrap/reports/defense_talk_track_3min_20260405.md`
