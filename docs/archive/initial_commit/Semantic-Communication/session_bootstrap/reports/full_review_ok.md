# Full Report

- execution_id: full_review_ok
- mode: full
- status: success
- timestamp: 2026-03-01T12:00:57+08:00
- env_file: /tmp/review_ok.env
- model_name: smoke_demo
- target: smoke_target
- shape_buckets: 64
- threads: 1
- full_timeout_sec: 10
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/smoke_db
- baseline_cmd: `sleep 0.2`
- current_cmd: `sleep 0.1`
- baseline_elapsed_ms: 216.436
- baseline_exit_code: 0
- current_elapsed_ms: 116.511
- current_exit_code: 0
- delta_ms_current_minus_baseline: -99.925
- improvement_pct: 46.17
- full_notes: review validation

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_review_ok.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_review_ok_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
