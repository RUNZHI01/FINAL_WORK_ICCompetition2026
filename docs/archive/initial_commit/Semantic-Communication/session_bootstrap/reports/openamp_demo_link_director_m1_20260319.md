# OpenAMP Demo Link Director M1

## APIs added

- `GET /api/link-director`
  - Returns the current link-director scaffold status, selected preset, preset catalog, backend binding state, and boundary notes.
- `POST /api/link-director/profile`
  - Accepts `{ "profile_id": "<preset>" }`.
  - Updates the selected preset when the requested preset differs from the current one.
  - Returns the updated scaffold status plus `change_applied` / `status_message`.
  - Rejects unsupported presets with `400`.

## Frontend wiring added

- `static/app.js` now fetches `/api/link-director` during normal dashboard refresh.
- The existing Mission Dashboard `Link Status` card now shows:
  - current selected link profile
  - preset switch buttons for the predefined profiles
  - scaffold/backend binding state
  - future binding hints (`netem` / physical weak-link placeholders)
  - explicit truth and mode-boundary notes
- Profile changes are reflected in-page after the POST completes; no browser reload is required.

## Event behavior

- A successful profile change publishes `LINK_PROFILE_CHANGED` into the existing event spine.
- The event payload records:
  - `profile_id`
  - `profile_label`
  - `previous_profile_id`
  - `previous_profile_label`
  - `backend_binding`
- After a real change, the demo also writes an event-spine snapshot with reason `link_profile_changed`.
- Re-selecting the already active preset is an honest no-op:
  - no event is emitted
  - no new archive snapshot is claimed

## Still mock / scaffold only

- This milestone does **not** execute `tc`, `netem`, qdisc changes, switch-port changes, or physical weak-link control.
- This milestone does **not** rewrite `guard_state`, `last_fault_code`, heartbeat, remoteproc, RPMsg, or any live board telemetry.
- `ui_scaffold_only` remains the truthful backend state for link-director binding in M1.
- The 4-core vs 3-core boundary remains unchanged:
  - 4-core Linux performance mode continues to cover headline performance and reconstruction evidence.
  - 3-core Linux + RTOS demo mode continues to cover OpenAMP admission, heartbeat, SAFE_STOP, and operator control-plane flow.
