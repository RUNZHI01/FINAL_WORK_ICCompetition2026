# Full Report

- execution_id: full_low_budget_hotspot_2026-03-01_01
- mode: full
- status: success
- timestamp: 2026-03-01T12:18:07+08:00
- env_file: ./session_bootstrap/config/full_low_budget_hotspot_2026-03-01.env
- model_name: example_model
- target: llvm
- shape_buckets: 64,128
- threads: 4
- full_timeout_sec: 120
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/local_db
- baseline_cmd: `bash "$FULL_RUNNER_SCRIPT" --label baseline --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_BASELINE_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- current_cmd: `bash "$FULL_RUNNER_SCRIPT" --label current --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_CURRENT_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- baseline_elapsed_ms: 83.072
- baseline_exit_code: 0
- current_elapsed_ms: 76.419
- current_exit_code: 0
- delta_ms_current_minus_baseline: -6.653
- improvement_pct: 8.01
- full_notes: full low-budget run driven by locked hotspot top list (2026-03-01)

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_low_budget_hotspot_2026-03-01_01.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_low_budget_hotspot_2026-03-01_01_raw.csv

## Full Run Result Template

- hotspot_tasks: conv2d_nchw_1,dense_1,layernorm_1
- task_count: 3
- trials_per_task: 2
- tuning_db_snapshot: ./session_bootstrap/tmp/local_db/full_hotspot_runs/full_payload_baseline_20260301_121807.csv; ./session_bootstrap/tmp/local_db/full_hotspot_runs/full_payload_current_20260301_121807.csv
- abnormal_cases: none
- next_action: run quick warm-start validation with same hotspot list and db
