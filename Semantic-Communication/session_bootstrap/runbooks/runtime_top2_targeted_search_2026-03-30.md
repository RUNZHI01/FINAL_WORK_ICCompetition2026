# Runtime-Top2 Targeted Search（2026-03-30）

适用范围：把 trusted current 下一轮 `4.2` 搜索从 stage-weight hotspot 切到 runtime profiling 的 top-2 定向搜索。

## Step 1：锁定 runtime top-2

当前锁定来源：

- runtime profiling report: `session_bootstrap/reports/profiling_judge_multi_20260330_184658.md`
- runtime hotspot candidates: `fused_conv2d_transpose2_add12,fused_conv2d_transpose1_add9`

这一步已经完成，本轮 scaffold 直接把这两个 op 固化进：

- env: `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_top2_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env`
- wrapper: `session_bootstrap/scripts/run_phytium_runtime_top2_targeted_search.sh`

## Step 2：执行 runtime-top2 定向搜索

默认执行入口：

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_top2_targeted_search.sh
```

如需先单独检查服务 / readiness，直接用新 env：

```bash
bash ./session_bootstrap/scripts/manage_rpc_services.sh \
  --env ./session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_top2_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env \
  status

bash ./session_bootstrap/scripts/check_rpc_readiness.sh \
  --env ./session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_top2_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env
```

默认选择：

- 基线脚本：复用 `run_phytium_baseline_seeded_warm_start_current_incremental.sh`
- 推理校验：复用 `inference_tvm310_safe.2026-03-10.phytium_pi.env`
- 目标 op：`fused_conv2d_transpose2_add12,fused_conv2d_transpose1_add9`
- `TUNE_TOTAL_TRIALS=500`
- `TUNE_MAX_TRIALS_PER_TASK=250`
- `TUNE_NUM_TRIALS_PER_ITER=32`
- `TUNE_RUNNER=rpc`
- warm-start DB：继续复用现有 baseline-seeded tuning DB

说明：

- wrapper 会生成一个临时 overlay env，再调用现有增量入口，因此不会引入并行的新调优系统。
- `--rebuild-env` 仍可传入别的 warm-start current env，但 wrapper 依然会把 runtime-top2 op 列表覆盖回这两个目标。
- 如需改预算，可直接附加例如 `--total-trials 1000`。

## Step 3：看什么结果决定是否继续

运行完成后，沿用现有 one-shot / incremental 产物：

- wrapper log：`session_bootstrap/logs/<report_id>_wrapper.log`
- one-shot summary md/json：`session_bootstrap/reports/<report_id>.md` / `.json`
- 本地输出目录：`session_bootstrap/tmp/<report_id>/`

最低验收点：

- summary 中 `search_mode=baseline_seeded_warm_start_incremental`
- `selected_op_names` 只包含 `fused_conv2d_transpose2_add12,fused_conv2d_transpose1_add9`
- 成功上传新的 `optimized_model.so`
- safe runtime inference 正常完成并产出新的 `run_median_ms`

若这一步收益仍然有限，再回到用户计划下一决策：

- 继续加这两个 op 的预算；
- 扩到 runtime top-3 / top-4；
- 或转向 `7.1` 手写 TIR / runtime artifact 路线，而不是回到 stage-weight 黑箱全局搜索。
