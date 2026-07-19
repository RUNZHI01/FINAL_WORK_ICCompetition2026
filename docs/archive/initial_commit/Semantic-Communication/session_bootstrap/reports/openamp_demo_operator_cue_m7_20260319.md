# OpenAMP Demo Operator Cue M7

## UI changes added

- Kept the existing single-page dashboard and added a compact `Operator Assist / Manual Cue` block inside the existing `Command Center`.
- The cue block now shows:
  - current recommended scene
  - next manual step
  - short presenter line
  - four scene readiness cards with checklist items
  - quick jump buttons to the relevant act or section
- Extended the existing scene cards so each scene now also shows cue text and readiness checks instead of only status summary.

## Backend additions

- Added a small derived `operator_cue` payload to `/api/system-status`.
- The payload is read-only and is built from existing state already exposed by the demo:
  - board/session readiness
  - live probe and guard state
  - job manifest gate verdict
  - link director selection
  - current active/last inference state
  - safety panel mirror state
  - event spine / archive readiness
- No new control actions or protocol side effects were introduced.

## How cue recommendations are derived

- Scene 1 is recommended first when the operator still needs to finish session setup, probe the board, or review a non-`allow` gate verdict.
- Scene 2 is recommended when Current live is the honest next manual action, or when Current is already running / still only showing archive fallback.
- Scene 3 is recommended after a valid Current live result is available and the page can move into compare viewer plus the 4-core vs 3-core boundary explanation.
- Scene 4 is recommended when a fault is latched or SAFE_STOP recovery is the live truth that needs to be explained.
- Scene checklists are derived from the existing truth surfaces only; they do not synthesize new board state.

## What remains manual / operator-driven

- Board credential entry
- probe-board action
- manifest gate preview
- Current live launch
- PyTorch/baseline launch
- fault injection
- SAFE_STOP recovery

The M7 layer is operator assist only. It recommends the next manual step and jump target, but it does not pretend the four-scene story is fully automated.
