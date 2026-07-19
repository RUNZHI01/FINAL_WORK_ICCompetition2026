# Runtime Profiling API Probe

- run_id: profiling_runtime_api_probe_20260330_182717
- env_file: session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
- remote_host: 100.121.87.73:22
- python_executable: /home/user/anaconda3/envs/tvm310_safe/bin/python
- tvm_version: 0.24.dev0
- tvm_import_ok: True
- relax_import_ok: True
- virtual_machine_class_found: True
- virtual_machine_has_profile: True
- profile_like_members: ['profile']
- runtime_profiling_import_ok: True

## Key Finding

当前飞腾板 `tvm310_safe` 环境里：

- `relax.VirtualMachine` **类级别**确实存在 `profile` 方法
- `tvm.runtime.profiling` 相关模块也能正常导入

因此，之前 fresh probe 中的：

- `AttributeError: Module has no function 'profile'`

**不是**因为 Python API 层根本没有 `profile`，而更可能是：

- 当前 trusted current 实际绑定的底层 runtime module / artifact 组合
- 在实例调用 `vm.profile('main', input)` 时
- 没有导出或支持对应的 runtime profiling 符号

## Raw JSON

```json
{
  "python_executable": "/home/user/anaconda3/envs/tvm310_safe/bin/python",
  "python_version": "3.10.20 | packaged by conda-forge | (main, Mar  5 2026, 16:36:56) [GCC 14.3.0]",
  "tvm_version": "0.24.dev0",
  "tvm_import_ok": true,
  "relax_import_ok": true,
  "virtual_machine_class_found": true,
  "virtual_machine_has_profile": true,
  "virtual_machine_profile_like_members": [
    "profile"
  ],
  "virtual_machine_selected_members": [
    "invoke_closure",
    "profile",
    "save_function",
    "set_input",
    "time_evaluator"
  ],
  "runtime_profiling_import_ok": true,
  "runtime_profiling_report_members": [
    "calls",
    "configuration",
    "csv",
    "device_metrics",
    "from_json",
    "json",
    "same_as",
    "table"
  ]
}
```
