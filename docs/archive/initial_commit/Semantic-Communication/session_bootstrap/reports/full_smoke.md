# Full Report

- execution_id: full_smoke
- mode: full
- status: success
- timestamp: 2026-03-01T11:12:06+08:00
- env_file: ./session_bootstrap/config/quick_smoke.env
- model_name: smoke_demo
- target: smoke_target
- shape_buckets: 64
- threads: 1
- full_timeout_sec: 10
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/smoke_db
- baseline_cmd: `sleep 1.2`
- current_cmd: `sleep 0.4`
- baseline_elapsed_ms: 1232.974
- baseline_exit_code: 0
- current_elapsed_ms: 421.020
- current_exit_code: 0
- delta_ms_current_minus_baseline: -811.954
- improvement_pct: 65.85
- full_notes: smoke run for full skeleton

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_smoke.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_smoke_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
