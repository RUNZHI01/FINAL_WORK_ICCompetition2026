# Runtime-Shifted-Top3 Targeted Search（2026-03-30）

适用范围：runtime-top2 定向深搜虽然显著压低了 `fused_conv2d_transpose2_add12` / `fused_conv2d_transpose1_add9`，但集成后的新 artifact 在 safe runtime payload 上严重回归，因此下一轮不能继续只盯旧 top-2，而要切到 runtime hotspot 已转移后的新目标集。

## Step 1：锁定 shifted-top3

当前锁定来源：

- 诊断结论：`session_bootstrap/reports/runtime_top2_targeted_search_diagnosis_20260330.md`
- 新 artifact runtime reprobe：`session_bootstrap/reports/profiling_runtime_top2_tuned_artifact_reprobe_20260330_2055.md`

当前下一轮 target ops：

- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`

这一步已固化进：

- env: `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_shifted_top3_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env`
- wrapper: `session_bootstrap/scripts/run_phytium_runtime_shifted_top3_targeted_search.sh`

## Step 2：执行 shifted-top3 定向搜索

默认执行入口：

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_shifted_top3_targeted_search.sh
```

如需先检查环境：

```bash
bash ./session_bootstrap/scripts/manage_rpc_services.sh \
  --env ./session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_shifted_top3_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env \
  status

bash ./session_bootstrap/scripts/check_rpc_readiness.sh \
  --env ./session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_shifted_top3_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env
```

默认选择：

- 基线脚本：复用 `run_phytium_baseline_seeded_warm_start_current_incremental.sh`
- 推理校验：复用 `inference_tvm310_safe.2026-03-10.phytium_pi.env`
- 目标 op：`fused_conv2d_transpose_add6,fused_conv2d3_add15,fused_conv2d2_add2`
- `TUNE_TOTAL_TRIALS=500`
- `TUNE_MAX_TRIALS_PER_TASK=160`
- `TUNE_NUM_TRIALS_PER_ITER=32`
- `TUNE_RUNNER=rpc`
- warm-start DB：继续复用现有 baseline-seeded tuning DB

说明：

- 这不是推翻前一轮 top-2 结果；相反，是利用前一轮证明“局部 top-2 已被压下去”的事实，把预算转投给新的 runtime top set。
- wrapper 会生成临时 overlay env，再调用现有增量入口，不引入新的平行调优系统。
- 和上一轮一样，若产物验证失败，不要 promote 到 trusted current，先做 runtime reprobe 和主线恢复。

## Step 3：这轮重点看什么

最低验收点：

- summary 中 `search_mode=baseline_seeded_warm_start_incremental`
- `selected_op_names` 只包含这 3 个 shifted-top3 目标
- 如果 payload / runtime reprobe 仍然显示瓶颈继续转移，则进入下一轮“runtime-shifted retarget”而不是继续盲加预算

重点判断：

1. `fused_conv2d_transpose_add6` 是否出现显著下降；
2. `fused_conv2d3_add15` 是否从 top-2 新瓶颈中退出；
3. `fused_conv2d2_add2` 是否被有效压低，避免它继续在 integrated artifact 中成簇出现；
4. 新 artifact 的 safe runtime payload 是否恢复到 trusted current 同量级，否则依然不得 promote。

## 与手写 TIR 的关系

如果这一轮 shifted-top3 仍只能带来局部收益、而 integrated artifact 继续把瓶颈转移到固定少数 op，那么再进入手写 TIR / NEON 才是更合理的时机。

换句话说：

- **先完成 runtime-shifted retarget**
- **再决定手写 TIR 的真实候选**

而不是继续围绕旧 top-2 直接手写。
