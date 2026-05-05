# OpenAMP Demo Delivery Index M11

Date: 2026-03-19

Scope: final docs-only index for the existing `openamp_control_plane_demo` cockpit. M11 adds no product behavior and no new launcher.

## 2026-03-22 Follow-up

After the M11 snapshot, the next minimal convergence pass was:

- baseline live user wording is kept on `PyTorch live` / `PyTorch signed live`
- backend state still preserves the truthful technical mode as `legacy_sha` or `signed_manifest_v1`
- Scene 3 default remains the archived PyTorch reference; the `2026-03-17` baseline `300 / 300` run stays historical evidence rather than the default operator branch

See: `session_bootstrap/reports/openamp_demo_baseline_semantics_alignment_20260322.md`

## 2026-04-03 Wording Freeze Follow-up

The next docs-only convergence pass further froze the defense wording:

- Scene 3 keeps the archived `PyTorch reference` as the default compare branch
- Scene 3 only quotes the two formal lines `1846.9 -> 130.219 ms` and `1850.0 -> 230.339 ms/image`
- `8115 / 300 / 300` is now explicitly framed as `TC-002` live reconstruction evidence, not `TC-010` / `RESET_REQ/ACK` closure
- top-line status acceptance is treated as docs-first wording plus presentation-day human verification, not as a promise that every UI field is already final in all live builds

See:
- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_docs_closure_summary_2026-04-03.md`

## Launch

Supported launch command from the repo root:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

Optional read-only board probe wiring:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --probe-env ./session_bootstrap/config/phytium_pi_login.env
```

## Read This First

Operator use:

1. `session_bootstrap/demo/openamp_control_plane_demo/README.md`
2. `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md`
3. `session_bootstrap/reports/openamp_demo_72s_script_m9_20260319.md`
4. `session_bootstrap/reports/openamp_demo_readiness_m8_20260319.md`
5. `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
6. `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
7. `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`

Engineering context:

1. `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md`
2. `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/README.md`
3. `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
4. Use the milestone table below to jump to the milestone-specific note you need.

## Milestone Index

Repo-state check performed on 2026-03-19 with `git log --oneline --decorate --all` and `git reflog --oneline -n 80`.
No reachable M9 commit hash is visible in the current checkout, so none is invented here.

| Milestone | Hash | One-line purpose | Main doc |
|---|---|---|---|
| M0 | `da92816` | Added the event spine for cockpit state/history and local archive snapshots. | `session_bootstrap/reports/openamp_demo_event_spine_m0_20260319.md` |
| M1 | `b0e713b` | Wired the Link Director in as a truthful weak-link planning surface. | `session_bootstrap/reports/openamp_demo_link_director_m1_20260319.md` |
| M2 | `fc12d2d` | Wired the Job Manifest Gate preview flow into the cockpit. | `session_bootstrap/reports/openamp_demo_job_manifest_gate_m2_20260319.md` |
| M3 | `0556ac7` | Added the blackbox timeline for local JSONL plus snapshot replay. | `session_bootstrap/reports/openamp_demo_blackbox_timeline_m3_20260319.md` |
| M4 | `5ab66de` | Added the compare viewer for Current versus PyTorch reference framing. | `session_bootstrap/reports/openamp_demo_compare_viewer_m4_20260319.md` |
| M5 | `763330e` | Added the safety panel for SAFE_STOP, latch, and ownership mirroring. | `session_bootstrap/reports/openamp_demo_safety_panel_m5_20260319.md` |
| M6 | `4cad012` | Added the Command Center layer for scene jumps and manual control framing. | `session_bootstrap/reports/openamp_demo_command_center_m6_20260319.md` |
| M7 | `053c137` | Added operator cues for the scene-by-scene manual presentation flow. | `session_bootstrap/reports/openamp_demo_operator_cue_m7_20260319.md` |
| M8 | `f0b4de8` | Added the readiness pass and focused smoke validation for the committed operator path. | `session_bootstrap/reports/openamp_demo_readiness_m8_20260319.md` |
| M9 | `not visible in current checkout` | Added the operator runbook and 72-second presentation script as docs, but no reachable commit hash is visible here. | `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md` and `session_bootstrap/reports/openamp_demo_72s_script_m9_20260319.md` |
| M10 | `396afac` | Added the handoff manifest for launch, sanity-check, document order, and caveats. | `session_bootstrap/reports/openamp_demo_handoff_manifest_m10_20260319.md` |

Note: M0 also had a visible follow-up fix at `394e637` (`fix(demo): restore event spine helper consistency`) before M1 landed.

## Top 5 Caveats / Honesty Constraints

1. The page is `operator-assist only`; probe, gate preview, live launch, fault injection, and `SAFE_STOP` remain manual operator actions.
2. `Link Director` remains `ui_scaffold_only`; it does not apply real `tc/netem`, qdisc, or physical weak-link control.
3. `demo-only` manifest preview is preview-only; it does not send a real `JOB_REQ` and does not start board execution.
4. Keep the mode split explicit: `4-core Linux performance mode` is for headline performance evidence, while `3-core Linux + RTOS demo mode` is the live OpenAMP operator flow.
5. Label every fallback honestly: Scene 3 defaults to the archived PyTorch reference, Linux UI only mirrors `SAFE_STOP`/GPIO ownership, and the blackbox timeline is local JSONL replay rather than rrweb or browser-session recording.
