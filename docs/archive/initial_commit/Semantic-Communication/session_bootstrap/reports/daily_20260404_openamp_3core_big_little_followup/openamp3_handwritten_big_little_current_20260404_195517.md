# big.LITTLE Wrapper Report

- status: ok
- run_id: openamp3_handwritten_big_little_current_20260404_195517
- variant: current
- execution_mode: pipeline
- remote_mode: ssh
- env_file: None
- processed_count: 300
- total_wall_ms: 75775.322
- images_per_sec: 3.959
- dry_run: False
- big_cores: [2]
- little_cores: [0, 1]
- output_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/openamp3_handwritten_big_little_current

## Affinity

- preloader: {'role': 'preloader', 'requested': [0, 1], 'before': [0, 1, 2], 'after': [0, 1], 'status': 'applied', 'error': None}
- inferencer: {'role': 'inferencer', 'requested': [2], 'before': [0, 1, 2], 'after': [2], 'status': 'applied', 'error': None}
- postprocessor: {'role': 'postprocessor', 'requested': [0, 1], 'before': [0, 1, 2], 'after': [0, 1], 'status': 'applied', 'error': None}
