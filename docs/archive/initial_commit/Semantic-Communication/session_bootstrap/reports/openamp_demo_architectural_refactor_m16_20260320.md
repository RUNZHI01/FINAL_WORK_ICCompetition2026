# OpenAMP Demo Architectural Refactor M16

Date: 2026-03-20

## New Information Architecture

- The page now opens as a command console instead of a stack of equal cards.
- `primary layer`: one command deck with:
  - a top command strip stating the current scene, current state, next operator action, and boundary note
  - one dominant scene workbench that follows the recommended act on first load and shows the active scene as the main viewport
- `secondary layer`: one operational side rail containing:
  - live verdict
  - operator cue
  - demo-only manifest gate
  - link director
  - SAFE_STOP mirror / alarm state
- `tertiary layer`: one lower evidence band plus supporting decks:
  - blackbox timeline / archive evidence
  - task queue, device status, return evidence
  - credential deck
  - performance metrics and source links

## What Moved

- `primary`:
  - act navigation and active act panel moved into the central workbench
  - compare / scene output became the dominant visual area instead of one card among many
  - command strip now owns the first-viewport story
- `secondary`:
  - gate, link director, and safety moved out of the equal-weight mission grid into the right rail
  - latest live status moved into the rail as a system readout instead of hero filler
- `tertiary`:
  - archive timeline became the anchor of the lower evidence band
  - credential entry and source materials were pushed below the main cockpit

## What Was Removed Or De-Emphasized

- The previous “many same-weight dashboards in sequence” read.
- Repeated scene summaries inside both command center and operator cue.
- Top-of-page explanatory copy that read like deck notes instead of software state.
- Early-page competition between queue, device, link, return, safety, and archive cards.

## Visual / Product Goal

- This pass aimed to make the demo feel like operator-facing mission software: sharper hierarchy, darker command-console surfaces, clearer state/action framing, and a more deliberate eye path.
- The redesign keeps the honest scope boundaries explicit but concentrates them where they matter:
  - `4-core Linux performance mode` vs `3-core Linux + RTOS demo mode`
  - `link director = ui_scaffold_only`
  - manifest preview is demo-only, not real `JOB_REQ` dispatch
  - Linux UI remains mirror/control surface only for `SAFE_STOP`
  - archive replay stays JSONL/snapshot replay, not browser recording
