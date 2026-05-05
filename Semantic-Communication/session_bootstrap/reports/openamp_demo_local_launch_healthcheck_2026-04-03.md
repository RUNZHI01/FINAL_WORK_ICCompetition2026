# OpenAMP Demo 本地启动健康检查（2026-04-03）

## 目的

在当前仓库状态下，重新实际拉起 `session_bootstrap/scripts/run_openamp_demo.sh`，确认：

1. 本地 dashboard 是否还能正常启动
2. 基础 API 是否可用
3. 当前真正阻塞 live 演示推进的点，是脚本/前端问题，还是板侧会话条件不足

---

## 1. 执行命令

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

启动后输出：

- `Feiteng semantic visual return demo dashboard: http://127.0.0.1:8079`
- `Project root: /home/tianxing/tvm_metaschedule_execution_project`

---

## 2. 本地接口检查结果

### `/api/health`

结果：

```json
{"status":"ok"}
```

结论：本地服务进程可正常启动。

### `/api/system-status`

关键结论：

- `execution_mode.label = 在线模式`
- `board_access.connection_ready = false`
- `missing_connection_fields = ["password"]`

这说明：

- dashboard 本地进程本身没有挂
- 当前不能继续把 live 会话推进下去的直接原因，不是服务没起，而是**板侧会话缺密码**

### `--prompt-password` launcher path（补充验证）

在补完 launcher 级 password prompt 后，额外实际验证：

```bash
printf 'demo-pass\n' | bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password
```

随后检查：

- `/api/health` 仍返回 `{"status":"ok"}`
- `/api/system-status` 显示：
  - `execution_mode.label = 在线模式`
  - `board_access.connection_ready = true`
  - `missing_connection_fields = []`
- `/api/snapshot` 仍能正确返回：
  - `mode.effective_label = 在线读数可用`
  - `board.current_status.label = 保存的只读 SSH 探板`
  - `valid_instance = 8115`
  - `artifact_sha = 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

这说明：

- launcher 的 `--prompt-password` 不只是把 password 带进 readiness preflight
- 它已经能把运行时 password 真正注入到 demo 会话配置里
- 当前若仍无法继续 live，下一步就不再是“会话字段没带进去”，而是更后续的真实板侧交互问题

### `--prompt-password --probe-startup` launcher path（补充验证）

进一步实际验证：

```bash
printf 'demo-pass\n' | bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password --probe-startup
```

随后检查：

- `/api/health` 仍返回 `{"status":"ok"}`
- `/api/system-status` 显示：
  - `execution_mode.label = 在线模式`
  - `board_access.connection_ready = true`
  - `missing_connection_fields = []`
- `/api/snapshot` 显示：
  - `mode.effective_label = 在线读数可用`
  - `board.current_status.label = 保存的只读 SSH 探板`
  - `board.current_status.summary` 仍明确写作“该结果来自上一次成功探板的保存记录”
  - `valid_instance = 8115`

这条验证能说明：

- `--prompt-password --probe-startup` 这条 launcher 路径本身是可执行的
- password 注入与 startup probe 参数传递没有把服务搞挂
- 但**当前还不能据此宣称 fresh live probe 已经成功**；从 snapshot 口径看，页面仍主要恢复的是保存的成功探板记录

因此，这一步更准确的意义是：

> launcher 已经具备“带运行时 password + 请求 startup probe”能力；下一步真正还需补的，是 fresh board-side probe / live interaction 的实证，而不是入口能力缺失。

### `/api/probe-board` fresh probe path（补充验证）

进一步实际验证：

1. 先运行：

```bash
printf 'demo-pass\n' | bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password
```

2. 再调用：

```bash
curl -X POST http://127.0.0.1:8079/api/probe-board -H 'Content-Type: application/json' -d '{}'
```

实际返回：

- `status = error`
- `reachable = false`
- `summary = 板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。`
- `error = 板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。`

同时，后续 `/api/snapshot` 仍显示：

- `mode.effective_label = 在线读数可用`
- `board.current_status.label = 保存的只读 SSH 探板`
- `board.current_status.summary` 继续说明该结果来自上一次成功探板的保存记录

这说明：

- fresh probe 请求路径本身已经被真实触发，不再只是理论入口
- 当前缺的不是 endpoint / launcher / session 注入能力
- 当前缺的是**真实可用 password**；在占位 password 下，系统会如实返回 SSH 认证失败，并继续保留上一次成功探板记录

### `/api/snapshot`

关键结论：

- `mode.effective_label = 在线读数可用`
- `mode.summary = 界面已从保存的成功探板记录恢复最近一次只读 SSH 结果；若需最新板卡状态，可手动再次读取。`
- `board.current_status.label = 保存的只读 SSH 探板`
- `valid_instance = 8115`
- `artifact_sha = 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

