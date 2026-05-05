# big.LITTLE Compare Report

- status: ok
- run_id: big_little_compare_20260318_095615
- env_file: ./session_bootstrap/config/big_little_pipeline.current.bestcurrent_snr10.2026-03-18.phytium_pi.env
- serial_total_wall_ms: 103416.354
- pipeline_total_wall_ms: 76437.341
- serial_images_per_sec: 2.901
- pipeline_images_per_sec: 3.925
- throughput_uplift_pct: 35.298

## Commands

- serial: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`
- pipeline: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current`
