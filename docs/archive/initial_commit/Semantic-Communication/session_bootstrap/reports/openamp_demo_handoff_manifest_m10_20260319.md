# OpenAMP Demo Handoff Manifest M10

Date: 2026-03-19

Scope: docs-only handoff for humans who need to launch, verify, and present the existing `openamp_control_plane_demo` cockpit. M10 adds no product feature and no new launcher.

## What Was Delivered

Reality check against `git log --oneline --decorate --all` and `git reflog` on 2026-03-19:

- committed demo milestone hashes are visible through M8 in this checkout;
- M9 doc assets exist in the working tree, but no reachable M9 commit hash is visible here, so this manifest does not invent one.

| Milestone | Hash | Delivered |
|---|---|---|
| M0 | `da92816` | Added the event spine for cockpit state/history. Immediate follow-up fix: `394e637` restored helper consistency before M1. |
| M1 | `b0e713b` | Wired the Link Director into the cockpit as a truthful planning surface. |
| M2 | `fc12d2d` | Wired the Job Manifest Gate preview flow into the cockpit. |
| M3 | `0556ac7` | Added the blackbox timeline / archive replay view. |
| M4 | `5ab66de` | Added the compare viewer for Current vs reference framing. |
| M5 | `763330e` | Added the safety panel for SAFE_STOP / latch / ownership mirroring. |
| M6 | `4cad012` | Added the command center / command-seat layer. |
| M7 | `053c137` | Added operator cue guidance for scene-by-scene manual flow. |
| M8 | `f0b4de8` | Added the readiness pass and focused smoke validation. |
| M9 | `not visible in current checkout` | Operator handoff docs exist at `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md` and `session_bootstrap/reports/openamp_demo_72s_script_m9_20260319.md`, but no reachable M9 commit hash is available from the current repo state. |

## Launch The Demo

From the repo root, use the existing launcher only:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

Default URL: `http://127.0.0.1:8079`

If you want the existing read-only board probe wired in at startup, still use the same launcher:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --probe-env ./session_bootstrap/config/phytium_pi_login.env
```

Practical note:

- Do not swap to an ad hoc `python3 server.py` entrypoint; the repo launcher is the supported path.
- The launcher will reclaim the port only from an older instance of the same OpenAMP demo server. It refuses to kill unrelated listeners.

## Quick Sanity Check

1. Open `http://127.0.0.1:8079` and confirm the page loads.
2. Confirm the top-line status still shows the established demo facts: `8115`, `Current 300 / 300`, `PyTorch reference 300 / 300 (archive)`, plus the `4-core Linux performance mode` vs `3-core Linux + RTOS demo mode` boundary. For the frozen acceptance wording and the `TC-002 / TC-010` boundary, cross-check `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`.
3. Check health:

```bash
curl -fsS http://127.0.0.1:8079/api/health
```

Expected payload:

```json
{"status":"ok"}
```

4. Check snapshot:

```bash
curl -fsS http://127.0.0.1:8079/api/snapshot | python3 -m json.tool
```

Quick fields to confirm:

- `latest_live_status.valid_instance = 8115`
- `latest_live_status.current_completed = "300 / 300"`
- `latest_live_status.baseline_completed = "300 / 300"`
- `latest_live_status.report_path = "session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md"`

5. Check operator cue state:

```bash
curl -fsS http://127.0.0.1:8079/api/system-status | python3 -m json.tool
```

Confirm `operator_cue` is present and still frames the page as manual / operator-assist.

## Docs To Read First

Read in this order:

1. `session_bootstrap/demo/openamp_control_plane_demo/README.md`
2. `session_bootstrap/reports/openamp_demo_operator_runbook_m9_20260319.md`
3. `session_bootstrap/reports/openamp_demo_72s_script_m9_20260319.md`
4. `session_bootstrap/reports/openamp_demo_readiness_m8_20260319.md`

Then keep these two evidence docs nearby for challenge questions:

- `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- `session_bootstrap/reports/openamp_demo_dashboard_local_acceptance_20260317.md`

## Known Caveats / Non-Goals

- M10 is docs-only. No new product behavior was added.
- The page remains operator-assist only. Probe, gate preview, Current/PyTorch launch, fault injection, and SAFE_STOP stay manual.
- Link Director remains `ui_scaffold_only`; it is not real `tc/netem`, qdisc, or physical weak-link control.
- `demo-only` manifest preview does not send a real `JOB_REQ` and does not start board execution.
- Scene 3 default compare remains the archived PyTorch reference path; do not present baseline live as the default story.
- The blackbox timeline is local JSONL plus snapshot replay, not rrweb and not a browser recording.
- Linux UI mirrors SAFE_STOP / GPIO state; physical ownership remains on RTOS / Bare Metal.
- Keep the narrative boundary fixed: performance headlines belong to `4-core Linux performance mode`; live OpenAMP operator flow belongs to `3-core Linux + RTOS demo mode`.
- Repo bookkeeping caveat: this checkout exposes committed hashes through M8 only; M9 assets are present but not reachable as a commit here.

## Final Operator Checklist

- [ ] Launch with `bash ./session_bootstrap/scripts/run_openamp_demo.sh`.
- [ ] Read this manifest, then the README, M9 runbook, M9 72s script, and M8 readiness note.
- [ ] Verify `/`, `/api/health`, `/api/snapshot`, and `/api/system-status`.
- [ ] Enter the board password in the page only; keep it in the current demo process only.
- [ ] Do one read-only board probe before any live action.
- [ ] Run the `demo-only` manifest preview before Current live.
- [ ] Keep Scene 3 on the PyTorch archive default unless an evaluator explicitly asks for another live branch.
- [ ] Show Scene 4 only if time allows or the evaluator asks.
- [ ] Label every fallback, replay, degraded branch, and control-plane boundary honestly.
