# OpenAMP Demo QA Card M13

Date: 2026-03-19

Scope: defense-only short answers for the current committed `openamp_control_plane_demo` cockpit and committed evidence/docs in `HEAD`.

Use rule: answer one line, then stop. If pressed beyond the line below, say `that is outside the current committed demo scope`.

| Likely evaluator question | Recommended answer | Red-line reminder |
|---|---|---|
| 1. What are you actually demonstrating here? | We are showing a semantic-visual-return data plane plus an OpenAMP control plane for admission, heartbeat, SAFE_STOP, and fault evidence. | Do not say OpenAMP is the speedup path or that the page is a full autonomous orchestrator. |
| 2. Why do you keep separating `4-core Linux performance mode` and `3-core Linux + RTOS demo mode`? | The 4-core mode is the formal performance headline, while this live OpenAMP cockpit is the 3-core Linux + RTOS operator demo path. | Do not mix 4-core performance numbers into the 3-core live demo story. |
| 3. Is this page fully automated? | No. The cockpit is `operator-assist only`; probe, gate preview, live launch, fault injection, and SAFE_STOP are still manual actions. | Do not call it one-click automation, a closed-loop autopilot, or a fully automated 72-second sequence. |
| 4. Is the board interaction real or just mocked? | The probe and live paths can use the real board, and when they cannot, the page falls back to archived evidence and labels that downgrade explicitly. | Do not call archive, replay, or fallback material a fresh live run. |
| 5. What does the `Link Director` prove today? | It is a truthful planning surface for weak-link presets, and the current backend binding is `ui_scaffold_only`. | Do not claim real `tc/netem`, qdisc, switch-port control, physical weak-link control, or rewritten live telemetry. |
| 6. Does `demo-only` manifest preview really dispatch a job? | No. It is a demo-only admitability preview that may do a read-only `STATUS_REQ` precheck, but it does not send a real `JOB_REQ` or start board execution. | Do not call it real dispatch, real `JOB_REQ`, or actual runner start. |
| 7. What is the live story in Scene 2? | Scene 2 is the Current 300-image live data-plane path; OpenAMP is the control and safety boundary around it, not the performance accelerator. | Do not say OpenAMP made inference faster. |
| 8. What is the default comparison story in Scene 3? | The default compare is Current versus the archived PyTorch reference, and on this page we only cite the two formal lines `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`; the `2026-03-17` baseline `300 / 300` result is historical evidence rather than the default live branch. | Do not present the default compare as a same-round baseline live run unless you actually ran it. |
| 9. What does the SAFE_STOP panel mean in ownership terms? | Physical SAFE_STOP and GPIO stay owned by RTOS/Bare Metal; Linux only mirrors that state and exposes the existing control surface. | Do not say Linux owns physical SAFE_STOP, clears GPIO directly, or has full recovery ownership. |
| 10. What is the `Blackbox Timeline` technically? | It is local read-only replay of archived `events.jsonl` plus `state_snapshot.json`. | Do not call it rrweb, browser recording, DOM/session capture, or full browser playback. |
| 11. Which FIT claims are actually closed on the real board? | The committed evidence package closes `FIT-01`, `FIT-02`, and `FIT-03`, and `FIT-03` keeps its `FAIL -> fix -> PASS` history. | Do not claim `FIT-04`, `FIT-05`, `RESET_REQ/ACK`, deadline enforcement, sticky-fault reset, or a complete fault-recovery system. |
| 12. What current board-backed result can you quote safely? | The dashboard surfaces `8115` as the valid demo instance, with committed `2026-03-17` live status showing Current `300 / 300` and Baseline `300 / 300`; this closes `TC-002` as live reconstruction evidence, not `TC-010`. | Do not imply that every board is valid, that this was rerun just now, or that the page itself created those results today. |
| 13. If the board is unstable during the defense, what is the honest fallback? | Stay in evidence mode and explain the committed board-backed proof and archive-backed compare instead of forcing a new on-stage experiment. | Do not relabel a degraded, blocked, or replay branch as full live OpenAMP success. |

## Global Red Lines

- Do not mix `4-core Linux performance mode` headline numbers with `3-core Linux + RTOS demo mode` live behavior.
- Do not use Scene 3 to quote anything other than `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`.
- Do not treat `300 / 300` as proof that `TC-010`, `RESET_REQ/ACK`, or sticky-fault reset are already closed.
- Do not say `Link Director` is real weak-link control; it is `ui_scaffold_only`.
- Do not say manifest preview is real dispatch; it is demo-only preview and may include only read-only precheck behavior.
- Do not say Linux owns physical `SAFE_STOP/GPIO`; ownership remains RTOS/Bare Metal.
- Do not say the archive timeline is rrweb or browser recording; it is local JSONL plus snapshot replay.
- Do not claim `FIT-04`, `FIT-05`, `RESET_REQ/ACK`, deadline enforcement, sticky-fault reset, or a full fault-recovery system.
- Do not claim capabilities that are not visible in the current committed cockpit or committed evidence package.

## Basis In `HEAD`

- `session_bootstrap/demo/openamp_control_plane_demo/README.md`
- `session_bootstrap/reports/openamp_demo_link_director_m1_20260319.md`
- `session_bootstrap/reports/openamp_demo_job_manifest_gate_m2_20260319.md`
- `session_bootstrap/reports/openamp_demo_blackbox_timeline_m3_20260319.md`
- `session_bootstrap/reports/openamp_demo_safety_panel_m5_20260319.md`
- `session_bootstrap/reports/openamp_demo_readiness_m8_20260319.md`
- `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md`
- `session_bootstrap/reports/openamp_demo_delivery_index_m11_20260319.md`
- `session_bootstrap/reports/openamp_demo_cheat_sheet_m12_20260319.md`
- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md`
- `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
