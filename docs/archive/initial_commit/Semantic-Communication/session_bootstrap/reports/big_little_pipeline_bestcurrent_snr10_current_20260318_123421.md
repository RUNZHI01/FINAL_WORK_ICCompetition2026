# big.LITTLE Wrapper Report

- status: ok
- run_id: big_little_pipeline_bestcurrent_snr10_current_20260318_123421
- variant: current
- execution_mode: pipeline
- remote_mode: ssh
- env_file: None
- processed_count: 300
- total_wall_ms: 44413.422
- images_per_sec: 6.755
- dry_run: False
- big_cores: [2]
- little_cores: [0, 1]
- output_dir: /home/user/Downloads/jscc-test/big_little_runs/big_little_pipeline_bestcurrent_snr10_current

## Affinity

- preloader: {'role': 'preloader', 'requested': [0, 1], 'before': [0, 1, 2, 3], 'after': [0, 1], 'status': 'applied', 'error': None}
- inferencer: {'role': 'inferencer', 'requested': [2], 'before': [0, 1, 2, 3], 'after': [2], 'status': 'applied', 'error': None}
- postprocessor: {'role': 'postprocessor', 'requested': [0, 1], 'before': [0, 1, 2, 3], 'after': [0, 1], 'status': 'applied', 'error': None}
