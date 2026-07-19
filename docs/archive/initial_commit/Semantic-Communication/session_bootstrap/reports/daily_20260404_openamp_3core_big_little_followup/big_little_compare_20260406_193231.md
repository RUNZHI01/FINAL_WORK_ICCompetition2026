# big.LITTLE Compare Report

- status: ok
- run_id: big_little_compare_20260406_193231
- env_file: ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/acl_big_little_compare.env
- serial_total_wall_ms: 105548.166
- pipeline_total_wall_ms: 78876.743
- serial_images_per_sec: 2.842
- pipeline_images_per_sec: 3.803
- throughput_uplift_pct: 33.814

## Commands

- serial: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300`
- pipeline: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --max-inputs 300`

## Board State

- capture_status: ok
- capture_reason: automatic ssh topology snapshots enabled
- pre_serial_status: ok
- pre_serial_online_cpus: 0,1,2
- pre_pipeline_status: ok
- pre_pipeline_online_cpus: 0,1,2
- post_pipeline_status: ok
- post_pipeline_online_cpus: 0,1,2
- online_cpu_changed_across_compare: False