保存的探板状态同时显示：

- `Phytium-Pi reachable`
- `remoteproc0 = offline`
- `0 rpmsg device(s)`
- firmware SHA：`ef14bc26c4f63ab07fc617cf9bac54abccb44a45520d8acb3af6cb74a82e6007`

---

## 3. 这轮检查的真实结论

### 已确认正常的部分

- 本地 dashboard 启动正常
- 本地 API 正常
- docs-first / evidence-led 模式仍可工作
- 已保存的探板结果、trusted SHA、performance 区块仍能正确展示

### 当前真实 blocker

- launcher 级 readiness / prompt-password / startup-probe / one-shot helper 都已经打通；
- 但 fresh `/api/probe-board` 的真实尝试仍会返回 `SSH 认证失败` 或超时，因此：
  - 当前真正缺的不是入口或会话字段注入
  - 而是**真实可用 SSH 凭据（以及必要时正确端口/用户名）**
  - 在拿到可用凭据前，仍无法把 Demo 未完成项直接改成完成

### 这意味着什么

当前 Demo 线的主要 blocker 不是：

- `run_openamp_demo.sh` 坏了
- 本地服务起不来
- docs-first 页面失效

而是：

> **真实彩排 / live operator flow 仍需要完整板侧会话条件（至少补齐 password），否则当前只能停在 operator-assist + 保存探板记录恢复模式。**

---

## 4. 新增可执行 readiness 检查入口

本轮已补充：

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness
```

如需直接调用脚本，也可运行：

```bash
python3 ./session_bootstrap/scripts/check_openamp_demo_session_readiness.py --format text
```

当前仓库状态下，实际输出会明确给出：

- `mode: 待补全密码`
- `missing_connection_fields: password`
- `current: ready=no missing_env=password`
- `baseline: ready=no missing_env=password`
- `exit_code: 2`

这一步把“当前 blocker 是缺 password”从报告描述，推进成了可重复执行的仓库内检查入口。

---

## 5. 对主清单的意义

这轮检查进一步支持当前对 Demo 未完成项的解释：

- 四幕 / 首屏 / 对比页 / fault panel 的**文档定义层**已经基本齐了
- 当前继续未完成，确实主要是因为：
  - 真实彩排未回填
  - 板侧 live 会话条件未补齐

而不是因为脚本或本地 dashboard 根本起不来

---

## 6. 建议下一步

若继续推进 Demo 主线，默认顺序应是：

1. 先运行 `bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness`
2. 若只差一次运行时 password，可先运行 `bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness-prompt-password`
3. 若希望一轮完成 fresh probe capture，优先运行 `bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password --post-probe-board`
4. 若希望 fresh probe 失败时直接给出非零退出码，运行 `bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password --strict-probe-board`
5. 若 fresh probe 真成功，再按 `openamp_demo_presentation_day_checklist_2026-04-03.md` 做真实彩排
6. 用 `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` 回填结果

---

## 7. 关联入口

- `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_task_completion_gate_matrix_2026-04-03.md`
- `session_bootstrap/reports/project_next_real_blockers_after_docs_freeze_2026-04-03.md`
- `session_bootstrap/demo/openamp_control_plane_demo/README.md`
