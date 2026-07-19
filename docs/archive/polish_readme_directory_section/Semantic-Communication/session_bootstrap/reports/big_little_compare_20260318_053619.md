# big.LITTLE Compare Report

- status: ok
- run_id: big_little_compare_20260318_053619
- env_file: ./session_bootstrap/config/big_little_pipeline.current.runtime_20260318_050239.env
- serial_total_wall_ms: 104217.906
- pipeline_total_wall_ms: 76322.697
- serial_images_per_sec: 2.879
- pipeline_images_per_sec: 3.931
- throughput_uplift_pct: 36.54

## Commands

- serial: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`
- pipeline: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current`
