# Profiling Runtime Support Blocker（2026-03-30）

## 结论

> 历史 blocker 已在 `2026-03-30` 晚间被定位并绕开：根因是 VM 实例化时未启用 `profile=True`，导致底层 module 未导出 profiling 符号。最新可用入口见 `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`。

截至 `2026-03-30` 白天时，trusted current `chunk4` 路线的 **remote runtime per-op profiling** 曾不可用。这个历史 blocker 不是基于推测，而是基于 fresh probe 的正式复验：

- 入口：`session_bootstrap/reports/profiling_judge_refresh_20260330_170808.md`
- 运行命令：
  - `bash session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1 --seed 0 --profile-ops --profile-samples 1`
- 结果：
  - `overall_status = stage_level_hotspot_only`
  - `runtime_status = fallback_only`
  - `fallback_reason = AttributeError: Module has no function 'profile'`

因此，当前状态应被明确表述为：

- **stage-weight hotspot evidence 已有**
- **remote trusted runtime per-op profile 暂不支持**

## 已确认事实

1. trusted current artifact 已固定为：
   - SHA256 `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
2. fresh probe 中远端实际加载的 artifact SHA 与预期一致：
   - `artifact_sha256_match = true`
3. runtime probe 并不是因为 artifact 漂移、输入目录错误或 SSH 未连通而失败。
4. 当前失败点明确落在：
   - `vm.profile('main', input)`
   - 报错：`AttributeError: Module has no function 'profile'`
5. `2026-03-30` 新增 API capability probe 已确认：
   - `relax.VirtualMachine` **类级别**存在 `profile`
   - `tvm.runtime.profiling` 模块可正常导入
   - 入口：`session_bootstrap/reports/profiling_runtime_api_probe_20260330_182717.md`
6. `2026-03-30` 新增 instance-level probe 已进一步确认：
   - `loaded_module_has_profile = false`
   - `vm_module_has_profile = false`
   - `get_function('profile') -> AttributeError: Module has no function 'profile'`
   - 入口：`session_bootstrap/reports/profiling_runtime_instance_probe_20260330.md`

这意味着问题不在 benchmark 封装，也不在 Python API 是否暴露 `profile` 本身，而更像是**当前 trusted current 实例绑定的底层 runtime module / artifact 组合，没有导出或支持 profiling 所需符号**。

## 当前仍可对外使用的替代口径

在没有 runtime per-op profile 的情况下，可以继续使用：

- `session_bootstrap/reports/profiling_judge_refresh_20260330_170808.md`
- `session_bootstrap/reports/profiling_trusted_current_20260312_154323.md`
- `session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.md`

可稳定对外说的内容是：

- 当前热点前列包括：
  - `reshape2`
  - `fused_variance1_add3_tir_sqrt1`
  - `reshape1`
  - `fused_mean1_subtract1_divide1_multiply1_add4`
- 这是可信的 stage-weight hotspot evidence
- 但不是 remote runtime per-op execution trace

## 若要真正补齐，需要什么

至少满足以下之一：

### 路线 A：更换 / 重建支持 profiling 的 remote TVM runtime

目标：
- 让远端 `relax.VirtualMachine` 或对应 runtime module 支持 `profile`
- 或提供等价的 runtime profiling API

最低验收：
- 在飞腾板当前 trusted artifact 上，`vm.profile('main', input)` 不再抛 `AttributeError`
- 至少能成功返回 1 个 sample 的 op-level profiling summary

### 路线 B：改 artifact / 编译链，使其生成可被当前 runtime profiling 的产物

目标：
- 保持 board env 不变
- 但让 current artifact 对当前 runtime profiling API 兼容

最低验收：
- trusted current artifact 在保持正确输出的同时，可完成 1 次 profile call

## 暂不建议的误导性做法

下面这些做法不应被拿来冒充“已经有 per-op profile” ：

- 把 stage-weight hotspot 列表写成 runtime profile 结果
- 用 local-only profile 替代 remote trusted runtime profile，却不说明差异
- 只贴 `vm.profile` 调用代码，不验证它在板端是否真正成功

## 建议对外表述

推荐一句话：

> 我们已经完成可信的热点定位，但 remote trusted runtime 这条线的 `vm.profile` 目前仍不支持，因此当前对外给出的 hotspot 证据是 stage-weight 级别，而不是完整 per-op trace。这是明确边界，不是遗漏。
