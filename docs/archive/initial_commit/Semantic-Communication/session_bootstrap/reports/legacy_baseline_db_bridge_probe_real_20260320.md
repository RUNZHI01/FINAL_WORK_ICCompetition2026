# Legacy baseline DB bridge probe

- report_id: legacy_baseline_db_bridge_probe_real_20260320
- source_db: session_bootstrap/tmp/remote_baseline_snapshot_20260320_211709/tuning_logs
- workload_rows: 23
- tuning_record_rows: 507
- workload_graph_formats: {"legacy_root_object_graph": 23}

## Direct current-safe probe

- workload_parse: {"success": false, "count": 23, "first_error": "ValueError: Invalid JSON Object Graph, expected `root_index` integer field"}
- tuning_record_parse: {"success": false, "count": 507, "first_error": "ValueError: workload index 0 is not parseable"}

## Normalization probe

- workload_parse: {"success": false, "count": 23, "first_error": "KeyError: 'key is not in Map'"}
- tuning_record_parse: {"success": false, "count": 507, "first_error": "ValueError: workload index 0 is not parseable"}
- workload_warnings: []

## Trace ops

- unsupported_ops: {"GetBlock": 4991}
- rewrite_counts: {"GetBlock": 4991}

## Candidate DB

- parse_validated: False
- candidate_dir: None

## Remaining blocker

- KeyError: 'key is not in Map'

## Next command

- `/home/tianxing/.venvs/tvm-ms/bin/python /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/probe_legacy_baseline_db_bridge.py --source-db session_bootstrap/tmp/remote_baseline_snapshot_20260320_211709/tuning_logs`
