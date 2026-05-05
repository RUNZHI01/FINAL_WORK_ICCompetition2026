# OpenAMP Demo 72s Script M9

Date: 2026-03-19

Default use: one tight pass through the committed cockpit without pretending that the page is autoplayed.

| Time | Operator action | Presenter line | Expected page reaction |
|---|---|---|---|
| `00-06s` | Enter the password if needed and click `保存并复用本场凭据`. | `这页是 operator-driven command seat；主机、用户、端口和 env 已预载，我现在只补本场密码。` | `会话接入` changes to `当前会话已可复用...`; the page stays manual, not auto-running. |
| `06-12s` | Click `探测板卡 / OpenAMP`. | `这是只读探板，不 reboot，不改 remoteproc，不发送 JOB_REQ。` | Act 1 / Mission Dashboard show `remoteproc=running` and `guard_state=READY` when the probe is usable; otherwise the wording stays on evidence fallback. |
| `12-18s` | Click `demo-only 票据预检`. | `这里是 preview-only gate；它只重查 admitability，不会把预检伪装成真实 launch。` | `Job Manifest Gate` updates to `可放行` or a truthful degraded verdict with reasons. |
| `18-22s` | Point at `Link Status`; do not click unless the evaluator asks. | `Link Director 现在只是导演台预案，backend_binding 仍是 ui_scaffold_only，我不宣称这里已经执行 tc/netem。` | No protocol or telemetry jump happens. The card still shows `ui_scaffold_only`. |
| `22-30s` | Click `启动 Current 数据面 300 张图在线推进`. | `第二幕由操作员手动启动，页面只负责显示进度和证据。` | Act 2 leaves `等待触发`; the progress badge, stage chips, and trace panel begin moving. |
| `30-54s` | Stay on Act 2 and let the progress strip run. | `这条 live operator flow 属于 3-core Linux + RTOS demo mode；headline performance 另算 4-core Linux performance mode。` | The count and current stage keep updating. If the run degrades, the label keeps the fallback wording visible instead of pretending success. |
| `54-64s` | Click `03 正式对照` or the `第三幕 Compare` jump. | `第三幕默认基线是 2026-03-12 的 PyTorch reference archive，不把历史 baseline live 当成当前这轮默认流程；这里正式只引用两条口径：1846.9 → 130.219 ms 与 1850.0 → 230.339 ms/image。` | Performance cards are visible. `Compare Viewer` shows the same sample; the right pane stays the PyTorch reference side. The left pane is `latest live result` only if this round has really completed, otherwise it remains `current archive`. |
| `64-72s` | If you have time or the evaluator asks for safety, click `注入错误 SHA`. Otherwise stop on Scene 3. | `第四幕也保持诚实：若这里进入回放模式，我会直接说它是回放；8115 上 recent 300/300 只用于证明 TC-002 的 live reconstruction 收口，不把它延伸成 TC-010 或 RESET_REQ/ACK 已闭环；Linux UI 只是 SAFE_STOP mirror/control surface。` | `faultStatusHeadline` switches to `真机注入` or the truthful replay label such as `FIT-01 回放模式`. `last_fault_code` updates. If archive writing is active, the blackbox timeline gains real local events; otherwise it stays on the mission fallback timeline. |

## Operator Reminder

- Do not click `运行 PyTorch 数据面 300 张图` in this 72-second version unless the evaluator explicitly asks for baseline live.
- Scene 3 only cites the two formal performance lines: `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`.
- `300/300` is allowed as live reconstruction proof and `TC-002` closure wording, but not as shorthand for `TC-010` / `RESET_REQ/ACK` completion.
- If Act 2 falls back, say that immediately and still use Scene 3 honestly.
- If Scene 4 is skipped, end on the Scene 3 boundary sentence, not on a fake fault story.
