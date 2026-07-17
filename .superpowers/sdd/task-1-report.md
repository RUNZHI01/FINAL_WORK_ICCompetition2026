# Task 1 Report: Source Registry And Historical Classifier

## Status

Implemented. The change is limited to the Task 1 source module, its focused tests, and this report; the commit is created after final verification.

## Implementation

- Added frozen `ReconstructionSource` records with case-insensitive include/exclude prefix filtering.
- Added all five source IDs:
  - `prerecorded-pytorch`
  - `prerecorded-tvm`
  - `prerecorded-mnn`
  - `usrp-qpsk`
  - `usrp-iq-direct`
- Preserved the existing prerecorded roots and added the exact QPSK/IQ USRP roots beneath the configured USRP root.
- Added conservative USRP classification. IQ evidence wins; QPSK requires transport schema evidence; ambiguous summaries return `None`.
- Added `extract_usrp_token()` for current, recovery, and retry job names.
- Added dry-run migration planning that reads only `batch_spool_summary.json`, checks exact then base local runs, records source/destination/mode/reason, and leaves unresolved entries without destinations.

## TDD Evidence

- RED: `python -m pytest tests/test_board_image_compare_sources.py -v` failed during collection with `ModuleNotFoundError: No module named 'scripts.board_image_compare.sources'`.
- GREEN: The same command passed with 8 tests.

## Verification

- `python -m pytest tests/test_board_image_compare_sources.py -v`: 8 passed.
- `python -m pytest tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py -q`: 28 passed.
- `python -m compileall -q scripts/board_image_compare/sources.py`: passed.
- `git diff --check`: passed.

## Concerns

The migration planner only produces decisions. It does not copy, move, or overwrite output; the later migration CLI owns those filesystem/SFTP operations and must retain dry-run and destination-existence safeguards.
