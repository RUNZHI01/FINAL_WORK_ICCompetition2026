# Task 4 Report: Cockpit Output Routing And Browser Configuration

## Status

Implemented the reviewed Task 4 brief within the four owned Cockpit files.

## Implementation

- `_usrp_stage_access()` now normalizes the effective `JSCC_LINK_MODE` and routes actual USRP outputs to `<usrp-root>/<mode>/<engine>`.
- TVM outputs use the exact `qpsk/tvm` and `iq-direct/tvm` roots; MNN outputs use `<mode>/mnn`.
- Existing run-specific output/report prefixes and all prerecorded generation/output paths remain unchanged.
- `ReconstructionBrowserConfig` now carries serialized `sources` and `default_source` instead of one `remote_root`.
- The browser manager posts the source tuple as a JSON list accepted by the comparison service.
- Cockpit browser launch supplies the five Task 1 source definitions and defaults to `usrp-iq-direct`. The prerecorded roots and prefix filters are unchanged, while both USRP TVM roots use the configured USRP base root.

## TDD Evidence

### Output Routing

- Baseline: focused server selection passed 4 tests.
- RED: the focused server command failed 3 tests because TVM and MNN roots omitted the link-mode segment.
- GREEN: the focused server command passed 5 tests after routing through `<mode>/<engine>`.

### Browser Contract

- RED: the browser suite failed because `ReconstructionBrowserConfig` did not accept `sources`.
- GREEN: the browser suite passed 2 tests after serializing `sources` and `default_source`.
- RED: the focused server command failed 1 test because Cockpit still constructed the removed `remote_root` field.
- GREEN: the focused server command passed 5 tests after supplying all five sources.

## Verification

Required focused commands:

```text
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -v
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or reconstruction_browser" -v
```

Final focused results: 2 passed and 5 passed, respectively. Both production modules passed `py_compile`, and `git diff --check` passed.

## Self-Review

- Confirmed the QPSK, IQ-direct, and MNN roots match the brief exactly.
- Confirmed source IDs, labels, prefix filters, and prerecorded roots match the Task 1 registry.
- Confirmed no production code outside the two owned Cockpit modules changed.

## Concerns

The complete two-module test run produced 210 passes and 25 unrelated failures in this Windows/live-board environment. Failures included SSH timeouts to the configured board, missing local runtime assets, and an existing Windows test patch that replaces global `subprocess.Popen` and breaks Bash discovery before Task 4 code runs. The required focused Task 4 suites pass independently.
