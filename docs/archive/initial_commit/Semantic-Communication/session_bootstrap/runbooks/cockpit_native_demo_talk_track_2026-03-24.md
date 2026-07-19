# cockpit_native demo talk track（2026-03-24）

## 目标

把 `cockpit_native` 当成**飞腾派 TVM/OpenAMP 演示座舱**来讲，不把它讲成“网页原型”或“静态可视化”。

## 最短启动

```bash
bash ./session_bootstrap/scripts/run_cockpit_native.sh
```

说明：
- 该入口现在会优先确保 operator server 在线。
- 若 `127.0.0.1:8079` 未启动，会自动后台拉起 `run_openamp_demo.sh`。
- native cockpit 默认软件安全渲染启动。

## 一键彩排

```bash
bash ./session_bootstrap/scripts/run_cockpit_native_demo_rehearsal.sh
```

用途：
- 确认 operator server 健康
- 导出 landing / flight / actiondock 三张备用图
- 再拉起 live cockpit

## 评委一句话版本

> 这套原生座舱不是 mock 页面，而是直接承接仓库现有 TVM/OpenAMP 合同、任务地图和 live action 的演示壳体；当前可信性能结论是 **Current 153.778 ms，对 baseline 1844.1 ms 提升 91.66%**。

## 30 秒开场词

> 各位老师，这不是网页 mock，而是原生 Qt / QML 座舱。它直接承接仓库现有的 TVM/OpenAMP 合同、任务地图和 live action。现在这套 cockpit 的可信 headline 很明确：**Current 从 baseline 的 1844.1 ms 降到 153.778 ms，提升 91.66%**。下面我先用首页给各位看任务态势，再切飞行合同页讲地图和位置来源，最后到执行页现场点按钮。

## 2 分钟完整版

> 这套 native cockpit 不是单独做的视觉原型，而是直接接现有仓库的 TVM/OpenAMP 演示合同。首页我们把中国任务区态势板、系统摘要和 live action 收在一页里，先给出评审最关心的 headline：**Current 153.778 ms，对 baseline 1844.1 ms 提升 91.66%**。  
> 接下来切到飞行合同页，这一页把地图、飞机合同、位置来源和性能结论放到同一个视图里。这里的位置来源是明确标注的，如果上游 GPS 在线，就走 `/api/aircraft-position`；如果没有 live feed，就会明确显示 repo-backed stub telemetry，不会伪装成真实定位。  
> 最后切到执行页，这一页不是信息页，而是控制台。演示顺序固定是 `Current 在线重建`、`重载合同`、`探测板卡状态`。Current 负责展示核心性能结论，Reload 负责说明这不是 mock，Probe 负责把 live 限制和板卡状态收口。这样三页讲下来，评审能同时看到任务态势、可信性能、和可点的 live action。

## 推荐讲解顺序

### 1. 首页

先说三句：

1. 这是**原生 Qt / PySide6 cockpit**，不是网页。
2. 首页主舞台直接是**中国任务区态势板**，不是手画示意。
3. 当前可信 headline 是：`1844.1 ms -> 153.778 ms`，`Current 相比 baseline 提升 91.66%`。

讲解重点：
- 左侧只保留系统摘要，避免评委被细节拖住。
- 中间地图直接承接任务态势。
- 底部 command dock 给出 live action 入口。

### 2. 飞行合同页

要说的点：

1. 地图仍然是中国飞行态势板，不是孤立小点。
2. 页面明确标注**位置来源**。
3. 如果没有真实 GPS，上面会直说是 `repo-backed stub telemetry`，不会伪装成 live GPS。

讲解句式：

> 这一页把任务地图、飞行合同和性能 headline 放在一起，评委可以同时看到任务态势、当前位置语义和可信性能结论。

### 3. 执行页

执行顺序固定按这三个动作讲：

1. `current_online_rebuild`
2. `reload_contracts`
3. `probe_live_board`

讲解句式：

> 执行页不是信息页，而是演示控制台。Current 在线重建是主动作，Reload 负责说明它不是 mock，Probe 负责把板卡状态和 live 限制说明收口。

## 当前可信性能结论

- baseline median: `1844.1 ms`
- current median: `153.778 ms`
- delta: `-1690.322 ms`
- improvement: `91.66%`
- speedup: `12.0x`

来源：
- `session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md`

## 当前 live 语义边界

- operator actions 通过 `http://127.0.0.1:8079` bridge 到 demo server。
- aircraft position 优先读 `/api/aircraft-position`。
- 若上游 GPS producer 不在线，cockpit 会明确显示 `backend_stub / stub`。
- 不允许把默认样例坐标说成真实 GPS。

## 现场如果被追问

### Q: 这是不是网页 mock？

答：

> 不是。这是原生 Qt / QML 座舱壳体，直接读取仓库已有 TVM/OpenAMP 合同和 operator action。

### Q: 你们 current 和 baseline 的关系是什么？

答：

> 当前可信结论是 Current 已明显快于 baseline。正式口径是 `1844.1 ms -> 153.778 ms`，提升 `91.66%`。

### Q: 飞机位置是不是真实时 GPS？

答：

> 页面会明确显示位置来源。真实 GPS 在线时走 `/api/aircraft-position`；如果当前没有 live feed，就明确显示 repo-backed stub telemetry，不伪装成真实定位。

### Q: 按钮是不是假的？

答：

> 不是纯装饰。Current、Reload、Probe 都是可点击动作；如果 live 条件不满足，界面会返回明确限制说明，而不是伪装成执行成功。

## 当前建议的演示页顺序

1. 首页：给 headline 和第一印象
2. 飞行合同页：讲地图、位置来源、性能结论
3. 执行页：点按钮，讲 live action 和边界
