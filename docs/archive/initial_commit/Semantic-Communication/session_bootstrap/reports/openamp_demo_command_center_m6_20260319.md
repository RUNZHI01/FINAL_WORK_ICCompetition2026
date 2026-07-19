# OpenAMP Demo Command Center M6

Date: 2026-03-19

## UI / flow changes added

- Kept the existing single-page dashboard and inserted a new top-level `Command Center` section above the mission dashboard.
- Added a compact command strip that rolls up:
  - current link-director preset
  - current job-manifest gate verdict
  - selected compare sample state
  - current SAFE_STOP / safety mirror state
  - current archive session / event count
- Added a recommended jump button and a quick-jump row so the operator can move directly to:
  - session access
  - manifest gate
  - Act 2 Current live
  - Act 3 compare viewer
  - Act 4 SAFE_STOP
  - blackbox timeline
- Added a four-scene status grid that mirrors the existing four-act structure, but summarizes each act as one operator-facing card with current status, note, and jump target.

## Backend additions

- None.
- M6 reuses the existing `/api/snapshot`, `/api/system-status`, `/api/link-director`, and archive-session payloads.

## How the modules are now tied together

- The command strip derives one top-level operator summary from already existing state instead of presenting link, manifest, compare, safety, and archive as isolated widgets.
- The four-scene cards explicitly map the current whole-page story:
  - Act 1: board access, probe state, and manifest gate
  - Act 2: Current live progress or honest fallback/archive state
  - Act 3: compare viewer sample and the 4-core vs 3-core boundary note
  - Act 4: SAFE_STOP / fault state plus archive timeline presence
- The jump buttons use stable section targets inside the same page, so the page now behaves more like a single command seat than a set of unrelated panels.

## Still operator-driven / manual

- Probe, ticket preview, Current run, PyTorch run, fault injection, and SAFE_STOP are still manually triggered by the operator.
- M6 does not claim a fully automated 72-second sequence.
- The 4-core Linux performance-mode headline vs 3-core Linux + RTOS demo-mode live boundary remains unchanged and explicitly visible.
