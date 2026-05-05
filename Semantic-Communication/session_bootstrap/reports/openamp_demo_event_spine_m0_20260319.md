# OpenAMP Demo Event Spine M0

## Integration point chosen

M0 is embedded at `DashboardState` inside `session_bootstrap/demo/openamp_control_plane_demo/server.py`.

- This is the smallest realistic seam because the existing demo already centralizes board probe refresh, live inference launch/progress, fault injection, recovery, and API responses there.
- The event spine stays additive and in-process.
- The TVM / reconstruction runner chain is untouched; M0 only observes existing control/data milestones and archives them locally.
- The strict split is preserved in the event model via `plane` and `mode_scope`:
  - `3-core Linux + RTOS demo mode` remains the OpenAMP admission / heartbeat / SAFE_STOP side.
  - `4-core Linux performance mode` remains the reconstruction / evidence side.

## Files changed

- `session_bootstrap/demo/openamp_control_plane_demo/event_spine.py`
- `session_bootstrap/demo/openamp_control_plane_demo/server.py`
- `session_bootstrap/demo/openamp_control_plane_demo/tests/test_event_spine.py`
- `session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`
- `session_bootstrap/reports/openamp_demo_event_spine_m0_20260319.md`

## APIs added

- `GET /api/event-spine?limit=<n>`
  - Returns recent events, aggregate state, event type catalog, and archive metadata.
- `GET /api/system-status`
  - Additive `event_spine` pointer added:
    - `api_path`
    - `session_id`
    - `event_count`
    - `last_event_at`
    - `archive_enabled`

## Archive format and path

Runtime server startup now enables a package-local archive root at:

- `session_bootstrap/demo/openamp_control_plane_demo/runtime/event_archives/<session_id>/events.jsonl`
- `session_bootstrap/demo/openamp_control_plane_demo/runtime/event_archives/<session_id>/state_snapshot.json`

Archive details:

- `events.jsonl` is append-only JSONL, one normalized event per line.
- `state_snapshot.json` is a lightweight aggregate snapshot written at key milestones and followed by an `ARCHIVE_SNAPSHOT_WRITTEN` event.
- Direct `DashboardState(...)` construction keeps archival disabled unless an archive root is passed explicitly. This keeps tests and ad hoc imports side-effect light while leaving normal demo runtime package-local.

## Still not implemented

- No frontend event timeline UI yet. M0 is backend proof only.
- No streaming transport yet; the event surface is read-only polling via HTTP.
- No per-job archive sharding yet; M0 keeps a session-local JSONL plus aggregate snapshot.
- `LINK_PROFILE_CHANGED` exists in the unified model, but M0 does not add new frontend wiring for live operator interaction.
- No cross-process persistence or replay hydration. The bus/store is in-process only for this milestone.
