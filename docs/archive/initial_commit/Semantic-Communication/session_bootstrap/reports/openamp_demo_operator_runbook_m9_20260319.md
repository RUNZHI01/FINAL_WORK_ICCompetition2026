# OpenAMP Demo Operator Runbook M9

Date: 2026-03-19

## Scope

This runbook is for the current committed `openamp_control_plane_demo` cockpit plus the M8 readiness state. It does not assume any future automation.

Keep this wording fixed throughout the demo:

- `4-core Linux performance mode` only covers headline performance and reconstruction evidence.
- `3-core Linux + RTOS demo mode` only covers the live OpenAMP operator flow, admission, heartbeat, SAFE_STOP, and fault evidence.
- The page is `operator-assist only`; probe, gate preview, Current/PyTorch launch, fault injection, and SAFE_STOP remain manual operator actions.

## Pre-Demo Checklist

- [ ] Launch with `bash ./session_bootstrap/scripts/run_openamp_demo.sh`. Do not use an ad hoc Python entrypoint; the launcher path is what enables the local archive root for the blackbox timeline.
- [ ] Confirm `最新 demo 结论` shows `唯一实例=8115`, `Current live=300 / 300`, `PyTorch 参考基线=300 / 300 (archive)`, and `reachable / remoteproc0=running`.
- [ ] Confirm the page still says headline performance belongs to `4-core Linux performance mode`, while the live operator flow belongs to `3-core Linux + RTOS demo mode`.
- [ ] In `会话接入`, verify `host / user / port / env_file` are preloaded. Before the audience-facing clicks, enter the password and keep it in the current demo process only.
- [ ] Confirm `Command Center` starts with the manual boundary note. If the cue does not say `operator-assist only`, stop and refresh before the demo.
- [ ] Decide before the room whether Scene 4 will be shown. The recommended compressed path is Scene 4 only on evaluator request or when time allows.
- [ ] Keep Scene 3 on the default PyTorch archive baseline unless an evaluator explicitly asks for PyTorch live. Do not make baseline live the default story.

## Default Operator Sequence

| Scene | Operator action | What to say | What to verify on screen |
|---|---|---|---|
| Opening | Do not click yet. Start at `Command Center`, then glance at `最新 demo 结论`. | `这是一页 operator command seat，不是自动编排。headline performance 用 4-core Linux performance mode，当前 live operator flow 用 3-core Linux + RTOS demo mode。` | `Command Center` shows the manual boundary note. The hero card still shows `8115`, `Current live 300 / 300`, and `PyTorch 参考基线 300 / 300 (archive)`. |
| Scene 1A | In `会话接入`, enter the password and click `保存并复用本场凭据`. | `这一步只把本场 SSH 会话保存在当前 demo 进程里，不会自动发起任务。` | `boardAccessSummary` changes to `当前会话已可复用...` and the password field switches to the reuse placeholder. |
| Scene 1B | Click `探测板卡 / OpenAMP`. | `这是只读探板，不 reboot，不发送 JOB_REQ，不改 remoteproc 所有权。` | `Device Status` / Act 1 show `remoteproc=running`, `guard_state=READY` when the probe is usable. If the probe does not refresh, the page must explicitly stay on evidence wording. |
| Scene 1C | Click `demo-only 票据预检`. | `这只是 preview-only gate 检查；会写 preview-only JOB_* 事件，但不会发送 JOB_REQ，也不会启动板端执行。` | `Job Manifest Gate` updates in place. Preferred state is `可放行`; acceptable degraded states are `待补全`, `待复核`, or `暂不放行`, with reasons shown in the card. |
| Link Director detour (optional) | If weak-link planning is worth one sentence, point at `Link Status`. Only click a profile if you explicitly want the visual change. | `Link Director 当前只是导演台预案；backend_binding 仍是 ui_scaffold_only，我不宣称这里已经执行 tc/netem 或物理断链。` | The card shows the selected profile and `backend_binding=ui_scaffold_only`. If you click another profile, only the preset label changes; live telemetry must not magically change with it. |
| Scene 2 | Click `启动 Current 数据面 300 张图在线推进`. Stay on Act 2 while the progress strip moves. | `第二幕是手动发起的 Current live。页面负责显示进度和证据，不伪装自动闭环。` | `liveProgressBadge` leaves the waiting state. The stage chips and log panel begin updating. Honest live labels are `真实在线推进` or `真实在线执行（控制面降级）`; honest fallback labels keep `归档样例` wording visible. |
| Scene 3 | Click `03 正式对照` or the `第三幕 Compare` jump. Do not click baseline live by default. | `第三幕默认基线是 2026-03-12 归档的 PyTorch reference，不把 2026-03-17 的 baseline live 历史结论当成本场默认 operator flow；这页只引用两条正式口径：1846.9 -> 130.219 ms 与 1850.0 -> 230.339 ms/image。` | The performance cards stay visible. In `Compare Viewer`, the right pane is still the PyTorch reference side. The left pane is `latest live result` only if this round has really finished; otherwise it stays `current archive` and must be described that way. |
| Scene 4 (optional) | If asked for safety/fault, go to Act 4 and click `注入错误 SHA`. Only click `SAFE_STOP 收口` if you actually want to show the recover path. | `第四幕也是 operator-driven。若这里进入回放模式，我会直接说是回放，不把它讲成真机自动化；8115 上 recent 300/300 只用于 TC-002 的 live reconstruction 收口，不把它延伸成 TC-010 / RESET_REQ/ACK 已闭环。Linux UI 只做 SAFE_STOP / GPIO mirror，不拥有物理所有权。` | `faultStatusHeadline` changes to `真机注入` or the truthful replay label such as `FIT-01 回放模式`. `last_fault_code` updates. When the launcher path is active and events have been written, `Event Timeline` moves from fallback copy to a real archive session. |

