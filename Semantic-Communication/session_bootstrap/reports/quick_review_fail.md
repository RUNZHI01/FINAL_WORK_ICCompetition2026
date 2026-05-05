# Quick Report

- execution_id: quick_review_fail
- mode: quick
- status: failed_current
- timestamp: 2026-03-01T12:02:52+08:00
- env_file: /tmp/review_fail.env
- model_name: smoke_demo
- target: smoke_target
- shape_buckets: 64
- threads: 1
- quick_repeat: 1
- tuning_db_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/tmp/smoke_db
- baseline_cmd: `echo baseline ok`
- current_cmd: `bash -lc "echo forced fail; exit 7"`
- baseline_count: 1
- baseline_median_ms: 14.825
- baseline_mean_ms: 14.825
- baseline_variance_ms2: 0.000000
- baseline_exit_code: 0
- current_count: 0
- current_median_ms: NA
- current_mean_ms: NA
- current_variance_ms2: NA
- current_exit_code: 7
- delta_ms_current_minus_baseline: NA
- improvement_pct: NA

## Artifacts

- log_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/quick_review_fail.log
- raw_csv_file: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/quick_review_fail_raw.csv
