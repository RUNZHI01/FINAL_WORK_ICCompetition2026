# big.LITTLE Compare Report

- status: ok
- run_id: big_little_compare_20260406_191650
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/openamp_3core_handwritten_mean4_v7_big_little_20260406.env
- serial_total_wall_ms: 103777.31
- pipeline_total_wall_ms: 74817.887
- serial_images_per_sec: 2.891
- pipeline_images_per_sec: 4.01
- throughput_uplift_pct: 38.706

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
