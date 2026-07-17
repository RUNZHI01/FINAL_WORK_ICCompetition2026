# USRP reconstruction output layout

## Browser sources

| Source ID | Board root | Selection |
|---|---|---|
| `prerecorded-pytorch` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | `pytorch_reference_reconstruction_*` |
| `prerecorded-tvm` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | Entries outside the PyTorch prefix |
| `prerecorded-mnn` | `/home/user/Downloads/jscc-test/mnn_benchmark_outputs` | All entries |
| `usrp-qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | Historical and new QPSK TVM jobs |
| `usrp-iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | Historical and new direct-IQ TVM jobs |

The prerecorded source roots stay at the paths above, and prerecorded jobs are not renamed. Only strict historical `openamp3_usrp_*_current` children selected from the legacy TVM root are eligible. New Demo jobs route to the QPSK or direct-IQ root from the effective `JSCC_LINK_MODE`; MNN uses the corresponding `mnn` leaf.

| Effective link mode | TVM output | MNN output |
|---|---|---|
| `qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | `/home/user/Downloads/jscc-test-usrp/qpsk/mnn` |
| `iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | `/home/user/Downloads/jscc-test-usrp/iq-direct/mnn` |

## Classification report

The report is `Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json`. Each decision records reversible `source` and `destination` paths, `mode`, `reason`, `classification`, and the local `evidence` path. Top-level lists separate `classified`, `moved`, `already_moved`, `unresolved`, `collisions`, and `missing` entries.

`exact-summary` means the job's own `batch_spool_summary.json` supplied the link evidence. `inherited-base-summary` is limited to a recovery/retry job classified from its base job. Missing or ambiguous summaries remain `unresolved` in the legacy root. Existing source and destination paths are a collision and block the entire apply; an existing destination with no source is `already_moved`.

## Commands

Dry-run is the default:

```powershell
python scripts/migrate_usrp_output_layout.py `
  --host 100.121.87.73 --user user --password user `
  --run-root USRP292x/qpsk_batch_spool_arq_runs `
  --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json
```

Use `--apply` only after the dry-run has the expected 239 exact direct-IQ jobs, four QPSK jobs, one inherited direct-IQ recovery job, one unresolved retry job, and no collisions or missing classified sources. Re-run the dry-run after apply; the 244 classified entries must be `already_moved`, while the unresolved retry remains in the legacy root.

```powershell
# Apply after review
python scripts/migrate_usrp_output_layout.py --host 100.121.87.73 --user user --password user --run-root USRP292x/qpsk_batch_spool_arq_runs --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json --apply

# Roll back destinations present in the report
python scripts/migrate_usrp_output_layout.py --host 100.121.87.73 --user user --password user --rollback-report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json --apply
```

The CLI uses Paramiko SFTP `stat`, `mkdir`, and `rename`; it does not issue remote shell move commands or overwrite a destination.

## 2026-07-17 evidence

The board was reachable, but the configured legacy root contained 122 children and no `openamp3_usrp_*_current` children. Both new USRP roots were absent. The guarded dry-run therefore recorded zero classified jobs and `safe: false`; apply and post-apply idempotence checks were not run. The expected unresolved retry job could not be identified in this board state. Restore or identify the historical legacy output snapshot, then repeat dry-run review before applying.
