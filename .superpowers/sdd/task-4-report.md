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

## Review Fixes

### Implementation

- USRP output routing now uses `current_jscc_link_mode()`, the same effective resolver used by board access and transport runtime.
- Missing and unknown link-mode values fall back to `qpsk`; `OPENAMP_DEMO_LINK_MODE` aliases remain supported.
- The TVM callback uses the same non-throwing resolver, so an unknown value cannot raise after transport staging succeeds.
- IQ-direct MNN remains routed to `/home/user/Downloads/jscc-test-usrp/iq-direct/mnn`.
- The shared Task 1 registry now keeps prerecorded MNN at `/home/user/Downloads/jscc-test/mnn_benchmark_outputs`. Cockpit serialization and actual USRP roots are unchanged.

### RED Evidence

```text
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access" -v
```

Result: 1 failed, 5 passed, 230 deselected. The unknown-mode case raised `ValueError` from strict `normalize_jscc_link_mode()`; missing fallback, alias routing, and IQ-direct MNN coverage already matched the required behavior.

```text
python -m pytest tests/test_board_image_compare_sources.py::test_prerecorded_filters_keep_existing_layout -v
```

Result: 1 failed. The registry returned `/home/user/Downloads/jscc-test/jscc/mnn_benchmark_outputs` instead of the unchanged prerecorded MNN root.

```text
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_usrp_tvm_stage_unknown_link_mode_falls_back_after_transport -v
```

Result: 1 failed. The post-transport TVM callback still raised `ValueError` from a second strict normalization.

### GREEN Evidence

- Routing cases: 6 passed, 230 deselected.
- Exact source-layout case: 1 passed.
- Post-transport fallback regression: 1 passed.

### Final Review Verification

```text
python -m pytest tests/test_board_image_compare_sources.py -v
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -v
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or usrp_tvm_stage or reconstruction_browser" -v
```

Results: 10 passed; 2 passed; 11 passed with 226 deselected. No new concerns were found in the review-fix scope.
