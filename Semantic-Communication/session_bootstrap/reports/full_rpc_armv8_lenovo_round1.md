# Full Report

- execution_id: full_rpc_armv8_lenovo_round1
- mode: full
- status: success
- timestamp: 2026-03-01T14:44:59+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_144456.env
- model_name: replace_with_model_name
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- full_timeout_sec: 180
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_lenovo_db
- baseline_cmd: `bash "$FULL_RUNNER_SCRIPT" --label baseline --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_BASELINE_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- current_cmd: `bash "$FULL_RUNNER_SCRIPT" --label current --hotspots "$FULL_HOTSPOT_TASKS" --trials-per-task "$FULL_TRIALS_PER_TASK" --work-units "$FULL_CURRENT_WORK_UNITS" --db-dir "$TUNING_DB_DIR/full_hotspot_runs"`
- baseline_elapsed_ms: 58.087
- baseline_exit_code: 0
- baseline_count: 1
- current_elapsed_ms: 54.120
- current_exit_code: 0
- current_count: 1
- delta_ms_current_minus_baseline: -3.967
- improvement_pct: 6.83
- full_notes: orchestrator-only mock payload, pending real TVM RPC hotspot command

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_rpc_armv8_lenovo_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_lenovo_round1_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
