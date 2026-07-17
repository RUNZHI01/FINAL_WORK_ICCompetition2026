# Task 5 Report: Safe Historical Migration And Documentation

## Status

`DONE_WITH_CONCERNS`. Code, tests, guarded dry-run report, and documentation are complete. The board migration was not applied because the required dry-run counts were not present.

## TDD evidence

Initial RED:

```text
python -m pytest tests/test_board_image_compare_sources.py -v
ERROR during collection: ModuleNotFoundError: No module named 'scripts.migrate_usrp_output_layout'
```

Initial GREEN after the structured SFTP implementation:

```text
python -m pytest tests/test_board_image_compare_sources.py -v
16 passed in 0.26s
```

Direct CLI regression RED/GREEN:

```text
python -m pytest tests/test_board_image_compare_sources.py::test_migration_script_runs_as_a_direct_cli -v
RED: direct execution failed with ModuleNotFoundError: scripts.board_image_compare
GREEN: 1 passed in 0.32s
```

Empty-discovery safety regression RED/GREEN:

```text
python -m pytest tests/test_board_image_compare_sources.py::test_empty_migration_plan_is_not_safe -v
RED: expected false, got true
python -m pytest tests/test_board_image_compare_sources.py -v
GREEN: 18 passed in 0.57s
```

The tests cover dry-run, apply parent creation and one rename, collision refusal, report-driven rollback, deterministic atomic report writes, and direct CLI execution.

## Migration evidence

Dry-run command using the original checkout's read-only run evidence:

```powershell
python scripts/migrate_usrp_output_layout.py --host 100.121.87.73 --user user --password user --run-root 'E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\USRP292x\qpsk_batch_spool_arq_runs' --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json
```

First result exposed the empty-plan safety defect: zero in every category with `safe: true`. Read-only Paramiko/SFTP inspection then found 122 children in `/home/user/Downloads/jscc-test/jscc/infer_outputs`, zero strict `openamp3_usrp_*_current` children, and no QPSK or IQ destination roots.

After the safety regression fix, the exact dry-run command returned:

```json
{"already_moved": 0, "classified": 0, "collisions": 0, "missing": 0, "moved": 0, "safe": false, "unresolved": 0, "usrp-iq-direct": 0, "usrp-qpsk": 0}
```

No `--apply` or rollback command was run. A post-apply idempotence check was therefore not applicable. No prerecorded root or child was renamed.

## Implementation

- `apply_migration()` performs a complete structured-SFTP preflight before any rename. Collisions, missing classified sources, and empty plans are unsafe.
- Apply creates missing destination parents with SFTP and renames without overwrite.
- Rollback reverses only classified report entries whose migrated destination exists.
- Reports are sorted deterministic JSON written via a temporary sibling and `Path.replace()`.
- Reports contain host, port, and user only; no password, private key, or Tailscale credential is stored.

## Concern

The reviewed brief expected 239 exact direct-IQ jobs, four QPSK jobs, one inherited direct-IQ recovery job, and one unresolved retry job. The connected board did not expose those historical job directories under the configured legacy root, so applying would not satisfy the task and was intentionally blocked. The checked-in report records the observed zero-count state and `safe: false`.

## Verification

```text
python -m pytest tests/test_board_image_compare_core.py tests/test_board_image_compare_remote.py tests/test_board_image_compare_service.py tests/test_board_image_compare_sources.py -v
60 passed in 9.69s

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_reconstruction_browser.py -v
2 passed in 0.16s

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp_stage_access or reconstruction_browser" -v
8 passed, 229 deselected in 1.90s

node --check scripts/board_image_compare/web/app.js
exit 0

python -m py_compile scripts/migrate_usrp_output_layout.py
exit 0

git diff --check
exit 0
```
