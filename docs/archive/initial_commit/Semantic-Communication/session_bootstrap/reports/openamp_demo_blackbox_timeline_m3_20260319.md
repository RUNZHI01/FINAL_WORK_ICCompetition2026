# OpenAMP Demo Blackbox Timeline M3

## APIs added

- `GET /api/archive/sessions`
  - Lists local archive sessions discovered under `session_bootstrap/demo/openamp_control_plane_demo/runtime/event_archives/<session_id>/`.
  - Returns per-session summary fields derived from archived files: `event_count`, `last_event_at`, `last_event_type`, `last_snapshot_reason`, `mode_boundary_note`, and archive paths.
- `GET /api/archive/session?session_id=...&limit=...`
  - Replays one archived session from disk and returns:
    - `summary`
    - reconstructed `aggregate`
    - `recent_events`
    - timeline projection for UI
    - snapshot metadata and archive paths

## UI wiring added

- Reused the existing mission dashboard `Event Timeline` card.
- Added a local archive session selector.
- Added blackbox session summary metrics:
  - archive session id
  - event count / last event type
  - last snapshot reason / time
  - last job id
- Added path inspection rows for:
  - `session_dir`
  - `events.jsonl`
  - `state_snapshot.json`
- Switched the card’s recent event list to prefer the new archive timeline payload; when no archive session exists yet, the card stays honest and shows a pending/fallback note instead of inventing replay.

## Archive sources used

- `runtime/event_archives/<session_id>/events.jsonl`
  - Source of truth for replayed event order, event counts, last event type/time, and recent timeline entries.
- `runtime/event_archives/<session_id>/state_snapshot.json`
  - Source of truth for last snapshot metadata, snapshot reason, mode-boundary note, and snapshot `extra` fields.
- Reused existing event-spine semantics only:
  - existing event types
  - existing planes and mode scopes
  - existing `MODE_BOUNDARY_NOTE`

## Current limits

- Read-only and local-only.
- No rrweb, no DOM/session recording, no synthetic “playback”.
- No storage change beyond reading the existing JSONL and snapshot JSON files.
- No protocol-story rewrite: the 3-core Linux + RTOS demo mode vs 4-core Linux performance mode boundary remains explicit.
