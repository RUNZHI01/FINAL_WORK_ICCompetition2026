# Full Report

- execution_id: full_low_budget_template
- mode: full
- status: success
- timestamp: 2026-03-01T11:36:09+08:00
- env_file: ./session_bootstrap/config/local.example
- model_name: example_model
- target: llvm
- shape_buckets: 64,128
- threads: 4
- full_timeout_sec: 120
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/local_db
- baseline_cmd: `bash "$FULL_RUNNER_SCRIPT" --label baseline --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_BASELINE_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- current_cmd: `bash "$FULL_RUNNER_SCRIPT" --label current --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_CURRENT_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- baseline_elapsed_ms: 48.240
- baseline_exit_code: 0
- current_elapsed_ms: 38.317
- current_exit_code: 0
- delta_ms_current_minus_baseline: -9.923
- improvement_pct: 20.57
- full_notes: low-budget hotspot validation template

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_template.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_template_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
