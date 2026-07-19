# OpenAMP Demo / 视频脚本口径同步说明（2026-04-03）

## 目的

把当前答辩主线、四幕 runbook、72 秒视频脚本和现场 cheat sheet 的口径同步到同一套说法，避免继续出现以下混写：

- 把第三幕默认 compare 误讲成 `baseline live`
- 把 `300/300` live reconstruction 既当作 `TC-002` 收口，又顺手夸成 `TC-010` 已闭环
- 把 3-core demo mode 的 live 画面和 4-core performance mode 的 headline performance 混成同一组数字

## 当前统一口径

### 1. 第三幕默认 compare 仍是归档 `PyTorch reference`

- `2026-03-17` 的 baseline `300/300` 属于**历史 live 证据**，不是本场默认 operator flow
- 第三幕默认停在 `Current vs PyTorch reference archive`
- 只有评委明确追问时，才额外解释 baseline live 的历史事实；不把它当当前默认按钮路径

### 2. 第三幕正式性能只展示两条口径

- 正式 payload：`1846.9 -> 130.219 ms`
- 正式真实端到端：`1850.0 -> 230.339 ms/image`

第三幕说这两条即可，不混写其他 demo live median、drift 数字或板态波动数字。

### 3. `300/300` 的角色要说清楚

- `8115` 上 recent live `300/300` 证明当前系统不是离线 mock，而是真实在线 reconstruction 路径
- 这部分**当前只用于 `TC-002` 的 live reconstruction 收口**
- 不把 `300/300` 延伸解释成 `TC-010` 已完成

### 4. `TC-010` 继续明确保留为边界

当前对外仍不主张：

- `RESET_REQ/ACK`
- sticky fault reset
- deadline enforcement
- `FIT-04/05`

因此视频脚本、cheat sheet、operator card 和讲稿里都应显式避免类似说法：

> “300/300 都跑完了，所以 fault recovery 也已经完整闭环。”

## 本次落地文件

- `session_bootstrap/reports/openamp_demo_72s_script_m9_20260319.md`
- `session_bootstrap/reports/openamp_demo_cheat_sheet_m12_20260319.md`
- `session_bootstrap/tasks/赛题对齐后续执行总清单_2026-03-13.md`
- `session_bootstrap/tasks/赛题对齐执行追踪板_2026-03-13.md`

## 对外一句话版本

> 第三幕默认是 Current 对照归档 PyTorch reference，并只引用两条正式性能口径：`1846.9 -> 130.219 ms` 与 `1850.0 -> 230.339 ms/image`。`8115` 上 recent `300/300` 用来证明 live reconstruction 和 `TC-002` 收口已经成立，但我们不把它讲成 `TC-010` 或 `RESET_REQ/ACK` 也已闭环。

## 关联依据

- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/demo_four_act_runbook.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/defense_talk_outline.md`
- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
