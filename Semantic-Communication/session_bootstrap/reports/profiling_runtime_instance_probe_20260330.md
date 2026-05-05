# Runtime Profiling Instance Probe

- run_id: profiling_runtime_instance_probe_20260330
- env_file: session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
- remote_host: 100.121.87.73:22
- python_executable: /home/user/anaconda3/envs/tvm310_safe/bin/python
- tvm_version: 0.24.dev0
- loaded_module_type: `<class 'tvm.runtime.module.Module'>`
- loaded_module_has_profile: False
- vm_has_profile: True
- vm_module_type: `<class 'tvm.runtime.module.Module'>`
- vm_module_has_profile: False
- get_function('profile'): `AttributeError: Module has no function 'profile'`
- get_function('main'): True
- get_function('set_input'): True
- get_function('invoke_stateful'): True

## Key Finding

这次 probe 把 blocker 从“类级 API 是否存在”进一步缩小到了“实例底层 module 是否导出 profile 符号”这一层：

- `relax.VirtualMachine` 类上确实有 `profile`
- 但实例底层 `vm.module` 上没有 `profile`
- 且 `vm.module.get_function('profile')` 直接报：
  - `AttributeError: Module has no function 'profile'`

因此，当前最准确的结论是：

> trusted current `chunk4` 这条线不是“Python API 缺 profile”，而是当前实际加载的 runtime module / artifact 组合没有导出 profiling 所需符号。

## Notes

- probe 中尝试把 latent 样本转成 TVM tensor 时，又额外暴露了一个与 profile 主 blocker 无关的小问题：
  - 当前快速探针脚本里对 `.pt` latent 的解包方式不够稳，最终命中了 `ValueError: unknown dtype object`
- 这个 dtype 问题不影响本次主结论，因为在它之前就已经成功证明：
  - `loaded_module_has_profile = false`
  - `vm_module_has_profile = false`
  - `get_function('profile')` 不存在

## Raw JSON

```json
{
  "artifact_exists": true,
  "latent_exists": true,
  "tvm_version": "0.24.dev0",
  "loaded_module_type": "Module",
  "loaded_module_type_full": "<class 'tvm.runtime.module.Module'>",
  "loaded_module_has_profile": false,
  "loaded_module_dir_profile_like": [],
  "vm_instance_type": "VirtualMachine",
  "vm_has_profile": true,
  "vm_dir_profile_like": [
    "profile"
  ],
  "vm_module_found": true,
  "vm_module_type": "Module",
  "vm_module_type_full": "<class 'tvm.runtime.module.Module'>",
  "vm_module_has_profile": false,
  "vm_module_dir_profile_like": [],
  "vm_module_has_get_function": true,
  "get_function_profile": "ERROR: AttributeError: Module has no function 'profile'",
  "get_function_main": true,
  "get_function_set_input": true,
  "get_function_invoke_stateful": true,
  "fatal_error": "ValueError: unknown dtype `object`"
}
```
