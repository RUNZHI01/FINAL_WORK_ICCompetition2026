# OpenAMP Demo Safety Panel M5

Date: 2026-03-19

## Scope

Finish the narrow M5 slice for the demo safety area without adding a new endpoint or changing physical ownership claims.

## Changes

- Added a derived `safety_panel` object to `current_system_status()` in [session_bootstrap/demo/openamp_control_plane_demo/server.py](/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/server.py).
  - Derived only from existing live status fields, current `last_fault` result, and the existing recover action path.
  - Exposes:
    - SAFE_STOP mirror state
    - latch state
    - `guard_state`
    - `last_fault_code`
    - `total_fault_count`
    - `board_online`
    - `status_source`
    - `status_note`
    - last replay/live fault result summary when present
    - recover action mapping for `/api/recover`
    - explicit ownership note that RTOS/Bare Metal owns physical `SAFE_STOP` / GPIO and Linux is mirror/control only

- Reworked the mission-dashboard safety card in [session_bootstrap/demo/openamp_control_plane_demo/static/app.js](/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/static/app.js) into a scoped front-panel readout backed by `systemStatus.safety_panel`.
  - Shows SAFE_STOP mirror state, latch, `guard_state`, `fault code`, `fault count`, source/note, last replay/live result, recover action mapping, and the ownership boundary note.
  - Did not add any new destructive action.

- Added scoped styling for the safety front panel in [session_bootstrap/demo/openamp_control_plane_demo/static/app.css](/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/static/app.css).

- Added focused assertions in [session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py](/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py) for:
  - `safety_panel` derivation with a recovered live SAFE_STOP result
  - `safety_panel` derivation from live control status without a cached `last_fault`
  - JS marker coverage for the safety front-panel renderer

## Constraints Kept

- No new endpoint; reused `/api/system-status` and existing `/api/recover`.
- No Linux-side claim of physical GPIO ownership.
- No broad dashboard redesign.
- Only M5-related files were intended for staging/commit.

## Focused Validation

Run only targeted server/dashboard tests covering the new payload and JS marker path.
