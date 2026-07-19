# big.LITTLE Compare Report

- status: ok
- run_id: local_mock_compare_validation_20260318
- env_file: session_bootstrap/config/big_little_pipeline.mock.local.example.env
- serial_total_wall_ms: 53.404
- pipeline_total_wall_ms: 45.351
- serial_images_per_sec: 74.901
- pipeline_images_per_sec: 88.201
- throughput_uplift_pct: 17.757

## Commands

- serial: `BIG_LITTLE_OUTPUT_PREFIX=big_little_pipeline_mock_serial_mock BIG_LITTLE_REPORT_PREFIX=big_little_pipeline_mock_serial_mock bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current --execution-mode serial`
- pipeline: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current`
