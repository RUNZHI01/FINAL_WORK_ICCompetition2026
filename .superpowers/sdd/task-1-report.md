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

## Review fixes

- Exact recovery/retry lookup now checks the exact job name across `run_root` and `legacy_root` before checking any base-token candidates. Added `test_plan_usrp_migration_checks_exact_recovery_across_all_roots_before_base`.
- `plan_usrp_migration()` keeps its four required positional arguments and accepts optional keyword-only `existing_destinations`. A classified job whose planned destination is present returns `destination: None`, retains its mode, and reports `destination already exists`. Added `test_plan_usrp_migration_reports_existing_destination_collision`.

### Review-fix TDD outputs

RED after adding both regression tests:

```text
10 items collected
8 passed, 2 failed
test_plan_usrp_migration_checks_exact_recovery_across_all_roots_before_base: selected the base run instead of the exact legacy recovery run
test_plan_usrp_migration_reports_existing_destination_collision: TypeError: unexpected keyword argument 'existing_destinations'
```

GREEN after the implementation fixes:

```text
python -m pytest tests/test_board_image_compare_sources.py -v
10 passed in 0.14s

python -m pytest tests/test_board_image_compare_sources.py tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py -q
38 passed in 5.22s

python -m compileall -q scripts/board_image_compare/sources.py
passed

git diff --check
passed
```
