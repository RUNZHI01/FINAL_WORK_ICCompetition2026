# big.LITTLE Wrapper Report

- status: ok
- run_id: tvm_current_audit_20260714_001150
- variant: current
- execution_mode: pipeline
- remote_mode: ssh
- env_file: C:/Users/Lenovo/AppData/Local/Temp/tmp.iKJUEIe6pd
- processed_count: 1
- total_wall_ms: 3645.324
- images_per_sec: 0.274
- dry_run: False
- big_cores: [2]
- little_cores: [0, 1]
- output_dir: /home/user/Downloads/jscc-test/jscc/infer_outputs/openamp3_handwritten_mean4_v7_big_little_current

## Affinity

- preloader: {'role': 'preloader', 'requested': [0, 1], 'before': [0, 1, 2], 'after': [0, 1], 'status': 'applied', 'error': None}
- inferencer: {'role': 'inferencer', 'requested': [2], 'before': [0, 1, 2], 'after': [2], 'status': 'applied', 'error': None}
- postprocessor: {'role': 'postprocessor', 'requested': [0, 1], 'before': [0, 1, 2], 'after': [0, 1], 'status': 'applied', 'error': None}
