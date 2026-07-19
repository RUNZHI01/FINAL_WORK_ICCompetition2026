# big.LITTLE Compare Report

- status: ok
- run_id: big_little_compare_20260318_051326
- env_file: ./session_bootstrap/config/big_little_pipeline.current.runtime_20260318_050239.env
- serial_total_wall_ms: 103948.643
- pipeline_total_wall_ms: 75913.179
- serial_images_per_sec: 2.886
- pipeline_images_per_sec: 3.952
- throughput_uplift_pct: 36.937

## Commands

- serial: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`
- pipeline: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current`
