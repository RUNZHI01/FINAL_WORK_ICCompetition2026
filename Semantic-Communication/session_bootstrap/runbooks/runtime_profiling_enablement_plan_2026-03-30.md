# Runtime Profiling Enablement Plan（2026-03-30）

适用范围：trusted current `chunk4` 路线的 remote runtime per-op profiling

> 更新：本计划的核心 blocker 已在 `2026-03-30` 晚间被打通，最新稳定入口见 `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`。本 runbook 保留为“问题是怎么被定位并解决的”记录。

## 1. 当前状态

当前 fresh probe 已确认：

- 入口：`session_bootstrap/reports/profiling_judge_refresh_20260330_170808.md`
- 结论：`stage_level_hotspot_only`
- 直接 blocker：`AttributeError: Module has no function 'profile'`

因此，这条线现在不是“没做”，而是“已经验证当前 runtime / artifact 组合不支持”。

## 2. 目标

把当前状态从：

- `stage_level_hotspot_only`

推进到：

- `runtime_operator_profile_available`

最低验收标准：

1. 在飞腾板 trusted current `chunk4` 上，`vm.module.get_function('profile')` 不再报 `AttributeError`
2. 且 `vm.profile('main', input)` 不再抛 `AttributeError`
3. 至少 1 个真实 sample 能返回 op-level summary
4. 生成一份新的报告，能替换当前 `profiling_judge_refresh_20260330_170808.md` 的 judge-facing 入口

## 3. 推荐路线

### 路线 A（优先）：换 runtime / 导出符号，不换证据口径

思路：
- 保持现有 trusted current artifact、输入目录、SNR、board 环境基本不变
- 只处理 remote TVM runtime 的 profiling 能力

优点：
- 不会动当前 headline performance 的 artifact lineage
- 更容易把 profiling 结果解释成“在同一 trusted artifact 上新增的观测能力”

最低动作：
1. 确认远端当前 `tvm.relax.VirtualMachine` / module API 能力
2. 找到支持 `profile` 的 runtime 版本或构建选项
3. 在飞腾板最小替换后，用 1 sample 验证

### 路线 B：换 artifact / 编译链，让其兼容现有 profiling API

思路：
- 保持 remote runtime 基本不变
- 通过新的编译产物或编译参数生成可 profile 的 artifact

风险：
- 容易引入“profiling 用 artifact”和“性能 headline 用 artifact”不是同一份的口径分叉
- 答辩时解释成本更高

默认不优先。

## 4. 最小执行顺序

### Step 1：只做 API 能力探针

目标：不跑完整模型，先确认远端 runtime 暴露了什么。

已完成结果：
- `session_bootstrap/reports/profiling_runtime_api_probe_20260330_182717.md`
- `session_bootstrap/reports/profiling_runtime_instance_probe_20260330.md`
- 结论：
  - `hasattr(relax.VirtualMachine, 'profile') == True`
  - `tvm.runtime.profiling` 可正常导入
  - 但 `loaded_module_has_profile = false`
  - 且 `vm.module.get_function('profile') -> AttributeError: Module has no function 'profile'`
  - 因此当前 blocker 并不是“API 层根本没有 profile”，而是实例调用时底层 runtime module / artifact 组合不支持对应 symbol

建议方式：
- 在飞腾板当前 TVM Python 环境中，最小化打印：
  - `hasattr(relax.VirtualMachine, 'profile')`
  - `dir(relax.VirtualMachine)`
  - profiling 相关模块接口

如果这里已经没有 `profile`，后续就不要反复重跑 `run_task_5_1_operator_profile.py` 期待奇迹；如果这里有 `profile` 但实例调用仍报 `Module has no function 'profile'`，则应把排查重点转向 runtime build / exported symbol / artifact compatibility。

### Step 2：最小 sample 复验

一旦 runtime 补好，先只跑：

```bash
python3 ./session_bootstrap/scripts/run_task_5_1_operator_profile.py \
  --run-id profiling_enablement_probe_$(date +%Y%m%d_%H%M%S) \
  --hotspot-mode reuse \
  --hotspot-existing-json ./session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.json \
  --hotspot-existing-md ./session_bootstrap/reports/hotspot_tasks_trusted_current_20260312_153906.md \
  --runtime-mode attempt \
  --trusted-env ./session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env \
  --trusted-variant current \
  --profile-samples 1 \
  --max-inputs 1
```

验收：
- `runtime_phase.status != fallback_only`
- `runtime_profile_supported = True`
- `runtime_hotspot_candidates` 非空

### Step 3：扩到小批量

只有 Step 2 通过后，再考虑：
- `--profile-samples 3`
- `--max-inputs 3`

目的是验证结果不是一次性偶然成功。

## 5. 失败时如何记录

若仍失败，不要只说“profiling 还不行”，至少记录：

- 当前 remote Python 路径
- 当前 TVM 版本
- `hasattr(relax.VirtualMachine, 'profile')` 结果
- 报错栈
- trusted artifact SHA 是否匹配

并将这些补回：
- `session_bootstrap/reports/profiling_runtime_support_blocker_20260330.md`

## 6. 当前默认对外口径

在 profiling enablement 完成之前，默认仍使用：

- `session_bootstrap/reports/profiling_judge_refresh_20260330_170808.md`
- `session_bootstrap/reports/profiling_runtime_support_blocker_20260330.md`

推荐表述：

> 我们已经完成可信的热点定位，但当前 remote trusted runtime 仍不支持 `vm.profile`，所以现阶段提供的是 stage-weight hotspot evidence，而不是完整 per-op trace。这是明确边界，不是缺失执行。
