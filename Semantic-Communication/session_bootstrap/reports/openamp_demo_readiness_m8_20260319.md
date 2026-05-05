# OpenAMP Demo Readiness M8（2026-03-19）

## 结论

本轮 M8 不是新功能扩张，而是对现有单页 cockpit 做一次窄范围演示就绪检查。结果是：

- operator command seat 主链已可用；
- 关键 API / page-state 路径已做 focused smoke；
- 页面刷新后会继续回填最近一次已完成的 Current / PyTorch 结果，避免 compare viewer 直接退回 archive-only 语境；
- 仍保持 operator-driven，不伪造自动化。

## 本轮验证了什么

- `Command Center / Operator Cue`
  - `/api/system-status` 能给出 `operator_cue`、scene 推荐、quick jumps、manual boundary note。
  - `app.js` 的 `refreshAll()` 会拉取 `snapshot` / `system-status` / `link-director` / `archive`，并在渲染链里调用 `renderCommandCenter()`。
- `Link Director`
  - `/api/link-director` 默认 scaffold 状态可读。
  - `/api/link-director/profile` 切换 profile 后会保留 truthful status，并写入 event spine / archive。
- `Job Manifest Gate`
  - `/api/job-manifest-gate/preview` 的 preview-only allow 路径可走通，不会伪造成真实 launch。
  - gate verdict、wire fields、protocol boundary note 会回到首页状态聚合。
- `Compare Viewer`
  - compare viewer 继续区分 Current / PyTorch reference。
  - 新增 refresh-hydration：`system-status.recent_results` 会让页面在刷新后继续拿到最近一次已完成结果。
- `Safety Panel`
  - `safety_panel` 会从 live control 或 evidence 派生 SAFE_STOP / latch / ownership mirror 文案。
- `Archive Timeline`
  - `/api/archive/sessions` 与 `/api/archive/session` 能回放本地 JSONL + snapshot session。
  - command seat / mission dashboard 会把 blackbox timeline 纳入 operator 视图。

## 推荐操作顺序

1. 先看 `Command Center`，确认当前 cue 停在第几幕，不要跳过 boundary note。
2. 补齐本场会话，再手动做只读探板。
3. 在第一幕执行 `demo-only` gate preview，确认 verdict 与 admission 口径。
4. 如需讲弱网预案，再切 `Link Director`；注意它仍是导演台预案，不执行真实 tc/netem。
5. 进入第二幕手动发起 Current live。
6. Current 完成后进入第三幕，用同一样例讲 Current vs PyTorch reference。
7. 如需安全演示，再进入第四幕做 fault / SAFE_STOP / archive timeline。

## Blockers / Caveats / Fallback

- `Link Director` 仍是 `ui_scaffold_only`，不会改写 live telemetry，也不会真的下发 tc/netem。
- 第三幕默认基线仍以 PyTorch reference archive 为正式对照口径，不把 baseline TVM live 混进本场默认叙事。
- 第三幕正式只引用 `1846.9 -> 130.219 ms` 与 `1850.0 -> 230.339 ms/image` 两条口径，不混写 demo live drift 数字。
- `8115 / 300 / 300` 现在只用于 `TC-002` live reconstruction 收口，不延伸 claim `TC-010` / `RESET_REQ/ACK` / sticky fault reset 已闭环。
- archive timeline 是本地 `JSONL + state_snapshot.json` replay，不是 rrweb，也不是全量浏览器录像。
- 本轮新增的 refresh-hydration 只保证“最近一次已完成结果”在刷新后仍可见；正在运行中的 live job 仍以 active progress / operator cue 为主，不宣称实现了完整中途恢复。
- SAFE_STOP / GPIO 物理所有权仍在 RTOS/Bare Metal，Linux UI 只做 mirror / control surface。

## 仍需人工完成的部分

- 录入或确认本场板卡会话。
- 执行只读探板。
- 点击 gate preview、Current/PyTorch 运行、fault injection、SAFE_STOP。
- 根据现场口径决定是否切换 link profile、是否展开第四幕。

## April 3 wording freeze follow-up

For the latest docs-first wording freeze, also cross-check:

- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`

## Focused Validation

- `python3 -m unittest session_bootstrap.demo.openamp_control_plane_demo.tests.test_demo_data session_bootstrap.demo.openamp_control_plane_demo.tests.test_server`
- 结果：`Ran 62 tests in 1.107s, OK (skipped=1)`
