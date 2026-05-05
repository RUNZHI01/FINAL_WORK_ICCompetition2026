# OpenAMP Demo UI Simplify M15

Date: 2026-03-20

## What Was Simplified

- Rebalanced the top of the page so the operator command layer reads first: the dark command strip now leads, the operator cue is lighter, and the jump row/scene cards are less repetitive.
- Reduced duplicated explanation around mode boundary, manual ownership, and archive provenance. The 4-core vs 3-core split is still explicit, but no longer repeated in every card.
- Simplified the command center model from five equal-weight rollups to three stronger summaries: launch readiness, Current/compare state, and safety/archive state.
- Converted operator cue scene cards into compact stage summaries and kept the detailed readiness checks only in the current focused scene.
- Made the mission dashboard calmer by giving the archive timeline a full-width lane, reducing card density, and trimming verbose mission notes.
- Simplified the compare viewer context: same-sample provenance is still visible, but the context block is shorter and file-path noise is truncated.
- Simplified the safety panel copy: mirror/ownership/recover wording is still honest, but repeated restatements were collapsed into a single footer line.
- Simplified the blackbox/archive area when no archive exists: it now shows a short pending state instead of a larger repeated explanation, while keeping fallback timeline behavior honest.
- Tightened spacing, card weights, and grid layout so fewer equal-priority blocks compete in the first viewport.

## What Was Intentionally Kept

- The single-page app structure and all current feature paths: probe, session entry, gate preview, Current run, PyTorch run, compare viewer, fault inject, SAFE_STOP recover, archive session replay.
- Existing IDs and core render functions used by the server/static tests.
- Honest separation between `4-core Linux performance mode` evidence and `3-core Linux + RTOS demo mode` live display.
- Honest `mirror/control surface only` safety framing for Linux UI.
- Archive replay staying local-only, read-only, and JSONL/snapshot based.

## Remaining Clutter / Debt Not Addressed

- Act 1 still has many KPI cards; it is calmer now mainly because the top-level command/mission layers carry less noise, but the act itself could still be pruned further.
- Act 2 and Act 4 still expose raw logs and operational detail directly; this is useful for evaluators, but the panels are still dense once expanded.
- The page still mixes Chinese labels, English technical terms, and bilingual headings from earlier milestones; M15 reduced visual noise more than language-system inconsistency.
- No server payload/schema cleanup was attempted in this pass; some UI copy is still shaped by verbose field names from existing data structures.

## Validation

- `node --check session_bootstrap/demo/openamp_control_plane_demo/static/app.js`
- `python3 -m unittest session_bootstrap.demo.openamp_control_plane_demo.tests.test_server.DemoHTTPServerTest.test_root_serves_dashboard_entry_page session_bootstrap.demo.openamp_control_plane_demo.tests.test_server.DemoHTTPServerTest.test_app_js_serves_dashboard_javascript session_bootstrap.demo.openamp_control_plane_demo.tests.test_server.DemoHTTPServerTest.test_app_css_serves_dashboard_stylesheet session_bootstrap.demo.openamp_control_plane_demo.tests.test_server.DemoHTTPServerTest.test_operator_readiness_smoke_state_covers_required_page_modules`
