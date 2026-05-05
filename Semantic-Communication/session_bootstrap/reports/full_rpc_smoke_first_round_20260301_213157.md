# Full Report

- execution_id: full_rpc_smoke_first_round_20260301_213157
- mode: full
- status: success
- timestamp: 2026-03-01T21:32:00+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/config/rpc_armv8_smoke.run_20260301_213157.env
- model_name: smoke_rpc_model
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224
- threads: 4
- full_timeout_sec: 120
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_smoke_db
- baseline_cmd: `bash "$FULL_RUNNER_SCRIPT" --label baseline --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_BASELINE_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- current_cmd: `bash "$FULL_RUNNER_SCRIPT" --label current --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_CURRENT_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- baseline_elapsed_ms: 65.154
- baseline_exit_code: 0
- baseline_count: 1
- current_elapsed_ms: 59.224
- current_exit_code: 0
- current_count: 1
- delta_ms_current_minus_baseline: -5.930
- improvement_pct: 9.10
- full_notes: offline mock of rpc hotspot full flow

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_rpc_smoke_first_round_20260301_213157.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_smoke_first_round_20260301_213157_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