## Scene Notes

### Scene 1 anchor

Use the cue/order that the current cockpit already recommends:

- Start from `Command Center`.
- Finish `会话接入`.
- Do one read-only probe.
- Do the manifest preview.

Do not skip the `Job Manifest Gate` sentence. M8 explicitly keeps this as `preview-only`, not a silent launch.

### Scene 2 anchor

The default defense path is `Current` only.

- Do not click `运行 PyTorch 数据面 300 张图`.
- Do not click `一键顺序运行 PyTorch + Current 数据面 300 张图` unless you intentionally want a longer live sequence.
- While Current is running, keep saying that the image board is still a stable presentation surface and that the progress strip is the truthful live indicator.

### Scene 3 anchor

The committed cockpit already separates these things. Keep them separated in speech:

- `Compare Viewer` is a side-by-side viewer, not a slider.
- The default third-act baseline is the archived PyTorch reference.
- Scene 3 only quotes the two formal lines: `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`.
- The performance cards are still the `4-core Linux performance mode` headline.
- The live operator flow that just ran belongs to `3-core Linux + RTOS demo mode`.
- `8115` recent `300/300` is valid as `TC-002` live reconstruction evidence, but not as shorthand for `TC-010` / `RESET_REQ/ACK` closure.

### Scene 4 anchor

For a tight defense, use the fastest admission-shaped fault:

- Recommended default: `注入错误 SHA`.
- Recommended evaluator-only branch: `注入心跳超时` when the question is specifically about watchdog history.
- `SAFE_STOP 收口` is valid only as an operator-triggered action; it is not a claim of Linux GPIO ownership.

## Fallback Branches

| Surface | Expected state | If not in the expected state | Truthful line to use | Continue with |
|---|---|---|---|---|
| Link Director | Selected preset is visible and `backend_binding=ui_scaffold_only`. | Profile buttons do nothing, or the profile changes but the live board data does not. | `Link Director 现在只是导演台预案；本页没有执行 tc/netem，也不会改写 live telemetry。` | Skip the detour and continue to Scene 2. |
| Manifest Gate | After preview with a complete session, the card should be `可放行`. | The card stays `待补全`, `待复核`, or `暂不放行`. | `当前 gate 只说明 admitability；它没有发 JOB_REQ，也没有启动板端执行。` | If the reason is missing password, fix the session and preview again. If the reason is `JOB_ACTIVE` or STATUS precheck failure, stop trying to force live and move to Scene 3 evidence. |
| Current live | Act 2 shows a running progress state or a completed live result. | The result says `保守阻断`, `启动前检查失败，回退展示（归档样例）`, `回退展示（归档样例）`, or `真实在线执行（控制面降级）`. | `这轮 Current 没有被我包装成成功的 OpenAMP live；当前页面明确在显示阻断、降级或归档回退。` | If it is `控制面降级`, you may keep the run as a real board execution but say the control handshake was not fully usable. If it is archive fallback, stop Act 2 and go to Scene 3 with the archived compare viewer. |
| Compare Viewer | Left pane becomes `latest live result` after this round finishes; right pane remains the PyTorch reference side. | Left pane remains `current archive`, or the selected sample context is missing. | `第三幕现在仍是归档对照，不把它说成刚完成的本轮 live compare。` | Use the performance cards plus the existing compare sample. Do not start baseline live unless the evaluator explicitly asks for it. |
| Safety Panel | `SAFE_STOP mirror`, `LATCH`, `fault code`, and the ownership note are visible. | Fault injection stays in replay, or the panel does not clear after recover. | `这里展示的是 control-plane mirror；物理 SAFE_STOP/GPIO 仍由 RTOS/Bare Metal 持有。` | If replay is shown, keep it as replay. If recover does not clear, stop at the current mirror state and use the FIT cards instead of forcing another action. |
| Archive / Blackbox Timeline | After preview, live, or fault actions on the launcher path, a local archive session should appear and event counts should rise. | The selector says there is no archive session yet, or the card still shows the mission fallback timeline. | `blackbox timeline 当前还没有本地 JSONL session 可回放，所以页面先显示 mission fallback timeline；这不是 rrweb，也不是浏览器录像。` | Keep the timeline explanation read-only. If you are still in prep, relaunch with `run_openamp_demo.sh`; do not debug archive wiring live on stage. |

## Concise Do-Not-Say List

- Do not say the `Link Director` has already applied real `tc/netem`, qdisc, or physical weak-link control.
- Do not say `demo-only 票据预检` has already sent a real `JOB_REQ` or started board execution.
- Do not say the `Compare Viewer` is an interactive slider or a pixel-diff tool.
- Do not use Scene 3 to quote anything other than `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`.
- Do not treat `300/300` as proof that `TC-010`, `RESET_REQ/ACK`, or sticky fault reset are already closed.
- Do not say Linux owns physical `SAFE_STOP` or GPIO.
- Do not say the `Blackbox Timeline` is rrweb, a browser recording, or full session playback.
- Do not say OpenAMP made the inference faster.
- Do not mix `4-core Linux performance mode` numbers with `3-core Linux + RTOS demo mode` live behavior.
- Do not call a fallback, replay, or runner-only branch a full OpenAMP handshake success.
- Do not call the PyTorch archive baseline a live baseline for this round unless you actually ran it and the page produced that result.
