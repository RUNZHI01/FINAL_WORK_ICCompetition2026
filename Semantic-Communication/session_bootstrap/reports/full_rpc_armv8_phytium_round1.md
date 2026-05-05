# Full Report

- execution_id: full_rpc_armv8_phytium_round1
- mode: full
- status: success
- timestamp: 2026-03-01T16:50:45+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/rpc_run_env_20260301_165035.env
- model_name: jscc
- target: llvm -mtriple=aarch64-linux-gnu -mattr=+neon
- shape_buckets: 1x3x224x224,1x3x256x256
- threads: 4
- full_timeout_sec: 600
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/rpc_armv8_phytium_pi_db
- baseline_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "sha256sum \"$REMOTE_TVM_PRIMARY_SO\" \"$REMOTE_TVM_PRIMARY_DB_RECORD\" \"$REMOTE_TVM_PRIMARY_DB_WORKLOAD\""`
- current_cmd: `bash ./session_bootstrap/scripts/ssh_with_password.sh --host "$REMOTE_HOST" --user "$REMOTE_USER" --pass "$REMOTE_PASS" -- "find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"optimized_model.so\" | sort && echo \"---\" && find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"database_tuning_record.json\" | sort && find \"$REMOTE_DOWNLOADS_DIR\" -type f -name \"database_workload.json\" | sort"`
- baseline_elapsed_ms: 801.478
- baseline_exit_code: 0
- baseline_count: 1
- current_elapsed_ms: 1555.451
- current_exit_code: 0
- current_count: 1
- delta_ms_current_minus_baseline: 753.973
- improvement_pct: -94.07
- full_notes: phytium remote artifact/db verification before replacing payload with true TVM tuning runner

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/full_rpc_armv8_phytium_round1.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/full_rpc_armv8_phytium_round1_raw.csv

## Full Run Result Template

- hotspot_tasks: TODO
- task_count: TODO
- trials_per_task: TODO
- tuning_db_snapshot: TODO
- abnormal_cases: TODO
- next_action: TODO
